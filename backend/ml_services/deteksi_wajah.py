"""Deteksi wajah - FUNGSI MURNI untuk integrasi backend (FastAPI, Flask, dll). Tanpa UI/Streamlit.

Pakai: muat model SEKALI (saat aplikasi start), lalu panggil .detect(gambar) berkali-kali.

    from deteksi_wajah import FaceDetector
    detektor = FaceDetector("yolov8n_face_harari.pt")        # muat sekali
    hasil = detektor.detect("foto.jpg", conf=0.1)            # panggil per-foto

Input `gambar` boleh:
    - path file (str / pathlib.Path), mis. "foto.jpg"
    - bytes isi file (mis. dari upload FastAPI: await file.read())
    - numpy array BGR (hasil cv2.imread)

Keluaran: dict JSON-ready (lihat contoh di README.md), berisi daftar wajah dengan:
    label ("Person 1".."Person N", urut kiri->kanan), box [x1,y1,x2,y2] piksel foto ASLI,
    confidence (0-1), lebar & tinggi wajah, dan (opsional) potongan wajah base64 JPEG.

Catatan: koordinat kotak SELALU dalam piksel foto asli (siap digambar di foto yang diunggah user).
Restorasi (auto-fix kecerahan/kontras) HANYA membantu deteksi; potongan wajah tetap diambil dari foto asli.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Union

import cv2
import numpy as np

Gambar = Union[str, Path, bytes, bytearray, np.ndarray]


# --------------------------------------------------------------------------- utilitas
def baca_gambar(gambar: Gambar) -> np.ndarray:
    """Normalkan input (path / bytes / ndarray) menjadi citra BGR 3-kanal. Raise ValueError bila gagal."""
    if isinstance(gambar, np.ndarray):
        img = gambar
    elif isinstance(gambar, (bytes, bytearray)):
        img = cv2.imdecode(np.frombuffer(bytes(gambar), np.uint8), cv2.IMREAD_COLOR)
    else:
        img = cv2.imread(str(gambar), cv2.IMREAD_COLOR)
    if img is None or getattr(img, "size", 0) == 0:
        raise ValueError("Gambar tidak dapat dibaca (path salah, file rusak, atau format tak didukung).")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _perkecil(img: np.ndarray, maks_sisi: int | None) -> tuple[np.ndarray, float]:
    """Perkecil foto sangat besar agar cepat. Kembalikan (citra, skala). skala<=1; kalikan balik utk koordinat asli."""
    if not maks_sisi:
        return img, 1.0
    h, w = img.shape[:2]
    s = maks_sisi / max(h, w)
    if s >= 1:
        return img, 1.0
    kecil = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    return kecil, s


def _potong(img: np.ndarray, box: tuple[int, int, int, int], margin: float) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    m = int(margin * max(x2 - x1, y2 - y1))
    return img[max(0, y1 - m):min(h, y2 + m), max(0, x1 - m):min(w, x2 + m)]


def _jpg_base64(img: np.ndarray, mutu: int = 95) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, mutu])
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""


def _gambar_kotak(img: np.ndarray, kotak: list[list[int]], skor: list[float]) -> np.ndarray:
    """Gambar kotak + label Person N untuk pratinjau (opsional)."""
    out = img.copy()
    t = max(2, round(max(img.shape[:2]) / 480))
    fs = max(0.45, max(img.shape[:2]) / 1700)
    for i, (b, s) in enumerate(zip(kotak, skor), 1):
        x1, y1, x2, y2 = b
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 200, 255), t)
        label = f"P{i} {s * 100:.0f}%" if (x2 - x1) < 0.045 * img.shape[1] else f"Person {i} ({s * 100:.0f}%)"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, max(1, t // 2))
        yt = max(th + 4, y1 - 4)
        cv2.rectangle(out, (x1, yt - th - 5), (x1 + tw + 5, yt + 2), (0, 200, 255), -1)
        cv2.putText(out, label, (x1 + 2, yt - 2), cv2.FONT_HERSHEY_SIMPLEX, fs, (20, 20, 20),
                    max(1, t // 2), cv2.LINE_AA)
    return out


# --------------------------------------------------------------------------- detektor
DEFAULT_DETECTOR_PATH = Path(__file__).resolve().parent / "models" / "deteksi_wajah.pt"


class FaceDetector:
    """Detektor wajah berbasis YOLO (YOLOv11m-face / deteksi_wajah). Muat sekali, pakai berkali-kali.

    model_path : file bobot ".pt" (PyTorch) atau ".onnx". Keduanya didukung Ultralytics.
    imgsz      : ukuran input inferensi (default 1088 = resolusi uji di eksperimen; kelipatan 32).
    device     : None (auto), "cpu", atau "cuda"/0.
    """

    def __init__(self, model_path: str | Path | None = None,
                 imgsz: int = 1088, device: str | int | None = None) -> None:
        from ultralytics import YOLO  # impor lokal agar modul ringan saat belum dipakai
        candidates = [
            Path(model_path) if model_path else None,
            Path(__file__).resolve().parent / "models" / "deteksi_wajah.pt",
            Path(__file__).resolve().parent / "models" / "deteksi_wajah.onnx",
            DEFAULT_DETECTOR_PATH,
        ]
        target_path = None
        for c in candidates:
            if c and c.exists():
                target_path = c
                break
        if target_path is None:
            target_path = candidates[1]  # fallback
        m_str = str(target_path)
        if m_str.endswith(".onnx"):
            self.model = YOLO(m_str, task="detect")
        else:
            self.model = YOLO(m_str)
        self.imgsz = int(imgsz)
        self.device = device

    def detect(
        self,
        gambar: Gambar,
        conf: float = 0.1,
        iou: float = 0.5,
        max_faces: int = 300,
        margin: float = 0.15,
        restore: bool = False,
        return_crops: str | None = "base64",   # "base64" | "numpy" | None
        return_annotated: bool = False,
        max_side: int | None = 1920,
        imgsz: int | None = None,
    ) -> dict[str, Any]:
        """Deteksi semua wajah pada satu foto.

        Parameter penting:
            conf           : ambang keyakinan. 0.1 = kejar recall (sedikit wajah terlewat); 0.27 = lebih presisi.
            restore        : True = auto-fix kecerahan/kontras dulu (bantu foto gelap). Default False.
            return_crops   : "base64" (JPEG base64 untuk JSON/React), "numpy" (array BGR), atau None.
            return_annotated: True = sertakan "gambar_anotasi_base64" (foto dengan kotak+label) untuk pratinjau.
            max_side       : foto lebih besar dari ini diperkecil saat proses (koordinat tetap skala foto asli).

        Return: dict (lihat README). Kotak dalam piksel foto ASLI.
        """
        asli = baca_gambar(gambar)
        H0, W0 = asli.shape[:2]
        kerja, skala = _perkecil(asli, max_side)

        kondisi: str | None = None
        if restore:
            from restorasi import analyze_quality, restore as _restore
            kondisi = analyze_quality(kerja).condition
            kerja, _info = _restore(kerja, "adaptif")

        res = self.model.predict(kerja, imgsz=imgsz or self.imgsz, conf=conf, iou=iou,
                                 max_det=max_faces, device=self.device, verbose=False)[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or len(boxes) == 0:
            xyxy = np.zeros((0, 4), np.float32)
            skor = np.zeros(0, np.float32)
        else:
            xyxy = boxes.xyxy.cpu().numpy()
            skor = boxes.conf.cpu().numpy()

        # kembalikan koordinat ke skala foto ASLI, urutkan kiri -> kanan (Person 1 = paling kiri)
        if skala != 1.0 and len(xyxy):
            xyxy = xyxy / skala
        order = np.argsort(xyxy[:, 0]) if len(xyxy) else np.zeros(0, dtype=int)
        xyxy, skor = xyxy[order], skor[order]

        wajah: list[dict[str, Any]] = []
        kotak_int: list[list[int]] = []
        for i, (b, s) in enumerate(zip(xyxy, skor), 1):
            x1 = max(0, min(W0, int(round(float(b[0])))))
            y1 = max(0, min(H0, int(round(float(b[1])))))
            x2 = max(0, min(W0, int(round(float(b[2])))))
            y2 = max(0, min(H0, int(round(float(b[3])))))
            kotak_int.append([x1, y1, x2, y2])
            item: dict[str, Any] = {
                "label": f"Person {i}",
                "box": [x1, y1, x2, y2],
                "confidence": round(float(s), 4),
                "lebar": x2 - x1,
                "tinggi": y2 - y1,
            }
            if return_crops:
                crop = _potong(asli, (x1, y1, x2, y2), margin)   # potong dari foto ASLI (tajam)
                if crop.size and return_crops == "base64":
                    item["crop_base64"] = _jpg_base64(crop)
                elif crop.size and return_crops == "numpy":
                    item["crop"] = crop
            wajah.append(item)

        hasil: dict[str, Any] = {
            "jumlah_wajah": len(wajah),
            "lebar": W0,
            "tinggi": H0,
            "pakai_restorasi": bool(restore),
            "kondisi_citra": kondisi,
            "wajah": wajah,
        }
        if return_annotated:
            hasil["gambar_anotasi_base64"] = _jpg_base64(_gambar_kotak(asli, kotak_int, [float(s) for s in skor]))
        return hasil


# --------------------------------------------------------------------------- helper sekali-panggil
_detektor_cache: dict[str, FaceDetector] = {}


def deteksi(gambar: Gambar, model_path: str | Path = "yolov11m_face_harari.pt", **kwargs) -> dict[str, Any]:
    """Versi fungsi langsung (model di-cache per path). Untuk skrip cepat / uji.
    Di server, lebih baik buat satu FaceDetector saat start lalu panggil .detect()."""
    key = str(model_path)
    if key not in _detektor_cache:
        _detektor_cache[key] = FaceDetector(model_path)
    return _detektor_cache[key].detect(gambar, **kwargs)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Pakai: python deteksi_wajah.py <foto.jpg> [model.pt]")
        raise SystemExit(1)
    model = sys.argv[2] if len(sys.argv) > 2 else "yolov8n_face_harari.pt"
    out = deteksi(sys.argv[1], model, return_crops=None)
    print(json.dumps({k: v for k, v in out.items() if k != "wajah"}, ensure_ascii=False))
    for w in out["wajah"]:
        print(f"  {w['label']:10s} box={w['box']} conf={w['confidence']:.2f} ukuran={w['lebar']}x{w['tinggi']}")
