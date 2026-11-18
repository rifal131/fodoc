import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from storage import get_object
from server import _process_photo_task

load_dotenv(Path(__file__).parent / ".env")

async def reprocess_events():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    # Drop old matches and faces so clean matches are generated
    photos = await db.photos.find({}).to_list(200)
    print(f"Reprocessing {len(photos)} photos...")
    for idx, p in enumerate(photos, 1):
        pid = p["id"]
        eid = p["event_id"]
        fn = p["stored_filename"]
        # Clear old matches and faces for this photo
        await db.matches.delete_many({"photo_id": pid})
        await db.faces.delete_many({"photo_id": pid})
        data, _ = get_object(fn)
        if not data:
            print(f"[{idx}/{len(photos)}] File missing: {fn}")
            continue
        await _process_photo_task(pid, data, eid)
        print(f"[{idx}/{len(photos)}] Done: {pid}")

    print("All photos successfully reprocessed!")

if __name__ == "__main__":
    asyncio.run(reprocess_events())
