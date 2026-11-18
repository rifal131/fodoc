# FODOC Auth Testing Playbook

## MongoDB checks
```
mongosh fodoc_db
db.users.findOne({role: "admin"}, {password_hash: 1})   // hash starts with $2b$
db.users.getIndexes()                                  // email unique
db.login_attempts.getIndexes()                         // identifier
db.login_attempts.find()                               // {identifier: "<ip>:<email>", count, locked_until}
```

## API
```
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@fodoc.ac.id","password":"Admin@123"}'
curl -b cookies.txt $API/api/auth/me
```

## Brute-force lockout
- 5 failed attempts per account (identifier = lowercase email, IP-independent, atomic $inc). Attempts 1-4 return 401 "Email atau password salah. Sisa percobaan: N". The 5th returns 429 and locks the account for 15 minutes.
- Spoofed X-Forwarded-For headers must NOT bypass the lock.
- While locked, even the correct password returns 429 "Akun dikunci sementara ...".
- A successful login clears the counter.
- Use a throwaway account for lockout tests. To unlock manually: `db.login_attempts.deleteMany({})`.
