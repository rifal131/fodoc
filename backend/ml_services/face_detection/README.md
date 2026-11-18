# Model deteksi wajah untuk aplikasi web (Rifal)

Dibuat 17-11-2026 dari hasil akhir eksperimen perbandingan YOLOv11 vs S3FD-VGG16 (bagian deteksi: Harari).
Isinya model deteksi terbaik **plus kode tampilan bingkai** sesuai arahan Pak Ilham, supaya aplikasi web
menampilkan hasil yang sama persis dengan aplikasi deteksi.

## Isi

| Berkas | Keterangan |
|---|---|
| `deteksi_wajah.pt` | **model deteksi wajah terbaik**: YOLOv11n-face, fine-tune pada DARK FACE + Dataset Kampus + WIDER FACE (data asli, skenario S3). Sama persis dengan model di paket Vikry |
| `deteksi_wajah.onnx` | model yang sama dalam format ONNX (tanpa PyTorch; lebih ringan untuk server) |
| `deteksi_wajah.py` | **pakai ini**: kelas `DetektorWajah` - deteksi, saringan, urutan P1..PN, bingkai, potongan wajah |
| `anotasi.py` | kode gambar bingkai: garis tipis tepat di wajah + label "P1, P2, ..." kecil |
| `saringan.py` | membuang kotak yang berada di dalam kotak lain (satu wajah terbingkai dua kali) |
| `info_model.json` | ambang, setelan, dan kinerja model (dibaca otomatis oleh `deteksi_wajah.py`) |

Kelima berkas harus tetap dalam **satu folder**: `deteksi_wajah.py` memanggil `anotasi.py`, `saringan.py`,
`info_model.json`, dan berkas model dari folder yang sama.

## Pustaka

    pip install opencv-python numpy pillow
    pip install onnxruntime            # bila memakai deteksi_wajah.onnx (disarankan untuk server)
    pip install ultralytics            # bila memakai deteksi_wajah.pt (ikut memasang PyTorch, besar)

`pillow` dipakai untuk huruf label yang rapi; tanpa pillow label tetap tergambar dengan huruf bawaan OpenCV.

## Mencoba dari baris perintah

Dari dalam folder ini:

    python deteksi_wajah.py --gambar foto.jpg --onnx
    python deteksi_wajah.py --gambar folder_foto --keluaran hasil_deteksi

Hasilnya `namafoto_berbingkai.jpg` dan `hasil.json` di folder keluaran.

## Memakai di aplikasi web

Muat model **sekali** saat server mulai, jangan di setiap permintaan. Contoh FastAPI:

```python
import sys
sys.path.insert(0, "path/ke/model_deteksi_untuk_rifal")   # folder paket ini

import cv2, numpy as np, base64
from fastapi import FastAPI, UploadFile
from deteksi_wajah import DetektorWajah

app = FastAPI()
det = DetektorWajah(onnx=True)          # sekali saja

@app.post("/deteksi")
async def deteksi(file: UploadFile):
    img = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "berkas bukan gambar"}
    hasil = det.deteksi(img)
    ok, jpg = cv2.imencode(".jpg", det.gambar(hasil), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return {**det.ke_json(hasil), "gambar_jpg_base64": base64.b64encode(jpg).decode()}
```

Pola yang sama berlaku untuk Flask/Django: `cv2.imdecode` dari bytes unggahan -> `det.deteksi` ->
`det.gambar` -> `cv2.imencode`.

### Isi hasil `det.deteksi(img)`

```json
{
  "jumlah_wajah": 3,
  "wajah": [
    {"label": "P1", "confidence": 0.9338, "kotak": [190, 540, 251, 617],
     "kotak_asli": [1013, 2880, 1339, 3291], "sisi_wajah_px": 326, "layak_recognition": true}
  ],
  "ambang": 0.4639,
  "saringan": {"masuk": 3, "terlalu_kecil": 0, "bentuk_tidak_wajar": 0, "di_dalam_kotak_lain": 0, "lolos": 3},
  "waktu_ms": 245.0
}
```

