"""Saringan kewajaran kotak deteksi: hanya WAJAH yang boleh diberi bingkai.

Arahan pembimbing: bingkai harus tepat pada wajah, dan yang bukan wajah tidak boleh ikut
dibingkai. Detektor sudah memberi skor keyakinan; ambang skor (ambang aplikasi, presisi
tinggi) menyingkirkan sebagian besar deteksi palsu. Saringan ini menyediakan tiga pemeriksaan
geometri tambahan; tiap aturan bisa dimatikan dengan nilai 0:

  1. terlalu kecil    : sisi terpendek < min_sisi piksel;
  2. bentuk tidak wajar: rasio lebar/tinggi di luar [rasio_min, rasio_maks];
  3. kotak di dalam kotak: >= tumpang_dalam bagian luasnya berada di dalam kotak lain yang
                        skornya lebih tinggi (mis. mulut/mata terdeteksi lagi sebagai "wajah"
                        di dalam wajah yang sama) - NMS biasa tidak membuangnya karena IoU-nya
                        kecil.

DASAR EMPIRIS SETELAN BAWAAN (7_bandingkan_yolo_s3fd.py, tabel saringan_per_aturan.csv; data
validasi, 7 pasangan model x skenario pada ambang aplikasi, 2.316 TP dan 117 FP):
  - min_sisi = 10 membuang 58 wajah BENAR dan 0 bingkai salah (kotak prediksi wajah 10-12 px
    sering sedikit di bawah 10 px); min_sisi <= 6 tidak membuang apa pun  -> DIMATIKAN (0);
  - rasio 0,45-1,60 membuang 16 wajah benar dan 0 bingkai salah (wajah terpotong tepi foto /
    tertutup sebagian memang tidak persegi); rentang yang lebih longgar pun hanya membuang
    wajah benar                                                           -> DIMATIKAN (0);
  - tumpang_dalam = 0,70 membuang 0 wajah benar dan 1 bingkai salah       -> DIPAKAI.
Artinya bingkai pada bukan-wajah terutama ditekan oleh AMBANG APLIKASI, bukan oleh aturan
geometri. Aturan 1 dan 2 tetap tersedia di config.yaml (aplikasi.saringan) bila kelak ada
data yang menunjukkan manfaatnya.
"""

from __future__ import annotations

import numpy as np

BAWAAN = {"aktif": True, "min_sisi": 0, "rasio_min": 0, "rasio_maks": 0, "tumpang_dalam": 0.70}


def setelan_saringan(cfg: dict | None) -> dict:
    s = dict(BAWAAN)
    s.update(((cfg or {}).get("aplikasi") or {}).get("saringan") or {})
    return s


def saring_kotak(boxes, scores, setelan: dict | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return (boxes, scores, info). info = jumlah kotak yang dibuang per alasan."""
    s = dict(BAWAAN)
    s.update(setelan or {})
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float32).reshape(-1)
    info = {"masuk": int(len(boxes)), "terlalu_kecil": 0, "bentuk_tidak_wajar": 0, "di_dalam_kotak_lain": 0}
    if not s.get("aktif", True) or len(boxes) == 0:
        info["lolos"] = int(len(boxes))
        return boxes, scores, info

    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]
    kecil = np.minimum(w, h) < float(s.get("min_sisi") or 0)
    rasio = w / np.maximum(h, 1e-6)
    r_min, r_maks = float(s.get("rasio_min") or 0), float(s.get("rasio_maks") or 0)   # 0 = aturan mati
    aneh = np.zeros(len(boxes), dtype=bool)
    if r_min > 0:
        aneh |= rasio < r_min
    if r_maks > 0:
        aneh |= rasio > r_maks
    aneh &= ~kecil
    info["terlalu_kecil"], info["bentuk_tidak_wajar"] = int(kecil.sum()), int(aneh.sum())
    keep = ~(kecil | aneh)

    batas = float(s.get("tumpang_dalam", 0) or 0)
    if batas > 0 and keep.sum() > 1:
        idx = np.flatnonzero(keep)
        idx = idx[np.argsort(-scores[idx], kind="stable")]          # skor tertinggi lebih dulu
        b = boxes[idx]
        luas = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
        hidup = np.ones(len(idx), dtype=bool)
        for i in range(1, len(idx)):
            atas = np.flatnonzero(hidup[:i])
            if atas.size == 0:
                continue
            lt = np.maximum(b[i, :2], b[atas, :2])
            rb = np.minimum(b[i, 2:], b[atas, 2:])
            irisan = np.clip(rb - lt, 0, None).prod(axis=1)
            # bagian kotak yang LEBIH KECIL yang tertutup irisan (kotak kecil di dalam kotak besar, atau sebaliknya)
            if np.any(irisan / np.maximum(np.minimum(luas[i], luas[atas]), 1e-6) >= batas):
                hidup[i] = False
        info["di_dalam_kotak_lain"] = int((~hidup).sum())
        keep[idx[~hidup]] = False
    info["lolos"] = int(keep.sum())
    return boxes[keep], scores[keep], info


def saring_prediksi(preds: dict, setelan: dict | None = None) -> dict:
    """Terapkan saringan ke seluruh prediksi (id -> {boxes, scores}); dipakai untuk mengukur
    pengaruh saringan pada data uji."""
    out = {}
    for k, p in preds.items():
        b, sc, _ = saring_kotak(p["boxes"], p["scores"], setelan)
        out[k] = {"boxes": b, "scores": sc}
    return out
