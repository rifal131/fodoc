# Iteration 4: atomic lockout (race), sequential lockout, expiry, token precedence
import os, uuid, time, requests, pytest, concurrent.futures as cf
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = BASE_URL + "/api"
PW = "Right@123"
_mongo = MongoClient("mongodb://localhost:27017")["fodoc_db"]
CREATED = []


def login(e, p, headers=None):
    return requests.post(f"{API}/auth/login", json={"email": e, "password": p}, headers=headers or {})


def new_user():
    e = f"test_lock4_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": e, "password": PW, "name": "TEST L4", "role": "mahasiswa"})
    assert r.status_code in (200, 201), r.text
    CREATED.append(e)
    return e


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for e in CREATED:
        _mongo.users.delete_one({"email": e})
        _mongo.login_attempts.delete_one({"identifier": e})


# Race: 30 concurrent wrong attempts x 6 trials -> exactly 5 evaluated, stays locked
@pytest.mark.parametrize("trial", range(6))
def test_race_burst_stays_locked(trial):
    e = new_user()
    with cf.ThreadPoolExecutor(30) as ex:
        rs = list(ex.map(lambda _: login(e, "wrong"), range(30)))
    codes = [r.status_code for r in rs]
    lock_msgs = [r for r in rs if r.status_code == 429 and "Terlalu banyak" in r.json()["detail"]]
    time.sleep(0.3)
    final = login(e, PW)
    doc = _mongo.login_attempts.find_one({"identifier": e})
    print(f"trial {trial}: 401={codes.count(401)} 429={codes.count(429)} lockmsg={len(lock_msgs)} correct={final.status_code} doc={doc}")
    assert codes.count(401) == 4
    assert len(lock_msgs) == 1
    assert codes.count(429) == 26
    assert final.status_code == 429
    assert doc["locked_until"] is not None


# Sequential: 4/3/2/1 then 429, correct pw while locked -> 429
def test_sequential_lockout():
    e = new_user()
    for remaining in (4, 3, 2, 1):
        r = login(e, "wrong")
        assert r.status_code == 401
        assert f"Sisa percobaan: {remaining}" in r.json()["detail"]
    r = login(e, "wrong")
    assert r.status_code == 429 and "15 menit" in r.json()["detail"]
    r = login(e, PW)
    assert r.status_code == 429 and "Coba lagi dalam" in r.json()["detail"]


def test_success_resets_counter():
    e = new_user()
    for _ in range(4):
        assert login(e, "wrong").status_code == 401
    assert login(e, PW).status_code == 200
    r = login(e, "wrong")
    assert r.status_code == 401 and "Sisa percobaan: 4" in r.json()["detail"]


def test_spoofed_xff_cannot_bypass():
    e = new_user()
    for i in range(5):
        login(e, "wrong", {"X-Forwarded-For": f"10.0.0.{i}", "X-Real-IP": f"10.1.0.{i}"})
    r = login(e, PW, {"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8"})
    assert r.status_code == 429


def test_other_account_unaffected():
    a, b = new_user(), new_user()
    for _ in range(5):
        login(a, "wrong")
    assert login(a, PW).status_code == 429
    assert login(b, PW).status_code == 200


def test_expired_lock_reopens_with_fresh_counter():
    e = new_user()
    for _ in range(5):
        login(e, "wrong")
    assert login(e, PW).status_code == 429
    _mongo.login_attempts.update_one({"identifier": e}, {"$set": {"locked_until": datetime.now(timezone.utc) - timedelta(minutes=1)}})
    r = login(e, "wrong")
    assert r.status_code == 401 and "Sisa percobaan: 4" in r.json()["detail"]
    assert login(e, PW).status_code == 200


def test_expired_lock_correct_password():
    e = new_user()
    for _ in range(5):
        login(e, "wrong")
    _mongo.login_attempts.update_one({"identifier": e}, {"$set": {"locked_until": datetime.now(timezone.utc) - timedelta(seconds=5)}})
    assert login(e, PW).status_code == 200


def test_unique_index_on_identifier():
    idx = _mongo.login_attempts.index_information()
    assert any(v.get("key") == [("identifier", 1)] and v.get("unique") for v in idx.values())


# Token precedence: Bearer header wins over cookie
def test_bearer_wins_over_cookie():
    a, b = new_user(), new_user()
    s = requests.Session()
    ra = s.post(f"{API}/auth/login", json={"email": a, "password": PW})
    assert ra.status_code == 200 and "access_token" in s.cookies
    tb = login(b, PW).json()["access_token"]
    assert s.get(f"{API}/auth/me").json()["email"] == a
    me = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tb}"})
    assert me.status_code == 200 and me.json()["email"] == b
    bad = s.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401


def test_cookie_httponly_and_bcrypt():
    e = new_user()
    r = login(e, PW)
    sc = r.headers.get("set-cookie", "")
    assert "access_token=" in sc and "httponly" in sc.lower()
    assert _mongo.users.find_one({"email": e})["password_hash"].startswith("$2b$")
