"""Kiểm thử Superset trên hệ thống đang chạy: metric của dataset phải khớp truy vấn SQL gốc trên bảng fact.

Chạy:  pytest -m smoke tests/smoke/test_superset.py
Cần: docker compose đang chạy, đã chạy dbt (models/superset) và `python src/superset/provision.py`.
SQL "gốc" ở đây chỉ dùng bảng fact_* và dim_*, không dùng các view ds_* để kiểm tra độc lập.
"""

import importlib.util
import time
from pathlib import Path

import psycopg
import pytest

from ingestion import db

pytestmark = pytest.mark.smoke

SUP_DIR = Path(__file__).resolve().parents[2] / "src" / "superset"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"sup_{name}", SUP_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(SUP_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SUP_DIR))
    return module


provision = _load("provision")
spec_mod = provision.spec


@pytest.fixture(scope="module")
def conn():
    try:
        connection = db.connect()
    except psycopg.OperationalError:
        pytest.skip("Không kết nối được PostgreSQL")
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def sup():
    try:
        client = provision.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Không kết nối được Superset: {exc}")
    return client


@pytest.fixture(scope="module")
def ids(sup):
    out = {}
    for ds in spec_mod.DATASETS:
        found = sup.find("dataset", "table_name", ds.table)
        if not found:
            pytest.skip(f"Chưa có dataset {ds.table}; chạy python src/superset/provision.py")
        out[ds.table] = found["id"]
    return out


def val(rows, key):
    assert len(rows) == 1, rows
    return rows[0][key]


def test_moi_metric_chay_duoc_va_co_so_lieu(sup, ids):
    for ds in spec_mod.DATASETS:
        for metric in ds.metrics:
            rows = sup.query(ids[ds.table], [metric.name])
            assert (
                rows and rows[0][metric.name] is not None
            ), f"{ds.table}.{metric.name} không có số liệu"


def test_dong_tien_nganh_tuan_khop_sql_goc(conn, sup, ids):
    week, sector, expected = conn.execute(
        """
        SELECT t.week_start_date, s.icb_l2_code, sum(f.net_value_bn)
        FROM dw.fact_money_flow f
        JOIN dw.dim_time t USING (date_key)
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_sector s USING (sector_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN'
          AND t.week_start_date = (SELECT max(week_start_date) - 14 FROM dw.dim_time WHERE is_trading_day)
        GROUP BY 1, 2 ORDER BY sum(f.buy_value_bn + f.sell_value_bn) DESC LIMIT 1
        """
    ).fetchone()
    rows = sup.query(
        ids["ds_sector_flow_weekly"],
        ["net_value_bn"],
        where=f"icb_l2_code = '{sector}' AND week_start_date = '{week}' AND investor_type = 'FOREIGN'",
    )
    assert val(rows, "net_value_bn") == pytest.approx(expected, abs=1e-3)


def test_dong_tien_theo_san_va_nhom_von_hoa_khop_sql_goc(conn, sup, ids):
    expected = conn.execute(
        """
        SELECT sum(f.net_value_bn)
        FROM dw.fact_money_flow f
        JOIN dw.dim_time t USING (date_key)
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE d.security_type = 'STOCK' AND d.exchange = 'HOSE' AND d.cap_group = 'large'
          AND it.code = 'FOREIGN' AND t.year = 2025 AND t.month = 6
        """
    ).fetchone()[0]
    rows = sup.query(
        ids["ds_flow_daily"],
        ["net_value_bn"],
        where="exchange = 'HOSE' AND cap_group = 'large' AND investor_type = 'FOREIGN' AND year = 2025 "
        "AND month_start_date = '2025-06-01'",
    )
    assert val(rows, "net_value_bn") == pytest.approx(expected, abs=1e-3)


def test_ty_le_mua_rong_tren_giao_dich(conn, sup, ids):
    buy, sell = conn.execute(
        """
        SELECT sum(f.buy_value_bn), sum(f.sell_value_bn)
        FROM dw.fact_money_flow f
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN'
        """
    ).fetchone()
    rows = sup.query(ids["ds_flow_daily"], ["net_ratio_pct"], where="investor_type = 'FOREIGN'")
    assert val(rows, "net_ratio_pct") == pytest.approx(100 * (buy - sell) / (buy + sell), rel=1e-6)


