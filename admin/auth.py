"""
Admin authentication: username/password login, hashed with passlib/bcrypt,
signed session cookie via itsdangerous. Replaces the old shared "?token="
link with a real per-admin login.

The cookie payload is just {"admin_id": <id>}, signed and time-limited by
itsdangerous.URLSafeTimedSerializer - not a JWT, no separate library needed
for this single-admin-account scale.
"""
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from config import config
from storage import store

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _serializer():
    if not config.ADMIN_SESSION_SECRET:
        raise RuntimeError(
            "ADMIN_SESSION_SECRET is not set in .env - generate a random string "
            "(e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`) and set it."
        )
    return URLSafeTimedSerializer(config.ADMIN_SESSION_SECRET, salt="admin-session")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_session_cookie_value(admin_id: int) -> str:
    return _serializer().dumps({"admin_id": admin_id})


def _read_session_cookie(cookie_value: str | None):
    if not cookie_value:
        return None
    try:
        data = _serializer().loads(cookie_value, max_age=config.ADMIN_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("admin_id")


def get_current_admin(request: Request):
    """FastAPI dependency: raises 401 (redirected to login by the route
    handler's caller) if there's no valid session, otherwise returns the
    admin dict. Every /admin/* route (except /admin/login) depends on this."""
    cookie_value = request.cookies.get(config.ADMIN_SESSION_COOKIE)
    admin_id = _read_session_cookie(cookie_value)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    admin = store.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return admin


def try_get_current_admin(request: Request):
    """Same as get_current_admin but returns None instead of raising -
    used on the login page to redirect an already-logged-in admin away."""
    cookie_value = request.cookies.get(config.ADMIN_SESSION_COOKIE)
    admin_id = _read_session_cookie(cookie_value)
    if not admin_id:
        return None
    return store.get_admin_by_id(admin_id)
