"""FODOC ML Pipeline Orchestrator.

Tahapan Pipeline Terintegrasi (Model Terbaru Tim):
1. Analisis kualitas citra CIELAB (dan restorasi adaptif sesuai konfigurasi `info_model.json`,
   default `pakai_restorasi=false` mengikuti model S3 terbaik Harari yang dilatih/diuji pada citra asli).
2. Deteksi banyak wajah dengan paket resmi Harari (`ml_services/face_detection/deteksi_wajah.py`):
   YOLOv11n-face ONNX (`deteksi_wajah.onnx`, imgsz=1088, NMS IoU=0.5, ambang default 0.4639,
   saringan kotak-di-dalam-kotak `saringan.py` tumpang_dalam=0.70, urutan kiri-ke-kanan P1..PN).
3. Deteksi 5 landmark (`landmark_wajah`) & Face alignment menggunakan similarity transform (LMEDS)
   ke template 5-titik ArcFace 112x112 (`align.py`).
4. Ekstraksi fitur biometrik AdaFace IR-50 WebFace4M (`adaface_ir50_webface4m.onnx`) lewat ONNX Runtime:
   input 112x112 kanal BGR (bukan RGB), normalisasi `(px/255 - 0.5)/0.5`, Flip TTA horizontal -> 512-D L2-normalized.
5. Cosine similarity (dot product) terhadap template pengguna (rata-rata L2-normalized dari 3 pose pendaftaran).
6. Keputusan berlapis:
   - COCOK: skor >= ambang_cocok (0.55), selisih >= ambang_selisih (0.10), sisi >= min_wajah_px (28), ketajaman >= ambang_ketajaman.
   - PERLU_CEK: ambang_perlu_cek (0.40) <= skor < ambang_cocok, atau wajah kecil/buram/ambigu.
   - UNKNOWN: selain itu.
   - Aturan 1 identitas per foto: jika >1 wajah COCOK ke orang sama, skor tertinggi tetap COCOK, lainnya diturunkan jadi PERLU_CEK.
   - Kemiripan >= 0.95 ke foto acuan ditandai kebocoran data.
"""
from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Pastikan folder paket deteksi Harari (face_detection) dimuat lebih dulu sebelum ml_services lama
ML_DIR = Path(__file__).parent / "ml_services"
FACE_DET_DIR = ML_DIR / "face_detection"
for p in (str(ML_DIR), str(FACE_DET_DIR)):
    if p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, str(ML_DIR))
sys.path.insert(0, str(FACE_DET_DIR))

from restorasi import analyze_quality, restore  # type: ignore  # noqa: E402
from deteksi_wajah import DetektorWajah, INFO as DET_INFO, AMBANG as DET_DEFAULT_AMBANG  # type: ignore  # noqa: E402
from recognition_service import extract_embedding, extract_embedding_with_norm  # type: ignore  # noqa: E402
from align import align_face, cari_landmark  # type: ignore  # noqa: E402

# ------------------------------------------------------- Singletons Model
_detector: DetektorWajah | None = None
_det_lock = threading.Lock()
_landmark_model = None


def get_detector() -> DetektorWajah:
    global _detector
    if _detector is None:
        with _det_lock:
            if _detector is None:
                # Gunakan ONNX sesuai rekomendasi Harari (ringan, tanpa PyTorch, hasil sama persis dengan .pt)
                onnx_exists = (FACE_DET_DIR / "deteksi_wajah.onnx").exists()
                _detector = DetektorWajah(onnx=onnx_exists, ambang=DET_DEFAULT_AMBANG)
    return _detector


def _run_detect(img_bgr: np.ndarray, conf_detect: float | None = None) -> dict[str, Any]:
    """Jalankan DetektorWajah secara thread-safe dengan ambang dinamis dari settings."""
    det = get_detector()
    ambang = float(conf_detect) if conf_detect is not None else float(DET_DEFAULT_AMBANG)
    with _det_lock:
        det.ambang = ambang
        return det.deteksi(img_bgr)


def get_landmark_model():
    global _landmark_model
    if _landmark_model is None:
        from ultralytics import YOLO
        candidate_weights = [
            ML_DIR / "models" / "landmark_wajah.pt",
            ML_DIR / "models" / "landmark_wajah.onnx",
        ]
        weight_path = next((p for p in candidate_weights if p.exists()), None)
        if weight_path:
            w_str = str(weight_path)
            if w_str.endswith(".onnx"):
                _landmark_model = YOLO(w_str, task="pose")
            else:
                _landmark_model = YOLO(w_str)
    return _landmark_model


