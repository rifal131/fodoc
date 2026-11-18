---
title: FODOC Backend API
emoji: 📸
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# FODOC — Foto Dokumentasi Universitas Mercu Buana (Backend API)

Backend FastAPI + Deteksi Multi-Wajah (YOLOv11n-face ONNX) + Pengenalan Wajah (AdaFace IR-50 WebFace4M ONNX) + MongoDB Atlas.

## Environment Variables / Secrets (di Hugging Face Space Settings)
- `MONGO_URL`: connection string MongoDB Atlas (`mongodb+srv://...`)
- `DB_NAME`: `fodoc_db`
- `JWT_SECRET`: string acak panjang (rahasia)
- `ADMIN_EMAIL`: `admin@fodoc.ac.id`
- `ADMIN_PASSWORD`: `Admin@123` (atau sandi baru Anda)
- `STORAGE_MODE`: `mongodb`
- `CORS_ORIGINS`: `https://<nama-project>.vercel.app` (atau `*`)
- Opsional SMTP Email OTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `ADMIN_NOTIFY_EMAIL`
