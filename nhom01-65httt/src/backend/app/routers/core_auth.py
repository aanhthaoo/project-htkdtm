"""Đăng ký, đăng nhập, thông tin tài khoản (lõi, do TV1 phụ trách)."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.deps import InvestorUser
from app.core.errors import ApiError
from app.core.security import create_token, hash_password, verify_password
from app.db import get_engine

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Tối thiểu 8 ký tự")
    full_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Số giây token còn hiệu lực")
    user: UserOut


def _auth_response(row) -> AuthResponse:
    token, ttl = create_token(row.id, row.role)
    return AuthResponse(
        access_token=token,
        expires_in=ttl,
        user=UserOut(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            role=row.role,
            created_at=getattr(row, "created_at", None),
        ),
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest):
    """Đăng ký tài khoản nhà đầu tư. Mật khẩu được băm bằng bcrypt, không lưu dạng thô."""
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                text(
                    "INSERT INTO app.users (email, password_hash, full_name, role) "
                    "VALUES (:email, :hash, :name, 'investor') "
                    "RETURNING id, email, full_name, role, created_at"
                ),
                {
                    "email": body.email.lower(),
                    "hash": hash_password(body.password),
                    "name": body.full_name.strip(),
                },
            ).one()
    except IntegrityError as exc:
        raise ApiError(409, "email_taken", "Email này đã được đăng ký") from exc
    return _auth_response(row)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    with get_engine().begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, email, full_name, role, created_at, password_hash, is_active "
                "FROM app.users WHERE lower(email) = :email"
            ),
            {"email": body.email.lower()},
        ).first()
        # Cùng một thông báo cho "sai email" và "sai mật khẩu" để không lộ email nào đã đăng ký
        if row is None or not verify_password(body.password, row.password_hash):
            raise ApiError(401, "invalid_credentials", "Email hoặc mật khẩu không đúng")
        if not row.is_active:
            raise ApiError(403, "account_disabled", "Tài khoản đã bị khóa")
        conn.execute(
            text("UPDATE app.users SET last_login_at = now() WHERE id = :id"), {"id": row.id}
        )
    return _auth_response(row)


@router.get("/me", response_model=UserOut)
def me(user: InvestorUser):
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
