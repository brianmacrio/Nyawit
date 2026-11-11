"""Keamanan dasar: kata sandi, sesi, peran, CSRF, batas laju, dan header keamanan.

* Kata sandi: PBKDF2-SHA256 210.000 iterasi + salt acak (pustaka standar Python).
* Sesi: token bertanda tangan HMAC-SHA256 di cookie HttpOnly + SameSite=Lax (tidak bisa dibaca JavaScript).
* CSRF: permintaan yang mengubah data wajib membawa header `X-Requested-With: PasporKebun`.
  Situs lain tidak bisa menambahkan header ini tanpa izin CORS.
* Peran: koperasi, pengepul, pabrik, verifikator, admin. Setiap endpoint tulis menyebut peran yang boleh.
* Batas laju: login, AI, dan unggah foto dibatasi per alamat IP.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from .config import COOKIE_SECURE, SECRET_KEY, SESSION_HOURS
from .db import get_db
from .models import User

COOKIE = "pk_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "PasporKebun"
ROLES = ("koperasi", "pengepul", "pabrik", "verifikator", "admin")
ROLE_LABEL = {
    "koperasi": "Petugas koperasi",
    "pengepul": "Pengepul",
    "pabrik": "Pabrik kelapa sawit",
    "verifikator": "Verifikator independen",
    "admin": "Admin",
}

# ---------------------------------------------------------------- kata sandi
_ITER = 210_000


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, it, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), base64.b64decode(salt_b64), int(it))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- token sesi
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: User) -> str:
    payload = _b64(json.dumps({"uid": user.id, "role": user.role, "exp": int(time.time()) + SESSION_HOURS * 3600},
                              separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".")
        good = _b64(hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(payload))
        return data if data.get("exp", 0) > time.time() else None
    except Exception:  # noqa: BLE001
        return None


def cookie_secure(request: Request) -> bool:
    if COOKIE_SECURE in ("1", "true"):
        return True
    if COOKIE_SECURE in ("0", "false"):
        return False
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


# ---------------------------------------------------------------- dependensi peran
def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    tok = request.cookies.get(COOKIE)
    data = read_token(tok) if tok else None
    if not data:
        return None
    u = db.get(User, data["uid"])
    return u if u and u.active else None


def require(*roles: str):
    """Dependensi FastAPI: wajib masuk, dan (bila disebut) berperan salah satu dari `roles`. Admin selalu boleh."""

    def dep(user: User | None = Depends(current_user)) -> User:
        if user is None:
            raise HTTPException(401, "Silakan masuk terlebih dahulu.")
        if roles and user.role not in roles and user.role != "admin":
            allowed = ", ".join(ROLE_LABEL[r].lower() for r in roles)
            raise HTTPException(403, f"Fitur ini untuk {allowed}. Anda masuk sebagai {ROLE_LABEL[user.role].lower()}.")
        return user

    return dep


def user_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "name": u.display_name, "role": u.role,
            "role_label": ROLE_LABEL.get(u.role, u.role), "collector_id": u.collector_id,
            "organisation": u.organisation, "is_demo": u.is_demo}


# ---------------------------------------------------------------- batas laju
class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, request: Request, key: str, limit: int, per_s: int) -> None:
        ip = request.client.host if request.client else "?"
        now = time.time()
        with self._lock:
            q = self._hits[(key, ip)]
            while q and q[0] < now - per_s:
                q.popleft()
            if len(q) >= limit:
                wait = int(per_s - (now - q[0])) + 1
                raise HTTPException(429, f"Terlalu banyak permintaan. Coba lagi dalam {wait} detik.")
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limit(key: str, limit: int, per_s: int):
    def dep(request: Request) -> None:
        limiter.check(request, key, limit, per_s)

    return dep


# ---------------------------------------------------------------- middleware
CSP = ("default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; font-src 'self' data:; connect-src 'self'; media-src 'self' blob:; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


class SecurityMiddleware(BaseHTTPMiddleware):
    """Header keamanan untuk semua respons + pemeriksaan CSRF untuk permintaan yang mengubah data."""

    async def dispatch(self, request: Request, call_next):
        if (request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/")
                and request.headers.get(CSRF_HEADER) != CSRF_VALUE):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Permintaan ditolak: header keamanan (CSRF) tidak ada."}, status_code=403)
        resp = await call_next(request)
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(self), geolocation=(self), microphone=()")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            h.setdefault("Content-Security-Policy", CSP)
        if cookie_secure(request):
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        return resp
