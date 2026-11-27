"""Điểm vào của backend FastAPI.

Cấu trúc router (mỗi người một thư mục, không sửa lõi):
  routers/core_*.py  lõi do TV1 phụ trách: đăng nhập, nhúng Superset, ETL/nhật ký chất lượng, webhook nội bộ, API mô hình
  routers/tv2/       mã cổ phiếu, theo dõi, cảnh báo, chatbot, quản trị
  routers/tv3/       thị trường, ngành, top mã gom/xả
  routers/tv4/       dự báo, độ chính xác, khuyến nghị
  routers/tv5/       tin tức, vĩ mô
Thêm router mới: tạo tệp trong thư mục của mình rồi thêm một dòng `app.include_router(...)` ở dưới.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import db
from app.config import get_settings
from app.core.errors import install_error_handlers
from app.core.security import hash_password
from app.routers import core_admin_etl, core_auth, core_superset
from app.routers.tv2 import admin as tv2_admin
from app.routers.tv2 import stocks_watch as tv2_stocks
from app.routers.tv3 import market_sectors as tv3_market
from app.routers.tv4 import predictions as tv4_predictions
from app.routers.tv5 import news_macro as tv5_news

log = logging.getLogger("app")


def _seed_user(email: str | None, password: str | None, role: str, full_name: str) -> None:
    if not (email and password):
        return
    with db.get_engine().begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM app.users WHERE lower(email) = :e"), {"e": email.lower()}
        ).first()
        if not exists:
            conn.execute(
                text(
                    "INSERT INTO app.users (email, password_hash, full_name, role) "
                    "VALUES (:e, :h, :n, :r)"
                ),
                {"e": email.lower(), "h": hash_password(password), "n": full_name, "r": role},
            )
            log.info("Đã tạo tài khoản %s (%s)", email, role)


def seed_users() -> None:
    """Tạo sẵn tài khoản quản trị (APP_ADMIN_*) và nhà đầu tư mẫu (APP_DEMO_*) nếu chưa có.
    Không ghi đè mật khẩu của tài khoản đã tồn tại."""
    s = get_settings()
    _seed_user(s.admin_email, s.admin_password, "admin", "Quản trị viên")
    _seed_user(s.demo_email, s.demo_password, "investor", "Nhà đầu tư mẫu")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.run_migrations()
    seed_users()
    yield


app = FastAPI(
    title="HTKDTM Nhom 01 - Backend",
    version="0.2.0",
    description="API website phân tích dòng tiền và luân chuyển ngành. Contract chốt: docs/openapi.json.",
    lifespan=lifespan,
)
install_error_handlers(app)


@app.get("/health", tags=["Hệ thống"])
def health():
    """Kiểm tra dịch vụ và kết nối cơ sở dữ liệu."""
    try:
        db.check_database()
    except Exception as exc:  # noqa: BLE001 - trả trạng thái lỗi thay vì làm sập dịch vụ
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "down", "detail": type(exc).__name__},
        )
    return {"status": "ok", "database": "ok"}


# Thứ tự quan trọng: /api/stocks/top-net (tv3) phải đứng trước /api/stocks/{symbol} (tv2)
app.include_router(core_auth.router)
app.include_router(core_superset.router)
app.include_router(core_admin_etl.admin)
app.include_router(core_admin_etl.internal)
app.include_router(core_admin_etl.ml)
app.include_router(tv3_market.router)
app.include_router(tv2_stocks.router)
app.include_router(tv2_admin.router)
app.include_router(tv4_predictions.router)
app.include_router(tv5_news.router)
