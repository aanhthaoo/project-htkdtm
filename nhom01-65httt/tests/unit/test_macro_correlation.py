"""Chạy truy vấn TV5 trên SQLite với hàm corr thay thế cho aggregate của PostgreSQL."""

from statistics import correlation

import pytest
from sqlalchemy import create_engine

from app.routers.tv5 import news_macro


class PearsonAggregate:
    """SQLite không có corr, dùng thư viện chuẩn để tính trên các cặp mà SQL chọn."""

    def __init__(self):
        self.x = []
        self.y = []

    def step(self, x, y):
        self.x.append(x)
        self.y.append(y)

    def finalize(self):
        if len(set(self.x)) < 2 or len(set(self.y)) < 2:
            return None
        return correlation(self.x, self.y)


@pytest.fixture
def correlation_db(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.connection.driver_connection.create_aggregate("corr", 2, PearsonAggregate)
        conn.exec_driver_sql("ATTACH ':memory:' AS dw")
        conn.exec_driver_sql("CREATE TABLE dw.dim_indicator(code TEXT, frequency TEXT)")
        conn.exec_driver_sql(
            "CREATE TABLE dw.mv_market_daily_kpi(trade_date INTEGER, foreign_net_bn REAL)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE dw.ds_macro_daily("
            "trade_date INTEGER, indicator_code TEXT, value REAL, pct_change_prev REAL)"
        )
        conn.exec_driver_sql("INSERT INTO dw.dim_indicator VALUES ('DXY', 'daily')")
    monkeypatch.setattr(news_macro, "get_engine", lambda: engine)
    yield engine
    engine.dispose()


@pytest.mark.parametrize(
    "changes,expected",
    [([1, 2, 3, 4, 5], 1.0), ([5, 4, 3, 2, 1], -1.0), ([1, 3, 2, 5, 4], 0.8)],
)
def test_correlation_uses_changes_on_matching_dates_in_latest_window(correlation_db, changes, expected):
    with correlation_db.begin() as conn:
        # Phiên cũ có giá trị ngoại lệ, phải bị loại khỏi cửa sổ 5 phiên.
        conn.exec_driver_sql("INSERT INTO dw.mv_market_daily_kpi VALUES (1, -9999)")
        conn.exec_driver_sql("INSERT INTO dw.ds_macro_daily VALUES (1, 'DXY', 100, 9999)")
        # Chèn ngược thứ tự để kiểm tra SQL chọn theo ngày thay vì thứ tự dòng.
        for day in range(6, 1, -1):
            conn.exec_driver_sql(
                "INSERT INTO dw.mv_market_daily_kpi VALUES (?, ?)", (day, day - 1)
            )
            conn.exec_driver_sql(
                "INSERT INTO dw.ds_macro_daily VALUES (?, 'DXY', ?, ?)",
                (day, 1000 - day, changes[day - 2]),
            )
        # Ngày quốc tế không có phiên Việt Nam tương ứng phải bị loại khi ghép.
        conn.exec_driver_sql("INSERT INTO dw.ds_macro_daily VALUES (7, 'DXY', 100, -9999)")

    result = news_macro.macro_correlation(user=None, codes="dxy,DXY", window=5)

    assert result.stub is False
    assert result.against == "foreign_net"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.code == "DXY"
    assert item.window == 5
    assert item.correlation == pytest.approx(expected)
