"""Chạy dbt với cấu hình lấy từ .env.   Ví dụ (từ thư mục src/dbt_dw):  python run.py build"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))  # để import ingestion.db

from ingestion import db  # noqa: E402


def main() -> int:
    env = {**os.environ, **{k: v for k, v in db.load_env().items() if k.startswith("POSTGRES")}}
    env["DBT_PROFILES_DIR"] = str(HERE)
    env["PYTHONUTF8"] = "1"  # dbt đọc tệp bằng mã hóa mặc định của Windows nếu không bật UTF-8
    env["PYTHONIOENCODING"] = "utf-8"
    exe = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    cmd = [str(exe), *sys.argv[1:]]
    return subprocess.call(cmd, cwd=HERE, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
