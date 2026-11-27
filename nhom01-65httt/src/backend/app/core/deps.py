"""Phụ thuộc dùng chung cho router: người dùng hiện tại, phân quyền theo vai trò, khóa dịch vụ, phân trang.

Vai trò: guest (chưa đăng nhập) < investor < admin. `require_role("investor")` cho phép investor và admin.
"""

import hmac
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.config import get_settings
from app.core.errors import ApiError
from app.core.security import decode_token
from app.db import get_engine

bearer = HTTPBearer(auto_error=False)
ROLE_RANK = {"guest": 0, "investor": 1, "admin": 2}


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    full_name: str
    role: str


def get_optional_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser | None:
    """Người dùng từ token; None nếu không gửi token (khách). Token sai hoặc hết hạn thì lỗi 401."""
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(401, "token_expired", "Phiên đăng nhập đã hết hạn") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "invalid_token", "Token không hợp lệ") from exc
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, email, full_name, role, is_active FROM app.users WHERE id = :id"),
            {"id": int(payload["sub"])},
        ).first()
    if row is None or not row.is_active:
        raise ApiError(401, "invalid_token", "Tài khoản không tồn tại hoặc đã bị khóa")
    return CurrentUser(row.id, row.email, row.full_name, row.role)


OptionalUser = Annotated[CurrentUser | None, Depends(get_optional_user)]


def require_role(min_role: str):
    """Dependency yêu cầu vai trò tối thiểu. Khách chưa đăng nhập: 401; đã đăng nhập nhưng thiếu quyền: 403."""
    if min_role not in ROLE_RANK:
        raise ValueError(min_role)

    def dependency(user: OptionalUser) -> CurrentUser | None:
        if min_role == "guest":
            return user
        if user is None:
            raise ApiError(401, "not_authenticated", "Cần đăng nhập để dùng chức năng này")
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise ApiError(403, "forbidden", "Tài khoản không đủ quyền để dùng chức năng này")
        return user

    return dependency


InvestorUser = Annotated[CurrentUser, Depends(require_role("investor"))]
AdminUser = Annotated[CurrentUser, Depends(require_role("admin"))]


def require_service_key(x_service_key: Annotated[str | None, Header()] = None) -> None:
    """Webhook nội bộ (n8n, bộ chạy ETL) gửi khóa dịch vụ ở header X-Service-Key."""
    expected = get_settings().service_key
    if not x_service_key or not hmac.compare_digest(x_service_key, expected):
        raise ApiError(401, "invalid_service_key", "Khóa dịch vụ không hợp lệ")


ServiceCall = Depends(require_service_key)


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page, page_size)


Pagination = Annotated[PageParams, Depends(page_params)]
