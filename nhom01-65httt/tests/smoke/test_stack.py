"""Smoke test: kiểm tra toàn bộ hệ thống sau `docker compose up`.

Chạy:  pytest -m smoke
Đọc cấu hình từ tệp .env (nếu có), nếu không dùng giá trị mặc định của .env.example.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.smoke

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env.example", ".env"):  # .env ghi đè .env.example
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


ENV = load_env()


def http_get(url: str, timeout: int = 10) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def connect(user: str, password: str, dbname: str | None = None):
    return psycopg.connect(
        host="127.0.0.1",
        port=int(ENV.get("POSTGRES_PORT", "5432")),
        user=user,
        password=password,
        dbname=dbname or ENV.get("POSTGRES_DB", "bi_dw"),
        connect_timeout=5,
    )


# ---------- Dịch vụ HTTP ----------


def test_backend_health_va_ket_noi_db():
    status, body = http_get(f"http://127.0.0.1:{ENV.get('BACKEND_PORT', '8000')}/health")
    assert status == 200
    assert json.loads(body) == {"status": "ok", "database": "ok"}


def test_frontend_tra_trang():
    status, body = http_get(f"http://127.0.0.1:{ENV.get('FRONTEND_PORT', '5173')}/")
    assert status == 200
    assert '<div id="root">' in body


def test_superset_health():
    status, _ = http_get(f"http://127.0.0.1:{ENV.get('SUPERSET_PORT', '8088')}/health")
    assert status == 200


def test_n8n_health():
    status, _ = http_get(f"http://127.0.0.1:{ENV.get('N8N_PORT', '5678')}/healthz")
    assert status == 200


# ---------- PostgreSQL ----------


def test_cac_schema_ton_tai():
    with connect(ENV["POSTGRES_USER"], ENV["POSTGRES_PASSWORD"]) as conn:
        rows = conn.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('raw','stg','dw','app')"
        ).fetchall()
    assert {r[0] for r in rows} == {"raw", "stg", "dw", "app"}


def test_bang_dq_log_ton_tai():
    with connect(ENV["POSTGRES_USER"], ENV["POSTGRES_PASSWORD"]) as conn:
        row = conn.execute("SELECT to_regclass('dw.dq_log')").fetchone()
    assert row[0] is not None


def test_database_phu_cho_superset_va_n8n_ton_tai():
    with connect(ENV["POSTGRES_USER"], ENV["POSTGRES_PASSWORD"]) as conn:
        rows = conn.execute(
            "SELECT datname FROM pg_database WHERE datname IN ('superset','n8n')"
        ).fetchall()
    assert {r[0] for r in rows} == {"superset", "n8n"}


def test_tai_khoan_chi_doc_doc_duoc_dw_nhung_khong_ghi_duoc():
    with connect("bi_readonly", ENV["BI_READONLY_PASSWORD"]) as conn:
        conn.execute("SELECT count(*) FROM dw.dq_log").fetchone()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO dw.dq_log (layer, check_name, severity, passed) "
                "VALUES ('dw', 'x', 'info', true)"
            )


def test_tai_khoan_chi_doc_khong_tao_duoc_bang_trong_raw():
    with connect("bi_readonly", ENV["BI_READONLY_PASSWORD"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE raw.should_fail (id int)")


def test_tai_khoan_ung_dung_ghi_duoc_app_nhung_khong_ghi_duoc_dw():
    with connect("bi_app", ENV["BI_APP_PASSWORD"]) as conn:
        conn.execute("CREATE TEMP TABLE app_probe (id int)")  # tài khoản đăng nhập được
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO dw.dq_log (layer, check_name, severity, passed) "
                "VALUES ('dw', 'x', 'info', true)"
            )
        conn.rollback()
        conn.execute("CREATE TABLE app.smoke_probe (id int)")
        conn.execute("INSERT INTO app.smoke_probe VALUES (1)")
        conn.rollback()  # không để lại dấu vết


def test_mui_gio_he_thong_la_gmt_7():
    with connect(ENV["POSTGRES_USER"], ENV["POSTGRES_PASSWORD"]) as conn:
        tz = conn.execute("SHOW timezone").fetchone()[0]
    assert tz in ("Asia/Ho_Chi_Minh", "Asia/Saigon", "Asia/Bangkok")
