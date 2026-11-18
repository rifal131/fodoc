"""Script utilitas untuk mengekstrak ulang embedding AdaFace IR-50 bagi seluruh mahasiswa terdaftar
dan memperbarui keputusan kecocokan di MongoDB."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from ml_pipeline import validate_enroll_pose
from server import _reprocess_decisions_logic
from storage import get_object

load_dotenv(Path(__file__).parent / ".env")


async def re_embed_students():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    users = await db.users.find({"role": "mahasiswa"}).to_list(200)
    for u in users:
        uid = str(u["_id"])
        name = u.get("name")
        profiles = await db.user_face_profiles.find({"user_id": uid}).to_list(10)
        if not profiles:
            continue
        print(f"Re-embedding student {name} ({len(profiles)} angles) dengan AdaFace IR-50...", flush=True)
        new_embeddings = []
        for p in profiles:
            img_bytes, _ = get_object(p["storage_path"])
            if not img_bytes:
                continue
            res = validate_enroll_pose(
                img_bytes, min_size_px=30, min_l_brightness=0.10, min_sharpness=1.0, conf_detect=0.4639
            )
            if res.get("ok"):
                new_embeddings.append(res["embedding"])
                await db.user_face_profiles.update_one(
                    {"_id": p["_id"]},
                    {"$set": {
                        "embedding": res["embedding"],
                        "face_box": res["face_box"],
                        "confidence": res["confidence"],
                        "landmarks": res.get("landmarks"),
                    }},
                )
                print(f"  Angle {p.get('angle')}: OK", flush=True)
            else:
                print(f"  Angle {p.get('angle')}: Failed: {res.get('error')}", flush=True)

        if new_embeddings:
            centroid = np.mean(np.asarray(new_embeddings, dtype=np.float32), axis=0)
            c_norm = float(np.linalg.norm(centroid))
            if c_norm > 1e-6:
                centroid = centroid / c_norm
            await db.users.update_one(
                {"_id": u["_id"]},
                {"$set": {
                    "face_embedding": centroid.tolist(),
                    "face_embeddings": new_embeddings,
                    "needs_re_enrollment": (len(new_embeddings) != 3),
                }},
            )
            print(f"Student {name} updated ({len(new_embeddings)} embeddings)!", flush=True)

    summary = await _reprocess_decisions_logic()
    print("Reprocess decisions summary:", summary, flush=True)


if __name__ == "__main__":
    asyncio.run(re_embed_students())
