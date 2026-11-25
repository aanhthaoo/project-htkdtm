"""Kết nối PostgreSQL, ghi hàng loạt (upsert) và nhật ký chạy cho lớp thu thập."""

import json
import logging
import os
from datetime import date
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]  # thư mục nhom01-65httt
SQL_DIR = Path(__file__).parent / "sql"


def load_env() -> dict[str, str]:
    """Đọc .env.example rồi .env (ghi đè) rồi biến môi trường (ghi đè cuối)."""
    values: dict[str, str] = {}
    for name in (".env.example", ".env"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip()
    values.update({k: v for k, v in os.environ.items() if k in values or k.startswith("POSTGRES")})
    return values


def connect() -> psycopg.Connection:
    env = load_env()
    return psycopg.connect(
        host=env.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        dbname=env.get("POSTGRES_DB", "bi_dw"),
        connect_timeout=10,
    )


def apply_ddl(conn: psycopg.Connection) -> None:
    conn.execute((SQL_DIR / "raw_tables.sql").read_text(encoding="utf-8"))
    conn.commit()


def dedupe_rows(rows: list[tuple], key_idx: tuple[int, ...]) -> list[tuple]:
    """Giữ dòng cuối cùng cho mỗi khóa (INSERT ... ON CONFLICT không chấp nhận khóa lặp trong một lệnh)."""
    seen: dict[tuple, tuple] = {}
    for row in rows:
        seen[tuple(row[i] for i in key_idx)] = row
    return list(seen.values())


def copy_upsert(
    conn: psycopg.Connection,
    table: str,
    columns: list[str],
    rows: list[tuple],
    key_cols: list[str],
    update_cols: list[str] | None = None,
) -> int:
    """Nạp hàng loạt bằng COPY vào bảng tạm rồi upsert. Chạy lại không nhân đôi dữ liệu."""
    if not rows:
        return 0
    key_idx = tuple(columns.index(c) for c in key_cols)
    rows = dedupe_rows(rows, key_idx)
    update_cols = update_cols or [c for c in columns if c not in key_cols]
    cols = ", ".join(columns)
    tmp = "tmp_" + table.replace(".", "_")
    set_parts = [f"{c} = EXCLUDED.{c}" for c in update_cols]
    # Các bảng raw luôn có cột fetched_at: cập nhật thời điểm lấy khi ghi đè
    if "fetched_at" not in columns and table.startswith("raw."):
        set_parts.append("fetched_at = now()")
    conflict_action = f"DO UPDATE SET {', '.join(set_parts)}" if set_parts else "DO NOTHING"
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE {tmp} (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
        with cur.copy(f"COPY {tmp} ({cols}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
        cur.execute(
            f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {tmp} "
            f"ON CONFLICT ({', '.join(key_cols)}) {conflict_action}"
        )
    conn.commit()
    return len(rows)


def jdump(obj) -> str | None:
    """Chuỗi JSON cho cột jsonb (loại ký tự NUL mà PostgreSQL không nhận)."""
    if obj in (None, {}, []):
        return None
    return json.dumps(obj, ensure_ascii=False).replace("\\u0000", "")


def clean_text(value: str | None) -> str | None:
    return value.replace("\x00", "") if isinstance(value, str) else value


# ----- Nhật ký chạy (tiếp tục từ chỗ dừng) -----


def is_done(conn: psycopg.Connection, source: str, task: str, window_key: str) -> bool:
    row = conn.execute(
        "SELECT status FROM raw.ingestion_run WHERE source=%s AND task=%s AND window_key=%s",
        (source, task, window_key),
    ).fetchone()
    return bool(row and row[0] == "done")


def mark_run(
    conn: psycopg.Connection,
    source: str,
    task: str,
    window_key: str,
    status: str,
    rows_loaded: int | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO raw.ingestion_run (source, task, window_key, status, rows_loaded, error, finished_at)
        VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s = 'running' THEN NULL ELSE now() END)
        ON CONFLICT (source, task, window_key) DO UPDATE
        SET status = EXCLUDED.status, rows_loaded = EXCLUDED.rows_loaded, error = EXCLUDED.error,
            started_at = CASE WHEN EXCLUDED.status = 'running' THEN now() ELSE raw.ingestion_run.started_at END,
            finished_at = EXCLUDED.finished_at
        """,
        (source, task, window_key, status, rows_loaded, error, status),
    )
    conn.commit()


def month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Các cửa sổ theo tháng dương lịch, từ tháng của `start` đến tháng của `end`."""
    windows = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        first = date(y, m, 1)
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        last = date(ny, nm, 1).fromordinal(date(ny, nm, 1).toordinal() - 1)
        windows.append((max(first, start), min(last, end)))
        y, m = ny, nm
    return windows