# ------------------------------------------------------- Utilitas Metrik Citra
def calculate_sharpness(img_bgr: np.ndarray) -> float:
    """Menghitung ketajaman citra berdasarkan variansi Laplacian."""
    if img_bgr is None or img_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def calculate_brightness_l(img_bgr: np.ndarray) -> float:
    """Menghitung rerata kecerahan kanal L* (ruang warna CIELAB) ternormalisasi 0.0 - 1.0."""
    if img_bgr is None or img_bgr.size == 0:
        return 0.0
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    return float(np.mean(lab[:, :, 0]) / 255.0)


def cosine_similarity(a: np.ndarray | list[float], b: np.ndarray | list[float]) -> float:
    """Cosine similarity (dot product) antara dua vektor fitur AdaFace."""
    va = np.asarray(a, dtype=np.float32).flatten()
    vb = np.asarray(b, dtype=np.float32).flatten()
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


POSE_FRONT_MIN = 0.38
POSE_FRONT_MAX = 0.62
POSE_RIGHT_MAX = 0.37
POSE_LEFT_MIN = 0.63


def calculate_pose_yaw(kp: np.ndarray) -> float:
    """Menghitung rasio arah hadap horizontal (yaw) wajah dari 5 landmark (tahan kemiringan/roll).

    Urutan 5 landmark: [mata_kiri_img, mata_kanan_img, hidung, mulut_kiri_img, mulut_kanan_img].
    Nilai acuan (kamera normal / tidak dicermin):
    - 0.38 .. 0.62 : menghadap lurus ke depan (front, ~0.50)
    - <= 0.37      : menoleh ke kanan (hidung mendekati mata/mulut kiri-gambar)
    - >= 0.63      : menoleh ke kiri (hidung mendekati mata/mulut kanan-gambar)
    """
    pts = np.asarray(kp, dtype=np.float32).reshape(5, 2)
    left_anchor = (pts[0] + pts[3]) / 2.0
    right_anchor = (pts[1] + pts[4]) / 2.0
    axis = right_anchor - left_anchor
    norm_sq = float(np.dot(axis, axis))
    if norm_sq < 1e-6:
        return 0.5
    rel_nose = pts[2] - left_anchor
    return float(np.dot(rel_nose, axis) / norm_sq)


def validate_pose_direction(yaw: float, expected_angle: str) -> tuple[bool, str | None]:
    """Memastikan arah hadap wajah pada foto sesuai perintah slot (front / right / left)."""
    if expected_angle == "front":
        if yaw < POSE_FRONT_MIN:
            return (
                False,
                "Wajah pada slot Depan terdeteksi menoleh ke kanan. Wajib foto yang menghadap lurus ke depan.",
            )
        if yaw > POSE_FRONT_MAX:
            return (
                False,
                "Wajah pada slot Depan terdeteksi menoleh ke kiri. Wajib foto yang menghadap lurus ke depan.",
            )
        return True, None

    if expected_angle == "right":
        if yaw >= POSE_LEFT_MIN:
            return (
                False,
                "Arah wajah salah! Foto terdeteksi menoleh ke kiri, bukan ke kanan. Wajib foto yang menoleh ke KANAN.",
            )
        if yaw > POSE_RIGHT_MAX:
            return (
                False,
                "Foto masih menghadap lurus ke depan (belum menoleh ke kanan). Wajib foto yang jelas menoleh ke KANAN.",
            )
        return True, None

    if expected_angle == "left":
        if yaw <= POSE_RIGHT_MAX:
            return (
                False,
                "Arah wajah salah! Foto terdeteksi menoleh ke kanan, bukan ke kiri. Wajib foto yang menoleh ke KIRI.",
            )
        if yaw < POSE_LEFT_MIN:
            return (
                False,
                "Foto masih menghadap lurus ke depan (belum menoleh ke kiri). Wajib foto yang jelas menoleh ke KIRI.",
            )
        return True, None

    return True, None


