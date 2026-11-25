"""Kết nối PostgreSQL cho backend."""

import os
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.environ["DATABASE_URL"]
    return create_engine(url, pool_pre_ping=True)


def check_database() -> None:
    """Chạy một truy vấn đơn giản; ném ngoại lệ nếu không kết nối được."""
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
