"""Kiểm tra hợp đồng HTTP của chuỗi vĩ mô TV5 với các dòng dữ liệu mẫu."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import CurrentUser, get_optional_user
from app.routers.tv5 import news_macro


@pytest.fixture
def macro_api(monkeypatch):
    app = FastAPI()
    app.include_router(news_macro.router)
    app.dependency_overrides[get_optional_user] = lambda: CurrentUser(1, "tv5@example.com", "TV5", "investor")
    engine = MagicMock()
    monkeypatch.setattr(news_macro, "get_engine", lambda: engine)
    conn = engine.connect.return_value.__enter__.return_value
    with TestClient(app) as client:
        yield client, conn


@pytest.mark.parametrize("frequency", [None, "daily", "monthly"])
def test_macro_points_by_frequency(macro_api, frequency):
    client, conn = macro_api
    monthly = frequency == "monthly"
    code = "CPI_YOY" if monthly else "DXY"
    row = SimpleNamespace(
        indicator_code=code, indicator_name=code, unit="%" if monthly else "index",
        trade_date=date(2026, 10, 31), value=3.1, pct_change_prev=None,
    )
    if monthly:
        row.published_date = date(2026, 11, 5)
    conn.execute.return_value.all.return_value = [row]
    params = {"codes": code.lower(), "from": "2026-10-01", "to": "2026-10-31"}
    if frequency:
        params["frequency"] = frequency
    response = client.get("/api/macro/series", params=params)

    assert response.status_code == 200, response.text
    query, bindings = conn.execute.call_args.args
    assert ("dw.fact_macro_indicator" if monthly else "dw.ds_macro_daily") in str(query)
    assert bindings == {"codes": [code], "d1": date(2026, 10, 1), "d2": date(2026, 10, 31)}
    point = {"date": "2026-10-31", "value": 3.1, "pct_change_prev": None}
    if monthly:
        point["published_date"] = "2026-11-05"
    assert response.json()["series"] == [
        {"code": code, "name_vi": code, "unit": row.unit, "points": [point]}
    ]


def test_unsupported_frequency_rejected_before_query(macro_api):
    client, conn = macro_api
    response = client.get("/api/macro/series", params={"codes": "DXY", "frequency": "weekly"})
    assert response.status_code == 422
    conn.execute.assert_not_called()