def _clamp_box(box: list[int] | tuple[int, int, int, int], w_img: int, h_img: int) -> tuple[int, int, int, int]:
    x1 = max(0, min(w_img, int(box[0])))
    y1 = max(0, min(h_img, int(box[1])))
    x2 = max(0, min(w_img, int(box[2])))
    y2 = max(0, min(h_img, int(box[3])))
    return x1, y1, x2, y2


def _crop_with_margin(img: np.ndarray, box: tuple[int, int, int, int], margin: float = 0.15) -> tuple[np.ndarray, int, int]:
    """Potong wajah dengan margin proporsional dari foto asli, kembalikan (crop, offset_x, offset_y)."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    m = int(margin * max(x2 - x1, y2 - y1))
    nx1 = max(0, x1 - m)
    ny1 = max(0, y1 - m)
    nx2 = min(w, x2 + m)
    ny2 = min(h, y2 + m)
    cropped = img[ny1:ny2, nx1:nx2]
    if cropped.size == 0:
        return img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)], max(0, x1), max(0, y1)
    return cropped, nx1, ny1


# ------------------------------------------------------- Validasi Registrasi 3-Pose
def validate_enroll_pose(
    image_bytes: bytes,
    min_size_px: int = 60,
    min_l_brightness: float = 0.30,
    min_sharpness: float = 15.0,
    conf_detect: float = 0.4639,
    expected_angle: str | None = None,
) -> dict[str, Any]:
    """Pemeriksaan kualitas otomatis & validasi arah pose di backend untuk tiap pose registrasi wajah mahasiswa.

    Kriteria:
    1. Tepat 1 wajah terdeteksi (YOLOv11n-face + saringan.py).
    2. Sisi wajah >= min_size_px (60 px).
    3. Kecerahan tidak gelap (rerata kanal L* ternormalisasi >= 0.30).
    4. Ketajaman variansi Laplacian memenuhi ambang (>= 15.0).
    5. 5 landmark terdeteksi, arah hadap wajah (yaw) sesuai perintah slot (`front`/`right`/`left`), dan bisa di-align.
    6. Ekstraksi embedding AdaFace IR-50 512-D L2-normalized + Flip TTA.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "error": "Format berkas citra tidak valid atau rusak"}

    # Perkecil foto resolusi sangat besar (mis. 4000x3000 dari kamera HP) agar deteksi cepat & bebas timeout
    h_img, w_img = img.shape[:2]
    max_dim = max(h_img, w_img)
    if max_dim > 1280:
        scale = 1280.0 / max_dim
        img = cv2.resize(img, (int(w_img * scale), int(h_img * scale)), interpolation=cv2.INTER_AREA)
        h_img, w_img = img.shape[:2]

    det_result = _run_detect(img, conf_detect=conf_detect)
    faces = det_result.get("wajah", [])

    # 1. Pemeriksaan jumlah wajah: harus tepat 1
    if len(faces) == 0:
        report = analyze_quality(img)
        if report.mean < min_l_brightness:
            return {"ok": False, "error": "Tambah pencahayaan: Wajah tidak terdeteksi karena pencahayaan terlalu gelap."}
        return {"ok": False, "error": "Wajah tidak terdeteksi. Posisikan wajah Anda tepat di depan kamera."}

    if len(faces) > 1:
        confident_faces = [f for f in faces if f["confidence"] >= conf_detect]
        if len(confident_faces) > 1:
            return {"ok": False, "error": "Pastikan hanya satu wajah. Terdeteksi lebih dari satu orang di depan kamera."}

    face = faces[0]
    x1, y1, x2, y2 = _clamp_box(face["kotak_asli"], w_img, h_img)
    lebar = x2 - x1
    tinggi = y2 - y1
    min_side = min(lebar, tinggi)

    # 2. Pemeriksaan ukuran wajah (sisi >= 60 px)
    if min_side < min_size_px:
        return {
            "ok": False,
            "error": f"Dekatkan/jauhkan wajah: Wajah terlalu jauh ({min_side}px). Dekatkan wajah ke kamera (minimal {min_size_px}px).",
        }

    tight_crop = img[y1:y2, x1:x2]
    if tight_crop.size == 0:
        return {"ok": False, "error": "Potongan area wajah kosong"}

    # 3. Pemeriksaan kecerahan kanal L* CIELAB (>= 0.30)
    brightness_l = calculate_brightness_l(tight_crop)
    if brightness_l < min_l_brightness:
        return {
            "ok": False,
            "error": f"Tambah pencahayaan: Foto terlalu gelap (kecerahan {brightness_l:.2f} < {min_l_brightness:.2f}). Pastikan ruangan memiliki cahaya yang cukup.",
        }

    # 4. Pemeriksaan ketajaman Laplacian (>= 15.0)
    sharpness = calculate_sharpness(tight_crop)
    if sharpness < min_sharpness:
        return {
            "ok": False,
            "error": f"Bersihkan lensa kamera: Citra wajah buram atau berbayang (ketajaman {sharpness:.1f} < {min_sharpness:.1f}). Bersihkan lensa kamera dan jangan bergerak.",
        }

    # 5. Landmark 5-titik dan alignment pada potongan wajah bermargin
    crop_padded, ox, oy = _crop_with_margin(img, (x1, y1, x2, y2), margin=0.15)
    lmk_model = get_landmark_model()
    kp = None
    used_crop = crop_padded
    if lmk_model is not None:
        try:
            kp, _ = cari_landmark(lmk_model, crop_padded, conf_min=0.15)
            if kp is None:
                kp, _ = cari_landmark(lmk_model, tight_crop, conf_min=0.15)
                if kp is not None:
                    used_crop = tight_crop
                    ox, oy = x1, y1
        except Exception:
            kp = None

    if kp is None:
        return {
            "ok": False,
            "error": "Gagal mendeteksi 5 landmark wajah. Pastikan seluruh area mata, hidung, dan mulut terlihat jelas tanpa tertutup rambut/aksesoris.",
        }

    # 5b. Validasi arah hadap wajah (yaw) agar wajib sesuai perintah slot (Depan / Kanan / Kiri)
    yaw_ratio = calculate_pose_yaw(kp)
    if expected_angle in ("front", "right", "left"):
        pose_ok, pose_err = validate_pose_direction(yaw_ratio, expected_angle)
        if not pose_ok:
            return {
                "ok": False,
                "error": pose_err,
                "yaw_ratio": float(round(yaw_ratio, 4)),
            }

    aligned = align_face(used_crop, kp, 112)
    if aligned is None or aligned.size == 0:
        return {
            "ok": False,
            "error": "Gagal melakukan penjajaran (alignment) wajah. Pastikan sudut kemiringan kepala wajar.",
        }

    # 6. Ekstraksi AdaFace IR-50 512-D
    emb, feat_norm = extract_embedding_with_norm(aligned)

    return {
        "ok": True,
        "embedding": emb.astype(np.float32).tolist(),
        "feature_norm": float(round(feat_norm, 4)),
        "face_box": [int(x1), int(y1), int(x2), int(y2)],
        "confidence": float(face["confidence"]),
        "sharpness": float(sharpness),
        "brightness_l": float(brightness_l),
        "yaw_ratio": float(round(yaw_ratio, 4)),
        "landmarks": [[round(float(pt[0] + ox), 1), round(float(pt[1] + oy), 1)] for pt in kp],
        "min_side": int(min_side),
    }


