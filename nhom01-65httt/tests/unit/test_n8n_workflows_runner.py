"""Workflow n8n, bộ chạy ETL và CSV mẫu: kiểm tra cấu trúc (không cần Docker)."""

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "src" / "n8n" / "workflows"
TEMPLATES = ROOT / "src" / "ingestion" / "templates"
TRIGGERS = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.webhook",
}


def load_workflows():
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(WORKFLOWS.glob("*.json"))
    }


def test_co_du_4_workflow_loi():
    assert set(load_workflows()) == {
        "etl-hourly",
        "etl-after-close",
        "etl-rerun-webhook",
        "alert-dispatch-sample",
    }


@pytest.mark.parametrize(
    "wid", ["etl-hourly", "etl-after-close", "etl-rerun-webhook", "alert-dispatch-sample"]
)
def test_workflow_hop_le(wid):
    wf = load_workflows()[wid]
    names = [n["name"] for n in wf["nodes"]]
    assert wf["id"] == wid and len(names) == len(set(names)), "tên nút phải duy nhất"
    assert any(n["type"] in TRIGGERS for n in wf["nodes"]), "thiếu nút kích hoạt"
    for src, outs in wf["connections"].items():
        assert src in names, f"nút nguồn {src} không tồn tại"
        for branch in outs["main"]:
            for target in branch:
                assert target["node"] in names, f"{src} -> {target['node']} không tồn tại"
    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.httpRequest":
            headers = {
                h["name"]: h["value"] for h in n["parameters"]["headerParameters"]["parameters"]
            }
            assert (
                headers.get("X-Service-Key") == "={{ $env.SERVICE_KEY }}"
            ), f"{n['name']} thiếu khóa dịch vụ"
            assert (
                "$env." in n["parameters"]["url"]
            ), "địa chỉ phải lấy từ biến môi trường, không ghi cứng"


def test_workflow_khong_chua_bi_mat_ghi_cung():
    text = "".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.json"))
    assert "password" not in text.lower() and "localhost" not in text and "127.0.0.1" not in text


def test_workflow_sau_phien_co_vong_cho_va_xu_ly_loi():
    wf = load_workflows()["etl-after-close"]
    conn = wf["connections"]
    assert "Chờ 60 giây" in {
        t["node"] for t in conn["Còn chạy?"]["main"][0]
    }, "phải có vòng chờ khi còn chạy"
    failed_calls = [n for n in wf["nodes"] if n["name"].startswith("Ghi lỗi vào nhật ký")]
    assert len(failed_calls) == 2, "lỗi khi khởi động và lỗi khi chạy đều phải ghi nhật ký"


def test_workflow_da_sinh_khop_ma_nguon():
    """Sửa build_workflows.py mà quên chạy lại thì test này báo."""
    spec = importlib.util.spec_from_file_location(
        "build_workflows", ROOT / "src" / "n8n" / "build_workflows.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    generated = {
        wf["id"]: wf
        for wf in (mod.hourly(), mod.after_close(), mod.rerun_webhook(), mod.alert_sample())
    }
    assert json.loads(json.dumps(generated)) == load_workflows()


# ---------------- Bộ chạy ETL ----------------
@pytest.fixture()
def runner():
    sys.path.insert(0, str(ROOT / "src"))
    from etl_runner import app as runner_app

    return runner_app


def test_cong_viec_etl_chi_dung_cac_buoc_da_dinh_nghia(runner):
    for job, steps in runner.JOBS.items():
        assert steps and all(s in runner.STEPS for s in steps), job
    # tin cần 30-40 phút nên không được nằm trong chuỗi sau phiên 15h30
    assert "news" not in runner.JOBS["after_close"]
    assert runner.JOBS["after_close"] == ["daily", "dbt_run", "dbt_test", "quality"]


def test_bo_chay_etl_can_khoa_dich_vu_va_chi_chay_mot_lan(runner):
    import os

    client = TestClient(runner.app)
    key = {"X-Service-Key": os.environ["SERVICE_KEY"]}
    assert client.post("/jobs/rss").status_code == 401
    assert client.post("/jobs/rss", headers={"X-Service-Key": "sai"}).status_code == 401
    assert client.post("/jobs/khong-co", headers=key).status_code == 404
    assert client.post("/jobs/rss?trigger=la", headers=key).status_code == 422
    assert runner._lock.acquire(blocking=False)
    try:
        assert client.post("/jobs/rss", headers=key).status_code == 409
        assert client.get("/health").json()["busy"] is True
    finally:
        runner._lock.release()


# ---------------- CSV mẫu ----------------
@pytest.mark.parametrize(
    ("name", "columns"),
    [
        (
            "macro_monthly.csv",
            {"period_end", "indicator_code", "value", "unit", "source", "published_date"},
        ),
        (
            "individual_investors_weekly.csv",
            {"week_start_date", "buy_value_bn", "sell_value_bn", "source"},
        ),
        ("etf_flows_monthly.csv", {"month_start_date", "etf_name", "net_flow_bn", "source"}),
    ],
)
def test_csv_mau_dung_cot_va_doc_duoc_utf8(name, columns):
    rows = list(csv.DictReader(open(TEMPLATES / name, encoding="utf-8")))
    assert rows and columns <= set(rows[0])
    for row in rows:
        for col in columns:
            assert row[col].strip(), f"{name}: cột {col} trống"
