"""CafeF: VN-Index (VNDirect không có chỉ số) và dữ liệu giá để đối chiếu.

API CafeF: tham số ngày MM/DD/YYYY, phản hồi ngày DD/MM/YYYY, tối đa 30 dòng mỗi trang, tối đa một năm mỗi
lần gọi, thỉnh thoảng trả rỗng nên phải thử lại.
"""

import logging
import math
from datetime import date, datetime

from ingestion import db
from ingestion.client import Client

log = logging.getLogger(__name__)

BASE = "https://cafef.vn/du-lieu/ajax/pagenew/datahistory/pricehistory.ashx"
HEADERS = {"Referer": "https://cafef.vn/"}
PAGE_SIZE = 30
EMPTY_RETRIES = 4
SOURCE = "cafef"
COLUMNS = [
    "symbol", "trade_date", "open_k", "high_k", "low_k", "close_k", "adj_close_k", "change_text",
    "matched_volume", "matched_value_bn", "putthrough_volume", "putthrough_value_bn",
]  # fmt: skip


def parse_row(symbol: str, row: dict) -> tuple:
    return (
        symbol,
        datetime.strptime(row["Ngay"], "%d/%m/%Y").date(),
        row.get("GiaMoCua"),
        row.get("GiaCaoNhat"),
        row.get("GiaThapNhat"),
        row.get("GiaDongCua"),
        row.get("GiaDieuChinh"),
        row.get("ThayDoi"),
        row.get("KhoiLuongKhopLenh"),
        row.get("GiaTriKhopLenh"),
        row.get("KLThoaThuan"),
        row.get("GtThoaThuan"),
    )


def fetch_page(client: Client, symbol: str, start: date, end: date, page: int) -> dict:
    """Một trang; thử lại khi TotalCount = 0 (nguồn thỉnh thoảng trả rỗng dù có dữ liệu)."""
    url = (
        f"{BASE}?Symbol={symbol}&StartDate={start:%m/%d/%Y}&EndDate={end:%m/%d/%Y}"
        f"&PageIndex={page}&PageSize={PAGE_SIZE}"
    )
    data: dict = {}
    for _ in range(EMPTY_RETRIES):
        data = client.get_json(url, HEADERS).get("Data", {}) or {}
        if data.get("TotalCount"):
            return data
    return data


def year_windows(start: date, end: date) -> list[tuple[date, date]]:
    return [
        (max(start, date(y, 1, 1)), min(end, date(y, 12, 31)))
        for y in range(start.year, end.year + 1)
    ]


def load_index(
    conn,
    client: Client,
    symbol: str = "VNINDEX",
    start: date = date(2020, 9, 1),
    end: date | None = None,
) -> int:
    end = end or date.today()
    total_rows = 0
    for first, last in year_windows(start, end):
        key = f"{symbol}:{first:%Y-%m-%d}:{last:%Y-%m-%d}"
        recent = last >= date.today().replace(day=1)
        if db.is_done(conn, SOURCE, "price", key) and not recent:
            continue
        db.mark_run(conn, SOURCE, "price", key, "running")
        rows: list[tuple] = []
        page, pages = 1, 1
        while page <= pages:
            data = fetch_page(client, symbol, first, last, page)
            items = data.get("Data") or []
            if page == 1:
                pages = math.ceil((data.get("TotalCount") or 0) / PAGE_SIZE)
            rows.extend(parse_row(symbol, r) for r in items)
            page += 1
        n = db.copy_upsert(conn, "raw.cafef_price", COLUMNS, rows, ["symbol", "trade_date"])
        status = "done" if n else "failed"
        db.mark_run(conn, SOURCE, "price", key, status, rows_loaded=n, error=None if n else "rỗng")
        total_rows += n
        log.info("cafef %s %s..%s: %d dòng", symbol, first, last, n)
    return total_rows
