"""RESTORASI CITRA ADAPTIF berbasis Koreksi Pencahayaan dan Kontras  (inti penelitian).

Prinsip (sesuai arahan pembimbing): struktur wajah TIDAK diubah. Yang dikoreksi
hanya kecerahan, kontras, dan derau, sehingga wajah yang semula tidak terdeteksi
menjadi terdeteksi.

"Adaptif" artinya keputusan (perlu dikoreksi atau tidak) DAN kekuatan koreksi
dihitung dari statistik masing-masing citra, bukan nilai tetap. Seluruh koreksi
dilakukan pada kanal L (lightness) ruang warna CIELAB sehingga rona warna
(kanal a & b) tidak bergeser:

  1. Analisis kualitas  : kecerahan rata-rata (mu), kontras (sigma), rentang
                          dinamis (p99 - p1), estimasi derau (Immerkaer, 1996)
                          -> kondisi {gelap, terang, kontras_rendah, normal}.
  2. Koreksi pencahayaan: gamma adaptif. Gamma dicari numerik (bisection) agar
                          rerata kecerahan mencapai target. gamma < 1 mencerahkan
                          citra gelap, gamma > 1 meredupkan citra terlalu terang.
                          Kurva diberi segmen linear di intensitas sangat rendah
                          (seperti kurva sRGB) agar derau kuantisasi tidak meledak.
  3. Reduksi derau      : Non-Local Means pada kanal L, hanya bila pencerahan kuat
                          DAN derau tinggi. Kekuatan filter ~ besar derau.
  4. Koreksi kontras    : CLAHE pada kanal L dengan clip limit sebanding
                          kekurangan kontras.
  5. Kompensasi kroma   : saat L dinaikkan, saturasi a/b ikut dinaikkan terbatas
                          agar warna tidak pucat.

Citra berkondisi normal dikembalikan apa adanya (tidak ikut "dirusak").

Modul ini juga menyediakan metode pembanding (baseline) untuk studi ablasi:
HE global, CLAHE tetap, gamma tetap, dan tiap komponen adaptif secara terpisah.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

CONDITIONS = ("gelap", "terang", "kontras_rendah", "normal")

DEFAULTS = {
    "dark_threshold": 0.30,  # mu < ini  -> gelap
    "bright_threshold": 0.65,  # mu > ini  -> terang
    "contrast_threshold": 0.12,  # sigma < ini -> kontras rendah
    "range_threshold": 0.40,  # (p99 - p1) < ini -> kontras rendah
    "target_dark": 0.40,  # target mu setelah koreksi citra gelap
    "target_bright": 0.55,  # target mu setelah koreksi citra terang
    "gamma_limits": [0.20, 3.0],
    "gamma_toe": 0.015,  # segmen linear kurva gamma untuk L < toe
    "denoise": "auto",  # auto | on | off
    "denoise_gamma": 0.70,  # denoise hanya bila gamma < ini (pencerahan kuat)
    "denoise_noise": 4.0,  # ... dan derau setelah pencerahan > ini (skala 0-255)
    "denoise_strength": 0.8,  # h NLM = strength * derau
    "denoise_h_limits": [3.0, 12.0],
    "clahe_target_std": 0.20,  # CLAHE aktif bila sigma < ini
    "clahe_floor_std": 0.06,  # pada sigma ini clip limit maksimum
    "clahe_clip_min": 1.0,
    "clahe_clip_max": 3.0,
    "clahe_tiles": 8,
    "chroma_gain_max": 1.6,  # 1.0 = tanpa kompensasi kroma
    "fixed_gamma": 0.5,  # untuk baseline gamma_tetap
    "fixed_clahe_clip": 2.0,  # untuk baseline clahe_tetap
}

# Nama metode -> keterangan (dipakai di laporan ablasi)
METHODS = {
    "tanpa": "Tanpa restorasi (citra asli)",
    "he": "Histogram Equalization global",
    "clahe_tetap": "CLAHE clip limit tetap",
    "gamma_tetap": "Koreksi gamma tetap",
    "gamma_adaptif": "Gamma adaptif saja",
    "clahe_adaptif": "CLAHE adaptif saja",
    "adaptif_tanpa_denoise": "Gamma adaptif + CLAHE adaptif",
    "adaptif": "Restorasi adaptif penuh (usulan)",
}


@dataclass
class QualityReport:
    mean: float  # rerata kecerahan L (0-1)
    std: float  # kontras global (simpangan baku L)
    p01: float
    p99: float
    dark_ratio: float  # proporsi piksel sangat gelap (< 0.15)
    bright_ratio: float  # proporsi piksel sangat terang (> 0.85)
    noise: float  # estimasi sigma derau (skala 0-255)
    condition: str

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _params(cfg: dict | None) -> dict:
    p = dict(DEFAULTS)
    if cfg:
        p.update({k: v for k, v in cfg.items() if k in DEFAULTS})
    return p


def _small(arr: np.ndarray, max_side: int = 512) -> np.ndarray:
    h, w = arr.shape[:2]
    s = max_side / max(h, w)
    if s >= 1:
        return arr
    return cv2.resize(arr, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)


def _lightness(img: np.ndarray) -> np.ndarray:
    """Kanal L (CIELAB) uint8 0-255."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0]


