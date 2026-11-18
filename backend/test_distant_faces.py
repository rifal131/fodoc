import asyncio
import os
import cv2
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

from storage import get_object
from ml_pipeline import get_detector, get_landmark_model, extract_embedding, _crop_with_margin
from align import cari_landmark, align_face

async def test():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    # Ambil foto Arunika
    photo = await db.photos.find_one({"id": "7c998a35-5fec-460e-9a24-f4939ae0627b"})
    if not photo:
        print("Photo not found")
        return
    data, _ = get_object(photo["stored_filename"])
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    
    lmk = get_landmark_model()
    faces = await db.faces.find({"photo_id": photo["id"]}).to_list(20)
    print(f"Total faces in photo: {len(faces)}")
    
    # Cek mahasiswa rifal
    rifal = await db.users.find_one({"name": "rifal"})
    r_probes = [np.asarray(e, dtype=np.float32) for e in rifal["face_embeddings"]]
    
    for i, f in enumerate(faces, 1):
        box = tuple(f["box"])
        crop = _crop_with_margin(img, box)
        h, w = crop.shape[:2]
        
        # Coba cari_landmark dengan conf default (0.25) vs conf rendah (0.05)
        kp_default, c_def = cari_landmark(lmk, crop, conf_min=0.25)
        kp_low, c_low = cari_landmark(lmk, crop, conf_min=0.05)
        
        # Hitung similarity jika unaligned vs aligned
        al_unaligned = cv2.resize(crop, (112, 112))
        emb_unaligned = extract_embedding(al_unaligned)
        sim_unaligned = max(float(np.dot(p, emb_unaligned) / (np.linalg.norm(p) * np.linalg.norm(emb_unaligned) + 1e-9)) for p in r_probes)
        
        sim_aligned = 0.0
        if kp_low is not None:
            al_aligned = align_face(crop, kp_low, 112)
            if al_aligned is not None:
                emb_aligned = extract_embedding(al_aligned)
                sim_aligned = max(float(np.dot(p, emb_aligned) / (np.linalg.norm(p) * np.linalg.norm(emb_aligned) + 1e-9)) for p in r_probes)
        
        print(f"Face #{i:02d} ({w}x{h} px): conf_landmark={c_low:.3f} | default_align={kp_default is not None} | low_align={kp_low is not None} | sim_unaligned={sim_unaligned:.4f} | sim_aligned={sim_aligned:.4f}")

if __name__ == "__main__":
    asyncio.run(test())