# ------------------------------------------------------- Pemrosesan Foto Acara
def process_event_photo(
    image_bytes: bytes,
    conf_detect: float = 0.4639,
    imgsz: int = 1088,
) -> dict[str, Any]:
    """Tahap 1, 2, 3, 4 Pipeline Terintegrasi:
    1. Analisis kualitas citra CIELAB (restorasi mengikuti `info_model.json`, default tidak dipakai pada model S3).
    2. Deteksi banyak wajah dengan DetektorWajah Harari (YOLOv11n-face ONNX, 1088px, saringan 0.70, P1..PN).
    3. Face alignment LMEDS 5-titik ke 112x112 (align.py).
    4. Ekstraksi embedding AdaFace IR-50 (WebFace4M) 512-D L2-normalized + Flip TTA.
    """
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "error": "Gambar tidak dapat dibaca", "faces": []}

    h_img, w_img = img.shape[:2]

    # Tahap 1: Analisis kualitas CIELAB (ikuti info_model.json -> pakai_restorasi=false)
    report = analyze_quality(img)
    condition = report.condition
    used_restoration = False
    work_img = img
    if bool(DET_INFO.get("pakai_restorasi", False)) and condition != "normal":
        restored, _info = restore(img, "adaptif")
        work_img = restored
        used_restoration = True

    # Tahap 2: Deteksi Multi-Wajah YOLOv11n-face + saringan kotak-di-dalam-kotak (Harari)
    det_result = _run_detect(work_img, conf_detect=conf_detect)
    detected_faces = det_result.get("wajah", [])

    lmk_model = get_landmark_model()
    face_records: list[dict[str, Any]] = []

    for idx, face in enumerate(detected_faces, 1):
        x1, y1, x2, y2 = _clamp_box(face["kotak_asli"], w_img, h_img)
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            continue
        min_side = min(w, h)

        # Potong dari citra ASLI (resolusi penuh)
        tight_crop = img[y1:y2, x1:x2]
        crop, ox, oy = _crop_with_margin(img, (x1, y1, x2, y2), margin=0.15)
        if crop.size == 0 or tight_crop.size == 0:
            continue

        sharpness = calculate_sharpness(tight_crop)

        # Tahap 3: Landmark 5-titik & Alignment
        kp = None
        aligned = None
        global_landmarks = []
        if lmk_model is not None and min_side >= 14:
            try:
                kp, _ = cari_landmark(lmk_model, crop, conf_min=0.15)
                if kp is not None:
                    aligned = align_face(crop, kp, 112)
                    global_landmarks = [[round(float(pt[0] + ox), 1), round(float(pt[1] + oy), 1)] for pt in kp]
            except Exception:
                aligned = None

        # Jika alignment gagal, resize biasa ke 112x112 (tanpa upscaling Lanczos4/unsharp masking)
        if aligned is None or aligned.size == 0:
            aligned = cv2.resize(tight_crop, (112, 112), interpolation=cv2.INTER_AREA)

        # Tahap 4: Ekstraksi fitur AdaFace IR-50 512-D + Flip TTA
        emb, feat_norm = extract_embedding_with_norm(aligned)

        face_id = str(uuid.uuid4())
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

        face_records.append({
            "face_id": face_id,
            "label": face.get("label", f"P{idx}"),
            "box": [int(x1), int(y1), int(x2), int(y2)],
            "confidence": float(face["confidence"]),
            "width": int(w),
            "height": int(h),
            "min_side": int(min_side),
            "sharpness": float(round(sharpness, 2)),
            "feature_norm": float(round(feat_norm, 4)),
            "landmarks": global_landmarks,
            "crop_bytes": buf.tobytes() if ok else b"",
            "embedding": emb.astype(np.float32).tolist(),
        })

    return {
        "ok": True,
        "condition": condition,
        "used_restoration": used_restoration,
        "image_width": int(w_img),
        "image_height": int(h_img),
        "saringan": det_result.get("saringan", {}),
        "faces": face_records,
    }


