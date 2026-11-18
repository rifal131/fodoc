# Iteration 3: per-account lockout (XFF-proof, atomic), event delete cascade notifications
import os
import time
import uuid
import concurrent.futures as cf
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
GROUP = "/app/tests/group.jpg"


def _register():
    email = f"test_lock3_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Right@123", "name": "TEST L3", "role": "mahasiswa"})
    assert r.status_code == 200, r.text
    return email


def _login(email, pw, headers=None):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, headers=headers or {})


# ---- Lockout: XFF spoofing ----
class TestLockoutXFF:
    def test_rotating_xff_wrong_attempts_still_count(self):
        email = _register()
        codes = []
        for i in range(5):
            r = _login(email, "wrong", headers={"X-Forwarded-For": f"10.0.0.{i}", "X-Real-IP": f"10.1.0.{i}"})
            codes.append(r.status_code)
        assert codes == [401, 401, 401, 401, 429], codes
        r = _login(email, "Right@123", headers={"X-Forwarded-For": "1.2.3.4"})
        assert r.status_code == 429, r.text

    def test_correct_pw_spoofed_xff_while_locked(self):
        email = _register()
        for _ in range(5):
            _login(email, "wrong")
        for ip in ("1.2.3.4", "8.8.8.8, 9.9.9.9", "127.0.0.1"):
            r = _login(email, "Right@123", headers={"X-Forwarded-For": ip})
            assert r.status_code == 429, f"{ip}: {r.status_code}"


# ---- Lockout: concurrency ----
class TestLockoutConcurrency:
    def test_parallel_wrong_attempts_lock(self):
        email = _register()
        with cf.ThreadPoolExecutor(10) as ex:
            codes = list(ex.map(lambda _: _login(email, "wrong").status_code, range(10)))
        print("parallel codes:", sorted(codes))
        assert codes.count(401) <= 5, codes
        time.sleep(0.5)
        r = _login(email, "Right@123")
        print("after burst correct pw:", r.status_code, r.text[:100])
        assert r.status_code == 429, "Account not locked after 10 parallel wrong attempts"

    def test_parallel_burst_20_then_locked(self):
        email = _register()
        with cf.ThreadPoolExecutor(20) as ex:
            codes = list(ex.map(lambda _: _login(email, "wrong").status_code, range(20)))
        print("burst20 codes:", sorted(codes))
        time.sleep(0.5)
        r = _login(email, "Right@123")
        print("after burst20 correct pw:", r.status_code)
        assert r.status_code == 429


# ---- Event delete cascades notifications ----
def test_delete_event_removes_notifications():
    tok = _login("budi@fodoc.ac.id", "Budi@123").json()["access_token"]
    ptok = _login("panitia@fodoc.ac.id", "Panitia@123").json()["access_token"]
    atok = _login("admin@fodoc.ac.id", "Admin@123").json()["access_token"]
    ev = requests.post(f"{API}/events", json={"name": f"TEST_Del_{uuid.uuid4().hex[:5]}"},
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
    assert found, "notification not created"
    # non-admin cannot delete
    assert requests.delete(f"{API}/events/{ev['id']}", headers={"Authorization": f"Bearer {ptok}"}).status_code == 403
    d = requests.delete(f"{API}/events/{ev['id']}", headers={"Authorization": f"Bearer {atok}"})
    assert d.status_code == 200
    data = requests.get(f"{API}/me/notifications", headers={"Authorization": f"Bearer {tok}"}).json()
    assert not any(n["photo_id"] == pid for n in data), "notification still present after event delete"
    assert all(n.get("event_name") for n in data), "orphan notifications with null event_name remain"
    requests.post(f"{API}/me/notifications/read-all", headers={"Authorization": f"Bearer {tok}"})
