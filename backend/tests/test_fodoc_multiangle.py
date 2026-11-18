# FODOC regression: auth, multi-angle enroll-face, enrollment status, pipeline greedy match, retro match, admin, export
import io
import os
import time
import uuid

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@fodoc.ac.id", "Admin@123")
BUDI = ("budi@fodoc.ac.id", "Budi@123")
PANITIA = ("panitia@fodoc.ac.id", "Panitia@123")
GROUP = "/app/tests/group.jpg"
REF = "/app/tests/ref.jpg"
STATE = {}

mdb = MongoClient("mongodb://localhost:27017")["fodoc_db"]


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def H(t):
    return {"Authorization": f"Bearer {t}"}


def ref_bytes():
    return open(REF, "rb").read()


def three(front=None, right=None, left=None):
    rb = ref_bytes()
    return {
        "front": ("f.jpg", front or rb, "image/jpeg"),
        "right": ("r.jpg", right or rb, "image/jpeg"),
        "left": ("l.jpg", left or rb, "image/jpeg"),
    }


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)["access_token"]


@pytest.fixture(scope="module")
def panitia_tok():
    return login(*PANITIA)["access_token"]


@pytest.fixture(scope="module")
def budi():
    return login(*BUDI)


# --- Auth
class TestAuth:
    def test_roles_login(self):
        for creds, role in [(ADMIN, "admin"), (PANITIA, "panitia"), (BUDI, "mahasiswa")]:
            r = requests.post(f"{API}/auth/login", json={"email": creds[0], "password": creds[1]})
            assert r.status_code == 200
            assert r.json()["user"]["role"] == role
            assert "access_token" in r.json()
            sc = r.headers.get("set-cookie", "")
            assert "access_token=" in sc and "HttpOnly" in sc

    def test_register_and_reject_admin(self):
        s = uuid.uuid4().hex[:6]
        for role in ("mahasiswa", "panitia"):
            r = requests.post(f"{API}/auth/register", json={"email": f"test_{role}_{s}@fodoc.ac.id", "password": "Test@123", "name": f"TEST {role}", "role": role})
            assert r.status_code == 200, r.text
            assert r.json()["user"]["role"] == role
        r = requests.post(f"{API}/auth/register", json={"email": f"test_admin_{s}@fodoc.ac.id", "password": "Test@123", "name": "x", "role": "admin"})
        assert r.status_code == 400

    def test_bcrypt_hash(self):
        u = mdb.users.find_one({"email": "admin@fodoc.ac.id"})
        assert u["password_hash"].startswith("$2b$")


