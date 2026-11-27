"""Cấu hình backend đọc từ biến môi trường (docker-compose truyền vào từ .env)."""

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Thiếu biến môi trường {name}")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_ttl_minutes: int
    service_key: str  # khóa dịch vụ cho webhook nội bộ (n8n, bộ chạy ETL)
    admin_email: str | None  # tài khoản quản trị tạo sẵn khi khởi động (nếu có)
    admin_password: str | None
    demo_email: str | None  # tài khoản nhà đầu tư mẫu tạo sẵn (nếu có)
    demo_password: str | None
    superset_url: str  # địa chỉ Superset trong mạng Docker
    superset_public_url: str  # địa chỉ trình duyệt dùng để tải iframe
    superset_admin_user: str
    superset_admin_password: str
    etl_runner_url: str


def get_settings() -> Settings:
    return Settings(
        database_url=_env("DATABASE_URL"),
        jwt_secret=_env("JWT_SECRET"),
        jwt_ttl_minutes=int(_env("JWT_TTL_MINUTES", "60")),
        service_key=_env("SERVICE_KEY"),
        admin_email=os.environ.get("APP_ADMIN_EMAIL") or None,
        admin_password=os.environ.get("APP_ADMIN_PASSWORD") or None,
        demo_email=os.environ.get("APP_DEMO_EMAIL") or None,
        demo_password=os.environ.get("APP_DEMO_PASSWORD") or None,
        superset_url=_env("SUPERSET_URL", "http://superset:8088"),
        superset_public_url=_env("SUPERSET_PUBLIC_URL", "http://localhost:8088"),
        superset_admin_user=_env("SUPERSET_ADMIN_USER", "admin"),
        superset_admin_password=os.environ.get("SUPERSET_ADMIN_PASSWORD", ""),
        etl_runner_url=_env("ETL_RUNNER_URL", "http://etl-runner:8100"),
    )
