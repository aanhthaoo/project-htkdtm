"""Truy vấn dùng chung trên kho dw."""

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection


def latest_trade_date(conn: Connection) -> date:
    d = conn.execute(
        text("SELECT max(trade_date) FROM dw.mv_market_daily_kpi")
    ).scalar_one_or_none()
    if d is None:
        raise LookupError("Kho dw chưa có dữ liệu")
    return d


def default_range(
    conn: Connection, date_from: date | None, date_to: date | None, days: int = 90
) -> tuple[date, date]:
    """Khoảng ngày mặc định: `days` ngày gần nhất tính tới ngày giao dịch mới nhất."""
    end = date_to or latest_trade_date(conn)
    return (date_from or end - timedelta(days=days)), end
