import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np

load_dotenv(Path(__file__).parent / ".env")

async def check():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    users = await db.users.find({}).to_list(100)
    print("=== DAFTAR USER DI DB ===")
    for u in users:
        has_emb = bool(u.get("face_embedding"))
        embs_count = len(u.get("face_embeddings") or [])
        print(f"User: {u.get('name')} | Email: {u.get('email')} | Role: {u.get('role')} | Enrolled: {has_emb} (embeddings: {embs_count})")

    harari = await db.users.find_one({"role": "mahasiswa"})
    if not harari:
        print("[!] Tidak ada user mahasiswa!")
        return

    if not harari.get("face_embedding") and not harari.get("face_embeddings"):
        print("[!] User mahasiswa BELUM MEMILIKI face_embedding (belum selesai verifikasi wajah)!")
        return

    probes = [np.asarray(e, dtype=np.float32) for e in (harari.get("face_embeddings") or [harari["face_embedding"]])]
    
    faces = await db.faces.find({}).to_list(500)
    print(f"\n=== CEK KEMIRIPAN DENGAN {len(faces)} WAJAH DI DOKUMENTASI ===")
    sims = []
    for f in faces:
        emb = f.get("embedding")
        if not emb:
            continue
        other = np.asarray(emb, dtype=np.float32)
        sim = max(float(np.dot(p, other) / (np.linalg.norm(p) * np.linalg.norm(other) + 1e-9)) for p in probes)
        sims.append((sim, f.get("photo_id"), f.get("face_id")))
    
    sims.sort(key=lambda x: x[0], reverse=True)
    print(f"Top 10 kemiripan tertinggi:")
    for sim, pid, fid in sims[:10]:
        print(f"  Similarity: {sim:.4f} ({(sim*100):.1f}%) | Photo ID: {pid}")

if __name__ == "__main__":
    asyncio.run(check())