- `label`: P1, P2, ... diurutkan **kiri ke kanan**. Hanya nomor urut di dalam satu foto, **bukan identitas**
  orang; siapa orangnya ditentukan modul recognition (Vikry).
- `kotak`: koordinat pada citra tampil (foto yang sudah diperkecil, sisi terpanjang maks 1600 px; inilah
  citra yang digambar `det.gambar`). `kotak_asli`: koordinat pada foto asli resolusi penuh.
- `layak_recognition`: `false` bila sisi wajah pada foto asli < 112 px (terlalu kecil untuk recognition).
- `det.ke_json(hasil)` membuang array gambar supaya hasil bisa langsung dikirim sebagai JSON.

### Menyambung ke recognition (Vikry)

```python
potongan = det.potong_wajah(img, hasil)     # list gambar wajah dari FOTO ASLI, urutan sama dengan P1..PN
```

Setelah recognition, beri warna bingkai per wajah (arahan bimbingan: cukup warna bingkai, tanpa tulisan
"unknown"):

```python
HIJAU, MERAH = (0, 200, 0), (0, 0, 230)    # BGR
warna = [HIJAU if dikenali else MERAH for dikenali in hasil_recognition]
gambar = det.gambar(hasil, warna_tiap=warna)
gambar_tanpa_label = det.gambar(hasil, tampil_label=False)   # bingkai saja, tanpa "P1"
```

## Tampilan bingkai (arahan Pak Ilham)

- Bingkai = kotak dari model apa adanya, **tepat di wajah**, garis tipis (1 px untuk wajah kecil, 2 px
  untuk wajah besar).
- Label hanya **"P1", "P2", ...** berupa tab kecil (huruf 6-11 px) di pojok kiri-atas. Pada wajah kecil
  (foto rombongan) tab dipindah ke atas bingkai supaya tidak menutupi wajah.
- **Hanya wajah yang dibingkai**: dijaga oleh ambang aplikasi (0,464) dan saringan kotak-di-dalam-kotak.
- Gambarlah pada citra tampil (yang dikembalikan `det.deteksi`), bukan pada foto resolusi penuh yang
  nanti diperkecil browser; kalau tidak, label ikut mengecil sampai tidak terbaca. Jangan mengubah
  ukuran label/bingkai di `anotasi.py` tanpa persetujuan Harari, karena tampilannya sudah disetujui
  pembimbing.

## Setelan (jangan diubah tanpa alasan)

| Setelan | Nilai | Dasar |
|---|---|---|
| Ukuran input model | 1088 | terbaik pada tuning (data validasi) |
| Ambang keyakinan | 0,464 | ambang terendah dengan precision >= 0,95 pada data validasi |
| NMS IoU | 0,5 | terbaik pada tuning |
| Saringan | kotak >= 70% di dalam kotak lain dibuang | membuang bingkai ganda tanpa membuang wajah benar |
| Restorasi citra | tidak dipakai | model terbaik dilatih dan diuji pada citra asli |
| Foto diperkecil | sisi terpanjang maks 1600 px | sama dengan aplikasi deteksi |

Untuk menangkap lebih banyak wajah (dengan risiko lebih banyak bingkai salah), ambang bisa diturunkan:
`DetektorWajah(ambang=0.34)`.

## Kinerja (data uji, tidak pernah dipakai training)

| Data uji | Precision | Recall | F1 | Bingkai salah |
|---|---|---|---|---|
| Dataset Kampus (21 foto, 124 wajah), ambang 0,464 | 0,992 | 0,992 | 0,992 | 1 |
| Gabungan 3 dataset (98 foto, 524 wajah), ambang 0,464 | 0,948 | 0,725 | 0,822 | 21 |

Waktu deteksi sekitar 0,2-0,4 detik per foto di CPU laptop. Dibanding S3FD-VGG16 akurasinya setara
secara statistik, tetapi 14,8x lebih cepat dan berkasnya 5,5 MB dibanding 89,9 MB.

Format `.pt` dan `.onnx` sudah diuji memberi kotak yang sama dengan aplikasi deteksi Harari pada 8 foto
kampus, dan foto rombongan 47 wajah terdeteksi dengan label yang tetap kecil.
