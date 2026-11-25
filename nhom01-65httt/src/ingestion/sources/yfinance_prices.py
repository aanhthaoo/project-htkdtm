"""yfinance: 7 chuỗi quốc tế (tỷ giá, chỉ số USD, S&P 500, dầu, vàng, lợi suất trái phiếu Mỹ)."""

import logging
from datetime import date

from ingestion import db

log = logging.getLogger(__name__)

TICKERS = {
    "VND=X": "USD/VND",
    "DX-Y.NYB": "Chỉ số USD (DXY)",
    "^GSPC": "S&P 500",
    "CL=F": "Dầu WTI",
    "BZ=F": "Dầu Brent",
    "GC=F": "Vàng",
    "^TNX": "Lợi suất trái phiếu Mỹ 10 năm",
}
COLUMNS = ["ticker", "trade_date", "open", "high", "low", "close", "adj_close", "volume"]


def frame_to_rows(ticker: str, frame) -> list[tuple]:
    """DataFrame (index ngày) -> tuple. Bỏ dòng không có giá đóng cửa."""
    rows = []
    for ts, rec in frame.iterrows():
        close = rec.get("Close")
        if close != close:  # NaN
            continue
        rows.append(
            (
                ticker,
                ts.date(),
                _num(rec.get("Open")),
                _num(rec.get("High")),
                _num(rec.get("Low")),
                _num(close),
                _num(rec.get("Adj Close")),
                _num(rec.get("Volume")),
            )
        )
    return rows


def _num(value):
    return None if value is None or value != value else float(value)


def load(conn, start: date = date(2020, 9, 1)) -> int:
    import yfinance as yf

    total = 0
    for ticker in TICKERS:
        frame = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=False)
        rows = frame_to_rows(ticker, frame)
        n = db.copy_upsert(conn, "raw.yf_prices", COLUMNS, rows, ["ticker", "trade_date"])
        db.mark_run(conn, "yfinance", "prices", ticker, "done", rows_loaded=n)
        total += n
        log.info("yfinance %s: %d dòng", ticker, n)
    return total
