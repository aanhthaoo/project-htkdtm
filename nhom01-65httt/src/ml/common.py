"""Phần dùng chung của các mô hình: kết nối, đăng ký mô hình vào dw.dim_model, ghi kết quả vào dw.

Chạy các mô hình từ thư mục src/:  python -m ml.clustering   python -m ml.forecast
"""

import json
import logging
from datetime import UTC, datetime

import pandas as pd
import psycopg

from ingestion import db

log = logging.getLogger("ml")
SEED = 20261126


def connect() -> psycopg.Connection:
    return db.connect()


def read_sql(conn: psycopg.Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        columns = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def register_model(
    conn: psycopg.Connection,
    name: str,
    task: str,
    version: str,
    train_range: str,
    metrics: dict,
) -> int:
    """Thêm một dòng vào dw.dim_model và trả model_key. Mỗi lần huấn luyện là một dòng mới (không ghi đè)."""
    with conn.cursor() as cur:
        cur.execute("SELECT coalesce(max(model_key), 0) + 1 FROM dw.dim_model")
        model_key = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO dw.dim_model (model_key, name, task, version, trained_at, train_range, metrics) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                model_key,
                name,
                task,
                version,
                datetime.now(UTC),
                train_range,
                json.dumps(metrics, default=float),
            ),
        )
    conn.commit()
    return model_key


def to_jsonable(obj):
    """Chuyển numpy/pandas sang kiểu JSON thuần (dùng cho cột metrics)."""
    return json.loads(json.dumps(obj, default=float))
