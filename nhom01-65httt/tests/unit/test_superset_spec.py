"""Đặc tả Superset (src/superset/spec.py) phải khớp tài liệu cho TV3 và các model dbt."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec_file = ROOT / "src" / "superset" / "spec.py"
_spec = importlib.util.spec_from_file_location("superset_spec", spec_file)
spec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spec)

DOC = (ROOT / "docs" / "superset_dataset_metric.md").read_text(encoding="utf-8")
MODELS = ROOT / "src" / "dbt_dw" / "models" / "superset"


def test_moi_dataset_co_model_dbt_va_duoc_ghi_trong_tai_lieu():
    for ds in spec.DATASETS:
        assert (MODELS / f"{ds.table}.sql").exists(), ds.table
        assert f"### {ds.table}:" in DOC, f"Tài liệu thiếu dataset {ds.table}"


def test_moi_metric_duoc_ghi_trong_tai_lieu_va_khong_trung_ten_trong_dataset():
    for ds in spec.DATASETS:
        names = [m.name for m in ds.metrics]
        assert len(names) == len(set(names)), ds.table
        section = DOC.split(f"### {ds.table}:")[1].split("\n### ")[0]
        for name in names:
            assert f"`{name}`" in section, f"{ds.table}.{name} chưa có trong tài liệu"


def test_cot_thoi_gian_va_bieu_do_thu_hop_le():
    for ds in spec.DATASETS:
        sql = (MODELS / f"{ds.table}.sql").read_text(encoding="utf-8")
        assert re.search(
            rf"\b{ds.main_dttm_col}\b", sql
        ), f"{ds.table} thiếu cột {ds.main_dttm_col}"
        assert ds.test_chart and ds.test_chart[0].startswith("[Thử]")
