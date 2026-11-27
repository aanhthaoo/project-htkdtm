"""Kết nối PostgreSQL cho backend: đọc schema dw, ghi schema app."""

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

MIGRATIONS = Path(__file__).parent / "migrations"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.environ["DATABASE_URL"]
    return create_engine(url, pool_pre_ping=True)


def check_database() -> None:
    """Chạy một truy vấn đơn giản; ném ngoại lệ nếu không kết nối được."""
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


def run_migrations() -> None:
    """Áp dụng các tệp SQL trong app/migrations theo thứ tự tên (idempotent)."""
    with get_engine().begin() as conn:
        for sql_file in sorted(MIGRATIONS.glob("*.sql")):
            conn.exec_driver_sql(sql_file.read_text(encoding="utf-8"))
