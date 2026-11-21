"""Validasi Identitas Mahasiswa Universitas Mercu Buana & Data Master PDDIKTI.

Aturan akses mahasiswa FODOC:
1. Email mahasiswa WAJIB berformat `<NIM>@student.mercubuana.ac.id` (prefix email sama persis dengan NIM).
2. NIM dan Nama Lengkap WAJIB sesuai dengan data PDDIKTI (koleksi `pddikti_students` di MongoDB,
   serta mendukung integrasi opsional ke endpoint Feeder/API resmi lewat env `PDDIKTI_API_URL`).
3. Perguruan Tinggi / Kampus WAJIB `UNIVERSITAS MERCU BUANA`.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

STUDENT_EMAIL_DOMAIN = "student.mercubuana.ac.id"
REQUIRED_CAMPUS = "UNIVERSITAS MERCU BUANA"
DISALLOWED_STATUSES = {"NON-AKTIF", "NONAKTIF", "DIKELUARKAN", "DROP OUT", "DO", "MENGUNDURKAN DIRI"}

# Data awal contoh mahasiswa Universitas Mercu Buana (hanya di-seed bila koleksi pddikti_students kosong).
# Admin dapat menambah, mengubah, menghapus, atau mengimpor CSV data PDDIKTI langsung dari Admin Panel.
DEFAULT_PDDIKTI_SEED: list[dict[str, str]] = [
    {
        "nim": "41523010007",
        "nama": "Nur Rifal",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010012",
        "nama": "Harari Zuhdi",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010006",
        "nama": "Vikry Aldiansyah",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010045",
        "nama": "Muhammad Banu Prayoga",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010035",
        "nama": "Dewandaru Satya Daniswara",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010018",
        "nama": "Fajar Satrio Wicaksono",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010019",
        "nama": "Muhammad Dandy Faturrahman",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010002",
        "nama": "Bagas Indra Lesmana",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010003",
        "nama": "Ahmad Fauzi",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010011",
        "nama": "Bagus Banil Mustopa",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010016",
        "nama": "Rizky Fernando",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010017",
        "nama": "Reyner Muhammad Gultom",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010025",
        "nama": "Abdullah Al Manan",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010029",
        "nama": "Jericho Rayhan Maulana",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
    {
        "nim": "41523010030",
        "nama": "Reza Pahlevi Setyadi",
        "kampus": "UNIVERSITAS MERCU BUANA",
        "prodi": "Teknik Informatika",
        "status": "Aktif",
    },
]


def normalize_text(value: str | None) -> str:
    """Normalisasi teks: rapikan spasi ganda, trim, dan huruf kapital."""
    return re.sub(r"\s+", " ", (value or "").strip()).upper()


def normalize_nim(value: str | None) -> str:
    """Bersihkan spasi pada NIM."""
    return re.sub(r"\s+", "", (value or "").strip())


def validate_student_email(email: str, nim: str | None) -> tuple[bool, str | None]:
    """Validasi ketat bahwa email mahasiswa harus `<NIM>@student.mercubuana.ac.id`."""
    clean_email = (email or "").strip().lower()
    clean_nim = normalize_nim(nim)

    if not clean_nim:
        return False, "NIM wajib diisi untuk pendaftaran mahasiswa."

    if not re.fullmatch(r"\d{6,15}", clean_nim):
        return False, "Format NIM tidak valid. NIM harus berupa angka 6 sampai 15 digit."

    if "@" not in clean_email:
        return False, f"Format email tidak valid. Gunakan {clean_nim}@{STUDENT_EMAIL_DOMAIN}."

    local_part, domain = clean_email.split("@", 1)
    if domain != STUDENT_EMAIL_DOMAIN:
        return (
            False,
            f"Email mahasiswa wajib menggunakan domain @{STUDENT_EMAIL_DOMAIN} (contoh: {clean_nim}@{STUDENT_EMAIL_DOMAIN}).",
        )

    if local_part != clean_nim:
        return (
            False,
            f"Format email mahasiswa wajib <NIM>@{STUDENT_EMAIL_DOMAIN}. Untuk NIM {clean_nim}, email harus {clean_nim}@{STUDENT_EMAIL_DOMAIN}.",
        )

    return True, None


def _query_external_pddikti(nim: str) -> dict[str, Any] | None:
    """Opsional: hubungi endpoint Feeder / API PDDIKTI resmi jika `PDDIKTI_API_URL` dikonfigurasi di .env."""
    base_url = (os.environ.get("PDDIKTI_API_URL") or "").strip().rstrip("/")
    if not base_url:
        return None

    api_key = (os.environ.get("PDDIKTI_API_KEY") or "").strip()
    url = f"{base_url}/{urllib.parse.quote(nim)}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        rows = raw.get("data", raw) if isinstance(raw, dict) else raw
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return None
        for row in rows:
            if not isinstance(row, dict):
                continue
            r_nim = normalize_nim(str(row.get("nim") or ""))
            if r_nim == nim:
                return {
                    "nim": r_nim,
                    "nama": str(row.get("nama") or row.get("name") or "").strip(),
                    "kampus": str(row.get("nama_pt") or row.get("kampus") or row.get("pt") or "").strip(),
                    "prodi": str(row.get("nama_prodi") or row.get("prodi") or "").strip(),
                    "status": str(row.get("status_saat_ini") or row.get("status") or "Aktif").strip(),
                }
    except Exception:
        return None
    return None


async def verify_student_pddikti(db, nim: str | None, name: str | None) -> dict[str, Any]:
    """Cocokkan NIM, Nama Lengkap, dan Kampus (UNIVERSITAS MERCU BUANA) dengan data PDDIKTI."""
    clean_nim = normalize_nim(nim)
    clean_name = normalize_text(name)

    if not clean_nim:
        return {"ok": False, "error": "NIM wajib diisi untuk verifikasi data mahasiswa."}
    if not clean_name:
        return {"ok": False, "error": "Nama lengkap wajib diisi sesuai data mahasiswa."}

    # 1. Cek database master PDDIKTI lokal (MongoDB) terlebih dahulu
    record = await db.pddikti_students.find_one({"nim": clean_nim})

    # 2. Fallback opsional ke endpoint resmi jika dikonfigurasi di .env
    if record is None and os.environ.get("PDDIKTI_API_URL"):
        import asyncio
        record = await asyncio.to_thread(_query_external_pddikti, clean_nim)

    if not record:
        return {
            "ok": False,
            "error": (
                f"Akses ditolak: NIM {clean_nim} tidak terdaftar pada data mahasiswa Universitas Mercu Buana. "
                "Pastikan NIM Anda benar atau hubungi Admin."
            ),
        }

    campus = normalize_text(record.get("kampus") or record.get("nama_pt") or "")
    if campus != REQUIRED_CAMPUS:
        campus_display = (record.get("kampus") or record.get("nama_pt") or "Tidak Diketahui").strip()
        return {
            "ok": False,
            "error": (
                f"Akses ditolak: Perguruan tinggi yang tercatat adalah '{campus_display}', "
                f"bukan {REQUIRED_CAMPUS}."
            ),
        }

    pddikti_name = normalize_text(record.get("nama"))
    if pddikti_name != clean_name:
        return {
            "ok": False,
            "error": (
                f"Akses ditolak: Nama lengkap tidak sesuai dengan data mahasiswa untuk NIM {clean_nim}. "
                "Masukkan nama lengkap yang sesuai dengan data resmi kampus."
            ),
        }

    status = normalize_text(record.get("status") or "Aktif")
    if status in DISALLOWED_STATUSES:
        return {
            "ok": False,
            "error": f"Akses ditolak: Status kemahasiswaan Anda tercatat '{record.get('status')}'.",
        }

    return {
        "ok": True,
        "record": {
            "nim": clean_nim,
            "nama": (record.get("nama") or "").strip(),
            "kampus": REQUIRED_CAMPUS,
            "prodi": (record.get("prodi") or "").strip(),
            "status": (record.get("status") or "Aktif").strip(),
        },
    }
