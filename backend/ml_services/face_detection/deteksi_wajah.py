"""Deteksi wajah siap pakai untuk aplikasi web (alur sama persis dengan aplikasi deteksi Harari).

foto -> diperkecil (sisi terpanjang maks 1600 px) -> YOLOv11n-face terlatih (input 1088, NMS IoU 0,5)
     -> hanya kotak dengan keyakinan >= AMBANG APLIKASI (0,464) -> saringan kotak-di-dalam-kotak
     -> diurutkan kiri ke kanan: P1, P2, ... -> bingkai tipis + label "P" kecil (anotasi.py)

Pakai sebagai modul (mis. di Flask/FastAPI/Django):

    from deteksi_wajah import DetektorWajah
    det = DetektorWajah()                      # muat model SEKALI saat server mulai
    hasil = det.deteksi(img_bgr)               # img_bgr: numpy array dari cv2.imread / cv2.imdecode
    gambar = det.gambar(hasil)                 # foto berbingkai (BGR) untuk ditampilkan
    hasil["wajah"]                             # [{"label": "P1", "confidence": .., "kotak": [..], ...}]

Atau dari baris perintah (untuk mencoba):

    python deteksi_wajah.py --gambar foto.jpg
    python deteksi_wajah.py --gambar folder_foto --keluaran hasil_deteksi --onnx

Format model:
    .pt   -> butuh pustaka ultralytics (dan torch)
    .onnx -> cukup onnxruntime + opencv + numpy (lebih ringan untuk server); hasilnya sama
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from anotasi import gambar_kotak_wajah   # bingkai tipis + label "P" kecil (revisi bimbingan)
from saringan import saring_kotak        # buang kotak yang berada di dalam kotak lain

HERE = Path(__file__).resolve().parent
INFO = json.loads((HERE / "info_model.json").read_text(encoding="utf-8"))

AMBANG = float(INFO.get("ambang_pakai") or INFO.get("ambang_aplikasi") or 0.464)
IMGSZ = int(INFO.get("imgsz_uji", 1088))
NMS_IOU = 0.5
MAKS_DETEKSI = 300
MAKS_SISI_PROSES = 1600          # foto besar (kamera/HP) diperkecil dulu, sama dengan aplikasi
MIN_RECOGNITION = int(INFO.get("min_piksel_recognition", 112))
WARNA_BINGKAI = (0, 200, 255)    # BGR (kuning-oranye), sama dengan aplikasi


def perkecil(img: np.ndarray, maks_sisi: int = MAKS_SISI_PROSES) -> np.ndarray:
    h, w = img.shape[:2]
    s = maks_sisi / max(h, w)
    if s >= 1:
        return img
    return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)


class _ModelPt:
    """deteksi_wajah.pt lewat Ultralytics."""

    def __init__(self, path: Path):
        from ultralytics import YOLO
        self.m = YOLO(str(path), task="detect")

    def __call__(self, img_bgr: np.ndarray, ambang: float):
        r = self.m.predict(img_bgr, imgsz=IMGSZ, conf=ambang, iou=NMS_IOU, max_det=MAKS_DETEKSI, verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            return np.zeros((0, 4), np.float32), np.zeros(0, np.float32)
        return r.boxes.xyxy.cpu().numpy().astype(np.float32), r.boxes.conf.cpu().numpy().astype(np.float32)


class _ModelOnnx:
    """deteksi_wajah.onnx lewat onnxruntime, tanpa Ultralytics/torch.
    Input [1,3,1088,1088] RGB 0-1 (letterbox, isi abu-abu 114); output [1,5,N] = cx, cy, w, h, skor."""

    def __init__(self, path: Path):
        import onnxruntime as ort
        self.s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.nama_input = self.s.get_inputs()[0].name

    def __call__(self, img_bgr: np.ndarray, ambang: float):
        h, w = img_bgr.shape[:2]
        r = min(IMGSZ / h, IMGSZ / w)
        nw, nh = int(round(w * r)), int(round(h * r))
        dx, dy = (IMGSZ - nw) / 2, (IMGSZ - nh) / 2
        kanvas = np.full((IMGSZ, IMGSZ, 3), 114, np.uint8)
        top, left = int(round(dy - 0.1)), int(round(dx - 0.1))
        kanvas[top:top + nh, left:left + nw] = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        x = cv2.cvtColor(kanvas, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0

        out = self.s.run(None, {self.nama_input: x})[0][0].T          # (N, 5)
        out = out[out[:, 4] >= ambang]
        if len(out) == 0:
            return np.zeros((0, 4), np.float32), np.zeros(0, np.float32)
        cx, cy, bw, bh, skor = out.T
        xyxy = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1)
        keep = cv2.dnn.NMSBoxes(np.stack([xyxy[:, 0], xyxy[:, 1], bw, bh], 1).tolist(), skor.tolist(),
                                ambang, NMS_IOU)
        keep = np.array(keep).reshape(-1)[:MAKS_DETEKSI]
        xyxy, skor = xyxy[keep], skor[keep]
        xyxy -= [left, top, left, top]                                  # kembali ke koordinat foto
        xyxy /= r
        xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, w)
        xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, h)
        return xyxy.astype(np.float32), skor.astype(np.float32)


class DetektorWajah:
    def __init__(self, onnx: bool = False, ambang: float | None = None):
        """onnx=True memakai deteksi_wajah.onnx (onnxruntime); default deteksi_wajah.pt (ultralytics).
        ambang=None memakai ambang aplikasi dari info_model.json (0,464)."""
        self.ambang = AMBANG if ambang is None else float(ambang)
        self.model = _ModelOnnx(HERE / "deteksi_wajah.onnx") if onnx else _ModelPt(HERE / "deteksi_wajah.pt")
        self.format = "onnx" if onnx else "pt"

    def deteksi(self, img_bgr: np.ndarray) -> dict:
        """Satu foto (BGR, ukuran bebas) -> dict hasil. Koordinat `kotak` pada citra `citra_tampil`
        (foto yang sudah diperkecil), `kotak_asli` pada foto asli yang dikirim."""
        t0 = time.perf_counter()
        img = perkecil(img_bgr)
        boxes, scores = self.model(img, self.ambang)
        boxes, scores, info_saringan = saring_kotak(boxes, scores, INFO.get("saringan"))
        urut = np.argsort(boxes[:, 0]) if len(boxes) else np.zeros(0, int)   # P1 = paling kiri
        boxes, scores = boxes[urut], scores[urut]

        skala = max(img_bgr.shape[:2]) / max(img.shape[:2])
        wajah = []
        for i, (b, s) in enumerate(zip(boxes, scores), 1):
            sisi_asli = float(min(b[2] - b[0], b[3] - b[1])) * skala
            wajah.append({
                "label": f"P{i}",
                "confidence": round(float(s), 4),
                "kotak": [int(round(float(v))) for v in b],
                "kotak_asli": [int(round(float(v) * skala)) for v in b],
                "sisi_wajah_px": int(round(sisi_asli)),
                "layak_recognition": bool(sisi_asli >= MIN_RECOGNITION),
            })
        return {
            "jumlah_wajah": len(wajah),
            "wajah": wajah,
            "ambang": round(self.ambang, 4),
            "saringan": info_saringan,
            "waktu_ms": round((time.perf_counter() - t0) * 1000, 1),
            "citra_tampil": img,           # numpy array; JANGAN ikut di-JSON-kan (lihat ke_json)
        }

    @staticmethod
    def gambar(hasil: dict, warna_tiap: list[tuple[int, int, int]] | None = None,
               tampil_label: bool = True) -> np.ndarray:
        """Foto berbingkai. warna_tiap: warna BGR per wajah, mis. hijau (0,200,0) = dikenali,
        merah (0,0,230) = tidak dikenali (arahan bimbingan: cukup warna bingkai, tanpa tulisan 'unknown')."""
        boxes = [w["kotak"] for w in hasil["wajah"]]
        labels = [w["label"] for w in hasil["wajah"]]
        return gambar_kotak_wajah(hasil["citra_tampil"], boxes, labels, warna=WARNA_BINGKAI,
                                  warna_tiap=warna_tiap, tampil_label=tampil_label)

    @staticmethod
    def potong_wajah(img_bgr_asli: np.ndarray, hasil: dict, margin: float = 0.15) -> list[np.ndarray]:
        """Potongan tiap wajah dari FOTO ASLI (resolusi penuh) untuk dikirim ke recognition (Vikry)."""
        h, w = img_bgr_asli.shape[:2]
        crops = []
        for wj in hasil["wajah"]:
            x1, y1, x2, y2 = wj["kotak_asli"]
            m = int(margin * max(x2 - x1, y2 - y1))
            crops.append(img_bgr_asli[max(0, y1 - m):min(h, y2 + m), max(0, x1 - m):min(w, x2 + m)].copy())
        return crops

    @staticmethod
    def ke_json(hasil: dict) -> dict:
        """Bagian hasil yang aman dikirim sebagai JSON (tanpa array gambar)."""
        return {k: v for k, v in hasil.items() if k != "citra_tampil"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Coba deteksi wajah pada foto/folder foto.")
    ap.add_argument("--gambar", required=True, help="file foto atau folder")
    ap.add_argument("--keluaran", default="hasil_deteksi")
    ap.add_argument("--onnx", action="store_true", help="pakai deteksi_wajah.onnx (onnxruntime)")
    ap.add_argument("--ambang", type=float, default=None, help=f"ambang keyakinan (default {AMBANG})")
    a = ap.parse_args()
    det = DetektorWajah(onnx=a.onnx, ambang=a.ambang)
    src, out = Path(a.gambar), Path(a.keluaran)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}) if src.is_dir() else [src]
    semua = {}
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            print(f"{f.name}: tidak terbaca")
            continue
        h = det.deteksi(img)
        cv2.imwrite(str(out / f"{f.stem}_berbingkai.jpg"), det.gambar(h), [cv2.IMWRITE_JPEG_QUALITY, 90])
        semua[f.name] = det.ke_json(h)
        print(f"{f.name}: {h['jumlah_wajah']} wajah ({h['waktu_ms']:.0f} ms)")
    (out / "hasil.json").write_text(json.dumps(semua, indent=2), encoding="utf-8")
    print(f"Selesai ({det.format}, ambang {det.ambang}) -> {out}")
