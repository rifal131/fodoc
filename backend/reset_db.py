import asyncio
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))
from auth import hash_password
from pddikti_service import DEFAULT_PDDIKTI_SEED

load_dotenv(Path(__file__).parent / ".env")

async def reset_database():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    print(f"[*] Menghubungkan ke MongoDB: {mongo_url} (database: {db_name})...")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fodoc.ac.id")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")

    # 1. Bersihkan koleksi transaksi & data event
    collections_to_empty = [
        "events",
        "photos",
        "faces",
        "matches",
        "notifications",
        "user_face_profiles",
        "feedback",
        "login_attempts",
        "email_otps",
        "files",
    ]

    print("[*] Mengosongkan data transaksi dan relasi...")
    for col in collections_to_empty:
        deleted = await db[col].delete_many({})
        print(f"  - Koleksi '{col}': {deleted.deleted_count} dokumen dihapus.")

    # 2. Bersihkan users: sisakan HANYA akun admin
    user_del = await db.users.delete_many({"email": {"$ne": admin_email}})
    print(f"[*] Menghapus user non-admin: {user_del.deleted_count} user dihapus.")

    # Pastikan akun admin tersedia dengan data bersih
    admin_doc = await db.users.find_one({"email": admin_email})
    if admin_doc is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "FODOC Admin",
            "role": "admin",
            "nim": None,
            "created_at": datetime.now(timezone.utc),
        })
        print(f"[+] Akun admin dibuat: {admin_email}")
    else:
        # Bersihkan referensi face/enrollment bila ada pada akun admin
        await db.users.update_one(
            {"_id": admin_doc["_id"]},
            {
                "$set": {
                    "password_hash": hash_password(admin_password),
                    "role": "admin",
                    "name": "FODOC Admin",
                },
                "$unset": {
                    "face_embedding": "",
                    "face_embeddings": "",
                    "reference_image": "",
                    "enrolled_at": "",
                }
            }
        )
        print(f"[+] Akun admin diperbarui dan dibersihkan: {admin_email}")

    # 3. Reset settings ke nilai default standar model terbaru (AdaFace IR-50 + YOLOv11n-face Harari)
    await db.settings.delete_many({})
    now = datetime.now(timezone.utc)
    default_settings = {
        "ambang_cocok": 0.55,
        "ambang_perlu_cek": 0.40,
        "ambang_selisih": 0.10,
        "min_wajah_px": 28,
        "min_wajah_acuan_px": 60,
        "ambang_ketajaman": 15.0,
        "confidence_deteksi": 0.4639,
    }
    for k, v in default_settings.items():
        await db.settings.insert_one({
            "key": k,
            "value": v,
            "created_at": now,
            "updated_at": now,
        })
    print(f"[+] Setting ambang di-reset ke default baru: {default_settings}")

    # 3b. Reset koleksi pddikti_students ke data awal bersih Universitas Mercu Buana
    await db.pddikti_students.delete_many({})
    for item in DEFAULT_PDDIKTI_SEED:
        await db.pddikti_students.insert_one({**item, "created_at": now, "updated_at": now})
    print(f"[+] Master data mahasiswa UMB di-reset ({len(DEFAULT_PDDIKTI_SEED)} data awal).")

    # 4. Bersihkan file penyimpanan lokal (storage_data/fodoc & test data)
    storage_dir = Path(__file__).parent / "storage_data"
    storage_fodoc = storage_dir / "fodoc"
    if storage_fodoc.exists():
        print(f"[*] Membersihkan folder penyimpanan file: {storage_fodoc}...")
        for sub in ["enrollments", "events", "faces"]:
            sub_path = storage_fodoc / sub
            if sub_path.exists():
                shutil.rmtree(sub_path, ignore_errors=True)
                sub_path.mkdir(parents=True, exist_ok=True)
                print(f"  - Folder '{sub}' dikosongkan.")

    test_crops = storage_dir / "test_crops"
    if test_crops.exists():
        shutil.rmtree(test_crops, ignore_errors=True)
        print("  - Folder 'test_crops' dihapus.")
    test_boxed = storage_dir / "test_boxed.jpg"
    if test_boxed.exists():
        test_boxed.unlink(missing_ok=True)
        print("  - File 'test_boxed.jpg' dihapus.")

    # 5. Verifikasi hasil akhir database
    print("\n[OK] Ringkasan Database Setelah Reset:")
    all_users = await db.users.find({}).to_list(10)
    for u in all_users:
        print(f"    - User: {u.get('name')} | Email: {u.get('email')} | Role: {u.get('role')}")

    print(f"    - Total Events      : {await db.events.count_documents({})}")
    print(f"    - Total Photos      : {await db.photos.count_documents({})}")
    print(f"    - Total Faces       : {await db.faces.count_documents({})}")
    print(f"    - Total Matches     : {await db.matches.count_documents({})}")
    print(f"    - Total Notifikasi  : {await db.notifications.count_documents({})}")
    print(f"    - Total Files       : {await db.files.count_documents({})}")
    print("\nDatabase siap digunakan dari awal!")

if __name__ == "__main__":
    asyncio.run(reset_database())
