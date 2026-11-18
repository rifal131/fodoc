"""FODOC Object Storage Service — Local Disk (dev) & MongoDB GridFS (cloud 24/7).

Mode penyimpanan diatur oleh env `STORAGE_MODE`:
- `local`   : menyimpan ke folder `backend/storage_data` (default di laptop/localhost).
- `mongodb` : menyimpan permanen ke MongoDB GridFS (otomatis aktif di Hugging Face Spaces
              saat env `SPACE_ID` terdeteksi, agar foto tidak hilang saat container restart).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

APP_NAME = "fodoc"
LOCAL_STORAGE_DIR = Path(__file__).parent / "storage_data"
MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

_gridfs = None


def _storage_mode() -> str:
    explicit = (os.environ.get("STORAGE_MODE") or "").strip().lower()
    if explicit in ("local", "mongodb"):
        return explicit
    # Otomatis pakai MongoDB GridFS di Hugging Face Spaces agar file permanen 24/7
    if os.environ.get("SPACE_ID"):
        return "mongodb"
    return "local"


def _get_gridfs():
    global _gridfs
    if _gridfs is None:
        from pymongo import MongoClient
        import gridfs

        client = MongoClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        _gridfs = gridfs.GridFS(db, collection="fodoc_storage")
    return _gridfs


def init_storage(force: bool = False) -> str:
    """Inisialisasi penyimpanan file FODOC (local atau mongodb GridFS)."""
    mode = _storage_mode()
    if mode == "mongodb":
        _get_gridfs()
        return "mongodb"
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return "local"


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Menyimpan berkas citra ke penyimpanan FODOC."""
    if _storage_mode() == "mongodb":
        fs = _get_gridfs()
        for existing in fs.find({"filename": path}):
            fs.delete(existing._id)
        fs.put(data, filename=path, content_type=content_type)
        return {"path": path, "content_type": content_type}

    dest = LOCAL_STORAGE_DIR / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"path": path, "content_type": content_type}


def get_object(path: str) -> tuple[bytes, str]:
    """Mengambil berkas citra dari penyimpanan FODOC."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    default_ctype = MIME.get(ext, "application/octet-stream")

    if _storage_mode() == "mongodb":
        fs = _get_gridfs()
        doc: Optional[object] = fs.find_one({"filename": path})
        if doc is None:
            return b"", "application/octet-stream"
        ctype = getattr(doc, "content_type", None) or default_ctype
        return doc.read(), ctype

    target = LOCAL_STORAGE_DIR / path
    if not target.exists():
        return b"", "application/octet-stream"
    return target.read_bytes(), default_ctype
