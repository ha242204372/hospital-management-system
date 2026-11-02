"""Authentication controller: PBKDF2 password hashing and HTTP session management."""
import hashlib
import secrets
from http import cookies
from app.config import ApiError
from app.models.db import one, audit

SESSIONS = {}


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 60000).hex()
    return f"{salt}${h}"


def check_pw(pw, stored):
    salt, _ = stored.split("$")
    return secrets.compare_digest(hash_pw(pw, salt), stored)


def current_user(cookie_header):
    c = cookies.SimpleCookie(cookie_header or "")
    return SESSIONS.get(c["sid"].value) if "sid" in c else None


def handle_login(conn, body):
    u = one(conn, "SELECT * FROM users WHERE username=?", (body.get("username", ""),))
    if not u or not check_pw(body.get("password", ""), u["password_hash"]):
        raise ApiError(401, "Invalid username or password")
    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = {
        "id": u["id"],
        "username": u["username"],
        "full_name": u["full_name"],
        "role": u["role"],
        "patient_id": u.get("patient_id"),
    }
    audit(conn, SESSIONS[sid], "login", "")
    return {"ok": True}, {"Set-Cookie": f"sid={sid}; Path=/; HttpOnly; SameSite=Strict"}


def handle_logout(cookie_header):
    c = cookies.SimpleCookie(cookie_header or "")
    if "sid" in c:
        SESSIONS.pop(c["sid"].value, None)
    return {"ok": True}, {"Set-Cookie": "sid=; Path=/; Max-Age=0"}
