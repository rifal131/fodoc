# Helper: panitia creates TEST event + uploads group.jpg after a delay (for UI toast tests)
import os, sys, time, uuid, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
time.sleep(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
t = requests.post(f"{API}/auth/login", json={"email": "panitia@fodoc.ac.id", "password": "Panitia@123"}).json()["access_token"]
h = {"Authorization": f"Bearer {t}"}
ev = requests.post(f"{API}/events", json={"name": f"TEST_UI3_{uuid.uuid4().hex[:5]}"}, headers=h).json()
with open("/app/tests/group.jpg", "rb") as f:
    r = requests.post(f"{API}/events/{ev['id']}/photos", files=[("files", ("group.jpg", f, "image/jpeg"))], headers=h)
print("event", ev["id"], ev["name"], "upload", r.status_code, flush=True)
