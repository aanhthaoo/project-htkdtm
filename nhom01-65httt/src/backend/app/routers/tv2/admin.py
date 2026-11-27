"""Trang quản trị: người dùng, nguồn thu thập, mô hình (module TV2). ETL và nhật ký chất lượng nằm ở core_admin_etl.py."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.deps import AdminUser, Pagination
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import Page, StubFlag

router = APIRouter(prefix="/api/admin", tags=["TV2: Quản trị"])


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserPatch(BaseModel):
    role: Literal["investor", "admin"] | None = None
    is_active: bool | None = None


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(user: AdminUser, p: Pagination):
    with get_engine().connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM app.users")).scalar_one()
        rows = conn.execute(
            text(
                "SELECT id, email, full_name, role, is_active, created_at, last_login_at FROM app.users "
                "ORDER BY id LIMIT :n OFFSET :o"
            ),
            {"n": p.page_size, "o": p.offset},
        ).all()
    return Page[AdminUserOut](
        items=[AdminUserOut(**r._mapping) for r in rows],
        page=p.page,
        page_size=p.page_size,
        total=total,
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user(user_id: int, body: AdminUserPatch, admin: AdminUser):
    if user_id == admin.id and (body.role == "investor" or body.is_active is False):
        raise ApiError(
            400, "self_demotion", "Không thể tự hạ quyền hoặc tự khóa tài khoản của mình"
        )
    sets, params = [], {"id": user_id}
    if body.role is not None:
        sets.append("role = :role")
        params["role"] = body.role
    if body.is_active is not None:
        sets.append("is_active = :active")
        params["active"] = body.is_active
    if not sets:
        raise ApiError(400, "nothing_to_update", "Không có trường nào để cập nhật")
    with get_engine().begin() as conn:
        row = conn.execute(
            text(
                f"UPDATE app.users SET {', '.join(sets)} WHERE id = :id "
                "RETURNING id, email, full_name, role, is_active, created_at, last_login_at"
            ),
            params,
        ).first()
    if row is None:
        raise ApiError(404, "not_found", "Không có người dùng này")
    return AdminUserOut(**row._mapping)


class Source(BaseModel):
    code: str
    name: str
    kind: str
    is_enabled: bool
    note: str


class SourcePut(BaseModel):
    is_enabled: bool
    note: str = ""


@router.get("/sources", response_model=list[Source])
def list_sources(user: AdminUser):
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT code, name, kind, is_enabled, note FROM app.data_sources ORDER BY code")
        ).all()
    return [Source(**r._mapping) for r in rows]


@router.put("/sources/{code}", response_model=Source)
def put_source(code: str, body: SourcePut, user: AdminUser):
    with get_engine().begin() as conn:
        row = conn.execute(
            text(
                "UPDATE app.data_sources SET is_enabled = :e, note = :n, updated_at = now() WHERE code = :c "
                "RETURNING code, name, kind, is_enabled, note"
            ),
            {"e": body.is_enabled, "n": body.note, "c": code},
        ).first()
    if row is None:
        raise ApiError(404, "not_found", "Không có nguồn này")
    return Source(**row._mapping)


class ModelInfo(BaseModel):
    model_key: int
    name: str
    task: str
    version: str
    trained_at: datetime
    train_range: str | None
    metrics: dict


class ModelsResponse(StubFlag):
    items: list[ModelInfo]


@router.get("/models", response_model=ModelsResponse)
def list_models(user: AdminUser):
    """Phiên bản và chỉ số các mô hình đã huấn luyện (dw.dim_model), mới nhất trước."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT model_key, name, task, version, trained_at, train_range, metrics "
                "FROM dw.dim_model ORDER BY trained_at DESC, model_key DESC"
            )
        ).all()
    return ModelsResponse(stub=False, items=[ModelInfo(**r._mapping) for r in rows])
