"""Nhúng dashboard Superset vào website, có phân quyền theo vai trò (lõi, TV1).

Mỗi dashboard được đăng ký trong DASHBOARDS: khóa dùng ở frontend, slug trong Superset, vai trò tối thiểu.
TV3 thêm dashboard mới bằng cách thêm một dòng vào DASHBOARDS (và bật "Nhúng" cho dashboard trong Superset
bằng src/superset/provision.py).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.core import superset_client
from app.core.deps import ROLE_RANK, OptionalUser
from app.core.errors import ApiError

router = APIRouter(prefix="/api/superset", tags=["Superset"])

DASHBOARDS: dict[str, dict] = {
    "overview": {
        "slug": "tong-quan-demo",
        "min_role": "guest",
        "title": "Tổng quan (khách xem được)",
    },
    "sector-rotation": {
        "slug": "luan-chuyen-nganh-demo",
        "min_role": "investor",
        "title": "Luân chuyển ngành (nhà đầu tư)",
    },
}


class DashboardInfo(BaseModel):
    key: str
    title: str
    min_role: str


class EmbedInfo(BaseModel):
    key: str
    dashboard_id: str
    superset_domain: str
    guest_token: str


@router.get("/dashboards", response_model=list[DashboardInfo])
def list_dashboards(user: OptionalUser):
    """Các dashboard người dùng hiện tại được xem."""
    rank = ROLE_RANK[user.role] if user else 0
    return [
        DashboardInfo(key=k, title=v["title"], min_role=v["min_role"])
        for k, v in DASHBOARDS.items()
        if ROLE_RANK[v["min_role"]] <= rank
    ]


@router.get("/embed/{key}", response_model=EmbedInfo)
def embed(key: str, user: OptionalUser):
    """Trả mã nhúng và guest token (hiệu lực ngắn, chỉ cho đúng dashboard này)."""
    cfg = DASHBOARDS.get(key)
    if cfg is None:
        raise ApiError(404, "not_found", "Không có dashboard này")
    if ROLE_RANK[cfg["min_role"]] > (ROLE_RANK[user.role] if user else 0):
        if user is None:
            raise ApiError(401, "not_authenticated", "Cần đăng nhập để xem dashboard này")
        raise ApiError(403, "forbidden", "Tài khoản không đủ quyền xem dashboard này")
    uuid = superset_client.embedded_uuid(cfg["slug"])
    username = f"web-{user.id}" if user else "web-guest"
    return EmbedInfo(
        key=key,
        dashboard_id=uuid,
        superset_domain=get_settings().superset_public_url,
        guest_token=superset_client.guest_token(uuid, username),
    )
