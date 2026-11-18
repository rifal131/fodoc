"""Alignment wajah 5-titik (standar ArcFace) untuk tahap pengenalan wajah.

Saran dari tim (Rifal): jangan hanya resize kotak wajah; luruskan dulu (alignment) berdasarkan
landmark mata/hidung/mulut sebelum ekstraksi. Ini menaikkan akurasi recognition pada wajah miring.

Pakai:
    from align import align_face, cari_landmark
    aligned = align_face(img_bgr, landmark5, size=112)
"""

from __future__ import annotations

import cv2
import numpy as np

# Template 5 titik acuan ArcFace untuk wajah 112x112:
# [mata kiri, mata kanan, hidung, sudut mulut kiri, sudut mulut kanan]
REF_112 = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)


def align_face(img: np.ndarray, landmark5, size: int = 112) -> np.ndarray | None:
    """Luruskan (align) wajah ke ukuran size x size berdasarkan 5 landmark.

    Transformasi kesebangunan (rotasi + skala + translasi) dari 5 landmark terdeteksi ke template
    acuan, lalu warp. Mengembalikan citra BGR (size x size), atau None bila transformasi gagal.
    """
    pts = np.ascontiguousarray(np.asarray(landmark5, dtype=np.float32).reshape(-1, 2))
    if pts.shape[0] != 5 or not np.isfinite(pts).all():
        return None
    ref = np.ascontiguousarray(REF_112 * (size / 112.0))
    M, _ = cv2.estimateAffinePartial2D(pts, ref, method=cv2.LMEDS)
    if M is None:
        return None
    return cv2.warpAffine(img, M, (size, size), borderValue=(0, 0, 0))


def sudut_mata(landmark5) -> float:
    """Kemiringan garis mata kiri->kanan terhadap horizontal, dalam derajat (0 = tegak, +-180 = terbalik)."""
    kp = np.asarray(landmark5, dtype=np.float32).reshape(-1, 2)
    dx, dy = kp[1] - kp[0]
    return float(np.degrees(np.arctan2(dy, dx)))


def landmark_wajar(landmark5) -> bool:
    """Cek bentuk 5 landmark: mulut di 'bawah' garis mata (tidak tercermin), tegak lurus, proporsi wajar."""
    kp = np.asarray(landmark5, dtype=np.float32).reshape(-1, 2)
    if kp.shape[0] != 5 or not np.isfinite(kp).all():
        return False
    e = kp[1] - kp[0]                                  # mata kiri -> mata kanan
    d = (kp[3] + kp[4]) / 2 - (kp[0] + kp[1]) / 2      # tengah mata -> tengah mulut
    ne, nd = float(np.linalg.norm(e)), float(np.linalg.norm(d))
    if ne < 1e-3 or nd < 1e-3:
        return False
    silang = float(e[0] * d[1] - e[1] * d[0])          # > 0 pada template tegak
    cos = abs(float(e @ d)) / (ne * nd)
    return silang > 0 and cos < 0.5 and 0.5 <= nd / ne <= 2.2


def _landmark_sekali(model, img):
    r = model.predict(img, imgsz=320, conf=0.10, iou=0.5, max_det=10, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0 or r.keypoints is None:
        return None, 0.0
    bx = r.boxes.xyxy.cpu().numpy()
    kxy = r.keypoints.xy.cpu().numpy()
    j = int(np.argmax((bx[:, 2] - bx[:, 0]) * (bx[:, 3] - bx[:, 1])))   # wajah terbesar = wajah utama
    if j >= len(kxy):
        return None, 0.0
    kp = np.asarray(kxy[j], dtype=np.float32).reshape(-1, 2)
    if kp.shape[0] != 5 or np.all(kp == 0):
        return None, 0.0
    return kp, float(r.boxes.conf.cpu().numpy()[j])


def _balik_rotasi(kp, rot, h: int, w: int):
    """Petakan landmark dari crop yang diputar kembali ke koordinat crop asli (tinggi h, lebar w)."""
    x, y = kp[:, 0], kp[:, 1]
    if rot == cv2.ROTATE_90_CLOCKWISE:
        return np.stack([y, h - 1 - x], 1)
    if rot == cv2.ROTATE_90_COUNTERCLOCKWISE:
        return np.stack([w - 1 - y, x], 1)
    if rot == cv2.ROTATE_180:
        return np.stack([w - 1 - x, h - 1 - y], 1)
    return kp


MIN_SISI = 14        # crop wajah minimal (px) untuk dicari landmark
MAKS_MIRING = 120.0  # tafsiran hampir terbalik (> ini) hampir selalu salah landmark pada foto acara


def cari_landmark(model, crop, conf_min: float = 0.18):
    """5 landmark pada potongan SATU wajah, tahan terhadap wajah miring & wajah berukuran kecil."""
    if crop is None or crop.size == 0:
        return None, 0.0
    h, w = crop.shape[:2]
    if min(h, w) < MIN_SISI:
        return None, 0.0

    # Untuk crop wajah kecil (< 64px), upscale dulu secara teratur agar model YOLO pose
    # dapat mendeteksi kelima landmark mata/hidung/mulut secara akurat
    scale_factor = 1.0
    crop_input = crop
    if min(h, w) < 64:
        scale_factor = 128.0 / max(h, w)
        crop_input = cv2.resize(
            crop, (max(1, int(w * scale_factor)), max(1, int(h * scale_factor))), interpolation=cv2.INTER_CUBIC
        )

    terbaik = (None, 0.0)
    for rot in (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180):
        target = crop_input if rot is None else cv2.rotate(crop_input, rot)
        kp, c = _landmark_sekali(model, target)
        if kp is None:
            continue
        ih, iw = target.shape[:2]
        kp = _balik_rotasi(kp, rot, ih, iw)
        if scale_factor != 1.0:
            kp = kp / scale_factor
        if landmark_wajar(kp) and abs(sudut_mata(kp)) <= MAKS_MIRING and c > terbaik[1]:
            terbaik = (kp, c)
        if rot is None and terbaik[0] is not None and c >= 0.5 and abs(sudut_mata(kp)) < 30:
            break
    return terbaik if terbaik[1] >= conf_min else (None, 0.0)