# ------------------------------------------------------- Tahap 5 & 6: Keputusan Berlapis
def evaluate_face_matches(
    faces: list[dict[str, Any]],
    enrolled_students: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Tahap 5 & 6 (Sesuai Spesifikasi AdaFace IR-50 WebFace4M):
    5. Template pengguna = rata-rata embedding foto pendaftaran, dinormalisasi L2.
       Skor identitas = dot(emb, template).
    6. Keputusan berlapis:
       - COCOK: skor >= ambang_cocok (0.55), selisih >= ambang_selisih (0.10),
                sisi >= min_wajah_px (28), ketajaman >= ambang_ketajaman.
       - PERLU_CEK: ambang_perlu_cek (0.40) <= skor < ambang_cocok, atau skor >= ambang_cocok
                    namun wajah kecil/buram/margin tipis.
       - UNKNOWN: selain itu.
       - Aturan 1 identitas per foto: jika >1 wajah COCOK ke orang sama, skor tertinggi tetap COCOK,
         lainnya diturunkan menjadi PERLU_CEK.
       - Kemiripan >= 0.95 ke salah satu foto acuan ditandai kebocoran data.
    """
    ambang_cocok = float(settings.get("ambang_cocok", 0.55))
    ambang_perlu_cek = float(settings.get("ambang_perlu_cek", 0.40))
    ambang_selisih = float(settings.get("ambang_selisih", 0.10))
    min_wajah_px = int(settings.get("min_wajah_px", 28))
    ambang_ketajaman = float(settings.get("ambang_ketajaman", 15.0))

    # Precompute template centroid L2-normalized per mahasiswa (sesuai spec AdaFace)
    prepared_students = []
    for st in enrolled_students:
        templates = st.get("face_embeddings") or ([st["face_embedding"]] if st.get("face_embedding") else [])
        if not templates:
            continue
        t_arr = np.asarray(templates, dtype=np.float32)
        if t_arr.ndim == 1:
            t_arr = t_arr[None, :]
        centroid = np.mean(t_arr, axis=0)
        c_norm = float(np.linalg.norm(centroid))
        if c_norm > 1e-6:
            centroid = centroid / c_norm
        prepared_students.append({
            "id": st["id"],
            "name": st.get("name", ""),
            "nim": st.get("nim", ""),
            "templates": t_arr,
            "centroid": centroid,
        })

    evaluated_faces: list[dict[str, Any]] = []

    for face in faces:
        emb = np.asarray(face["embedding"], dtype=np.float32)
        min_side = face.get("min_side")
        if min_side is None:
            if face.get("box") and len(face["box"]) == 4:
                x1, y1, x2, y2 = face["box"]
                min_side = min(abs(x2 - x1), abs(y2 - y1))
            else:
                min_side = min(face.get("width", 50), face.get("height", 50))
        sharpness = face.get("sharpness")
        if sharpness is None:
            sharpness = 30.0

        student_scores: list[dict[str, Any]] = []
        data_leakage = False

        for st in prepared_students:
            raw_sims = []
            for t in st["templates"]:
                sim_t = cosine_similarity(emb, t)
                raw_sims.append(sim_t)
                if sim_t >= 0.95:
                    data_leakage = True

            # Skor identitas AdaFace: dot(emb, template_centroid_L2)
            identity_score = cosine_similarity(emb, st["centroid"])

            student_scores.append({
                "user_id": st["id"],
                "name": st["name"],
                "nim": st["nim"],
                "score": round(identity_score, 4),
                "raw_sims": [round(s, 4) for s in sorted(raw_sims, reverse=True)],
            })

        student_scores.sort(key=lambda x: x["score"], reverse=True)

        if student_scores:
            top1 = student_scores[0]
            top1_score = top1["score"]
            top1_user_id = top1["user_id"]
            top1_name = top1["name"]
            top1_nim = top1["nim"]
            top2_score = student_scores[1]["score"] if len(student_scores) > 1 else 0.0
            selisih = round(top1_score - top2_score, 4)
        else:
            top1_score = 0.0
            top1_user_id = None
            top1_name = None
            top1_nim = None
            top2_score = 0.0
            selisih = 0.0

        # Aturan keputusan berlapis
        is_large_enough = (min_side >= min_wajah_px)
        is_sharp = (sharpness >= ambang_ketajaman)
        meets_cocok_score = (top1_score >= ambang_cocok)
        meets_margin = (selisih >= ambang_selisih)

        if top1_user_id and meets_cocok_score and meets_margin and is_large_enough and is_sharp:
            status = "COCOK"
        elif top1_user_id and (
            (ambang_perlu_cek <= top1_score < ambang_cocok) or
            (meets_cocok_score and (not is_large_enough or not is_sharp or not meets_margin))
        ):
            status = "PERLU_CEK"
        else:
            status = "UNKNOWN"

        eval_item = {
            **face,
            "top1_user_id": top1_user_id,
            "top1_name": top1_name,
            "top1_nim": top1_nim,
            "top1_score": top1_score,
            "top2_score": top2_score,
            "selisih": selisih,
            "status": status,
            "min_side": min_side,
            "sharpness": sharpness,
            "data_leakage": data_leakage,
        }
        evaluated_faces.append(eval_item)

    # Aturan Satu Identitas per Foto:
    # Jika dua wajah COCOK ke orang yang sama, simpan yang skornya tertinggi dan turunkan yang lain menjadi PERLU_CEK.
    seen_cocok_users: dict[str, int] = {}
    for i, ef in enumerate(evaluated_faces):
        if ef["status"] == "COCOK":
            uid = ef["top1_user_id"]
            if uid not in seen_cocok_users:
                seen_cocok_users[uid] = i
            else:
                prev_i = seen_cocok_users[uid]
                if ef["top1_score"] > evaluated_faces[prev_i]["top1_score"]:
                    evaluated_faces[prev_i]["status"] = "PERLU_CEK"
                    seen_cocok_users[uid] = i
                else:
                    evaluated_faces[i]["status"] = "PERLU_CEK"

    return evaluated_faces
