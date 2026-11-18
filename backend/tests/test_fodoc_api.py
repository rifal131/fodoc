# FODOC backend regression tests: auth, enrollment, events, ML pipeline, gallery, notifications, admin, role guards, files, export
import io
import os
import time
import uuid

import pytest
import requests
from PIL import Image

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


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def blank_jpg():
    b = io.BytesIO()
    Image.new("RGB", (300, 300), (120, 160, 200)).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def panitia_tok():
    return login(*PANITIA)


@pytest.fixture(scope="module")
def budi_tok():
    return login(*BUDI)


# --- Auth
class TestAuth:
    def test_login_cookies_and_me(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "admin" and isinstance(d["access_token"], str)
        sc = r.headers.get("set-cookie", "").lower()
        assert "access_token=" in sc and "httponly" in sc
        me = requests.get(f"{API}/auth/me", headers=H(d["access_token"]))
        assert me.status_code == 200 and me.json()["email"] == ADMIN[0]
        assert "password_hash" not in me.json()

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": "wrong"})
        assert r.status_code == 401

    def test_me_unauth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_register_mahasiswa_panitia_and_reject_admin(self):
        sfx = uuid.uuid4().hex[:6]
        for role in ("mahasiswa", "panitia"):
            email = f"test_{role}_{sfx}@fodoc.ac.id"
            r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@123", "name": f"TEST {role}", "role": role})
            assert r.status_code == 200, r.text
            assert r.json()["user"]["role"] == role
            STATE.setdefault("cleanup_users", []).append(r.json()["user"]["id"])
            # login with new account
            assert login(email, "Test@123")
        r = requests.post(f"{API}/auth/register", json={"email": f"test_admin_{sfx}@fodoc.ac.id", "password": "Test@123", "name": "x", "role": "admin"})
        assert r.status_code == 400
        # duplicate
        r = requests.post(f"{API}/auth/register", json={"email": f"test_mahasiswa_{sfx}@fodoc.ac.id", "password": "Test@123", "name": "x", "role": "mahasiswa"})
        assert r.status_code == 400

    def test_logout(self):
        r = requests.post(f"{API}/auth/logout")
        assert r.status_code == 200 and r.json()["ok"] is True


# --- Role guards
class TestRoleGuards:
    def test_mahasiswa_cannot_create_event(self, budi_tok):
        assert requests.post(f"{API}/events", json={"name": "x"}, headers=H(budi_tok)).status_code == 403

    def test_mahasiswa_panitia_cannot_admin(self, budi_tok, panitia_tok):
        for tok in (budi_tok, panitia_tok):
            assert requests.get(f"{API}/admin/stats", headers=H(tok)).status_code == 403
            assert requests.get(f"{API}/admin/users", headers=H(tok)).status_code == 403
            assert requests.post(f"{API}/admin/threshold", json={"threshold": 0.5}, headers=H(tok)).status_code == 403

    def test_panitia_cannot_enroll(self, panitia_tok):
        with open(REF, "rb") as f:
            r = requests.post(f"{API}/enrollment/upload", files={"file": ("ref.jpg", f, "image/jpeg")}, headers=H(panitia_tok))
        assert r.status_code == 403


# --- Enrollment
class TestEnrollment:
    def test_enroll_no_face_400(self, budi_tok):
        r = requests.post(f"{API}/enrollment/upload", files={"file": ("blank.jpg", blank_jpg(), "image/jpeg")}, headers=H(budi_tok), timeout=60)
        assert r.status_code == 400, r.text

    def test_enroll_ref_ok(self, budi_tok):
        with open(REF, "rb") as f:
            r = requests.post(f"{API}/enrollment/upload", files={"file": ("ref.jpg", f, "image/jpeg")}, headers=H(budi_tok), timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True and len(d["face_box"]) == 4
        STATE["ref_url"] = d["reference_url"]
        st = requests.get(f"{API}/enrollment/status", headers=H(budi_tok)).json()
        assert st["enrolled"] is True


# --- Files
class TestFiles:
    def test_file_requires_auth(self, budi_tok):
        url = STATE.get("ref_url")
        if not url:
            pytest.skip("no ref url")
        assert requests.get(f"{BASE_URL}{url}").status_code == 401
        r = requests.get(f"{BASE_URL}{url}?auth={budi_tok}", timeout=60)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/")


# --- Events + pipeline + gallery + retro-match
class TestPipeline:
    def test_create_event(self, panitia_tok):
        r = requests.post(f"{API}/events", json={"name": "TEST_Backend Event", "description": "d", "location": "Aula"}, headers=H(panitia_tok))
        assert r.status_code == 200, r.text
        STATE["event_id"] = r.json()["id"]
        g = requests.get(f"{API}/events/{STATE['event_id']}", headers=H(panitia_tok))
        assert g.status_code == 200 and g.json()["name"] == "TEST_Backend Event"

    def test_upload_and_process(self, panitia_tok):
        eid = STATE["event_id"]
        with open(GROUP, "rb") as f:
            r = requests.post(f"{API}/events/{eid}/photos", files=[("files", ("group.jpg", f, "image/jpeg"))], headers=H(panitia_tok), timeout=120)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 1
        pid = r.json()["uploaded"][0]["id"]
        STATE["photo_id"] = pid
        statuses = set()
        photo = None
        for _ in range(45):
            ps = requests.get(f"{API}/events/{eid}/photos", headers=H(panitia_tok)).json()
            photo = next(p for p in ps if p["id"] == pid)
            statuses.add(photo["status"])
            if photo["status"] in ("done", "failed"):
                break
            time.sleep(2)
        print("statuses seen:", statuses, "photo:", {k: photo[k] for k in ("status", "face_count", "match_count")})
        assert photo["status"] == "done"
        assert 5 <= photo["face_count"] <= 9
        assert photo["match_count"] == 1  # only budi enrolled, greedy rule
        ev = requests.get(f"{API}/events/{eid}", headers=H(panitia_tok)).json()
        assert ev["photo_count"] == 1

    def test_photo_detail_matches(self, budi_tok):
        r = requests.get(f"{API}/photos/{STATE['photo_id']}", headers=H(budi_tok))
        assert r.status_code == 200
        d = r.json()
        assert len(d["matches"]) == 1 and d["matches"][0]["name"]
        assert len(d["faces"]) == d["face_count"]
        assert d["image_width"] and d["image_height"]

    def test_gallery_and_notifications(self, budi_tok):
        g = requests.get(f"{API}/me/gallery", headers=H(budi_tok)).json()
        assert any(p["id"] == STATE["photo_id"] for p in g)
        n = requests.get(f"{API}/me/notifications", headers=H(budi_tok)).json()
        assert any(x.get("photo_id") == STATE["photo_id"] for x in n)
        assert requests.post(f"{API}/me/notifications/read-all", headers=H(budi_tok)).status_code == 200

    def test_retro_match_new_student(self):
        email = f"test_retro_{uuid.uuid4().hex[:6]}@fodoc.ac.id"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@123", "name": "TEST Retro", "role": "mahasiswa"})
        assert r.status_code == 200
        tok = r.json()["access_token"]
        STATE.setdefault("cleanup_users", []).append(r.json()["user"]["id"])
        with open(REF, "rb") as f:
            e = requests.post(f"{API}/enrollment/upload", files={"file": ("ref.jpg", f, "image/jpeg")}, headers=H(tok), timeout=60)
        assert e.status_code == 200
        g = requests.get(f"{API}/me/gallery", headers=H(tok)).json()
        assert any(p["id"] == STATE["photo_id"] for p in g)
        n = requests.get(f"{API}/me/notifications", headers=H(tok)).json()
        assert len(n) >= 1


# --- Admin
class TestAdmin:
    def test_stats(self, admin_tok):
        r = requests.get(f"{API}/admin/stats", headers=H(admin_tok))
        assert r.status_code == 200
        for k in ("users_total", "enrolled_students", "photos_total", "faces_total", "matches_total", "similarity_threshold"):
            assert k in r.json()

    def test_threshold_persist(self, admin_tok):
        orig = requests.get(f"{API}/admin/threshold", headers=H(admin_tok)).json()["threshold"]
        assert requests.post(f"{API}/admin/threshold", json={"threshold": 0.55}, headers=H(admin_tok)).status_code == 200
        assert requests.get(f"{API}/admin/threshold", headers=H(admin_tok)).json()["threshold"] == 0.55
        assert requests.post(f"{API}/admin/threshold", json={"threshold": 1.5}, headers=H(admin_tok)).status_code == 422
        requests.post(f"{API}/admin/threshold", json={"threshold": orig}, headers=H(admin_tok))

    def test_role_change_and_delete(self, admin_tok):
        email = f"test_role_{uuid.uuid4().hex[:6]}@fodoc.ac.id"
        uid = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@123", "name": "TEST Role", "role": "mahasiswa"}).json()["user"]["id"]
        assert requests.patch(f"{API}/admin/users/{uid}/role", json={"role": "panitia"}, headers=H(admin_tok)).status_code == 200
        users = requests.get(f"{API}/admin/users", headers=H(admin_tok)).json()
        assert next(u for u in users if u["id"] == uid)["role"] == "panitia"
        assert requests.patch(f"{API}/admin/users/{uid}/role", json={"role": "bogus"}, headers=H(admin_tok)).status_code == 400
        assert requests.delete(f"{API}/admin/users/{uid}", headers=H(admin_tok)).status_code == 200
        users = requests.get(f"{API}/admin/users", headers=H(admin_tok)).json()
        assert not any(u["id"] == uid for u in users)

    def test_cannot_delete_self(self, admin_tok):
        me = requests.get(f"{API}/auth/me", headers=H(admin_tok)).json()
        assert requests.delete(f"{API}/admin/users/{me['id']}", headers=H(admin_tok)).status_code == 400

    def test_invalid_object_id_handling(self, admin_tok):
        r = requests.delete(f"{API}/admin/users/not-an-id", headers=H(admin_tok))
        assert r.status_code in (400, 404), f"got {r.status_code}"


# --- Export
class TestExport:
    def test_export_zip_headers(self):
        r = requests.get(f"{API}/dev/download-project-source", stream=True, timeout=180)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert "fodoc_project_source.zip" in r.headers.get("content-disposition", "")
        chunk = next(r.iter_content(4))
        assert chunk[:2] == b"PK"
        r.close()


# --- Cleanup
class TestZCleanup:
    def test_cleanup(self, admin_tok):
        for uid in STATE.get("cleanup_users", []):
            requests.delete(f"{API}/admin/users/{uid}", headers=H(admin_tok))
        if STATE.get("event_id"):
            assert requests.delete(f"{API}/events/{STATE['event_id']}", headers=H(admin_tok)).status_code == 200
