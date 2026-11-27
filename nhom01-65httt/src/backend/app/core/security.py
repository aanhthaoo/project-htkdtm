"""Băm mật khẩu (bcrypt) và token JWT."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_token(user_id: int, role: str, ttl_minutes: int | None = None) -> tuple[str, int]:
    """Trả (token, số giây hiệu lực)."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.jwt_ttl_minutes if ttl_minutes is None else ttl_minutes)
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_token(token: str) -> dict:
    """Ném jwt.ExpiredSignatureError / jwt.InvalidTokenError nếu token hết hạn hoặc sai."""
    return jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
