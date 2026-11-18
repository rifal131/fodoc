"""Gambar kotak (bingkai) wajah + label ringkas "P1, P2, ..." pada foto.

Revisi bimbingan (label "P" kecil saja, bingkai berukuran normal tepat di wajah):
  - BINGKAI = kotak hasil detektor apa adanya (pas di wajah, tidak diperbesar), garisnya tipis:
    1 px untuk wajah kecil, 2 px untuk wajah sedang/besar - bingkai tidak menutupi wajah;
  - LABEL "P<n>" berupa tab KECIL: tinggi huruf = 16% sisi pendek wajah, dibatasi 6-11 px
    (sebelumnya 30% dan sampai 14 px sehingga tab menutupi dahi/mata pada wajah sedang);
  - tab menempel di pojok kiri-atas DI DALAM bingkai hanya bila ia menutupi <= 22% tinggi dan
    <= 45% lebar wajah; selain itu (wajah kecil, mis. barisan belakang foto rombongan) tab
    diletakkan tepat DI ATAS bingkai (menutupi rambut/latar, bukan wajah);
  - isi label cukup "P<n>" (persentase keyakinan tetap ada di JSON / daftar hasil di aplikasi);
  - yang digambar hanya kotak yang lolos ambang aplikasi + saringan kewajaran (src/saringan.py),
    sehingga selain wajah tidak ikut diberi bingkai.

Dipakai bersama oleh demo (5_demo_deteksi.py), web app, Streamlit, dan buat_dataset_vikry.py
agar tampilan labelnya seragam. Gambarlah pada citra berukuran TAMPIL (mis. maks 1600 px),
bukan pada foto resolusi penuh yang nanti diperkecil, supaya ukuran label tetap sesuai.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import cv2
import numpy as np

# Font TrueType (Windows: arial/segoe; Linux: DejaVu). Bila tidak ada, dipakai font bawaan OpenCV.
_FONT_KANDIDAT = ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "arial.ttf", "DejaVuSans.ttf")

FONT_MIN_PX = 6      # wajah sangat kecil (foto rombongan) -> label tetap terbaca
FONT_MAX_PX = 11     # wajah besar (selfie) -> label tidak ikut membesar
FONT_RASIO = 0.16    # ukuran huruf = 16% sisi pendek kotak wajah (lalu dibatasi min/maks di atas)
MAKS_TUTUP = 0.22    # tab di dalam kotak maks. 22% tinggi wajah; lebih dari itu -> tab di atas kotak
MAKS_LEBAR = 0.45    # ... dan maks. 45% lebar wajah
TEBAL_TIPIS_SAMPAI = 70   # sisi pendek wajah < 70 px -> garis bingkai 1 px, selebihnya 2 px


@lru_cache(maxsize=32)
def _font(px: int):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for nama in _FONT_KANDIDAT:
        try:
            return ImageFont.truetype(nama, px)
        except OSError:
            continue
    return None


def _ukuran(sisi: float) -> tuple[int, int]:
    """(ukuran huruf px, tebal garis px) berdasarkan sisi pendek kotak wajah."""
    font_px = int(np.clip(round(sisi * FONT_RASIO), FONT_MIN_PX, FONT_MAX_PX))
    tebal = 1 if sisi < TEBAL_TIPIS_SAMPAI else 2
    return font_px, tebal


def _warna_teks(warna: tuple[int, int, int]) -> tuple[int, int, int]:
    """Teks gelap di atas warna terang (kuning/oranye), teks putih di atas warna gelap (merah/hijau/abu)."""
    b, g, r = warna
    return (20, 20, 20) if (0.114 * b + 0.587 * g + 0.299 * r) > 150 else (255, 255, 255)


def gambar_kotak_wajah(img: np.ndarray, boxes: Sequence[Sequence[float]], labels: Sequence[str] | None = None,
                       warna: tuple[int, int, int] = (0, 200, 255),
                       warna_tiap: Sequence[tuple[int, int, int]] | None = None,
                       tampil_label: bool = True) -> np.ndarray:
    """Gambar kotak tiap wajah + tab label kecil di pojok kiri-atas di dalam kotak.

    boxes      : [[x1, y1, x2, y2], ...] dalam piksel citra `img`.
    labels     : teks tiap kotak (default "P1", "P2", ...).
    warna      : warna kotak (BGR) untuk semua wajah.
    warna_tiap : (opsional) warna per wajah, mis. hijau = dikenali, merah = terdeteksi tapi tidak dikenali
                 (arahan bimbingan 5: cukup bingkai berwarna, tidak perlu tulisan "unknown").
    tampil_label: False = bingkai saja tanpa tab "P<n>" (mis. tampilan untuk pengguna akhir).
    """
    out = img.copy()
    if len(boxes) == 0:
        return out
    h_img, w_img = out.shape[:2]
    labels = list(labels) if labels is not None else [f"P{i}" for i in range(1, len(boxes) + 1)]
    warna_list = list(warna_tiap) if warna_tiap is not None else [warna] * len(boxes)

    kotak = []
    for b in boxes:
        x1, y1, x2, y2 = (int(round(float(v))) for v in b[:4])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img - 1, x2), min(h_img - 1, y2)
        kotak.append((x1, y1, x2, y2))

    # 1) semua garis kotak dulu, 2) baru tab label, agar label tidak tertimpa garis kotak lain
    tab = []
    for (x1, y1, x2, y2), lab, wr in zip(kotak, labels, warna_list):
        font_px, t = _ukuran(min(x2 - x1, y2 - y1))
        cv2.rectangle(out, (x1, y1), (x2, y2), wr, t, cv2.LINE_AA)
        tab.append((x1 - t // 2, y1 - t // 2, y2 - y1, x2 - x1, lab, wr, font_px))

    if not tampil_label:
        return out
    font_ok = _font(FONT_MAX_PX) is not None
    teks_pil = []
    for x, y, tinggi_wajah, lebar_wajah, lab, wr, font_px in tab:
        pad_x, pad_y = max(2, round(font_px * 0.28)), max(1, round(font_px * 0.2))
        if font_ok:
            f = _font(font_px)
            l, t_, r, b_ = f.getbbox(lab)
            tw, th = r - l, b_ - t_
        else:
            skala = 0.72 * font_px / 22
            (tw, th), _ = cv2.getTextSize(lab, cv2.FONT_HERSHEY_SIMPLEX, skala, 1)
        tinggi_tab = th + 2 * pad_y
        terlalu_besar = tinggi_tab > MAKS_TUTUP * tinggi_wajah or tw + 2 * pad_x > MAKS_LEBAR * lebar_wajah
        if terlalu_besar and y - tinggi_tab >= 0:
            y -= tinggi_tab                     # wajah kecil: tab menempel di atas kotak
        x, y = max(0, min(x, w_img - 1)), max(0, y)
        x2t, y2t = min(w_img - 1, x + tw + 2 * pad_x), min(h_img - 1, y + tinggi_tab)
        cv2.rectangle(out, (x, y), (x2t, y2t), wr, -1)
        if font_ok:
            teks_pil.append(((x + pad_x - l, y + pad_y - t_), lab, f, _warna_teks(wr)))
        else:
            cv2.putText(out, lab, (x + pad_x, y + pad_y + th), cv2.FONT_HERSHEY_SIMPLEX, skala,
                        _warna_teks(wr), 1, cv2.LINE_AA)

    if teks_pil:
        from PIL import Image, ImageDraw
        pil = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(pil)
        for pos, lab, f, (b, g, r) in teks_pil:
            d.text(pos, lab, font=f, fill=(r, g, b))
        out = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
    return out
