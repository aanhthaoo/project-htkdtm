"""Gói dữ liệu seed: xuất và phục hồi cơ sở dữ liệu để thành viên mới (hoặc máy mới) không phải thu thập lại từ đầu.

Hai loại gói (tệp `pg_dump -Fc` nén, nằm ở `data/seed/`, KHÔNG đưa vào git vì lớn; chia sẻ qua ổ đĩa nhóm):
  dev   chỉ schema `dw` (kho đã dựng, kèm kết quả mô hình): đủ cho TV2-TV5 làm backend, frontend, Superset. Phục hồi vài phút.
  full  schema `raw` + `stg` + `dw`: đủ để chạy lại dbt, ETL tin tức và mô hình từ dữ liệu thô (dùng khi kiểm tra từ đầu).

Chạy từ `src/` khi hệ thống đang chạy (docker compose up):
    python -m handover.seed export dev                     # -> data/seed/dw_dev.dump
    python -m handover.seed export full                    # -> data/seed/full_raw_stg_dw.dump
    python -m handover.seed restore data/seed/dw_dev.dump  # vào cơ sở dữ liệu đang chạy (xóa schema tương ứng trước)
    python -m handover.seed restore <tệp> --project htkdtm_verify   # vào một dự án compose khác (kiểm tra tách biệt)

Sau khi phục hồi: `python -m ingestion.cli init-db` (tạo bảng raw mới nếu có), `python dbt_dw/run.py seed` rồi
`python dbt_dw/run.py run` nếu gói cũ hơn mã. Tài khoản website (schema app) KHÔNG nằm trong gói: backend tự tạo tài khoản mẫu khi khởi động.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "seed"
PACKAGES = {
    "dev": ("dw_dev.dump", ["dw"]),
    "full": ("full_raw_stg_dw.dump", ["raw", "stg", "dw"]),
}
DB, USER = "bi_dw", "bi_admin"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True)


def container(project: str) -> str:
    return f"{project}-postgres-1"


def export(kind: str, project: str) -> Path:
    name, schemas = PACKAGES[kind]
    ct = container(project)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    args = [
        "docker",
        "exec",
        ct,
        "pg_dump",
        "-U",
        USER,
        "-d",
        DB,
        "-Fc",
        "-Z",
        "4",
        "-f",
        "/tmp/seed.dump",
    ]
    for s in schemas:
        args += ["-n", s]
    run(args)
    out = SEED_DIR / name
    run(["docker", "cp", f"{ct}:/tmp/seed.dump", str(out)])
    run(["docker", "exec", ct, "rm", "-f", "/tmp/seed.dump"], check=False)
    print(f"Đã xuất {out} ({out.stat().st_size / 1e6:.0f} MB) trong {time.time() - start:.0f} giây")
    return out


def schemas_in_dump(ct: str) -> list[str]:
    """Các schema có trong tệp dump (đọc mục lục bằng pg_restore -l)."""
    out = subprocess.run(
        ["docker", "exec", ct, "pg_restore", "-l", "/tmp/seed.dump"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    return sorted({ln.split()[-2] for ln in out.splitlines() if " SCHEMA - " in ln})


def restore(path: Path, project: str) -> None:
    """Phục hồi: xóa và tạo lại các schema có trong gói, nạp dữ liệu, cấp lại quyền đọc cho bi_readonly và bi_app.

    Quyền mặc định do script khởi tạo (src/database/init/02-schemas.sql) gắn với schema nên bị mất khi xóa schema; hàm này đặt lại.
    """
    ct = container(project)
    start = time.time()
    run(["docker", "cp", str(path), f"{ct}:/tmp/seed.dump"])
    schemas = schemas_in_dump(ct)
    print("Schema trong gói:", schemas)

    def psql(sql: str) -> None:
        run(
            ["docker", "exec", ct, "psql", "-U", USER, "-d", DB, "-v", "ON_ERROR_STOP=1", "-c", sql]
        )

    for s in schemas:
        psql(f"DROP SCHEMA IF EXISTS {s} CASCADE")
        psql(f"CREATE SCHEMA {s}")
    if "dw" in schemas:
        psql("GRANT USAGE ON SCHEMA dw TO bi_readonly, bi_app")
        psql("ALTER DEFAULT PRIVILEGES IN SCHEMA dw GRANT SELECT ON TABLES TO bi_readonly, bi_app")
    proc = run(
        [
            "docker",
            "exec",
            ct,
            "pg_restore",
            "-U",
            USER,
            "-d",
            DB,
            "-j",
            "4",
            "--no-owner",
            "--no-privileges",
            "/tmp/seed.dump",
        ],
        check=False,
    )  # lỗi "schema already exists" khi nạp CREATE SCHEMA là bình thường vì đã tạo ở trên
    if "dw" in schemas:
        psql("GRANT SELECT ON ALL TABLES IN SCHEMA dw TO bi_readonly, bi_app")
    run(["docker", "exec", ct, "rm", "-f", "/tmp/seed.dump"], check=False)
    print(
        f"Đã phục hồi {path.name} vào {ct} trong {time.time() - start:.0f} giây (pg_restore mã {proc.returncode})"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export")
    p.add_argument("kind", choices=sorted(PACKAGES))
    p.add_argument("--project", default="htkdtm_nhom01")
    p = sub.add_parser("restore")
    p.add_argument("file")
    p.add_argument("--project", default="htkdtm_nhom01")
    args = parser.parse_args()
    if args.cmd == "export":
        export(args.kind, args.project)
    else:
        restore(Path(args.file), args.project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
