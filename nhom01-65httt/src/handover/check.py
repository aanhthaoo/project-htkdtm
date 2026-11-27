"""N10: kiểm tra 10 hạng mục của gói bàn giao giai đoạn 1 trên một hệ thống đang chạy, in bảng đạt/không đạt.

Chạy từ `src/` (hệ thống chính, cổng mặc định):
    python -m handover.check
Hệ thống kiểm tra tách biệt (cổng khác), ví dụ cổng 25432/28000:
    POSTGRES_PORT=25432 python -m handover.check --backend http://localhost:28000 --frontend http://localhost:25173 \
        --superset http://localhost:28088 --n8n http://localhost:25678 --etl-runner http://localhost:28100

Mỗi hạng mục chạy kiểm tra thật (truy vấn dw, gọi HTTP, chạy pytest theo nhóm), không đọc kết quả cũ. Mã thoát 0 khi cả 10 hạng mục đạt.
Hạng mục 9 gọi `POST /api/admin/etl/run` với job `quality` (nhanh, chỉ đọc) nên ghi thêm một dòng vào app.etl_runs.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # nhom01-65httt
SRC = ROOT / "src"

# Số dòng tối thiểu: khoảng 95% số dòng lúc bàn giao (27/11/2026: giá 2,49 triệu, dòng tiền 2,21 triệu, bài 315.701, quan hệ bài-mã/ngành 654.787).
# Chỉ để phát hiện nạp thiếu; số chính xác ở docs/thiet_ke_kho.md và docs/kiem_thu_tu_dau.md.
MIN_ROWS = {
    "dw.dim_stock": 1800,
    "dw.fact_daily_price": 2_400_000,
    "dw.fact_money_flow": 2_100_000,
    "dw.dim_article": 300_000,
    "dw.bridge_article_entity": 600_000,
    "dw.fact_news_sentiment": 500_000,
    "dw.fact_prediction": 3_000,
    "dw.fact_recommendation": 3_000,
    "dw.stock_cluster": 1_800,
    "dw.dim_model": 4,
}
FIRST_DAY, MIN_LAST_DAY_YEAR = "2020-09-01", 2026


@dataclass
class Item:
    no: int
    name: str
    ok: bool = False
    detail: str = ""
    seconds: float = 0.0


def http(
    method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 30
):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (
                json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode(errors="replace")
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw.decode(errors="replace")


def pytest(args: list[str], env_extra: dict | None = None) -> tuple[bool, str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(SRC), str(SRC / "backend"), str(ROOT)]),
        "PYTHONUTF8": "1",
        **(env_extra or {}),
    }
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    tail = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1:] or [
        "(không có đầu ra)"
    ]
    return proc.returncode == 0, tail[0]


def connect():
    sys.path.insert(0, str(SRC))
    from ingestion import db

    return db.connect()


def check_stack(args) -> tuple[bool, str]:
    """1. `docker compose up` chạy đủ dịch vụ: mọi cổng trả sống."""
    probes = {
        "backend": f"{args.backend}/health",
        "frontend": args.frontend,
        "superset": f"{args.superset}/health",
        "n8n": f"{args.n8n}/healthz",
        "etl-runner": f"{args.etl_runner}/health",
    }
    bad = []
    for name, url in probes.items():
        try:
            status, _ = http("GET", url, timeout=15)
            if status != 200:
                bad.append(f"{name}={status}")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{name}: {type(exc).__name__}")
    conn = connect()
    conn.execute("SELECT 1")
    conn.close()
    return not bad, "5 dịch vụ HTTP + PostgreSQL sống" if not bad else "; ".join(bad)


def check_warehouse(args) -> tuple[bool, str]:
    """2. dw có dữ liệu thật: số dòng và độ phủ thời gian đạt mức cam kết."""
    conn = connect()
    problems, shown = [], []
    for table, minimum in MIN_ROWS.items():
        n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        shown.append(f"{table.split('.')[1]}={n:,}")
        if n < minimum:
            problems.append(f"{table} {n:,} < {minimum:,}")
    first, last = conn.execute(
        "SELECT min(trade_date), max(trade_date) FROM dw.fact_daily_price"
    ).fetchone()
    if str(first) > FIRST_DAY:
        problems.append(f"giá bắt đầu {first} muộn hơn {FIRST_DAY}")
    if last.year < MIN_LAST_DAY_YEAR:
        problems.append(f"giá chỉ đến {last}")
    conn.close()
    return not problems, f"giá {first}..{last}; " + "; ".join(problems or shown[:5])


def check_superset(args) -> tuple[bool, str]:
    """3. Dataset và metric Superset khớp SQL gốc."""
    ok, tail = pytest(
        ["tests/smoke/test_superset.py", "-m", "smoke"], {"SUPERSET_URL": args.superset}
    )
    return ok, tail


def check_auth(args) -> tuple[bool, str]:
    """4. Khung backend: đăng nhập, phân quyền theo vai trò, nhúng Superset; frontend test."""
    ok, tail = pytest(
        [
            "tests/smoke/test_api.py",
            "-m",
            "smoke",
            "-k",
            "quyen or auth or dang or contract or superset or role or phan",
        ]
    )
    return ok, tail


def check_contract(args) -> tuple[bool, str]:
    """5. API contract chốt: openapi.json khớp API thực."""
    ok, tail = pytest(
        ["tests/smoke/test_api.py", "-m", "smoke", "-k", "openapi or contract or schema"]
    )
    return ok, tail


def check_ml_tables(args) -> tuple[bool, str]:
    """6. dw có kết quả mô hình và API mô hình trả đúng schema."""
    ok1, t1 = pytest(
        [
            "tests/smoke/test_ml_warehouse.py",
            "tests/smoke/test_ml_sentiment_warehouse.py",
            "-m",
            "smoke",
        ]
    )
    ok2, t2 = pytest(
        ["tests/smoke/test_api.py", "-m", "smoke", "-k", "mo_hinh or du_bao or khuyen_nghi"]
    )
    return ok1 and ok2, f"kho: {t1} | API: {t2}"


def check_sample_for_tv5(args) -> tuple[bool, str]:
    """7. Tập mẫu cảm xúc 300-500 bài cho TV5 đã xuất, có cột nhãn trống và hướng dẫn."""
    import csv

    path = ROOT / "data" / "samples" / "sentiment_validation_sample.csv"
    guide = ROOT / "docs" / "huong_dan_gan_nhan_cam_xuc.md"
    if not path.exists():
        return False, f"thiếu {path.name}: chạy python -m etl.news.samples (hoặc giải nén gói seed)"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    empty = sum(1 for r in rows if not (r.get("label_human") or "").strip())
    ok = (
        300 <= len(rows) <= 500
        and "label_human" in rows[0]
        and guide.exists()
        and empty == len(rows)
    )
    return (
        ok,
        f"{len(rows)} bài, {empty} chưa gán nhãn, hướng dẫn: {'có' if guide.exists() else 'THIẾU'}",
    )


def check_templates(args) -> tuple[bool, str]:
    """8. Bộ mẫu chạy được: trang React, router API, workflow n8n, CSV (bộ nạp kiểm tra tệp mẫu)."""
    need = [
        "src/frontend/src/pages/tv2/StocksPage.jsx",
        "src/frontend/src/pages/tv3/SectorsPage.jsx",
        "src/frontend/src/pages/tv4/ForecastPage.jsx",
        "src/frontend/src/pages/tv5/NewsPage.jsx",
        "src/backend/app/routers/tv2/stocks_watch.py",
        "src/backend/app/routers/tv3/market_sectors.py",
        "src/backend/app/routers/tv4/predictions.py",
        "src/backend/app/routers/tv5/news_macro.py",
        "src/n8n/workflows/etl-hourly.json",
        "src/n8n/workflows/etl-after-close.json",
        "src/n8n/workflows/etl-rerun-webhook.json",
        "src/n8n/workflows/alert-dispatch-sample.json",
        "src/ingestion/templates/macro_monthly.csv",
        "src/ingestion/templates/individual_investors_weekly.csv",
        "src/ingestion/templates/etf_flows_monthly.csv",
    ]
    missing = [p for p in need if not (ROOT / p).exists()]
    ok, tail = pytest(["tests/unit/test_manual_csv.py", "tests/unit/test_n8n_workflows_runner.py"])
    return (
        not missing and ok,
        f"{len(need) - len(missing)}/{len(need)} tệp mẫu; kiểm thử mẫu: {tail}"
        + (f"; thiếu {missing}" if missing else ""),
    )


def check_etl_rerun(args) -> tuple[bool, str]:
    """9. Endpoint chạy lại ETL ghi nhật ký: gọi job `quality`, chờ xong, kiểm tra app.etl_runs và dw.dq_log."""
    from_env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            from_env[k.strip()] = v.strip()
    email = os.environ.get("APP_ADMIN_EMAIL", from_env.get("APP_ADMIN_EMAIL", ""))
    password = os.environ.get("APP_ADMIN_PASSWORD", from_env.get("APP_ADMIN_PASSWORD", ""))
    status, body = http(
        "POST", f"{args.backend}/api/auth/login", {"email": email, "password": password}
    )
    if status != 200:
        return False, f"không đăng nhập được quản trị ({status})"
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    conn = connect()
    dq_before = conn.execute("SELECT count(*) FROM dw.dq_log").fetchone()[0]
    status, body = http("POST", f"{args.backend}/api/admin/etl/run", {"job": "quality"}, headers)
    if status != 202:
        return False, f"POST /api/admin/etl/run trả {status}: {body}"
    deadline, run = time.time() + 600, None
    while time.time() < deadline:
        _, runs = http("GET", f"{args.backend}/api/admin/etl/runs?page_size=5", headers=headers)
        run = next((r for r in runs["items"] if r["id"] == body["run_id"]), None)
        if run and run["status"] in ("success", "failed"):
            break
        time.sleep(3)
    dq_after = conn.execute("SELECT count(*) FROM dw.dq_log").fetchone()[0]
    conn.close()
    ok = bool(run) and run["status"] == "success" and dq_after > dq_before
    return (
        ok,
        f"run {body['run_id']}: {run['status'] if run else 'không thấy'}; dq_log +{dq_after - dq_before} dòng",
    )


def check_conventions(args) -> tuple[bool, str]:
    """10. Hướng dẫn nhánh/PR/quy ước có trong README và hook commit tồn tại."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    needs = ["Quy chuẩn commit", "Fork", "Pull Request", "nhom01-65httt"]
    missing = [t for t in needs if t not in readme]
    hook = ROOT / "tools" / "hooks" / "commit-msg"
    claude = (ROOT / "CLAUDE.md").exists()
    return (
        not missing and hook.exists() and claude,
        f"README thiếu {missing or 'không'}; hook {'có' if hook.exists() else 'THIẾU'}; CLAUDE.md {'có' if claude else 'THIẾU'}",
    )


