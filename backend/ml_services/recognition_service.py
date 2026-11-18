"""AdaFace IR-50 (WebFace4M) Face Recognition Service - ONNX Runtime.

Sesuai spesifikasi `adaface_ir50_webface4m.onnx.txt`:
- INPUT  'input'     float32 [N, 3, 112, 112] NCHW
         wajah ter-align 112x112 (template 5 titik ArcFace, align.py), kanal BGR (bukan RGB!)
         nilai = (piksel / 255.0 - 0.5) / 0.5
- OUTPUT 'embedding' float32 [N, 512] sudah dinormalisasi L2
         'norm'      float32 [N, 1]   norma fitur (kualitas wajah), opsional
- Flip TTA:
         emb = embedding(wajah) + embedding(flip horizontal wajah); emb = emb / ||emb||
"""
import os
from pathlib import Path
import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WEIGHTS_PATH = BASE_DIR / "models" / "adaface_ir50_webface4m.onnx"


class AdaFaceExtractor:
    """AdaFace IR-50 (WebFace4M) feature extractor menggunakan ONNX Runtime."""

    def __init__(self, weights_path=None):
        if weights_path is None:
            weights_path = DEFAULT_WEIGHTS_PATH

        model_path = Path(weights_path)
        if not model_path.exists():
            raise FileNotFoundError(f"File model AdaFace tidak ditemukan di {model_path}")

        print(f"[+] Memuat model pengenal wajah AdaFace IR-50 ONNX ({model_path.name})...")
        self.ort_sess = None
        self.input_name = "input"
        self.output_names = None
        try:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.log_severity_level = 3
            self.ort_sess = ort.InferenceSession(
                str(model_path), sess_options=so, providers=["CPUExecutionProvider"]
            )
            self.input_name = self.ort_sess.get_inputs()[0].name
            self.output_names = [o.name for o in self.ort_sess.get_outputs()]
        except Exception as e:
            print(f"[!] ONNXRuntime tidak tersedia atau gagal: {e}, fallback ke cv2.dnn")
            self.net = cv2.dnn.readNetFromONNX(str(model_path))

    def _preprocess_bgr(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Siapkan tensor NCHW [1, 3, 112, 112] kanal BGR (BUKAN RGB!) dengan (px/255 - 0.5)/0.5."""
        if crop_bgr.shape[:2] != (112, 112):
            face_bgr = cv2.resize(crop_bgr, (112, 112), interpolation=cv2.INTER_LINEAR)
        else:
            face_bgr = crop_bgr
        # Kanal BGR (bukan RGB!) sesuai spesifikasi AdaFace IR-50 WebFace4M
        x = ((face_bgr.astype(np.float32) / 255.0) - 0.5) / 0.5
        return x.transpose(2, 0, 1)[None, ...].astype(np.float32)

    def extract_with_norm(self, crop_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        """Mengekstrak (embedding 512-D L2-normalized dengan Flip TTA, feature_norm)."""
        if crop_bgr is None or crop_bgr.size == 0 or crop_bgr.shape[0] < 5 or crop_bgr.shape[1] < 5:
            return np.zeros(512, dtype=np.float32), 0.0

        feat_norm = 0.0
        if self.ort_sess is not None:
            blob = self._preprocess_bgr(crop_bgr)
            blob_flip = blob[:, :, :, ::-1].copy()
            # Jalankan batch [2, 3, 112, 112] (asli + flip horizontal)
            batch = np.concatenate([blob, blob_flip], axis=0)
            outputs = self.ort_sess.run(None, {self.input_name: batch})
            embs = outputs[0]  # [2, 512]
            if len(outputs) > 1 and outputs[1] is not None:
                feat_norm = float(np.mean(outputs[1]))
            feat = (embs[0] + embs[1]).flatten().astype(np.float32)
        else:
            # Fallback cv2.dnn: swapRB=False karena AdaFace memakai BGR
            blob = cv2.dnn.blobFromImage(
                crop_bgr,
                scalefactor=1.0 / 127.5,
                size=(112, 112),
                mean=(127.5, 127.5, 127.5),
                swapRB=False,
            )
            self.net.setInput(blob)
            emb = self.net.forward().flatten().astype(np.float32)
            blob_flip = blob[:, :, :, ::-1].copy()
            self.net.setInput(blob_flip)
            emb_flip = self.net.forward().flatten().astype(np.float32)
            feat = (emb + emb_flip).astype(np.float32)

        norm = float(np.linalg.norm(feat))
        if norm > 1e-6:
            feat = feat / norm
        return feat, feat_norm

    def extract(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Mengekstrak embedding vektor 512-dimensi ternormalisasi L2 dari wajah BGR 112x112."""
        feat, _ = self.extract_with_norm(crop_bgr)
        return feat


# Alias backward-compatible
ArcFaceExtractor = AdaFaceExtractor


def load_adaface_extractor(weights_path=None) -> AdaFaceExtractor:
    return AdaFaceExtractor(weights_path)


load_arcface_extractor = load_adaface_extractor

print("[*] Memuat model ekstraksi fitur AdaFace IR-50 ONNX...")
model_recognizer = load_adaface_extractor()


def extract_embedding(crop_bgr: np.ndarray) -> np.ndarray:
    """Mengekstrak embedding vektor 512-dimensi ternormalisasi L2 (AdaFace IR-50 + Flip TTA)."""
    return model_recognizer.extract(crop_bgr)


def extract_embedding_with_norm(crop_bgr: np.ndarray) -> tuple[np.ndarray, float]:
    """Mengekstrak (embedding 512-D L2-normalized, feature_norm)."""
    return model_recognizer.extract_with_norm(crop_bgr)


def build_gallery_database(reference_dir="dataset/reference", detector=None):
    gallery_db = {}
    if not os.path.exists(reference_dir):
        os.makedirs(reference_dir, exist_ok=True)
        return gallery_db

    for identity_name in os.listdir(reference_dir):
        person_dir = os.path.join(reference_dir, identity_name)
        if not os.path.isdir(person_dir):
            continue

        embeddings_list = []
        for file_name in os.listdir(person_dir):
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                img_path = os.path.join(person_dir, file_name)
                img = cv2.imread(img_path)
                if img is None or img.size == 0:
                    continue

                face_crop = img
                if detector is not None and callable(detector):
                    results = detector(img, conf=0.4639, verbose=False)
                    crops_found = []
                    for r in results:
                        for box in r.boxes.xyxy.cpu().numpy():
                            x1, y1, x2, y2 = map(int, box)
                            w, h = x2 - x1, y2 - y1
                            if w > 14 and h > 14:
                                crop_area = img[max(0, y1):min(img.shape[0], y2), max(0, x1):min(img.shape[1], x2)]
                                if crop_area.size > 0:
                                    crops_found.append((crop_area, w * h))
                    if crops_found:
                        crops_found.sort(key=lambda x: x[1], reverse=True)
                        face_crop = crops_found[0][0]

                if face_crop.size > 0:
                    embeddings_list.append(extract_embedding(face_crop))

        if len(embeddings_list) > 0:
            centroid = np.mean(embeddings_list, axis=0)
            norm = np.linalg.norm(centroid)
            gallery_db[identity_name] = centroid / (norm + 1e-6)

    print(f"[+] Gallery DB siap. Terdaftar {len(gallery_db)} identitas: {list(gallery_db.keys())}")
    return gallery_db
