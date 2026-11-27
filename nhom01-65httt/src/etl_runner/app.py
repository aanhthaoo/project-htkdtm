"""Bộ chạy ETL: nhận yêu cầu chạy một bước hoặc cả chuỗi, chạy nền, ghi từng bước vào app.etl_runs.

Gọi bởi: n8n (workflow theo giờ, sau 15h, webhook chạy lại) và backend (trang quản trị). Xác thực bằng header
X-Service-Key. Mỗi lúc chỉ chạy một lần (tránh hai tiến trình cùng ghi dữ liệu); yêu cầu thêm nhận 409.

Công việc (JOBS) là danh sách bước; bước lỗi thì các bước sau của cùng công việc được bỏ qua.
Tin tức: bước `news` (làm sạch toàn bộ tin) mất 30-40 phút nên KHÔNG nằm trong `after_close`; chạy riêng ban đêm.
"""

import hmac
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

import psycopg
from fastapi import FastAPI, Header, HTTPException

SRC = os.environ.get("ETL_SRC_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
STEP_TIMEOUT_S = int(os.environ.get("ETL_STEP_TIMEOUT_S", str(3 * 3600)))

STEPS = {
    "rss": ["-m", "ingestion.cli", "rss"],
    "daily": ["-m", "ingestion.cli", "daily"],
    "news": ["-m", "etl.news.pipeline"],
    "dbt_run": ["dbt_dw/run.py", "run"],
    "dbt_test": ["dbt_dw/run.py", "test"],
    "quality": ["-m", "etl.quality_checks"],
}
JOBS: dict[str, list[str]] = {
    "rss": ["rss"],
    "daily": ["daily"],
    "news": ["news", "dbt_run"],
    "dbt": ["dbt_run"],
    "quality": ["dbt_test", "quality"],
    # Sau phiên (15h): cập nhật giá, quốc tế, VN-Index, tin mới -> dựng kho -> kiểm tra chất lượng
    "after_close": ["daily", "dbt_run", "dbt_test", "quality"],
}

_lock = threading.Lock()


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ.get("POSTGRES_DB", "bi_dw"),
        autocommit=True,
        connect_timeout=10,
    )


def check_key(key: str | None) -> None:
    expected = os.environ.get("SERVICE_KEY", "")
    if not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Khóa dịch vụ không hợp lệ")


def _update(
    run_id: int, steps: list[dict], status: str | None = None, log_tail: str | None = None
) -> None:
    with connect() as conn:
        if status:
            conn.execute(
                "UPDATE app.etl_runs SET steps = %s, status = %s, finished_at = now(), log_tail = %s WHERE id = %s",
                (json.dumps(steps), status, (log_tail or "")[-4000:], run_id),
            )
        else:
            conn.execute(
                "UPDATE app.etl_runs SET steps = %s WHERE id = %s", (json.dumps(steps), run_id)
            )


def execute(run_id: int, step_names: list[str]) -> None:
    steps: list[dict] = [{"name": n, "status": "pending"} for n in step_names]
    log_tail, failed = "", False
    try:
        for step in steps:
            if failed:
                step["status"] = "skipped"
                continue
            step["status"] = "running"
            _update(run_id, steps)
            started = time.time()
            try:
                proc = subprocess.run(  # noqa: S603 - lệnh cố định trong STEPS
                    [PY, *STEPS[step["name"]]],
                    cwd=SRC,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=STEP_TIMEOUT_S,
                    env={
                        **os.environ,
                        "PYTHONUTF8": "1",
                        "DBT_HOST": os.environ.get("POSTGRES_HOST", "postgres"),
                    },
                )
                output = (proc.stdout or "") + (proc.stderr or "")
                code = proc.returncode
            except subprocess.TimeoutExpired:
                output, code = f"Quá thời gian {STEP_TIMEOUT_S}s", -9
            step.update(
                status="success" if code == 0 else "failed",
                exit_code=code,
                seconds=round(time.time() - started, 1),
            )
            log_tail = f"[{step['name']}] " + output[-3000:]
            if code != 0:
                failed = True
            _update(run_id, steps)
    except Exception as exc:  # noqa: BLE001 - mọi lỗi bất ngờ vẫn phải ghi nhận
        failed = True
        log_tail = f"Lỗi bộ chạy: {exc!r}"
    finally:
        _update(run_id, steps, "failed" if failed else "success", log_tail)
        _lock.release()


def mark_interrupted() -> None:
    """Lần chạy còn 'running' từ trước khi bộ chạy khởi động lại chắc chắn đã bị cắt ngang."""
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE app.etl_runs SET status = 'failed', finished_at = now(), "
                "log_tail = 'Bị ngắt do bộ chạy ETL khởi động lại' WHERE status = 'running' AND trigger_type <> 'n8n'"
            )
    except psycopg.Error:
        pass  # bảng app.etl_runs do backend tạo; nếu chưa có thì không có gì để đánh dấu


@asynccontextmanager
async def lifespan(_: FastAPI):
    mark_interrupted()
    yield


app = FastAPI(title="ETL runner", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "busy": _lock.locked()}


@app.get("/jobs")
def list_jobs():
    return {"jobs": {name: steps for name, steps in JOBS.items()}}


@app.post("/jobs/{job}", status_code=202)
def start_job(
    job: str,
    trigger: str = "manual",
    requested_by: str | None = None,
    x_service_key: str | None = Header(default=None),
):
    check_key(x_service_key)
    if job not in JOBS:
        raise HTTPException(
            status_code=404, detail=f"Không có công việc {job}. Có: {', '.join(JOBS)}"
        )
    if trigger not in {"manual", "schedule", "n8n", "admin"}:
        raise HTTPException(status_code=422, detail="trigger không hợp lệ")
    if not _lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Đang có một lần chạy ETL khác")
    try:
        with connect() as conn:
            run_id = conn.execute(
                "INSERT INTO app.etl_runs (job, trigger_type, requested_by, steps) VALUES (%s, %s, %s, %s) RETURNING id",
                (
                    job,
                    trigger,
                    requested_by,
                    json.dumps([{"name": n, "status": "pending"} for n in JOBS[job]]),
                ),
            ).fetchone()[0]
        threading.Thread(target=execute, args=(run_id, JOBS[job]), daemon=True).start()
    except Exception:
        _lock.release()
        raise
    return {
        "run_id": run_id,
        "job": job,
        "status": "running",
        "started_at": datetime.now().isoformat(),
    }


@app.get("/jobs/{run_id}")
def get_run(run_id: int, x_service_key: str | None = Header(default=None)):
    check_key(x_service_key)
    with connect() as conn:
        row = conn.execute(
            "SELECT id, job, trigger_type, status, requested_by, started_at, finished_at, steps, log_tail "
            "FROM app.etl_runs WHERE id = %s",
            (run_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Không có lần chạy này")
    keys = [
        "id",
        "job",
        "trigger_type",
        "status",
        "requested_by",
        "started_at",
        "finished_at",
        "steps",
        "log_tail",
    ]
    return {
        k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in zip(keys, row, strict=True)
    }