CHECKS = [
    (1, "docker compose up chạy cả hệ thống", check_stack),
    (2, "dw có dữ liệu thật, độ phủ đúng cam kết", check_warehouse),
    (3, "Dataset và metric Superset khớp SQL gốc", check_superset),
    (4, "Backend: auth, phân quyền, nhúng Superset", check_auth),
    (5, "API contract chốt (openapi khớp API thực)", check_contract),
    (6, "Mô hình: dw có kết quả, API mô hình đúng schema", check_ml_tables),
    (7, "Tập mẫu cảm xúc cho TV5 và hướng dẫn", check_sample_for_tv5),
    (8, "Bộ mẫu (React, router, n8n, CSV) chạy được", check_templates),
    (9, "Chạy lại ETL qua API, có nhật ký và dq_log", check_etl_rerun),
    (10, "Hướng dẫn nhánh/PR/quy ước", check_conventions),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--frontend", default="http://localhost:5173")
    parser.add_argument("--superset", default="http://localhost:8088")
    parser.add_argument("--n8n", default="http://localhost:5678")
    parser.add_argument("--etl-runner", default="http://localhost:8100")
    parser.add_argument("--only", type=int, nargs="*", help="Chỉ chạy các hạng mục này (số thứ tự)")
    parser.add_argument("--json", help="Ghi kết quả ra tệp JSON")
    args = parser.parse_args()
    items = []
    for no, name, fn in CHECKS:
        if args.only and no not in args.only:
            continue
        item = Item(no, name)
        start = time.time()
        try:
            item.ok, item.detail = fn(args)
        except Exception as exc:  # noqa: BLE001
            item.ok, item.detail = False, f"{type(exc).__name__}: {exc}"
        item.seconds = time.time() - start
        items.append(item)
        print(
            f"{'ĐẠT ' if item.ok else 'LỖI '} {item.no:>2}. {item.name} ({item.seconds:.0f}s)\n        {item.detail}",
            flush=True,
        )
    passed = sum(i.ok for i in items)
    print(f"\n{passed}/{len(items)} hạng mục đạt")
    if args.json:
        Path(args.json).write_text(
            json.dumps([i.__dict__ for i in items], ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0 if passed == len(items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