def test_ty_trong_dong_tien_nganh_cong_lai_bang_100(conn, sup, ids):
    week = conn.execute(
        "SELECT max(week_start_date) - 14 FROM dw.dim_time WHERE is_trading_day"
    ).fetchone()[0]
    rows = sup.query(
        ids["ds_sector_flow_weekly"],
        ["turnover_share_pct"],
        columns=["icb_l2_code"],
        where=f"week_start_date = '{week}' AND investor_type = 'FOREIGN'",
    )
    assert len(rows) >= 15
    assert sum(r["turnover_share_pct"] for r in rows) == pytest.approx(100.0, abs=1e-6)


def test_luy_ke_cuoi_chuoi_bang_tong_ron(conn, sup, ids):
    expected = conn.execute(
        """
        SELECT sum(f.net_value_bn)
        FROM dw.fact_money_flow f
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN'
        """
    ).fetchone()[0]
    rows = sup.query(
        ids["ds_market_flow_series"],
        ["cum_net_value_bn"],
        columns=["trade_date"],
        where="investor_type = 'FOREIGN'",
        orderby=[["trade_date", False]],
        row_limit=1,
    )
    assert rows[0]["cum_net_value_bn"] == pytest.approx(expected, abs=1e-3)


def test_top_ma_khoi_ngoai_mua_rong_khop_sql_goc(conn, sup, ids):
    expected = conn.execute(
        """
        SELECT d.symbol, sum(f.net_value_bn) AS net
        FROM dw.fact_money_flow f
        JOIN dw.dim_time t USING (date_key)
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN'
          AND t.week_start_date = (SELECT max(week_start_date) - 14 FROM dw.dim_time WHERE is_trading_day)
        GROUP BY 1 ORDER BY net DESC LIMIT 5
        """
    ).fetchall()
    week = conn.execute(
        "SELECT max(week_start_date) - 14 FROM dw.dim_time WHERE is_trading_day"
    ).fetchone()[0]
    rows = sup.query(
        ids["ds_stock_flow_daily"],
        ["net_value_bn"],
        columns=["symbol"],
        where=f"week_start_date = '{week}' AND investor_type = 'FOREIGN'",
        orderby=[["net_value_bn", False]],
        row_limit=5,
    )
    assert [r["symbol"] for r in rows] == [e[0] for e in expected]
    for r, e in zip(rows, expected, strict=True):
        assert r["net_value_bn"] == pytest.approx(e[1], abs=1e-3)


def test_gia_dong_cua_theo_ma_khop_fact(conn, sup, ids):
    day, expected = conn.execute(
        """
        SELECT p.trade_date, p.close_price
        FROM dw.fact_daily_price p JOIN dw.dim_stock d USING (stock_key)
        WHERE d.symbol = 'VNM' AND p.has_trading ORDER BY p.trade_date DESC OFFSET 3 LIMIT 1
        """
    ).fetchone()
    rows = sup.query(
        ids["ds_stock_daily"], ["close_price"], where=f"symbol = 'VNM' AND trade_date = '{day}'"
    )
    assert val(rows, "close_price") == pytest.approx(expected)


def test_vi_mo_khop_fact(conn, sup, ids):
    expected = conn.execute(
        """
        SELECT m.value FROM dw.fact_macro_indicator m JOIN dw.dim_indicator i USING (indicator_key)
        WHERE i.code = 'USDVND' ORDER BY m.trade_date DESC LIMIT 1
        """
    ).fetchone()[0]
    rows = sup.query(
        ids["ds_macro_daily"],
        ["value"],
        columns=["trade_date"],
        where="indicator_code = 'USDVND'",
        orderby=[["trade_date", False]],
        row_limit=1,
    )
    assert rows[0]["value"] == pytest.approx(expected)


