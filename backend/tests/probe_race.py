# Probe: can concurrent in-flight wrong attempts clear locked_until (unlocking the account)?
import os, uuid, time, requests, concurrent.futures as cf
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

def login(e, p):
    return requests.post(f"{API}/auth/login", json={"email": e, "password": p})

unlocked = 0
for trial in range(5):
    e = f"test_race_{uuid.uuid4().hex[:8]}@example.com"
    requests.post(f"{API}/auth/register", json={"email": e, "password": "Right@123", "name": "TEST R", "role": "mahasiswa"})
    with cf.ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda _: login(e, "wrong").status_code, range(30)))
    time.sleep(0.3)
    r = login(e, "Right@123")
    print(f"trial {trial}: 401s={codes.count(401)} 429s={codes.count(429)} -> correct pw: {r.status_code}")
    if r.status_code == 200:
        unlocked += 1
print("UNLOCKED trials:", unlocked)
