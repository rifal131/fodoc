"""FODOC - Face-based Object and Document Organizer for Campus (FastAPI Backend)."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import csv
import hashlib
import hmac
import io
import logging
import os
import secrets
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from auth import create_access_token, create_refresh_token, get_current_user, hash_password, require_role, verify_password
from ml_pipeline import (
    cosine_similarity,
    evaluate_face_matches,
    get_detector,
    get_landmark_model,
    process_event_photo,
    validate_enroll_pose,
)
from storage import APP_NAME, MIME, get_object, init_storage, put_object
from pddikti_service import (
    DEFAULT_PDDIKTI_SEED,
    REQUIRED_CAMPUS,
    STUDENT_EMAIL_DOMAIN,
    normalize_nim,
    normalize_text,
    validate_student_email,
    verify_student_pddikti,
)
from email_service import (
    send_otp_email,
    send_panitia_decision_email,
    send_panitia_request_email_to_admin,
)
import asyncio
import jwt as pyjwt
from fastapi import Query, Request
from auth import get_jwt_secret, JWT_ALGORITHM

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="FODOC API - Foto Dokumentasi")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fodoc")

# ------------------------------------------------- Konfigurasi Default Ambang Batas
DEFAULT_SETTINGS = {
    "ambang_cocok": 0.55,
    "ambang_perlu_cek": 0.40,
    "ambang_selisih": 0.10,
    "min_wajah_px": 28,
    "min_wajah_acuan_px": 60,
    "ambang_ketajaman": 15.0,
    "confidence_deteksi": 0.4639,
}


# ------------------------------------------------- Pydantic schemas
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    nim: Optional[str] = None
    role: str = Field(default="mahasiswa")  # mahasiswa | panitia | admin
    committee_reason: Optional[str] = None
    otp_code: Optional[str] = None


class SendOtpIn(BaseModel):
    email: EmailStr
    name: str
    nim: str


class PddiktiVerifyIn(BaseModel):
    nim: str
    name: str


class PddiktiStudentIn(BaseModel):
    nim: str
    nama: str
    kampus: str = Field(default=REQUIRED_CAMPUS)
    prodi: Optional[str] = ""
    status: Optional[str] = "Aktif"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EventIn(BaseModel):
    name: str
    description: Optional[str] = ""
    date: Optional[str] = None  # ISO date string
    location: Optional[str] = ""


class SettingsIn(BaseModel):
    ambang_cocok: float = Field(default=0.55, ge=0.0, le=1.0)
    ambang_perlu_cek: float = Field(default=0.40, ge=0.0, le=1.0)
    ambang_selisih: float = Field(default=0.10, ge=0.0, le=1.0)
    min_wajah_px: int = Field(default=28, ge=10, le=300)
    min_wajah_acuan_px: int = Field(default=60, ge=20, le=400)
    ambang_ketajaman: float = Field(default=15.0, ge=1.0, le=500.0)
    confidence_deteksi: float = Field(default=0.4639, ge=0.05, le=0.99)


class UserRoleIn(BaseModel):
    role: str


class FeedbackIn(BaseModel):
    photo_id: str
    face_id: Optional[str] = None
    reason: Optional[str] = "not_me"


# ------------------------------------------------- helpers
def _set_auth_cookies(resp: Response, access: str, refresh: str) -> None:
    resp.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=12 * 3600, path="/")
    resp.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=7 * 86400, path="/")


def _serialize_user(doc: dict) -> dict:
    embs = doc.get("face_embeddings") or []
    has_valid_enrollment = (len(embs) == 3)
    needs_re_enroll = doc.get("needs_re_enrollment", not has_valid_enrollment if doc.get("role") == "mahasiswa" and bool(doc.get("face_embedding")) else False)
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc.get("name", ""),
        "nim": doc.get("nim"),
        "role": doc.get("role", "mahasiswa"),
        "approval_status": doc.get("approval_status", "approved"),
        "organization": doc.get("organization") or (doc.get("nim") if doc.get("role") == "panitia" else None),
        "committee_reason": doc.get("committee_reason"),
        "kampus": doc.get("kampus"),
        "prodi": doc.get("prodi"),
        "pddikti_verified": bool(doc.get("pddikti_verified", False)),
        "has_enrollment": has_valid_enrollment,
        "needs_re_enrollment": bool(needs_re_enroll),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
    }


async def _get_all_settings() -> dict:
    current = dict(DEFAULT_SETTINGS)
    async for doc in db.settings.find({}):
        k = doc.get("key")
        if k in current:
            current[k] = doc.get("value")
    return current


async def _get_setting(key: str, default=None):
    doc = await db.settings.find_one({"key": key})
    return doc.get("value") if doc else default


async def _set_setting(key: str, value):
    await db.settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def _load_enrolled_students() -> list[dict[str, Any]]:
    enrolled = []
    async for u in db.users.find({"role": "mahasiswa", "face_embeddings": {"$exists": True, "$ne": None}}):
        embs = u.get("face_embeddings") or []
        if len(embs) == 3:
            enrolled.append({
                "id": str(u["_id"]),
                "name": u.get("name", ""),
                "nim": u.get("nim", ""),
                "face_embeddings": embs,
            })
    return enrolled


async def _reprocess_decisions_logic() -> dict[str, Any]:
    """Menghitung ulang status dari skor/embedding yang tersimpan saat ambang diubah, tanpa ekstraksi ulang."""
    settings = await _get_all_settings()
    students = await _load_enrolled_students()

    photos = await db.photos.find({}).to_list(1000)
    photos_processed = 0
    total_cocok = 0
    total_perlu_cek = 0
    total_unknown = 0

    now = datetime.now(timezone.utc)

    for photo in photos:
        pid = photo["id"]
        eid = photo.get("event_id")
        faces = await db.faces.find({"photo_id": pid}).to_list(500)
        if not faces:
            continue

        # Evaluasi keputusan berlapis + aturan 1 identitas per foto
        evaluated = evaluate_face_matches(faces, students, settings)

        # Hapus match lama untuk foto ini
        await db.matches.delete_many({"photo_id": pid})

        photo_cocok_count = 0
        faces_summary = []

        for ef in evaluated:
            fid = ef["face_id"]
            status = ef["status"]
            if status == "COCOK":
                total_cocok += 1
                photo_cocok_count += 1
            elif status == "PERLU_CEK":
                total_perlu_cek += 1
            else:
                total_unknown += 1

            # Update dokumen face
            update_fields = {
                "status": status,
                "top1_user_id": ef.get("top1_user_id"),
                "top1_name": ef.get("top1_name"),
                "top1_score": ef.get("top1_score", 0.0),
                "top2_score": ef.get("top2_score", 0.0),
                "selisih": ef.get("selisih", 0.0),
                "min_side": ef.get("min_side"),
                "sharpness": ef.get("sharpness", 0.0),
                "data_leakage": ef.get("data_leakage", False),
            }
            if ef.get("landmarks"):
                update_fields["landmarks"] = ef["landmarks"]

            await db.faces.update_one({"face_id": fid}, {"$set": update_fields})

            # Simpan ke db.matches jika COCOK atau PERLU_CEK
            if status in ("COCOK", "PERLU_CEK") and ef.get("top1_user_id"):
                await db.matches.insert_one({
                    "user_id": ef["top1_user_id"],
                    "name": ef.get("top1_name"),
                    "face_id": fid,
                    "photo_id": pid,
                    "event_id": eid,
                    "similarity": ef.get("top1_score", 0.0),
                    "selisih": ef.get("selisih", 0.0),
                    "status": status,
                    "created_at": now,
                })

            crop_url = ef.get("crop_url") or (f"/api/files/{ef.get('crop_path')}" if ef.get("crop_path") else None)
            faces_summary.append({
                "face_id": fid,
                "box": ef["box"],
                "confidence": ef.get("confidence", 0.0),
                "crop_url": crop_url,
                "status": status,
                "top1_name": ef.get("top1_name"),
                "top1_score": ef.get("top1_score", 0.0),
            })

        await db.photos.update_one(
            {"id": pid},
            {"$set": {
                "match_count": photo_cocok_count,
                "faces": faces_summary,
            }},
        )
        photos_processed += 1

    return {
        "ok": True,
        "photos_processed": photos_processed,
        "total_cocok": total_cocok,
        "total_perlu_cek": total_perlu_cek,
        "total_unknown": total_unknown,
    }


# ------------------------------------------------- startup
@app.on_event("startup")
async def startup():
    # indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier", unique=True)
    await db.events.create_index("created_at")
    await db.photos.create_index("event_id")
    await db.photos.create_index("status")
    await db.matches.create_index("user_id")
    await db.matches.create_index("photo_id")
    await db.matches.create_index("status")
    await db.faces.create_index("photo_id")
    await db.faces.create_index("face_id", unique=True)
    await db.faces.create_index("status")
    await db.feedback.create_index("user_id")
    await db.feedback.create_index("photo_id")
    await db.notifications.create_index("user_id")
    await db.user_face_profiles.create_index([("user_id", 1), ("angle", 1)])
    await db.pddikti_students.create_index("nim", unique=True)
    await db.email_otps.create_index("email", unique=True)
    await db.email_otps.create_index("expires_at", expireAfterSeconds=0)

    # Seed data master PDDIKTI contoh Universitas Mercu Buana jika masih kosong
    if await db.pddikti_students.count_documents({}) == 0:
        now_seed = datetime.now(timezone.utc)
        for item in DEFAULT_PDDIKTI_SEED:
            await db.pddikti_students.update_one(
                {"nim": item["nim"]},
                {"$setOnInsert": {**item, "created_at": now_seed, "updated_at": now_seed}},
                upsert=True,
            )
        logger.info("Seeded %d default PDDIKTI student records (UMB)", len(DEFAULT_PDDIKTI_SEED))

    # Backfill panitia lama yang belum punya kolom approval_status menjadi approved
    await db.users.update_many(
        {"role": "panitia", "approval_status": {"$exists": False}},
        {"$set": {"approval_status": "approved"}},
    )

    # Seed Admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fodoc.ac.id")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "FODOC Admin",
            "role": "admin",
            "nim": None,
            "created_at": datetime.now(timezone.utc),
        })
        logger.info("Seeded admin user: %s", admin_email)
    else:
        if not verify_password(admin_password, existing["password_hash"]):
            await db.users.update_one({"_id": existing["_id"]}, {"$set": {"password_hash": hash_password(admin_password)}})

    # Inisialisasi Koleksi settings dengan Nilai Awal Standar
    for key, val in DEFAULT_SETTINGS.items():
        doc = await db.settings.find_one({"key": key})
        if doc is None:
            await db.settings.insert_one({
                "key": key,
                "value": val,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

    # Tandai akun mahasiswa lama yang tidak memiliki tepat 3 pose acuan
    async for u in db.users.find({"role": "mahasiswa"}):
        embs = u.get("face_embeddings") or []
        if len(embs) != 3:
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"needs_re_enrollment": True}})
        else:
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"needs_re_enrollment": False}})

    try:
        init_storage()
    except Exception as exc:
        logger.error("Storage init failed: %s", exc)

    # Pre-warm model deteksi & landmark di background thread agar verifikasi pertama tidak lambat/timeout
    def _warmup_models():
        try:
            get_detector()
            get_landmark_model()
            logger.info("ML detector & landmark models warmed up")
        except Exception as exc:
            logger.warning("ML warmup warning: %s", exc)

    import threading
    threading.Thread(target=_warmup_models, daemon=True).start()


from collections import OrderedDict

_THUMB_CACHE: OrderedDict[tuple[str, int], bytes] = OrderedDict()
_THUMB_CACHE_MAX = 256


def _make_thumbnail(data: bytes, max_w: int) -> bytes | None:
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((max_w, max_w), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=80, optimize=True)
            return out.getvalue()
    except Exception:
        return None


@api.get("/files/{path:path}")
async def serve_file(
    path: str,
    request: Request,
    auth: Optional[str] = Query(None),
    w: Optional[int] = Query(None, ge=64, le=1600),
):
    token = request.cookies.get("access_token") or auth
    hdr = request.headers.get("Authorization", "")
    if not token and hdr.startswith("Bearer "):
        token = hdr[7:]
    try:
        pyjwt.decode(token or "", get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    if w is not None:
        # Bulatkan lebar ke kelipatan 64px agar cache hit tinggi
        bucket_w = max(128, min(1280, ((w + 63) // 64) * 64))
        cache_key = (path, bucket_w)
        cached = _THUMB_CACHE.get(cache_key)
        if cached is not None:
            _THUMB_CACHE.move_to_end(cache_key)
            return Response(
                content=cached,
                media_type="image/jpeg",
                headers={"Cache-Control": "private, max-age=604800"},
            )
        data, ctype = await asyncio.to_thread(get_object, path)
        thumb = await asyncio.to_thread(_make_thumbnail, data, bucket_w)
        if thumb:
            _THUMB_CACHE[cache_key] = thumb
            if len(_THUMB_CACHE) > _THUMB_CACHE_MAX:
                _THUMB_CACHE.popitem(last=False)
            return Response(
                content=thumb,
                media_type="image/jpeg",
                headers={"Cache-Control": "private, max-age=604800"},
            )
        return Response(
            content=data,
            media_type=record.get("content_type", ctype),
            headers={"Cache-Control": "private, max-age=86400"},
        )

    data, ctype = await asyncio.to_thread(get_object, path)
    return Response(content=data, media_type=record.get("content_type", ctype),
                    headers={"Cache-Control": "private, max-age=86400"})


# ====================================================================
# AUTH & VERIFIKASI PDDIKTI + PERSETUJUAN PANITIA
# ====================================================================
@api.post("/pddikti/verify")
async def check_pddikti_student(payload: PddiktiVerifyIn):
    """Pengecekan awal NIM + Nama terhadap data PDDIKTI Universitas Mercu Buana (tanpa membocorkan daftar nama)."""
    nim = normalize_nim(payload.nim)
    res = await verify_student_pddikti(db, nim, payload.name)
    if not res["ok"]:
        return {"valid": False, "message": res["error"]}
    rec = res["record"]
    return {
        "valid": True,
        "message": f"Data mahasiswa terverifikasi ({rec['kampus']}).",
        "kampus": rec["kampus"],
        "prodi": rec.get("prodi") or "",
        "status": rec.get("status") or "Aktif",
        "expected_email": f"{nim}@{STUDENT_EMAIL_DOMAIN}",
    }


OTP_EXPIRE_MINUTES = 5
OTP_COOLDOWN_SECONDS = 45
OTP_MAX_ATTEMPTS = 5


def _hash_otp(email: str, otp_code: str) -> str:
    secret = get_jwt_secret()
    return hashlib.sha256(f"{email.lower()}:{otp_code}:{secret}".encode("utf-8")).hexdigest()


@api.post("/auth/send-otp")
async def send_register_otp(payload: SendOtpIn):
    """Kirim kode verifikasi OTP 6 digit ke email mahasiswa (<NIM>@student.mercubuana.ac.id)."""
    email = payload.email.lower().strip()
    name = payload.name.strip()
    nim = normalize_nim(payload.nim)

    ok_email, email_err = validate_student_email(email, nim)
    if not ok_email:
        raise HTTPException(status_code=400, detail=email_err)

    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    if await db.users.find_one({"role": "mahasiswa", "nim": nim}):
        raise HTTPException(status_code=400, detail=f"NIM {nim} sudah terdaftar pada akun lain.")

    pddikti_res = await verify_student_pddikti(db, nim, name)
    if not pddikti_res["ok"]:
        raise HTTPException(status_code=403, detail=pddikti_res["error"])

    now = datetime.now(timezone.utc)
    existing = await db.email_otps.find_one({"email": email})
    if existing and existing.get("sent_at"):
        sent_at = existing["sent_at"]
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        elapsed = (now - sent_at).total_seconds()
        if elapsed < OTP_COOLDOWN_SECONDS:
            wait_s = max(1, int(OTP_COOLDOWN_SECONDS - elapsed))
            raise HTTPException(
                status_code=429,
                detail=f"Tunggu {wait_s} detik sebelum mengirim ulang kode verifikasi.",
            )

    otp_code = f"{secrets.randbelow(1000000):06d}"
    otp_hash = _hash_otp(email, otp_code)
    expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)

    await db.email_otps.update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "nim": nim,
                "otp_hash": otp_hash,
                "attempts": 0,
                "sent_at": now,
                "expires_at": expires_at,
            }
        },
        upsert=True,
    )

    rec = pddikti_res["record"]
    try:
        mail_res = await asyncio.to_thread(send_otp_email, email, otp_code, rec["nama"], OTP_EXPIRE_MINUTES)
    except Exception as exc:
        await db.email_otps.delete_one({"email": email})
        logger.error("SMTP gagal kirim OTP ke %s: %s", email, exc)
        raise HTTPException(
            status_code=500,
            detail="Gagal mengirim email kode verifikasi. Periksa konfigurasi SMTP_USER/SMTP_PASS di backend/.env.",
        )

    if mail_res.get("dev_mode"):
        return {
            "ok": True,
            "sent_via_email": False,
            "dev_mode": True,
            "cooldown_seconds": OTP_COOLDOWN_SECONDS,
            "expires_minutes": OTP_EXPIRE_MINUTES,
            "message": (
                f"Mode uji coba (SMTP belum diisi di backend/.env): Kode OTP 6 digit untuk {email} "
                "telah dicetak di terminal server backend."
            ),
        }

    return {
        "ok": True,
        "sent_via_email": True,
        "dev_mode": False,
        "cooldown_seconds": OTP_COOLDOWN_SECONDS,
        "expires_minutes": OTP_EXPIRE_MINUTES,
        "message": f"Kode verifikasi 6 digit telah dikirim ke {email}. Cek kotak masuk atau folder Spam.",
    }


@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response, background_tasks: BackgroundTasks):
    email = payload.email.lower().strip()
    name = payload.name.strip()
    if payload.role not in ("mahasiswa", "panitia"):
        raise HTTPException(status_code=400, detail="Role tidak valid untuk pendaftaran mandiri")

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Nama lengkap wajib diisi")

    exists = await db.users.find_one({"email": email})
    if exists:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    now = datetime.now(timezone.utc)

    # ---------- PENDAFTARAN MAHASISWA: WAJIB <NIM>@student.mercubuana.ac.id + DATA MAHASISWA UMB + OTP EMAIL ----------
    if payload.role == "mahasiswa":
        nim = normalize_nim(payload.nim)
        ok_email, email_err = validate_student_email(email, nim)
        if not ok_email:
            raise HTTPException(status_code=400, detail=email_err)

        nim_exists = await db.users.find_one({"role": "mahasiswa", "nim": nim})
        if nim_exists:
            raise HTTPException(status_code=400, detail=f"NIM {nim} sudah terdaftar pada akun lain.")

        pddikti_res = await verify_student_pddikti(db, nim, name)
        if not pddikti_res["ok"]:
            raise HTTPException(status_code=403, detail=pddikti_res["error"])

        # Verifikasi kode OTP 6 digit dari email
        otp_input = (payload.otp_code or "").strip()
        if not otp_input or len(otp_input) != 6 or not otp_input.isdigit():
            raise HTTPException(
                status_code=400,
                detail="Masukkan kode verifikasi OTP 6 digit yang dikirim ke email Anda terlebih dahulu.",
            )

        otp_doc = await db.email_otps.find_one({"email": email})
        if not otp_doc:
            raise HTTPException(
                status_code=400,
                detail="Kode OTP belum dikirim atau sudah kedaluwarsa. Klik 'Kirim Kode OTP' terlebih dahulu.",
            )

        exp = otp_doc.get("expires_at")
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                await db.email_otps.delete_one({"email": email})
                raise HTTPException(status_code=400, detail="Kode OTP sudah kedaluwarsa. Silakan kirim ulang kode baru.")

        attempts = int(otp_doc.get("attempts", 0))
        if attempts >= OTP_MAX_ATTEMPTS:
            await db.email_otps.delete_one({"email": email})
            raise HTTPException(status_code=400, detail="Terlalu banyak percobaan OTP salah. Silakan minta kode OTP baru.")

        expected_hash = otp_doc.get("otp_hash", "")
        if not hmac.compare_digest(_hash_otp(email, otp_input), expected_hash):
            new_attempts = attempts + 1
            if new_attempts >= OTP_MAX_ATTEMPTS:
                await db.email_otps.delete_one({"email": email})
                raise HTTPException(status_code=400, detail="Kode OTP salah (batas percobaan habis). Silakan minta kode OTP baru.")
            await db.email_otps.update_one({"email": email}, {"$set": {"attempts": new_attempts}})
            raise HTTPException(
                status_code=400,
                detail=f"Kode OTP tidak sesuai. Sisa percobaan: {OTP_MAX_ATTEMPTS - new_attempts}.",
            )

        # OTP valid -> hapus OTP agar sekali pakai
        await db.email_otps.delete_one({"email": email})

        rec = pddikti_res["record"]
        doc = {
            "email": email,
            "password_hash": hash_password(payload.password),
            "name": rec["nama"],  # gunakan nama resmi dari data mahasiswa
            "nim": nim,
            "role": "mahasiswa",
            "approval_status": "approved",
            "pddikti_verified": True,
            "email_verified": True,
            "kampus": rec["kampus"],
            "prodi": rec.get("prodi") or "",
            "needs_re_enrollment": True,
            "created_at": now,
        }
        result = await db.users.insert_one(doc)
        user_id = str(result.inserted_id)
        access = create_access_token(user_id, email, "mahasiswa")
        refresh = create_refresh_token(user_id)
        _set_auth_cookies(response, access, refresh)
        doc["_id"] = result.inserted_id
        return {"user": _serialize_user(doc), "access_token": access}

    # ---------- PENDAFTARAN PANITIA: WAJIB PERSETUJUAN (ACC) ADMIN ----------
    organization = (payload.nim or "").strip()
    if len(organization) < 2:
        raise HTTPException(
            status_code=400,
            detail="Wajib mengisi nama Unit / Organisasi / Kepanitiaan Anda agar Admin dapat memverifikasi asal panitia.",
        )

    reason_text = (payload.committee_reason or "").strip()
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": name,
        "nim": organization,
        "organization": organization,
        "committee_reason": reason_text,
        "role": "panitia",
        "approval_status": "pending",
        "needs_re_enrollment": False,
        "created_at": now,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    background_tasks.add_task(send_panitia_request_email_to_admin, name, email, organization, reason_text)
    return {
        "pending_approval": True,
        "message": (
            "Permohonan akun Panitia berhasil dikirim! Menunggu persetujuan (ACC) dari Admin "
            "untuk memastikan keabsahan panitia sebelum Anda dapat masuk dan mengunggah foto."
        ),
        "user": _serialize_user(doc),
    }


MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    identifier = email
    now = datetime.now(timezone.utc)
    try:
        await db.login_attempts.update_one({"identifier": identifier},
                                           {"$setOnInsert": {"count": 0, "locked_until": None}}, upsert=True)
    except DuplicateKeyError:
        pass

    await db.login_attempts.update_one({"identifier": identifier, "locked_until": {"$lte": now}},
                                       {"$set": {"locked_until": None, "count": 0}})

    slot = await db.login_attempts.find_one_and_update(
        {"identifier": identifier, "locked_until": None, "count": {"$lt": MAX_LOGIN_ATTEMPTS}},
        {"$inc": {"count": 1}, "$set": {"last_attempt": now}}, return_document=ReturnDocument.AFTER)
    if slot is None:
        doc = await db.login_attempts.find_one({"identifier": identifier})
        until = doc.get("locked_until") if doc else None
        mins = max(1, int((until.replace(tzinfo=timezone.utc) - now).total_seconds() // 60) + 1) if until else LOCKOUT_MINUTES
        raise HTTPException(status_code=429, detail=f"Akun dikunci sementara karena terlalu banyak percobaan gagal. Coba lagi dalam {mins} menit.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        count = slot["count"]
        if count >= MAX_LOGIN_ATTEMPTS:
            await db.login_attempts.update_one(
                {"identifier": identifier, "locked_until": None},
                {"$set": {"locked_until": now + timedelta(minutes=LOCKOUT_MINUTES)}})
            raise HTTPException(status_code=429, detail=f"Terlalu banyak percobaan gagal. Akun dikunci selama {LOCKOUT_MINUTES} menit.")
        raise HTTPException(status_code=401, detail=f"Email atau password salah. Sisa percobaan: {MAX_LOGIN_ATTEMPTS - count}")

    role = user.get("role", "mahasiswa")

    # Cek persetujuan Admin untuk Panitia
    if role == "panitia":
        approval = user.get("approval_status", "approved")
        if approval == "pending":
            raise HTTPException(
                status_code=403,
                detail="Akun Panitia Anda sedang menunggu persetujuan (ACC) dari Admin. Silakan coba masuk kembali setelah disetujui.",
            )
        if approval == "rejected":
            raise HTTPException(
                status_code=403,
                detail="Permohonan akun Panitia Anda ditolak oleh Admin. Hubungi Admin jika ini keliru.",
            )

    # Cek validitas email <NIM>@student.mercubuana.ac.id & PDDIKTI UMB untuk Mahasiswa
    if role == "mahasiswa":
        ok_email, email_err = validate_student_email(email, user.get("nim"))
        if not ok_email:
            raise HTTPException(status_code=403, detail=email_err)
        pddikti_res = await verify_student_pddikti(db, user.get("nim"), user.get("name"))
        if not pddikti_res["ok"]:
            raise HTTPException(status_code=403, detail=pddikti_res["error"])

    await db.login_attempts.update_one({"identifier": identifier, "locked_until": None}, {"$set": {"count": 0}})
    access = create_access_token(str(user["_id"]), email, role)
    refresh = create_refresh_token(str(user["_id"]))
    _set_auth_cookies(response, access, refresh)
    return {"user": _serialize_user(user), "access_token": access}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return _serialize_user(doc)


# ====================================================================
# FACE ENROLLMENT (Arahan Dosen: Kamera Langsung Wajib 3 Pose)
# ====================================================================
ANGLES = (("front", "Tampak Depan"), ("right", "Menoleh ke Kanan"), ("left", "Menoleh ke Kiri"))


@api.post("/auth/enroll-face")
async def enroll_face(
    background_tasks: BackgroundTasks,
    front: Optional[UploadFile] = File(None),
    right: Optional[UploadFile] = File(None),
    left: Optional[UploadFile] = File(None),
    user: dict = Depends(require_role("mahasiswa")),
):
    """Perekaman/unggah 3 pose wajah terstandar (Depan, Kanan, Kiri) mahasiswa.

    Setiap pose diperiksa ketat di backend:
    - 3 berkas berbeda (anti-duplikat hash & embedding)
    - tepat 1 wajah terdeteksi
    - sisi wajah >= min_wajah_acuan_px (60 px)
    - kecerahan tidak gelap (L* >= 0.30)
    - ketajaman Laplacian memenuhi ambang (>= 15)
    - 5 landmark terdeteksi, arah hadap wajah (yaw) WAJIB sesuai perintah slot (Depan / Kanan / Kiri)
    - konsistensi identitas lintas 3 pose (orang yang sama).
    """
    settings = await _get_all_settings()
    min_size = int(settings.get("min_wajah_acuan_px", 60))
    min_sharpness = float(settings.get("ambang_ketajaman", 15.0))
    conf_detect = float(settings.get("confidence_deteksi", 0.4639))

    uploads = {"front": front, "right": right, "left": left}
    label_map = dict(ANGLES)
    missing = [label for angle, label in ANGLES if not uploads.get(angle)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Wajib melengkapi tepat 3 pose (Tampak Depan, Menoleh ke Kanan, dan Menoleh ke Kiri). Pose belum lengkap: {', '.join(missing)}.",
        )

    # 1. Baca seluruh berkas & deteksi duplikat identik (jangan berhenti di slot ke-2 agar semua slot salah terdeteksi)
    raw_bytes: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for angle, label in ANGLES:
        content = await uploads[angle].read()
        if not content:
            raise HTTPException(status_code=400, detail=f"[{label}] Data foto kosong. Silakan pilih atau ambil ulang.")
        raw_bytes[angle] = content
        hashes[angle] = hashlib.sha256(content).hexdigest()

    duplicate_errors: dict[str, str] = {}
    if hashes["right"] == hashes["front"]:
        duplicate_errors["right"] = (
            "[Menoleh ke Kanan] Foto identik dengan foto Depan. Wajib unggah foto berbeda yang menoleh ke KANAN."
        )
    if hashes["left"] == hashes["front"]:
        duplicate_errors["left"] = (
            "[Menoleh ke Kiri] Foto identik dengan foto Depan. Wajib unggah foto berbeda yang menoleh ke KIRI."
        )
    elif hashes["left"] == hashes["right"]:
        duplicate_errors["left"] = (
            "[Menoleh ke Kiri] Foto identik dengan foto Kanan. Wajib unggah foto berbeda yang menoleh ke KIRI."
        )

    # 2. Validasi kualitas + arah hadap pose (front / right / left) pada tiap slot
    validated = []
    pose_errors: list[str] = []
    for angle, label in ANGLES:
        if angle in duplicate_errors:
            pose_errors.append(duplicate_errors[angle])
            continue

        content = raw_bytes[angle]
        result = await asyncio.to_thread(
            validate_enroll_pose,
            content,
            min_size_px=min_size,
            min_l_brightness=0.30,
            min_sharpness=min_sharpness,
            conf_detect=conf_detect,
            expected_angle=angle,
        )
        if not result["ok"]:
            pose_errors.append(f"[{label}] {result['error']}")
        else:
            validated.append((angle, content, result))

    if pose_errors:
        if len(pose_errors) == 1:
            raise HTTPException(status_code=400, detail=pose_errors[0])
        raise HTTPException(
            status_code=400,
            detail=f"Verifikasi gagal pada {len(pose_errors)} pose: " + " | ".join(pose_errors),
        )

    # 3. Validasi silang lintas-pose: pastikan kanan vs kiri benar-benar berlawanan, bukan foto nyaris sama, dan orang yang sama
    res_by_angle = {angle: res for angle, _, res in validated}
    yaw_right = float(res_by_angle["right"].get("yaw_ratio", 0.5))
    yaw_left = float(res_by_angle["left"].get("yaw_ratio", 0.5))

    if (yaw_left - yaw_right) < 0.26:
        raise HTTPException(
            status_code=400,
            detail="[Menoleh ke Kanan] [Menoleh ke Kiri] Arah menoleh pada foto Kanan dan Kiri kurang berbeda. Pastikan satu foto jelas menoleh ke kanan dan satu lagi jelas menoleh ke kiri.",
        )

    pairs = (("front", "right"), ("front", "left"), ("right", "left"))
    for a, b in pairs:
        sim = cosine_similarity(res_by_angle[a]["embedding"], res_by_angle[b]["embedding"])
        yaw_diff = abs(float(res_by_angle[a].get("yaw_ratio", 0.5)) - float(res_by_angle[b].get("yaw_ratio", 0.5)))
        if sim >= 0.96 and yaw_diff < 0.12:
            raise HTTPException(
                status_code=400,
                detail=f"[{label_map[b]}] Foto terdeteksi hampir identik dengan pose {label_map[a]}. Wajib menggunakan 3 foto dengan arah pose berbeda.",
            )
        if a == "front" and sim < 0.22:
            raise HTTPException(
                status_code=400,
                detail=f"[{label_map[b]}] Wajah tidak tampak seperti orang yang sama dengan foto Depan. Pastikan ketiga foto adalah wajah Anda sendiri.",
            )

    now = datetime.now(timezone.utc)
    await db.user_face_profiles.delete_many({"user_id": user["id"]})
    profiles_out = []

    for angle, content, result in validated:
        orig_ct = (uploads[angle].content_type or "image/jpeg").lower()
        if orig_ct not in ("image/jpeg", "image/png", "image/webp"):
            orig_ct = "image/jpeg"
        ext = ".png" if orig_ct == "image/png" else (".webp" if orig_ct == "image/webp" else ".jpg")
        stored = await asyncio.to_thread(
            put_object, f"{APP_NAME}/enrollments/{user['id']}/{angle}_{uuid.uuid4()}{ext}", content, orig_ct
        )
        path = stored["path"]
        await db.files.insert_one({
            "storage_path": path, "content_type": orig_ct, "is_deleted": False, "created_at": now
        })
        await db.user_face_profiles.insert_one({
            "user_id": user["id"],
            "angle": angle,
            "embedding": result["embedding"],
            "storage_path": path,
            "confidence": result["confidence"],
            "face_box": result["face_box"],
            "sharpness": result.get("sharpness"),
            "brightness_l": result.get("brightness_l"),
            "yaw_ratio": result.get("yaw_ratio"),
            "landmarks": result.get("landmarks"),
            "created_at": now,
        })
        profiles_out.append({"angle": angle, "confidence": result["confidence"], "image_url": f"/api/files/{path}"})

    import numpy as np
    embeddings = [r["embedding"] for _, _, r in validated]
    centroid_arr = np.mean(np.asarray(embeddings, dtype=np.float32), axis=0)
    c_norm = float(np.linalg.norm(centroid_arr))
    centroid_embedding = (centroid_arr / c_norm).tolist() if c_norm > 1e-6 else embeddings[0]

    await db.users.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {
            "face_embedding": centroid_embedding,
            "face_embeddings": embeddings,
            "reference_image": profiles_out[0]["image_url"][len("/api/files/"):],
            "needs_re_enrollment": False,
            "enrolled_at": now,
        }},
    )

    # Sinkronisasi retroaktif keputusan di background agar respons verifikasi langsung cepat (hindari 504 timeout)
    background_tasks.add_task(_reprocess_decisions_logic)

    return {
        "ok": True,
        "message": "Perekaman 3 pose biometrik wajah terstandar berhasil diselesaikan.",
        "profiles": profiles_out,
    }


@api.get("/enrollment/status")
async def enrollment_status(user: dict = Depends(get_current_user)):
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    profiles = []
    async for p in db.user_face_profiles.find({"user_id": user["id"]}):
        profiles.append({
            "angle": p["angle"],
            "confidence": p.get("confidence"),
            "image_url": f"/api/files/{p['storage_path']}",
        })
    embs = doc.get("face_embeddings") or []
    has_valid_3 = (len(embs) == 3)
    needs_re_enroll = doc.get("needs_re_enrollment", not has_valid_3 if doc.get("role") == "mahasiswa" else False)

    return {
        "enrolled": has_valid_3,
        "needs_re_enrollment": bool(needs_re_enroll),
        "profiles": profiles,
        "reference_url": f"/api/files/{doc['reference_image']}" if doc.get("reference_image") else None,
        "enrolled_at": doc.get("enrolled_at").isoformat() if isinstance(doc.get("enrolled_at"), datetime) else doc.get("enrolled_at"),
    }


# ====================================================================
# EVENTS (panitia + admin)
# ====================================================================
@api.post("/events")
async def create_event(payload: EventIn, user: dict = Depends(require_role("panitia", "admin"))):
    doc = {
        "name": payload.name.strip(),
        "description": payload.description or "",
        "date": payload.date,
        "location": payload.location or "",
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_at": datetime.now(timezone.utc),
        "photo_count": 0,
    }
    result = await db.events.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


@api.get("/events")
async def list_events(user: dict = Depends(get_current_user)):
    cursor = db.events.find({}).sort("created_at", -1)
    events = []
    async for e in cursor:
        events.append({
            "id": str(e["_id"]),
            "name": e.get("name", ""),
            "description": e.get("description", ""),
            "date": e.get("date"),
            "location": e.get("location", ""),
            "created_by_name": e.get("created_by_name", ""),
            "photo_count": e.get("photo_count", 0),
            "created_at": e["created_at"].isoformat() if isinstance(e.get("created_at"), datetime) else e.get("created_at"),
        })
    return events


@api.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(get_current_user)):
    try:
        e = await db.events.find_one({"_id": ObjectId(event_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid event id")
    if not e:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")
    return {
        "id": str(e["_id"]),
        "name": e.get("name", ""),
        "description": e.get("description", ""),
        "date": e.get("date"),
        "location": e.get("location", ""),
        "created_by_name": e.get("created_by_name", ""),
        "photo_count": e.get("photo_count", 0),
    }


@api.delete("/events/{event_id}")
async def delete_event(event_id: str, user: dict = Depends(require_role("admin"))):
    await db.events.delete_one({"_id": ObjectId(event_id)})
    photos = db.photos.find({"event_id": event_id})
    async for p in photos:
        await db.faces.delete_many({"photo_id": p["id"]})
        await db.matches.delete_many({"photo_id": p["id"]})
        await db.notifications.delete_many({"photo_id": p["id"]})
        await db.feedback.delete_many({"photo_id": p["id"]})
    await db.photos.delete_many({"event_id": event_id})
    return {"ok": True}


# ====================================================================
# PHOTO UPLOAD + BACKGROUND PIPELINE
# ====================================================================
async def _process_photo_task(photo_id: str, image_bytes: bytes, event_id: str):
    """Background task pemrosesan foto acara sekuensial sesuai modul tim."""
    try:
        await db.photos.update_one({"id": photo_id}, {"$set": {"status": "processing"}})

        settings = await _get_all_settings()
        conf_det = float(settings.get("confidence_deteksi", 0.4639))

        # Tahap 1, 2, 3, 4
        result = await asyncio.to_thread(process_event_photo, image_bytes, conf_detect=conf_det, imgsz=1088)
        if not result["ok"]:
            await db.photos.update_one({"id": photo_id}, {"$set": {"status": "failed", "error": result.get("error")}})
            return

        # Simpan crop wajah ke storage & DB
        now = datetime.now(timezone.utc)
        stored_faces = []
        for face in result["faces"]:
            crop_path = None
            if face.get("crop_bytes"):
                stored = await asyncio.to_thread(
                    put_object, f"{APP_NAME}/faces/{event_id}/{face['face_id']}.jpg", face["crop_bytes"], "image/jpeg"
                )
                crop_path = stored["path"]
                await db.files.insert_one({
                    "storage_path": crop_path, "content_type": "image/jpeg", "is_deleted": False, "created_at": now
                })

            face_doc = {
                "face_id": face["face_id"],
                "photo_id": photo_id,
                "event_id": event_id,
                "label": face["label"],
                "box": face["box"],
                "confidence": face["confidence"],
                "width": face["width"],
                "height": face["height"],
                "min_side": face["min_side"],
                "sharpness": face["sharpness"],
                "landmarks": face["landmarks"],
                "crop_path": crop_path,
                "embedding": face["embedding"],
                "status": "UNKNOWN",
                "created_at": now,
            }
            await db.faces.insert_one(face_doc)
            stored_faces.append(face_doc)

        # Tahap 5 & 6: Evaluasi Keputusan Berlapis
        students = await _load_enrolled_students()
        evaluated = evaluate_face_matches(stored_faces, students, settings)

        total_cocok = 0
        faces_summary = []
        matched_user_ids: set[str] = set()

        for ef in evaluated:
            fid = ef["face_id"]
            status = ef["status"]
            if status == "COCOK":
                total_cocok += 1
                if ef.get("top1_user_id"):
                    matched_user_ids.add(ef["top1_user_id"])

            update_fields = {
                "status": status,
                "top1_user_id": ef.get("top1_user_id"),
                "top1_name": ef.get("top1_name"),
                "top1_score": ef.get("top1_score", 0.0),
                "top2_score": ef.get("top2_score", 0.0),
                "selisih": ef.get("selisih", 0.0),
                "data_leakage": ef.get("data_leakage", False),
            }
            await db.faces.update_one({"face_id": fid}, {"$set": update_fields})

            if status in ("COCOK", "PERLU_CEK") and ef.get("top1_user_id"):
                await db.matches.insert_one({
                    "user_id": ef["top1_user_id"],
                    "name": ef.get("top1_name"),
                    "face_id": fid,
                    "photo_id": photo_id,
                    "event_id": event_id,
                    "similarity": ef.get("top1_score", 0.0),
                    "selisih": ef.get("selisih", 0.0),
                    "status": status,
                    "created_at": now,
                })

            crop_url = f"/api/files/{ef.get('crop_path')}" if ef.get("crop_path") else None
            faces_summary.append({
                "face_id": fid,
                "box": ef["box"],
                "confidence": ef["confidence"],
                "crop_url": crop_url,
                "status": status,
                "top1_name": ef.get("top1_name"),
                "top1_score": ef.get("top1_score", 0.0),
            })

        # Kirim notifikasi HANYA untuk mahasiswa yang berstatus COCOK
        ev_doc = await db.events.find_one({"_id": ObjectId(event_id)})
        event_name = ev_doc.get("name", "acara kampus") if ev_doc else "acara kampus"

        for uid in matched_user_ids:
            await db.notifications.insert_one({
                "user_id": uid,
                "message": f"Anda memiliki 1 foto baru terverifikasi dari acara {event_name}",
                "photo_id": photo_id,
                "event_id": event_id,
                "event_name": event_name,
                "read": False,
                "created_at": now,
            })

        await db.photos.update_one(
            {"id": photo_id},
            {"$set": {
                "status": "done",
                "condition": result["condition"],
                "used_restoration": result["used_restoration"],
                "image_width": result["image_width"],
                "image_height": result["image_height"],
                "face_count": len(result["faces"]),
                "match_count": total_cocok,
                "faces": faces_summary,
                "processed_at": now,
                "error": None,
            }},
        )
    except Exception as exc:
        logger.exception("Pipeline failed for photo %s: %s", photo_id, exc)
        await db.photos.update_one({"id": photo_id}, {"$set": {"status": "failed", "error": str(exc)}})


@api.post("/events/{event_id}/photos")
async def upload_photos(
    event_id: str,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_role("panitia", "admin")),
):
    try:
        event = await db.events.find_one({"_id": ObjectId(event_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid event id")
    if not event:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")

    created = []
    allowed_exts = {"jpg", "jpeg", "png", "webp"}
    for upload in files:
        content = await upload.read()
        if not content:
            continue
        ext = (upload.filename or "img.jpg").rsplit(".", 1)[-1].lower()
        if ext not in allowed_exts:
            ext = "jpg"

        photo_id = str(uuid.uuid4())
        stored = await asyncio.to_thread(put_object, f"{APP_NAME}/events/{event_id}/{photo_id}.{ext}", content, MIME.get(ext, "image/jpeg"))
        filename = stored["path"]
        await db.files.insert_one({
            "storage_path": filename, "content_type": MIME.get(ext, "image/jpeg"), "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
        })

        doc = {
            "id": photo_id,
            "event_id": event_id,
            "original_filename": upload.filename,
            "stored_filename": filename,
            "uploaded_by": user["id"],
            "status": "queued",
            "created_at": datetime.now(timezone.utc),
            "face_count": 0,
            "match_count": 0,
        }
        await db.photos.insert_one(doc)
        await db.events.update_one({"_id": ObjectId(event_id)}, {"$inc": {"photo_count": 1}})
        background.add_task(_process_photo_task, photo_id, content, event_id)
        created.append({"id": photo_id, "filename": filename, "status": "queued"})

    return {"uploaded": created, "count": len(created)}


@api.get("/events/{event_id}/photos")
async def list_event_photos(event_id: str, user: dict = Depends(get_current_user)):
    cursor = db.photos.find({"event_id": event_id}).sort("created_at", -1)
    results = []
    async for p in cursor:
        results.append({
            "id": p["id"],
            "stored_filename": p["stored_filename"],
            "original_filename": p.get("original_filename"),
            "url": f"/api/files/{p['stored_filename']}",
            "status": p.get("status"),
            "face_count": p.get("face_count", 0),
            "match_count": p.get("match_count", 0),
            "condition": p.get("condition"),
            "used_restoration": p.get("used_restoration", False),
            "image_width": p.get("image_width"),
            "image_height": p.get("image_height"),
            "faces": p.get("faces", []),
            "created_at": p["created_at"].isoformat() if isinstance(p.get("created_at"), datetime) else p.get("created_at"),
        })
    return results


@api.get("/photos/{photo_id}")
async def photo_detail(photo_id: str, user: dict = Depends(get_current_user)):
    p = await db.photos.find_one({"id": photo_id})
    if not p:
        raise HTTPException(status_code=404, detail="Photo not found")

    is_student = (user.get("role") == "mahasiswa")
    query_match = {"photo_id": photo_id}
    if is_student:
        # PRIVASI MAHASISWA: Mahasiswa HANYA boleh melihat kecocokan dirinya sendiri!
        query_match["user_id"] = user["id"]
        query_match["status"] = "COCOK"

    matches = []
    user_matched_face_ids = set()
    async for m in db.matches.find(query_match):
        u = await db.users.find_one({"_id": ObjectId(m["user_id"])})
        user_matched_face_ids.add(m["face_id"])
        matches.append({
            "user_id": m["user_id"],
            "name": u.get("name", "Mahasiswa") if u else "Mahasiswa",
            "nim": u.get("nim") if u else None,
            "face_id": m["face_id"],
            "similarity": m.get("similarity", 0.0),
            "status": m.get("status", "COCOK"),
        })

    # Ambil daftar wajah (fallback ke db.faces jika p.faces kosong)
    raw_faces = p.get("faces")
    if not raw_faces:
        raw_faces = []
        async for fdoc in db.faces.find({"photo_id": photo_id}):
            raw_faces.append({
                "face_id": fdoc["face_id"],
                "box": fdoc["box"],
                "confidence": fdoc.get("confidence", 0.0),
                "crop_url": f"/api/files/{fdoc['crop_path']}" if fdoc.get("crop_path") else None,
                "status": fdoc.get("status", "UNKNOWN"),
                "top1_name": fdoc.get("top1_name"),
                "top1_score": fdoc.get("top1_score", 0.0),
                "top1_user_id": fdoc.get("top1_user_id"),
            })

    # Filter face details jika mahasiswa: lindungi privasi mahasiswa lain
    faces_out = []
    for f in raw_faces:
        f_item = dict(f)
        if is_student:
            if f_item.get("face_id") in user_matched_face_ids:
                f_item["is_me"] = True
                f_item["status"] = "COCOK"
                f_item["top1_name"] = user.get("name", "Anda")
            else:
                f_item["is_me"] = False
                f_item["status"] = "UNKNOWN"
                f_item.pop("top1_name", None)
                f_item.pop("top1_score", None)
                f_item.pop("top1_user_id", None)
        faces_out.append(f_item)

    return {
        "id": p["id"],
        "url": f"/api/files/{p['stored_filename']}",
        "event_id": p["event_id"],
        "status": p.get("status"),
        "face_count": p.get("face_count", 0),
        "match_count": len(matches) if is_student else p.get("match_count", 0),
        "image_width": p.get("image_width"),
        "image_height": p.get("image_height"),
        "faces": faces_out,
        "matches": matches,
        "condition": p.get("condition"),
        "used_restoration": p.get("used_restoration", False),
    }


# ====================================================================
# STUDENT PERSONAL GALLERY & NOTIFICATIONS
# ====================================================================
@api.get("/me/gallery")
async def my_gallery(
    event_id: Optional[str] = Query(default=None),
    user: dict = Depends(require_role("mahasiswa")),
):
    """Galeri Pribadi Mahasiswa.

    Aturan:
    - Tanpa filter slider dinamis dari sisi pengguna.
    - HANYA memuat foto yang berstatus COCOK.
    - Foto yang dilaporkan sebagai 'Bukan Foto Saya' dikecualikan.
    """
    rejected = set()
    async for fb in db.feedback.find({"user_id": user["id"], "reason": "not_me"}):
        if fb.get("photo_id"):
            rejected.add(fb["photo_id"])

    match_query = {"user_id": user["id"], "status": "COCOK"}
    if event_id and event_id != "all":
        match_query["event_id"] = event_id

    cursor = db.matches.find(match_query).sort("created_at", -1)
    seen_photos = set()
    sim_map: dict[str, float] = {}
    photo_ids: list[str] = []

    async for m in cursor:
        pid = m["photo_id"]
        if pid in rejected:
            continue
        if pid in seen_photos:
            sim_map[pid] = max(sim_map[pid], m.get("similarity", 0.0))
            continue
        seen_photos.add(pid)
        photo_ids.append(pid)
        sim_map[pid] = m.get("similarity", 0.0)

    photos = []
    for pid in photo_ids:
        p = await db.photos.find_one({"id": pid})
        if not p:
            continue
        ev = await db.events.find_one({"_id": ObjectId(p["event_id"])})
        photos.append({
            "id": p["id"],
            "url": f"/api/files/{p['stored_filename']}",
            "event_name": ev.get("name", "") if ev else "",
            "event_id": p["event_id"],
            "similarity": sim_map.get(pid, 0.0),
            "created_at": p["created_at"].isoformat() if isinstance(p.get("created_at"), datetime) else p.get("created_at"),
        })
    return photos


@api.post("/photos/{photo_id}/not-me")
async def mark_photo_not_me(
    photo_id: str,
    user: dict = Depends(require_role("mahasiswa")),
):
    """Tandai umpan balik 'Bukan Foto Saya'.

    Foto dikeluarkan dari galeri mahasiswa, status match dihapus,
    dan dicatat di koleksi 'feedback' (user_id, photo_id, face_id, skor, waktu).
    """
    match = await db.matches.find_one({"user_id": user["id"], "photo_id": photo_id})
    score = match.get("similarity", 0.0) if match else 0.0
    face_id = match.get("face_id") if match else None

    # Hapus match
    await db.matches.delete_many({"user_id": user["id"], "photo_id": photo_id})

    # Kurangi match_count pada photo jika sebelumnya COCOK
    p = await db.photos.find_one({"id": photo_id})
    event_id = p.get("event_id") if p else None
    if p and p.get("match_count", 0) > 0:
        await db.photos.update_one({"id": photo_id}, {"$inc": {"match_count": -1}})

    # Catat ke koleksi feedback
    now = datetime.now(timezone.utc)
    await db.feedback.insert_one({
        "user_id": user["id"],
        "photo_id": photo_id,
        "face_id": face_id,
        "event_id": event_id,
        "score": score,
        "reason": "not_me",
        "reported_at": now,
    })

    return {"ok": True, "message": "Foto berhasil ditandai bukan foto Anda dan dikeluarkan dari galeri."}


@api.post("/me/gallery/feedback")
async def gallery_feedback(
    data: FeedbackIn,
    user: dict = Depends(require_role("mahasiswa")),
):
    return await mark_photo_not_me(data.photo_id, user)


@api.get("/me/notifications")
async def my_notifications(user: dict = Depends(get_current_user)):
    cursor = db.notifications.find({"user_id": user["id"]}).sort("created_at", -1).limit(50)
    out = []
    async for n in cursor:
        photo = await db.photos.find_one({"id": n.get("photo_id")}) if n.get("photo_id") else None
        event = await db.events.find_one({"_id": ObjectId(photo["event_id"])}) if photo else None
        out.append({
            "id": str(n["_id"]),
            "message": n["message"],
            "photo_id": n.get("photo_id"),
            "photo_url": f"/api/files/{photo['stored_filename']}" if photo else None,
            "event_name": event.get("name") if event else None,
            "read": n.get("read", False),
            "created_at": n["created_at"].isoformat() if isinstance(n.get("created_at"), datetime) else n.get("created_at"),
        })
    return out


@api.post("/me/notifications/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["id"]}, {"$set": {"read": True}})
    return {"ok": True}


# ====================================================================
# KONFIRMASI FOTO PERLU_CEK (Khusus Akun Mahasiswa Bersangkutan & Admin)
# ====================================================================
@api.get("/verification/queue")
async def get_verification_queue(user: dict = Depends(require_role("mahasiswa", "admin"))):
    """Daftar wajah PERLU_CEK.
    - Mahasiswa: HANYA melihat wajah kandidat dirinya sendiri (top1_user_id == user['id']) demi privasi.
    - Admin: dapat memantau seluruh antrean evaluasi.
    """
    query: dict[str, Any] = {"status": "PERLU_CEK"}
    if user.get("role") == "mahasiswa":
        query["top1_user_id"] = user["id"]

    cursor = db.faces.find(query).sort("created_at", -1)
    queue = []
    async for f in cursor:
        pid = f.get("photo_id")
        photo = await db.photos.find_one({"id": pid})
        ev = await db.events.find_one({"_id": ObjectId(f["event_id"])}) if f.get("event_id") else None
        queue.append({
            "face_id": f["face_id"],
            "photo_id": pid,
            "event_id": f.get("event_id"),
            "event_name": ev.get("name", "Acara Kampus") if ev else "Acara Kampus",
            "label": f.get("label", "Wajah"),
            "crop_url": f"/api/files/{f['crop_path']}" if f.get("crop_path") else None,
            "photo_url": f"/api/files/{photo['stored_filename']}" if photo else None,
            "box": f["box"],
            "candidate_user_id": f.get("top1_user_id"),
            "candidate_name": f.get("top1_name", "Kandidat Tidak Diketahui"),
            "candidate_nim": f.get("top1_nim"),
            "score": f.get("top1_score", 0.0),
            "selisih": f.get("selisih", 0.0),
            "min_side": f.get("min_side", 0),
            "sharpness": f.get("sharpness", 0.0),
            "data_leakage": f.get("data_leakage", False),
            "created_at": f["created_at"].isoformat() if isinstance(f.get("created_at"), datetime) else f.get("created_at"),
        })
    return queue


@api.post("/verification/{face_id}/confirm")
async def confirm_verification_face(face_id: str, user: dict = Depends(require_role("mahasiswa", "admin"))):
    """Konfirmasi wajah PERLU_CEK menjadi COCOK lalu masukkan ke galeri pribadi mahasiswa."""
    face = await db.faces.find_one({"face_id": face_id})
    if not face:
        raise HTTPException(status_code=404, detail="Wajah tidak ditemukan")

    uid = face.get("top1_user_id")
    if not uid:
        raise HTTPException(status_code=400, detail="Wajah ini tidak memiliki identitas kandidat")

    # Privasi & otorisasi: Mahasiswa hanya boleh mengonfirmasi wajah kandidat miliknya sendiri
    if user.get("role") == "mahasiswa" and uid != user["id"]:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk mengonfirmasi wajah ini")

    now = datetime.now(timezone.utc)
    pid = face["photo_id"]
    eid = face["event_id"]

    await db.faces.update_one({"face_id": face_id}, {"$set": {"status": "COCOK"}})
    await db.matches.update_one(
        {"face_id": face_id},
        {"$set": {
            "user_id": uid,
            "name": face.get("top1_name"),
            "face_id": face_id,
            "photo_id": pid,
            "event_id": eid,
            "similarity": face.get("top1_score", 0.0),
            "selisih": face.get("selisih", 0.0),
            "status": "COCOK",
            "confirmed_by": user["id"],
            "confirmed_at": now,
        }},
        upsert=True,
    )

    # Sinkronkan status face & match_count di dokumen foto
    await db.photos.update_one(
        {"id": pid, "faces.face_id": face_id},
        {"$set": {"faces.$.status": "COCOK"}},
    )
    cocok_count = await db.matches.count_documents({"photo_id": pid, "status": "COCOK"})
    await db.photos.update_one({"id": pid}, {"$set": {"match_count": cocok_count}})

    # Jika dikonfirmasi oleh Admin, kirim notifikasi ke mahasiswa
    if user.get("role") != "mahasiswa":
        ev = await db.events.find_one({"_id": ObjectId(eid)}) if eid else None
        ev_name = ev.get("name", "acara kampus") if ev else "acara kampus"
        await db.notifications.insert_one({
            "user_id": uid,
            "message": f"Foto baru Anda dari acara {ev_name} telah dikonfirmasi masuk ke galeri.",
            "photo_id": pid,
            "event_id": eid,
            "event_name": ev_name,
            "read": False,
            "created_at": now,
        })

    return {"ok": True, "message": "Foto berhasil dikonfirmasi dan langsung ditambahkan ke Galeri Pribadi Anda."}


@api.post("/verification/{face_id}/reject")
async def reject_verification_face(face_id: str, user: dict = Depends(require_role("mahasiswa", "admin"))):
    """Tolak wajah PERLU_CEK menjadi UNKNOWN (tidak masuk ke galeri)."""
    face = await db.faces.find_one({"face_id": face_id})
    if not face:
        raise HTTPException(status_code=404, detail="Wajah tidak ditemukan")

    if user.get("role") == "mahasiswa" and face.get("top1_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk menolak wajah ini")

    await db.faces.update_one({"face_id": face_id}, {"$set": {"status": "UNKNOWN"}})
    await db.matches.delete_many({"face_id": face_id})
    await db.photos.update_one(
        {"id": face["photo_id"], "faces.face_id": face_id},
        {"$set": {"faces.$.status": "UNKNOWN"}},
    )

    return {"ok": True, "message": "Wajah ditandai bukan milik Anda dan dihapus dari daftar konfirmasi."}


# ====================================================================
# ADMIN SETTINGS & MANAGEMENT
# ====================================================================
@api.get("/admin/settings")
async def get_admin_settings(user: dict = Depends(require_role("admin"))):
    """Membaca konfigurasi ambang batas dari koleksi settings."""
    settings = await _get_all_settings()
    return {"settings": settings}


@api.put("/admin/settings")
async def update_admin_settings(payload: SettingsIn, user: dict = Depends(require_role("admin"))):
    """Mengubah konfigurasi ambang batas dengan validasi ketat."""
    if payload.ambang_perlu_cek >= payload.ambang_cocok:
        raise HTTPException(
            status_code=400,
            detail="Validasi Gagal: ambang_perlu_cek harus lebih kecil dari ambang_cocok.",
        )

    for k, v in payload.dict().items():
        await _set_setting(k, v)

    updated = await _get_all_settings()
    return {"ok": True, "message": "Konfigurasi ambang berhasil diperbarui", "settings": updated}


@api.post("/admin/reprocess-decisions")
async def reprocess_decisions(user: dict = Depends(require_role("admin"))):
    """Menghitung ulang status dari skor yang tersimpan saat ambang diubah, tanpa ekstraksi ulang."""
    result = await _reprocess_decisions_logic()
    return result


@api.get("/admin/feedback-summary")
async def get_feedback_summary(user: dict = Depends(require_role("admin"))):
    """Ringkasan umpan balik 'Bukan Foto Saya' per acara untuk evaluasi false acceptance."""
    events = await db.events.find({}).to_list(1000)
    event_map = {str(e["_id"]): e.get("name", "Tanpa Nama") for e in events}

    reports = await db.feedback.find({"reason": "not_me"}).to_list(5000)
    per_event: dict[str, dict] = {}

    for r in reports:
        eid = r.get("event_id") or "other"
        ename = event_map.get(eid, "Acara Lainnya")
        if eid not in per_event:
            per_event[eid] = {
                "event_id": eid,
                "event_name": ename,
                "count": 0,
                "reports": [],
            }
        per_event[eid]["count"] += 1
        per_event[eid]["reports"].append({
            "user_id": r.get("user_id"),
            "photo_id": r.get("photo_id"),
            "score": r.get("score"),
            "reported_at": r["reported_at"].isoformat() if isinstance(r.get("reported_at"), datetime) else r.get("reported_at"),
        })

    summary_list = sorted(list(per_event.values()), key=lambda x: x["count"], reverse=True)
    return {
        "total_feedback": len(reports),
        "per_event": summary_list,
    }


@api.get("/admin/stats")
async def admin_stats(user: dict = Depends(require_role("admin"))):
    users_total = await db.users.count_documents({})
    mhs = await db.users.count_documents({"role": "mahasiswa"})
    panitia = await db.users.count_documents({"role": "panitia"})
    enrolled = await db.users.count_documents({"role": "mahasiswa", "face_embeddings": {"$size": 3}})
    events_total = await db.events.count_documents({})
    photos_total = await db.photos.count_documents({})
    photos_done = await db.photos.count_documents({"status": "done"})
    faces_total = await db.faces.count_documents({})
    faces_cocok = await db.faces.count_documents({"status": "COCOK"})
    faces_perlu_cek = await db.faces.count_documents({"status": "PERLU_CEK"})
    feedback_total = await db.feedback.count_documents({"reason": "not_me"})
    pending_panitia = await db.users.count_documents({"role": "panitia", "approval_status": "pending"})
    pddikti_count = await db.pddikti_students.count_documents({})
    settings = await _get_all_settings()

    return {
        "users_total": users_total,
        "mahasiswa": mhs,
        "panitia": panitia,
        "pending_panitia": pending_panitia,
        "pddikti_count": pddikti_count,
        "enrolled_students": enrolled,
        "events_total": events_total,
        "photos_total": photos_total,
        "photos_done": photos_done,
        "faces_total": faces_total,
        "faces_cocok": faces_cocok,
        "faces_perlu_cek": faces_perlu_cek,
        "feedback_not_me": feedback_total,
        "settings": settings,
    }


# ---------- ADMIN: PERSETUJUAN (ACC) PANITIA ----------
@api.get("/admin/panitia/pending")
async def list_pending_panitia(user: dict = Depends(require_role("admin"))):
    """Daftar permohonan akun Panitia yang menunggu persetujuan (ACC) Admin."""
    cursor = db.users.find({"role": "panitia", "approval_status": "pending"}).sort("created_at", -1)
    return [_serialize_user(u) async for u in cursor]


@api.post("/admin/panitia/{user_id}/approve")
async def approve_panitia(user_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_role("admin"))):
    """Setujui (ACC) permohonan akun Panitia agar dapat masuk dan mengelola acara."""
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Akun panitia tidak ditemukan")
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"approval_status": "approved", "approved_by": user["id"], "approved_at": now}},
    )
    background_tasks.add_task(
        send_panitia_decision_email,
        target.get("email", ""),
        target.get("name", ""),
        target.get("organization") or target.get("nim") or "",
        True,
    )
    return {"ok": True, "message": f"Akun panitia {target.get('name')} ({target.get('email')}) telah disetujui (ACC)."}


@api.post("/admin/panitia/{user_id}/reject")
async def reject_panitia(user_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_role("admin"))):
    """Tolak permohonan akun Panitia."""
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Akun panitia tidak ditemukan")
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"approval_status": "rejected", "rejected_by": user["id"], "rejected_at": now}},
    )
    background_tasks.add_task(
        send_panitia_decision_email,
        target.get("email", ""),
        target.get("name", ""),
        target.get("organization") or target.get("nim") or "",
        False,
    )
    return {"ok": True, "message": f"Permohonan panitia {target.get('name')} telah ditolak."}


# ---------- ADMIN: DATABASE MASTER PDDIKTI (UNIVERSITAS MERCU BUANA) ----------
@api.get("/admin/pddikti")
async def list_pddikti_students(q: Optional[str] = Query(None), user: dict = Depends(require_role("admin"))):
    """Daftar data master mahasiswa PDDIKTI yang tersimpan di sistem."""
    query: dict[str, Any] = {}
    if q and q.strip():
        kw = q.strip()
        query = {
            "$or": [
                {"nim": {"$regex": kw, "$options": "i"}},
                {"nama": {"$regex": kw, "$options": "i"}},
                {"prodi": {"$regex": kw, "$options": "i"}},
                {"kampus": {"$regex": kw, "$options": "i"}},
            ]
        }
    cursor = db.pddikti_students.find(query).sort("nim", 1).limit(500)
    out = []
    async for d in cursor:
        out.append({
            "nim": d.get("nim", ""),
            "nama": d.get("nama", ""),
            "kampus": d.get("kampus", REQUIRED_CAMPUS),
            "prodi": d.get("prodi", ""),
            "status": d.get("status", "Aktif"),
        })
    return out


@api.post("/admin/pddikti")
async def upsert_pddikti_student(payload: PddiktiStudentIn, user: dict = Depends(require_role("admin"))):
    """Tambah atau perbarui satu data mahasiswa PDDIKTI."""
    nim = normalize_nim(payload.nim)
    if not nim.isdigit() or not (6 <= len(nim) <= 15):
        raise HTTPException(status_code=400, detail="NIM harus berupa angka 6 sampai 15 digit")
    nama = payload.nama.strip()
    if len(nama) < 2:
        raise HTTPException(status_code=400, detail="Nama lengkap wajib diisi")
    kampus = normalize_text(payload.kampus) or REQUIRED_CAMPUS
    now = datetime.now(timezone.utc)

    await db.pddikti_students.update_one(
        {"nim": nim},
        {
            "$set": {
                "nim": nim,
                "nama": nama,
                "kampus": kampus,
                "prodi": (payload.prodi or "").strip(),
                "status": (payload.status or "Aktif").strip(),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return {"ok": True, "message": f"Data PDDIKTI untuk {nama} ({nim}) berhasil disimpan."}


@api.post("/admin/pddikti/import-csv")
async def import_pddikti_csv(file: UploadFile = File(...), user: dict = Depends(require_role("admin"))):
    """Import massal data mahasiswa PDDIKTI dari berkas CSV (kolom: nim,nama,kampus,prodi,status)."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Berkas CSV kosong")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Header CSV tidak ditemukan. Gunakan kolom: nim,nama,kampus,prodi,status")

    now = datetime.now(timezone.utc)
    imported = 0
    skipped = 0

    for row in reader:
        norm_row = {str(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
        nim = normalize_nim(norm_row.get("nim") or norm_row.get("npm") or "")
        nama = (norm_row.get("nama") or norm_row.get("nama_lengkap") or norm_row.get("name") or "").strip()
        kampus = normalize_text(norm_row.get("kampus") or norm_row.get("nama_pt") or norm_row.get("perguruan_tinggi") or REQUIRED_CAMPUS)
        prodi = (norm_row.get("prodi") or norm_row.get("nama_prodi") or "").strip()
        status = (norm_row.get("status") or norm_row.get("status_saat_ini") or "Aktif").strip()

        if not nim or not nim.isdigit() or len(nama) < 2:
            skipped += 1
            continue

        await db.pddikti_students.update_one(
            {"nim": nim},
            {
                "$set": {
                    "nim": nim,
                    "nama": nama,
                    "kampus": kampus,
                    "prodi": prodi,
                    "status": status,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        imported += 1

    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "message": f"Import CSV selesai: {imported} data mahasiswa disimpan ({skipped} baris dilewati).",
    }


@api.delete("/admin/pddikti/{nim}")
async def delete_pddikti_student(nim: str, user: dict = Depends(require_role("admin"))):
    """Hapus data mahasiswa dari database master PDDIKTI."""
    clean_nim = normalize_nim(nim)
    res = await db.pddikti_students.delete_one({"nim": clean_nim})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Data NIM tidak ditemukan")
    return {"ok": True, "message": f"Data PDDIKTI NIM {clean_nim} berhasil dihapus."}


@api.get("/admin/users")
async def list_users(user: dict = Depends(require_role("admin"))):
    cursor = db.users.find({}).sort("created_at", -1)
    out = []
    async for u in cursor:
        out.append(_serialize_user(u))
    return out


@api.patch("/admin/users/{user_id}/role")
async def update_role(user_id: str, payload: UserRoleIn, user: dict = Depends(require_role("admin"))):
    if payload.role not in ("mahasiswa", "panitia", "admin"):
        raise HTTPException(status_code=400, detail="Role tidak valid")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": payload.role}})
    return {"ok": True}


@api.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_role("admin"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun sendiri")
    await db.users.delete_one({"_id": ObjectId(user_id)})
    await db.matches.delete_many({"user_id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    await db.user_face_profiles.delete_many({"user_id": user_id})
    await db.feedback.delete_many({"user_id": user_id})
    return {"ok": True}


# ====================================================================
# DEV: Source code export
# ====================================================================
EXCLUDE_DIR_NAMES = {"node_modules", "__pycache__", ".git", ".venv", "venv", ".cache", ".next", "build", "dist", "test_reports",
                     "memory", ".ruff_cache", ".pytest_cache"}
EXCLUDE_PATH_PREFIXES = ("/app/uploads",)
EXCLUDE_PATH_SUBSTR = ("/app/frontend/.cache", "/app/.yarn")


def _should_include(path: str) -> bool:
    if any(path.startswith(p) for p in EXCLUDE_PATH_PREFIXES):
        return False
    if any(s in path for s in EXCLUDE_PATH_SUBSTR):
        return False
    parts = Path(path).parts
    for name in parts:
        if name in EXCLUDE_DIR_NAMES:
            return False
    return True


MODEL_WEIGHT_EXT = (".pt", ".pth", ".onnx")
MODELS_NOTE = """FODOC - Model Weights
======================
File bobot model tidak disertakan dalam ZIP ini karena ukurannya besar.
Salin file model YOLOv11 dan ArcFace ResNet-50 ke folder backend/ml_services/models/
"""


@api.get("/dev/download-project-source")
def download_project_source(user: dict = Depends(require_role("admin"))):
    root = Path("/app")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
            if not _should_include(dirpath):
                dirnames[:] = []
                continue
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if fname == ".env" or fname.endswith(MODEL_WEIGHT_EXT) or not _should_include(full):
                    continue
                try:
                    arcname = os.path.relpath(full, root)
                    zf.write(full, arcname=arcname)
                except Exception as exc:
                    logger.warning("Skip %s: %s", full, exc)
        zf.writestr("backend/ml_services/models/README_MODELS.txt", MODELS_NOTE)
    data = buf.getvalue()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="fodoc_project_source.zip"',
                 "Content-Length": str(len(data))},
    )


@api.get("/")
async def root():
    return {
        "service": "FODOC API",
        "description": "FODOC — Foto Dokumentasi Universitas Mercu Buana",
        "ok": True,
    }


# ------------------------------------------------- mount
app.include_router(api)

# Serve React production build (frontend/build) pada port yang sama agar bisa dibuka lewat 1 link HTTPS di HP
FRONTEND_BUILD_DIR = ROOT_DIR.parent / "frontend" / "build"
if FRONTEND_BUILD_DIR.exists():
    static_dir = FRONTEND_BUILD_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="frontend-static")

    @app.get("/{full_path:path}")
    async def serve_react_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        target = (FRONTEND_BUILD_DIR / full_path).resolve()
        if full_path and target.is_file() and str(target).startswith(str(FRONTEND_BUILD_DIR.resolve())):
            cache_hdr = "public, max-age=604800" if full_path.startswith("images/") else "public, max-age=3600"
            return FileResponse(target, headers={"Cache-Control": cache_hdr})
        return FileResponse(FRONTEND_BUILD_DIR / "index.html", headers={"Cache-Control": "no-cache"})

@app.middleware("http")
async def add_static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response

app.add_middleware(GZipMiddleware, minimum_size=500)

_raw_cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
_cors_is_wildcard = "*" in _raw_cors
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[] if _cors_is_wildcard else _raw_cors,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.devtunnels\.ms|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?" if _cors_is_wildcard else None,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
