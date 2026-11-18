# Iteration 2: login lockout + notifications (photo_url/event_name) tests
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
GROUP = "/app/tests/group.jpg"


def _register(prefix="lock"):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Right@123", "name": "TEST Lock", "role": "mahasiswa"})
    assert r.status_code == 200, r.text
    return email


def _login(email, pw, headers=None):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, headers=headers or {})


# ---- Lockout ----
class TestLockout:
    def test_lockout_sequence(self):
        email = _register()
        for remaining in (4, 3, 2, 1):
            r = _login(email, "wrong")
            assert r.status_code == 401, r.text
            assert f"Sisa percobaan: {remaining}" in r.json()["detail"]
        r = _login(email, "wrong")
        assert r.status_code == 429
        assert r.json()["detail"] == "Terlalu banyak percobaan gagal. Akun dikunci selama 15 menit."
        r = _login(email, "Right@123")
        assert r.status_code == 429
        assert r.json()["detail"].startswith("Akun dikunci sementara")
        r = _login(email, "wrong")
        assert r.status_code == 429

    def test_success_resets_counter(self):
        email = _register()
        assert _login(email, "wrong").status_code == 401
        r = _login(email, "wrong")
        assert "Sisa percobaan: 3" in r.json()["detail"]
        r = _login(email, "Right@123")
        assert r.status_code == 200 and r.json()["access_token"]
        r = _login(email, "wrong")
        assert r.status_code == 401 and "Sisa percobaan: 4" in r.json()["detail"]
        assert _login(email, "Right@123").status_code == 200

    def test_other_email_not_affected(self):
        locked = _register()
        other = _register()
        for _ in range(5):
            _login(locked, "wrong")
        assert _login(locked, "Right@123").status_code == 429
        r = _login(other, "Right@123")
        assert r.status_code == 200

    def test_case_insensitive_email_shares_counter(self):
        email = _register()
        _login(email.upper(), "wrong")
        r = _login(email, "wrong")
        assert "Sisa percobaan: 3" in r.json()["detail"]
        _login(email, "Right@123")

    def test_nonexistent_email_returns_401_with_remaining(self):
        r = _login(f"nouser_{uuid.uuid4().hex[:6]}@example.com", "x")
        assert r.status_code == 401
        assert "Sisa percobaan: 4" in r.json()["detail"]

    def test_xff_spoof_bypass(self):
        """Security probe: does a client-supplied X-Forwarded-For bypass lockout?"""
        email = _register()
        for _ in range(5):
            _login(email, "wrong")
        r = _login(email, "Right@123", headers={"X-Forwarded-For": "1.2.3.4"})
        print("XFF spoof status:", r.status_code, r.text[:120])
        assert r.status_code == 429, "Lockout bypassable via spoofed X-Forwarded-For header"


# ---- Regression logins ----
@pytest.mark.parametrize("email,pw,role", [
    ("admin@fodoc.ac.id", "Admin@123", "admin"),
    ("panitia@fodoc.ac.id", "Panitia@123", "panitia"),
    ("budi@fodoc.ac.id", "Budi@123", "mahasiswa"),
])
def test_seed_login(email, pw, role):
    r = _login(email, pw)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == role
    assert "access_token" in r.cookies or any("access_token" in c for c in r.headers.get("set-cookie", "").split(";"))


# ---- Notifications ----
def test_notifications_have_photo_url_event_name():
    tok = _login("budi@fodoc.ac.id", "Budi@123").json()["access_token"]
    ptok = _login("panitia@fodoc.ac.id", "Panitia@123").json()["access_token"]
    ev = requests.post(f"{API}/events", json={"name": f"TEST_Notif_{uuid.uuid4().hex[:5]}"},
                       headers={"Authorization": f"Bearer {ptok}"}).json()
    with open(GROUP, "rb") as f:
        r = requests.post(f"{API}/events/{ev['id']}/photos", files=[("files", ("group.jpg", f, "image/jpeg"))],
                          headers={"Authorization": f"Bearer {ptok}"})
    assert r.status_code == 200
    pid = r.json()["uploaded"][0]["id"]
    found = None
    for _ in range(30):
        time.sleep(2)
        data = requests.get(f"{API}/me/notifications", headers={"Authorization": f"Bearer {tok}"}).json()
        found = next((n for n in data if n["photo_id"] == pid), None)
        if found:
            break
    assert found, "No notification created for budi"
    assert found["photo_url"].startswith("/api/files/")
    assert found["event_name"] == ev["name"]
    assert found["read"] is False
    img = requests.get(f"{BASE_URL}{found['photo_url']}?auth={tok}")
    print("photo fetch status", img.status_code)
    atok = _login("admin@fodoc.ac.id", "Admin@123").json()["access_token"]
    requests.delete(f"{API}/events/{ev['id']}", headers={"Authorization": f"Bearer {atok}"})