# --- Enroll face multi-angle
class TestEnroll:
    def test_enroll_ok(self, budi):
        r = requests.post(f"{API}/auth/enroll-face", files=three(), headers=H(budi["access_token"]), timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert [p["angle"] for p in d["profiles"]] == ["front", "right", "left"]
        docs = list(mdb.user_face_profiles.find({"user_id": budi["user"]["id"]}))
        assert len(docs) == 3
        assert sorted(x["angle"] for x in docs) == ["front", "left", "right"]

    def test_reenroll_replaces(self, budi):
        r = requests.post(f"{API}/auth/enroll-face", files=three(), headers=H(budi["access_token"]), timeout=120)
        assert r.status_code == 200
        assert mdb.user_face_profiles.count_documents({"user_id": budi["user"]["id"]}) == 3

    def test_group_photo_rejected_nothing_saved(self, budi):
        before = [str(x["_id"]) for x in mdb.user_face_profiles.find({"user_id": budi["user"]["id"]})]
        r = requests.post(f"{API}/auth/enroll-face", files=three(right=open(GROUP, "rb").read()), headers=H(budi["access_token"]), timeout=120)
        assert r.status_code == 400
        assert r.json()["detail"].startswith("Hadap Kanan: Terdeteksi lebih dari satu wajah")
        after = [str(x["_id"]) for x in mdb.user_face_profiles.find({"user_id": budi["user"]["id"]})]
        assert before == after

    def test_blank_rejected(self, budi):
        b = io.BytesIO(); Image.new("RGB", (300, 300), (120, 160, 200)).save(b, "JPEG")
        r = requests.post(f"{API}/auth/enroll-face", files=three(front=b.getvalue()), headers=H(budi["access_token"]), timeout=120)
        assert r.status_code == 400
        assert r.json()["detail"] == "Hadap Depan: Tidak ada wajah terdeteksi"

    def test_missing_slot_422(self, budi):
        f = three(); f.pop("left")
        r = requests.post(f"{API}/auth/enroll-face", files=f, headers=H(budi["access_token"]), timeout=60)
        assert r.status_code == 422

    def test_panitia_403(self, panitia_tok):
        r = requests.post(f"{API}/auth/enroll-face", files=three(), headers=H(panitia_tok), timeout=60)
        assert r.status_code == 403

    def test_status_and_files(self, budi):
        tok = budi["access_token"]
        st = requests.get(f"{API}/enrollment/status", headers=H(tok)).json()
        assert st["enrolled"] is True
        assert len(st["profiles"]) == 3
        for p in st["profiles"]:
            assert p["angle"] in ("front", "right", "left")
            assert isinstance(p["confidence"], float)
            r = requests.get(f"{BASE_URL}{p['image_url']}?auth={tok}")
            assert r.status_code == 200 and r.headers["content-type"].startswith("image/jpeg")
            assert requests.get(f"{BASE_URL}{p['image_url']}").status_code == 401


# --- Pipeline + gallery + retro
class TestPipeline:
    def test_upload_process(self, panitia_tok, budi):
        r = requests.post(f"{API}/events", json={"name": "TEST_Event Multiangle", "location": "Aula"}, headers=H(panitia_tok))
        assert r.status_code == 200
        eid = r.json()["id"]; STATE["eid"] = eid
        r = requests.post(f"{API}/events/{eid}/photos", files={"files": ("group.jpg", open(GROUP, "rb"), "image/jpeg")}, headers=H(panitia_tok), timeout=60)
        assert r.status_code == 200 and r.json()["count"] == 1
        pid = r.json()["uploaded"][0]["id"]; STATE["pid"] = pid
        photo = None
        for _ in range(30):
            time.sleep(3)
            ph = requests.get(f"{API}/events/{eid}/photos", headers=H(panitia_tok)).json()
            photo = ph[0]
            if photo["status"] in ("done", "failed"):
                break
        assert photo["status"] == "done", photo
        assert 6 <= photo["face_count"] <= 8, photo["face_count"]
        budi_matches = mdb.matches.count_documents({"photo_id": pid, "user_id": budi["user"]["id"]})
        assert budi_matches == 1
        STATE["match_count"] = photo["match_count"]

    def test_gallery_and_notif(self, budi):
        tok = budi["access_token"]
        g = requests.get(f"{API}/me/gallery", headers=H(tok)).json()
        assert any(x["id"] == STATE["pid"] for x in g)
        n = requests.get(f"{API}/me/notifications", headers=H(tok)).json()
        assert any(x.get("photo_id") == STATE["pid"] for x in n)

    def test_photo_detail(self, budi):
        d = requests.get(f"{API}/photos/{STATE['pid']}", headers=H(budi["access_token"])).json()
        assert len(d["faces"]) >= 6
        assert any(m["user_id"] == budi["user"]["id"] for m in d["matches"])

    def test_retro_match(self, admin_tok):
        s = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/auth/register", json={"email": f"test_retro_{s}@fodoc.ac.id", "password": "Test@123", "name": "TEST Retro", "role": "mahasiswa"})
        tok = r.json()["access_token"]; uid = r.json()["user"]["id"]
        r = requests.post(f"{API}/auth/enroll-face", files=three(), headers=H(tok), timeout=120)
        assert r.status_code == 200
        g = requests.get(f"{API}/me/gallery", headers=H(tok)).json()
        assert any(x["id"] == STATE["pid"] for x in g)
        requests.delete(f"{API}/admin/users/{uid}", headers=H(admin_tok))


# --- Admin
class TestAdmin:
    def test_threshold(self, admin_tok):
        assert requests.get(f"{API}/admin/threshold", headers=H(admin_tok)).json()["threshold"] == 0.4
        assert requests.post(f"{API}/admin/threshold", json={"threshold": 0.5}, headers=H(admin_tok)).json()["threshold"] == 0.5
        assert requests.get(f"{API}/admin/threshold", headers=H(admin_tok)).json()["threshold"] == 0.5
        requests.post(f"{API}/admin/threshold", json={"threshold": 0.4}, headers=H(admin_tok))
        assert requests.get(f"{API}/admin/threshold", headers=H(admin_tok)).json()["threshold"] == 0.4
        assert requests.post(f"{API}/admin/threshold", json={"threshold": 1.5}, headers=H(admin_tok)).status_code == 422

    def test_stats_users_role(self, admin_tok):
        st = requests.get(f"{API}/admin/stats", headers=H(admin_tok)).json()
        assert st["enrolled_students"] >= 1 and st["similarity_threshold"] == 0.4
        users = requests.get(f"{API}/admin/users", headers=H(admin_tok)).json()
        t = [u for u in users if u["email"].startswith("test_mahasiswa_")]
        assert t
        uid = t[0]["id"]
        assert requests.patch(f"{API}/admin/users/{uid}/role", json={"role": "panitia"}, headers=H(admin_tok)).status_code == 200
        users = requests.get(f"{API}/admin/users", headers=H(admin_tok)).json()
        assert [u for u in users if u["id"] == uid][0]["role"] == "panitia"

    # Export source: admin-only RBAC + valid small zip without secrets/weights
    def test_export_zip_rbac(self, panitia_tok, budi):
        assert requests.get(f"{API}/dev/download-project-source", timeout=60).status_code == 401
        assert requests.get(f"{API}/dev/download-project-source", headers=H(panitia_tok), timeout=60).status_code == 403
        assert requests.get(f"{API}/dev/download-project-source", headers=H(budi["access_token"]), timeout=60).status_code == 403

    def test_export_zip_admin_valid(self, admin_tok):
        import zipfile
        r = requests.get(f"{API}/dev/download-project-source", headers=H(admin_tok), timeout=120)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert "fodoc_project_source.zip" in r.headers.get("content-disposition", "")
        assert len(r.content) < 5 * 1024 * 1024
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        assert zf.testzip() is None
        names = zf.namelist()
        assert "backend/server.py" in names
        assert "backend/ml_services/models/README_MODELS.txt" in names
        assert any(n.startswith("frontend/src/") for n in names)
        assert not any(n.endswith(".env") or os.path.basename(n) == ".env" for n in names)
        assert not any(n.endswith((".pt", ".pth")) for n in names)

    # Greedy: match_count never exceeds enrolled students
    def test_match_count_le_enrolled(self, admin_tok):
        st = requests.get(f"{API}/admin/stats", headers=H(admin_tok)).json()
        if "match_count" in STATE:
            assert STATE["match_count"] <= st["enrolled_students"]
        for p in mdb.photos.find({"status": "done"}):
            uids = [m["user_id"] for m in mdb.matches.find({"photo_id": p["id"]})]
            assert len(uids) == len(set(uids)), p["id"]

    def test_cleanup(self, admin_tok):
        users = requests.get(f"{API}/admin/users", headers=H(admin_tok)).json()
        for u in users:
            if u["email"].startswith("test_"):
                requests.delete(f"{API}/admin/users/{u['id']}", headers=H(admin_tok))
        # TEST_ event kept so budi's gallery has a photo for UI tests; delete via DELETE /api/events/{id}
