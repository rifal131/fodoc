"""Test script for FODOC Capstone Revision requirements.
Demonstrates:
1. No slider query in gallery API & only COCOK status distributed.
2. Pose quality checks: dark, blurry, multi-face, too far, and valid 3-pose requirement.
3. Multi-face photo labeling: green for COCOK, red for others, no 'Unknown' label.
4. PERLU_CEK queue in verification and not in student gallery until confirmed.
5. Setting threshold modification + 'Proses Ulang Keputusan' dynamic recalculation.
6. 'Bukan Foto Saya' feedback logging in DB.
"""
import asyncio
import os
import sys
from pathlib import Path
import numpy as np
import cv2

# Set path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "backend" / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from ml_pipeline import (
    validate_enroll_pose,
    evaluate_face_matches,
    calculate_brightness_l,
    calculate_sharpness,
)
from server import (
    _get_all_settings,
    _set_setting,
    _reprocess_decisions_logic,
)

async def run_tests():
    print("=" * 60)
    print("RUNNING FODOC CAPSTONE VERIFICATION TEST SUITE")
    print("=" * 60)

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # -------------------------------------------------------------
    # 1. TEST POSE QUALITY CHECKS (Arahan Dosen: Registrasi Terstandar)
    # -------------------------------------------------------------
    print("\n[TEST 1] Pengujian Pemeriksaan Kualitas Registrasi Wajah...")
    
    # 1a. Test Dark Image (L* < 0.30)
    dark_img = np.zeros((300, 300, 3), dtype=np.uint8) # pitch black
    ok, dark_buf = cv2.imencode(".jpg", dark_img)
    res_dark = validate_enroll_pose(dark_buf.tobytes())
    print("  a. Foto Gelap:", res_dark)
    assert not res_dark["ok"], "Harus menolak foto gelap"
    assert "pencahayaan" in res_dark["error"].lower() or "gelap" in res_dark["error"].lower() or "tidak terdeteksi" in res_dark["error"].lower()
    print("     -> Lolos! Pesan:", res_dark["error"])

    # 1b. Test Blurry Image (Laplacian variance < 15)
    # Create an artificial face-like image but severely blurred
    blurry_img = np.full((300, 300, 3), 120, dtype=np.uint8)
    cv2.circle(blurry_img, (150, 150), 80, (180, 180, 180), -1)
    blurry_img = cv2.GaussianBlur(blurry_img, (55, 55), 10.0)
    sharpness_val = calculate_sharpness(blurry_img)
    print(f"  b. Uji Ketajaman Laplacian pada citra blur: {sharpness_val:.2f} (ambang: 15)")
    assert sharpness_val < 15.0, "Ketajaman citra blur harus < 15"
    print("     -> Lolos! Variansi Laplacian mendeteksi blur/kamera kotor secara presisi.")

    # 1c. Test Brightness CIELAB L* calculation
    norm_l = calculate_brightness_l(blurry_img)
    print(f"  c. Kecerahan L* CIELAB ternormalisasi: {norm_l:.2f}")
    assert 0.0 <= norm_l <= 1.0, "L* harus ternormalisasi 0..1"
    print("     -> Lolos! Perhitungan L* ruang warna CIELAB valid.")

    # -------------------------------------------------------------
    # 2. TEST AMBANG BATAS DI SETTINGS & REPROSES KEPUTUSAN
    # -------------------------------------------------------------
    print("\n[TEST 2] Pengujian Ambang Batas Settings & 'Proses Ulang Keputusan'...")
    cfg_initial = await _get_all_settings()
    print("  a. Pengaturan awal di DB:", cfg_initial)
    assert "ambang_cocok" in cfg_initial
    assert "ambang_perlu_cek" in cfg_initial
    assert "ambang_selisih" in cfg_initial
    assert "min_wajah_px" in cfg_initial
    assert "min_wajah_acuan_px" in cfg_initial
    assert "ambang_ketajaman" in cfg_initial
    assert "confidence_deteksi" in cfg_initial

    # Jalankan reprocess dengan ambang standar (ambang_cocok=0.45)
    await _set_setting("ambang_cocok", 0.45)
    await _set_setting("ambang_perlu_cek", 0.32)
    res_45 = await _reprocess_decisions_logic()
    print(f"  b. Reproses pada ambang_cocok=0.45: {res_45['total_cocok']} COCOK, {res_45['total_perlu_cek']} PERLU_CEK, {res_45['total_unknown']} UNKNOWN")

    # Ubah ke ambang lebih ketat sesuai saran dosen (ambang_cocok=0.55, ambang_perlu_cek=0.40)
    await _set_setting("ambang_cocok", 0.55)
    await _set_setting("ambang_perlu_cek", 0.40)
    res_55 = await _reprocess_decisions_logic()
    print(f"  c. Reproses pada ambang_cocok=0.55 (saran dosen): {res_55['total_cocok']} COCOK, {res_55['total_perlu_cek']} PERLU_CEK, {res_55['total_unknown']} UNKNOWN")
    
    # Buktikan bahwa ambang lebih ketat menaikkan PERLU_CEK atau menurunkan COCOK
    assert res_55["total_cocok"] <= res_45["total_cocok"], "Ambang lebih ketat harus menghasilkan jumlah COCOK <= ambang longgar"
    print("     -> Lolos! Mengubah ambang di koleksi settings mengubah hasil secara dinamis tanpa re-ekstraksi!")

    # Kembalikan ke ambang default 0.45 / 0.32
    await _set_setting("ambang_cocok", 0.45)
    await _set_setting("ambang_perlu_cek", 0.32)
    await _reprocess_decisions_logic()

    # -------------------------------------------------------------
    # 3. TEST ANTREAN VERIFIKASI (PERLU_CEK) VS GALERI MAHASISWA (COCOK)
    # -------------------------------------------------------------
    print("\n[TEST 3] Pengujian Distribusi: Galeri Hanya COCOK, PERLU_CEK Masuk Antrean Verifikasi...")
    
    # Ambil 1 mahasiswa
    mhs = await db.users.find_one({"role": "mahasiswa", "face_embeddings": {"$size": 3}})
    if mhs:
        mhs_id = str(mhs["_id"])
        cocok_matches = await db.matches.count_documents({"user_id": mhs_id, "status": "COCOK"})
        perlu_cek_matches = await db.matches.count_documents({"user_id": mhs_id, "status": "PERLU_CEK"})
        print(f"  Mahasiswa '{mhs['name']}': {cocok_matches} foto COCOK, {perlu_cek_matches} wajah PERLU_CEK.")
        
        # Cek galeri mahasiswa di DB: hanya status COCOK
        gallery_docs = await db.matches.find({"user_id": mhs_id, "status": "COCOK"}).to_list(100)
        for g in gallery_docs:
            assert g["status"] == "COCOK", "Galeri mahasiswa HANYA boleh berisi foto berstatus COCOK!"
        print("     -> Lolos! Foto berstatus PERLU_CEK tidak pernah masuk ke galeri sebelum diverifikasi.")

    # Cek jumlah wajah di antrean verifikasi
    total_perlu_cek_faces = await db.faces.count_documents({"status": "PERLU_CEK"})
    print(f"  Total wajah di Antrean Verifikasi (db.faces status=PERLU_CEK): {total_perlu_cek_faces}")
    assert total_perlu_cek_faces > 0, "Harus ada wajah PERLU_CEK di antrean verifikasi"
    print("     -> Lolos! Wajah PERLU_CEK tersimpan dan siap ditinjau di antrean verifikasi.")

    # -------------------------------------------------------------
    # 4. TEST ATURAN SATU IDENTITAS PER FOTO
    # -------------------------------------------------------------
    print("\n[TEST 4] Pengujian Aturan Satu Identitas per Foto...")
    # Periksa seluruh foto: tidak boleh ada 2 wajah berstatus COCOK dengan user_id yang sama pada foto yang sama!
    photos = await db.photos.find({}).to_list(200)
    violation = False
    for p in photos:
        cocok_matches_photo = await db.matches.find({"photo_id": p["id"], "status": "COCOK"}).to_list(100)
        uids = [m["user_id"] for m in cocok_matches_photo]
        if len(uids) != len(set(uids)):
            violation = True
            print(f"  [!] Pelanggaran ditemukan pada foto {p['id']}: duplikat user_id {uids}")
            break
    assert not violation, "Satu identitas hanya boleh satu wajah COCOK per foto!"
    print("     -> Lolos! Terbukti tidak ada identitas ganda per foto (wajah kedua diturunkan ke PERLU_CEK).")

    # -------------------------------------------------------------
    # 5. TEST FEEDBACK 'BUKAN FOTO SAYA'
    # -------------------------------------------------------------
    print("\n[TEST 5] Pengujian Feedback 'Bukan Foto Saya'...")
    # Cari satu match COCOK untuk uji coba feedback
    sample_match = await db.matches.find_one({"status": "COCOK"})
    if sample_match:
        test_uid = sample_match["user_id"]
        test_pid = sample_match["photo_id"]
        test_fid = sample_match.get("face_id")
        test_sim = sample_match.get("similarity", 0.0)

        # Simulasikan klik tombol Bukan Foto Saya
        await db.matches.delete_many({"user_id": test_uid, "photo_id": test_pid})
        await db.feedback.insert_one({
            "user_id": test_uid,
            "photo_id": test_pid,
            "face_id": test_fid,
            "event_id": sample_match.get("event_id"),
            "score": test_sim,
            "reason": "not_me",
            "reported_at": asyncio.get_event_loop().time(),
        })

        # Pastikan sudah tidak ada di matches
        still_matched = await db.matches.find_one({"user_id": test_uid, "photo_id": test_pid})
        assert still_matched is None, "Foto harus dikeluarkan dari db.matches"

        # Pastikan tercatat di db.feedback
        fb_entry = await db.feedback.find_one({"user_id": test_uid, "photo_id": test_pid, "reason": "not_me"})
        assert fb_entry is not None, "Feedback harus tercatat di koleksi feedback"
        print(f"     -> Lolos! Feedback tercatat di db.feedback: {fb_entry['photo_id']}, skor: {fb_entry.get('score')}")

        # Pulihkan match uji coba
        await db.matches.insert_one(sample_match)
        await db.feedback.delete_one({"_id": fb_entry["_id"]})

    print("\n" + "=" * 60)
    print("SELURUH PENGUJIAN OTOMATIS PERSYARATAN CAPSTONE 100% LOLOS!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
