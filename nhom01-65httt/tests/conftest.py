"""Cấu hình chung cho test: nạp biến môi trường mà backend cần (từ .env nếu có, nếu không dùng giá trị thử)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env.example", ".env"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip()
    return values


_env = _read_env()
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://bi_app:{pw}@127.0.0.1:{port}/{db}".format(
        pw=_env.get("BI_APP_PASSWORD", "change_me_app"),
        port=_env.get("POSTGRES_PORT", "5432"),
        db=_env.get("POSTGRES_DB", "bi_dw"),
    ),
)
os.environ.setdefault(
    "JWT_SECRET", _env.get("JWT_SECRET", "test-secret-test-secret-test-secret-123")
)
os.environ.setdefault("SERVICE_KEY", _env.get("SERVICE_KEY", "test-service-key"))
os.environ.setdefault("SUPERSET_URL", f"http://127.0.0.1:{_env.get('SUPERSET_PORT', '8088')}")
os.environ.setdefault("SUPERSET_ADMIN_USER", _env.get("SUPERSET_ADMIN_USER", "admin"))
os.environ.setdefault("SUPERSET_ADMIN_PASSWORD", _env.get("SUPERSET_ADMIN_PASSWORD", ""))
os.environ.setdefault("ETL_RUNNER_URL", f"http://127.0.0.1:{_env.get('ETL_RUNNER_PORT', '8100')}")
os.environ.setdefault("JWT_TTL_MINUTES", "60")
