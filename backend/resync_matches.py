import asyncio
from datetime import datetime, timezone
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32).flatten()
    b = np.asarray(b, dtype=np.float32).flatten()
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

async def resync():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['fodoc_db']

    # Load enrolled students
    enrolled = []
    async for u in db.users.find({"role": "mahasiswa", "face_embedding": {"$exists": True, "$ne": None}}):
        embs = u.get("face_embeddings") or ([u["face_embedding"]] if u.get("face_embedding") else [])
        if embs:
            enrolled.append({
                "id": str(u["_id"]),
                "name": u.get("name", ""),
                "embeddings": [np.asarray(e, dtype=np.float32) for e in embs]
            })
    print(f"Loaded {len(enrolled)} enrolled students: {[s['name'] for s in enrolled]}")

    setting = await db.settings.find_one({"key": "similarity_threshold"})
    threshold = float(setting.get("value", 0.32)) if setting else 0.32
    print(f"Using threshold: {threshold}")

    # Clear existing matches
    deleted = await db.matches.delete_many({})
    print(f"Deleted {deleted.deleted_count} old matches")

    # Fetch all photos
    photos = await db.photos.find().to_list(1000)
    print(f"Processing {len(photos)} photos...")

    total_new_matches = 0

    for p in photos:
        pid = p["id"]
        eid = p.get("event_id")
        faces = await db.faces.find({"photo_id": pid}).to_list(500)
        
        candidates = []
        for face in faces:
            emb = face.get("embedding")
            if not emb:
                continue
            f_vec = np.asarray(emb, dtype=np.float32)
            for student in enrolled:
                best_sim = max(cosine_similarity(f_vec, se) for se in student["embeddings"])
                if best_sim >= threshold:
                    candidates.append((best_sim, student["id"], face["face_id"]))

        # Sort desc by similarity (greedy assignment: each student matched at most once per photo)
        candidates.sort(reverse=True, key=lambda x: x[0])
        matched_user_ids = set()
        photo_matches = 0

        for sim, uid, fid in candidates:
            if uid in matched_user_ids:
                continue
            matched_user_ids.add(uid)
            photo_matches += 1
            total_new_matches += 1
            await db.matches.insert_one({
                "user_id": uid,
                "face_id": fid,
                "photo_id": pid,
                "event_id": eid,
                "similarity": sim,
                "created_at": datetime.now(timezone.utc),
            })

        await db.photos.update_one(
            {"id": pid},
            {"$set": {"match_count": photo_matches}}
        )

    print(f"\nResync complete! Created {total_new_matches} matches across {len(photos)} photos.")

    # Show count of photos in gallery for each student
    for s in enrolled:
        distinct_pids = await db.matches.distinct("photo_id", {"user_id": s["id"]})
        print(f"  Student {s['name']}: {len(distinct_pids)} matched photos in gallery")

asyncio.run(resync())
