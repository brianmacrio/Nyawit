from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEMO_ACCOUNTS, SESSION_HOURS
from ..db import get_db
from ..models import User
from ..schemas import DemoLoginIn, LoginIn
from ..security import COOKIE, ROLE_LABEL, cookie_secure, current_user, make_token, rate_limit, user_dict, verify_password
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["Akun"])


def _set_session(resp: Response, request: Request, user: User) -> None:
    resp.set_cookie(COOKIE, make_token(user), max_age=SESSION_HOURS * 3600, httponly=True, samesite="lax",
                    secure=cookie_secure(request), path="/")


@router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    # pesan sama untuk nama salah dan kata sandi salah (tidak membocorkan akun mana yang ada)
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Nama pengguna atau kata sandi salah.")
    _set_session(response, request, u)
    audit.log_user(db, u, "masuk", "akun", u.id, f"{u.display_name} masuk")
    db.commit()
    return user_dict(u)


@router.post("/demo", dependencies=[Depends(rate_limit("demo", 30, 60))])
def demo_login(body: DemoLoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Masuk satu klik untuk akun demo (khusus penilaian juri; dimatikan dengan PK_DEMO_ACCOUNTS=0)."""
    if not DEMO_ACCOUNTS:
        raise HTTPException(404, "Akun demo dinonaktifkan.")
    u = db.scalar(select(User).where(User.username == body.username, User.is_demo.is_(True)))
    if not u or not u.active:
        raise HTTPException(404, "Akun demo tidak ditemukan.")
    _set_session(response, request, u)
    return user_dict(u)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"detail": "Keluar"}


@router.get("/me")
def me(user: User | None = Depends(current_user)):
    return {"user": user_dict(user) if user else None}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    if not DEMO_ACCOUNTS:
        return []
    rows = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.id))
    return [{"username": u.username, "name": u.display_name, "role": u.role, "role_label": ROLE_LABEL[u.role],
             "organisation": u.organisation} for u in rows]