def estimate_noise(gray_u8: np.ndarray) -> float:
    """Estimasi simpangan baku derau Gaussian (metode cepat Immerkaer, 1996)."""
    g = gray_u8.astype(np.float32)
    h, w = g.shape
    if h < 3 or w < 3:
        return 0.0
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    conv = cv2.filter2D(g, -1, kernel, borderType=cv2.BORDER_REFLECT)
    return float(np.sqrt(np.pi / 2) * np.abs(conv[1:-1, 1:-1]).sum() / (6.0 * (w - 2) * (h - 2)))


def analyze_quality(img: np.ndarray, cfg: dict | None = None) -> QualityReport:
    p = _params(cfg)
    L_full = _lightness(img)
    L = _small(L_full).astype(np.float32) / 255.0
    mean, std = float(L.mean()), float(L.std())
    p01, p99 = (float(v) for v in np.percentile(L, [1, 99]))
    if mean < p["dark_threshold"]:
        cond = "gelap"
    elif mean > p["bright_threshold"]:
        cond = "terang"
    elif std < p["contrast_threshold"] or (p99 - p01) < p["range_threshold"]:
        cond = "kontras_rendah"
    else:
        cond = "normal"
    return QualityReport(
        mean=mean,
        std=std,
        p01=p01,
        p99=p99,
        dark_ratio=float((L < 0.15).mean()),
        bright_ratio=float((L > 0.85).mean()),
        noise=estimate_noise(L_full),
        condition=cond,
    )


# ----------------------------------------------------------------------------
# Komponen-komponen koreksi (bekerja pada kanal L uint8)
# ----------------------------------------------------------------------------
def gamma_curve(x: np.ndarray, gamma: float, toe: float = 0.0) -> np.ndarray:
    """y = x^gamma, dengan segmen linear untuk x < toe saat mencerahkan (gamma < 1)."""
    y = np.power(np.maximum(x, 1e-6), gamma)
    if gamma < 1.0 and toe > 0:
        slope = toe ** (gamma - 1.0)
        y = np.where(x < toe, x * slope, y)
    return y


def gamma_table(gamma: float, toe: float = 0.0) -> np.ndarray:
    y = gamma_curve(np.arange(256) / 255.0, gamma, toe)
    return np.clip(np.round(y * 255.0), 0, 255).astype(np.uint8)


def solve_gamma(x: np.ndarray, target: float, limits=(0.2, 3.0), toe: float = 0.0, iters: int = 30) -> float:
    """Cari gamma sehingga mean(gamma_curve(x)) = target (bisection pada domain log)."""
    x = np.clip(x.astype(np.float32), 0.0, 1.0)
    lo, hi = float(np.log(limits[0])), float(np.log(limits[1]))

    def mean_after(log_g: float) -> float:
        return float(np.mean(gamma_curve(x, float(np.exp(log_g)), toe)))

    # mean_after menurun terhadap gamma
    if mean_after(lo) <= target:
        return float(limits[0])
    if mean_after(hi) >= target:
        return float(limits[1])
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if mean_after(mid) > target:
            lo = mid
        else:
            hi = mid
    return float(np.exp(0.5 * (lo + hi)))


def _clahe(L: np.ndarray, clip: float, tiles: int) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(int(tiles), int(tiles))).apply(L)