def test_tin_tuc_khop_sql_goc(conn, sup, ids):
    total, market = conn.execute(
        """
        SELECT count(*), count(*) FILTER (WHERE is_market_related)
        FROM dw.dim_article WHERE NOT is_duplicate AND session_date IS NOT NULL
        """
    ).fetchone()
    rows = sup.query(ids["ds_news_article"], ["n_articles", "n_market_articles"])
    assert val(rows, "n_articles") == total
    assert val(rows, "n_market_articles") == market
    top = conn.execute(
        """
        SELECT d.symbol, count(DISTINCT a.article_key) AS n
        FROM dw.bridge_article_entity b
        JOIN dw.dim_article a USING (article_key)
        JOIN dw.dim_stock d ON d.stock_key = b.stock_key
        WHERE b.entity_type = 'STOCK' AND a.is_market_related AND NOT a.is_duplicate AND a.session_date IS NOT NULL
        GROUP BY 1 ORDER BY n DESC, d.symbol LIMIT 1
        """
    ).fetchone()
    rows = sup.query(
        ids["ds_news_stock_daily"],
        ["n_articles"],
        columns=["symbol"],
        orderby=[["n_articles", False]],
        row_limit=50,
    )
    assert max(r["n_articles"] for r in rows) == top[1]


def test_cam_xuc_khop_sql_goc(conn, sup, ids):
    row = conn.execute(
        """
        SELECT s.entity_code, t.week_start_date, count(DISTINCT s.article_key), avg(s.sentiment_score)
        FROM dw.fact_news_sentiment s JOIN dw.dim_time t ON t.date_key = s.session_date_key
        WHERE s.entity_type = 'SECTOR'
        GROUP BY 1, 2 ORDER BY count(DISTINCT s.article_key) DESC, 1, 2 LIMIT 1
        """
    ).fetchone()
    code, week, n, avg = row
    rows = sup.query(
        ids["ds_news_sentiment"],
        ["n_articles", "avg_sentiment"],
        where=f"entity_type = 'SECTOR' AND entity_code = '{code}' AND week_start_date = '{week}'",
    )
    assert val(rows, "n_articles") == n
    assert val(rows, "avg_sentiment") == pytest.approx(avg, abs=1e-9)


def test_du_bao_khop_sql_goc_va_do_chinh_xac_trong_dim_model(conn, sup, ids):
    metrics = conn.execute(
        "SELECT metrics FROM dw.dim_model WHERE task = 'forecast' ORDER BY trained_at DESC LIMIT 1"
    ).fetchone()[0]
    rows = sup.query(ids["ds_prediction"], ["accuracy", "n_predictions"])
    assert val(rows, "n_predictions") == metrics["n"]
    assert val(rows, "accuracy") == pytest.approx(metrics["model"]["accuracy"], abs=1e-9)
    net = conn.execute(
        "SELECT sum(p.actual_net_value_bn) FROM dw.fact_prediction p JOIN dw.dim_model m USING (model_key) "
        "WHERE m.task = 'forecast' AND p.model_key = (SELECT model_key FROM dw.dim_model WHERE task = 'forecast' "
        "ORDER BY trained_at DESC LIMIT 1)"
    ).fetchone()[0]
    assert val(
        sup.query(ids["ds_prediction"], ["actual_net_bn"]), "actual_net_bn"
    ) == pytest.approx(net, abs=1e-3)


def test_bieu_do_thu_hien_thi_duoc_va_tai_nhanh(sup):
    for ds in spec_mod.DATASETS:
        name = ds.test_chart[0]
        chart = sup.find("chart", "slice_name", name)
        assert chart, f"Chưa có biểu đồ thử {name}"
        start = time.time()
        rows = provision.chart_rows(sup, chart["id"])
        elapsed = time.time() - start
        assert len(rows) > 0, f"{name} không có dữ liệu"
        assert elapsed < 30, f"{name} tải {elapsed:.1f}s, quá chậm"


def test_bo_loc_hoat_dong(sup, ids):
    all_rows = sup.query(ids["ds_flow_daily"], ["net_value_bn"], columns=["exchange"])
    one = sup.query(ids["ds_flow_daily"], ["net_value_bn"], where="exchange = 'HNX'")
    by_exchange = {r["exchange"]: r["net_value_bn"] for r in all_rows}
    assert set(by_exchange) == {"HOSE", "HNX", "UPCOM"}
    assert val(one, "net_value_bn") == pytest.approx(by_exchange["HNX"], abs=1e-3)
