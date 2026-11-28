"""Kiểm tra hợp đồng HTTP của chuỗi vĩ mô TV5 với các dòng dữ liệu mẫu."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import CurrentUser, get_optional_user
from app.core.errors import install_error_handlers
from app.routers.tv5 import news_macro


@pytest.fixture
def macro_api(monkeypatch):
    app = FastAPI()
    install_error_handlers(app)
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


@pytest.mark.parametrize("window", [4, 251])
def test_correlation_rejects_out_of_range_window(macro_api, window):
    client, conn = macro_api
    response = client.get("/api/macro/correlation", params={"window": window})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    conn.execute.assert_not_called()


@pytest.mark.parametrize("bad_code,status", [("MISSING", 404), ("CPI_YOY", 422)])
def test_correlation_rejects_invalid_code_in_mixed_request(macro_api, bad_code, status):
    client, conn = macro_api
    catalog = [("DXY", "daily")]
    if bad_code == "CPI_YOY":
        catalog.append((bad_code, "monthly"))
    conn.execute.return_value.tuples.return_value.all.return_value = catalog
    response = client.get("/api/macro/correlation", params={"codes": f"dxy,{bad_code}"})
    assert response.status_code == status
    assert bad_code in response.json()["error"]["message"]
    conn.execute.assert_called_once()


@pytest.mark.parametrize("window", [5, 250])
def test_correlation_accepts_window_limits_and_valid_code_without_data(macro_api, window):
    client, conn = macro_api
    catalog = MagicMock()
    catalog.tuples.return_value.all.return_value = [("DXY", "daily")]
    conn.execute.side_effect = [catalog, []]
    response = client.get("/api/macro/correlation", params={"codes": " dxy,DXY ", "window": window})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert conn.execute.call_args.args[1] == {"codes": ["DXY"], "window_size": window}