def _with_L(img: np.ndarray, fn) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = fn(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _compensate_chroma(lab: np.ndarray, L_before: np.ndarray, gain_max: float) -> None:
    """Naikkan saturasi a/b sebanding kenaikan L (dibatasi), in-place."""
    lb = cv2.GaussianBlur(L_before.astype(np.float32) / 255.0, (0, 0), 3)
    la = cv2.GaussianBlur(lab[..., 0].astype(np.float32) / 255.0, (0, 0), 3)
    ratio = np.clip((la + 0.05) / (lb + 0.05), 1.0, gain_max)
    for c in (1, 2):
        ch = (lab[..., c].astype(np.float32) - 128.0) * ratio + 128.0
        lab[..., c] = np.clip(np.round(ch), 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------
# Fungsi utama
# ----------------------------------------------------------------------------
def adaptive_restore(
    img: np.ndarray, cfg: dict | None = None, use_gamma: bool = True, use_denoise: bool = True,
    use_clahe: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    p = _params(cfg)
    rep = analyze_quality(img, p)
    info: dict[str, Any] = {"kondisi": rep.condition, "langkah": [], "gamma": 1.0, "denoise_h": None,
                            "clahe_clip": None}
    if rep.condition == "normal":
        return img.copy(), info

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    L_before = lab[..., 0].copy()
    L = lab[..., 0]

    # 2) Koreksi pencahayaan (gamma adaptif)
    gamma = 1.0
    if use_gamma and rep.condition in ("gelap", "terang"):
        target = p["target_dark"] if rep.condition == "gelap" else p["target_bright"]
        need = rep.mean < target if rep.condition == "gelap" else rep.mean > target
        if need:
            x = _small(L).astype(np.float32) / 255.0
            gamma = solve_gamma(x, target, tuple(p["gamma_limits"]), p["gamma_toe"])
            if abs(gamma - 1.0) > 1e-3:
                L = cv2.LUT(L, gamma_table(gamma, p["gamma_toe"]))
                info["langkah"].append("gamma")
                info["gamma"] = round(gamma, 4)
            else:
                gamma = 1.0

    # 3) Reduksi derau adaptif
    mode = str(p["denoise"]).lower()
    if use_denoise and mode != "off":
        noise_now = estimate_noise(L)
        info["derau_setelah_gamma"] = round(noise_now, 3)
        if mode == "on" or (gamma < p["denoise_gamma"] and noise_now > p["denoise_noise"]):
            h_lo, h_hi = p["denoise_h_limits"]
            h = float(np.clip(p["denoise_strength"] * noise_now, h_lo, h_hi))
            L = cv2.fastNlMeansDenoising(L, None, h=h, templateWindowSize=7, searchWindowSize=21)
            lab[..., 1] = cv2.GaussianBlur(lab[..., 1], (0, 0), 1.0)
            lab[..., 2] = cv2.GaussianBlur(lab[..., 2], (0, 0), 1.0)
            info["langkah"].append("denoise")
            info["denoise_h"] = round(h, 2)

    # 4) Koreksi kontras (CLAHE adaptif)
    if use_clahe:
        std_now = float((_small(L).astype(np.float32) / 255.0).std())
        deficit = p["clahe_target_std"] - std_now
        if deficit > 0:
            span = max(p["clahe_target_std"] - p["clahe_floor_std"], 1e-6)
            s = float(np.clip(deficit / span, 0.0, 1.0))
            clip = p["clahe_clip_min"] + (p["clahe_clip_max"] - p["clahe_clip_min"]) * s
            h, w = L.shape
            tiles = int(max(2, min(p["clahe_tiles"], min(h, w) // 64)))
            L = _clahe(L, clip, tiles)
            info["langkah"].append("clahe")
            info["clahe_clip"] = round(clip, 3)

    if not info["langkah"]:
        return img.copy(), info

    lab[..., 0] = L
    # 5) Kompensasi kroma bila citra dicerahkan
    if gamma < 1.0 and p["chroma_gain_max"] > 1.0:
        _compensate_chroma(lab, L_before, p["chroma_gain_max"])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), info


def restore(img: np.ndarray, method: str = "adaptif", cfg: dict | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Jalankan satu metode restorasi. Mengembalikan (citra_hasil, info)."""
    t0 = time.perf_counter()
    p = _params(cfg)
    info: dict[str, Any]
    if method == "tanpa":
        out, info = img.copy(), {"langkah": []}
    elif method == "he":
        out, info = _with_L(img, cv2.equalizeHist), {"langkah": ["he"]}
    elif method == "clahe_tetap":
        out = _with_L(img, lambda L: _clahe(L, p["fixed_clahe_clip"], p["clahe_tiles"]))
        info = {"langkah": ["clahe"], "clahe_clip": p["fixed_clahe_clip"]}
    elif method == "gamma_tetap":
        out = _with_L(img, lambda L: cv2.LUT(L, gamma_table(p["fixed_gamma"], p["gamma_toe"])))
        info = {"langkah": ["gamma"], "gamma": p["fixed_gamma"]}
    elif method == "gamma_adaptif":
        out, info = adaptive_restore(img, p, use_gamma=True, use_denoise=False, use_clahe=False)
    elif method == "clahe_adaptif":
        out, info = adaptive_restore(img, p, use_gamma=False, use_denoise=False, use_clahe=True)
    elif method == "adaptif_tanpa_denoise":
        out, info = adaptive_restore(img, p, use_gamma=True, use_denoise=False, use_clahe=True)
    elif method == "adaptif":
        out, info = adaptive_restore(img, p)
    else:
        raise ValueError(f"Metode restorasi tidak dikenal: {method}. Pilihan: {list(METHODS)}")
    info["metode"] = method
    info["waktu_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return out, info
