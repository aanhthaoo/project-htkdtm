"""Vietcap: danh sách mã, nhóm chỉ số và thông tin công ty (ICB cấp 2 và 4, vốn hóa)."""

import logging
from datetime import date, datetime

from ingestion import db
from ingestion.client import Client, HttpError

log = logging.getLogger(__name__)

SYMBOLS_URL = "https://trading.vietcap.com.vn/api/price/symbols/getAll"
GROUP_URL = "https://trading.vietcap.com.vn/api/price/symbols/getByGroup?group={group}"
COMPANY_URL = "https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}"
GROUPS = ["VN30", "VN100", "VNMidCap", "VNSmallCap", "HNX30"]
LISTED_BOARDS = ("HSX", "HNX", "UPCOM")
MAX_TEXT = 2000  # trường văn bản dài (giới thiệu công ty...) không lưu vào payload


def symbol_row(item: dict) -> tuple:
    return (
        item["symbol"],
        item.get("type"),
        item.get("board"),
        item.get("organName"),
        item.get("organShortName"),
        item.get("productGrpID"),
        item.get("icbCode2"),
        db.jdump(item),
    )


def load_symbols(conn, client: Client) -> int:
    items = client.get_json(SYMBOLS_URL)
    cols = [
        "symbol", "type", "board", "organ_name", "organ_short_name",
        "product_grp_id", "icb_code2", "payload",
    ]  # fmt: skip
    rows = [symbol_row(i) for i in items]
    n = db.copy_upsert(conn, "raw.vietcap_symbols", cols, rows, ["symbol"])
    log.info("vietcap symbols: %d dòng", n)
    return n


def load_groups(conn, client: Client) -> int:
    total = 0
    for group in GROUPS:
        items = client.get_json(GROUP_URL.format(group=group))
        rows = [(group, i["symbol"]) for i in items]
        total += db.copy_upsert(
            conn, "raw.vietcap_groups", ["group_name", "symbol"], rows, ["group_name", "symbol"]
        )
        log.info("vietcap group %s: %d mã", group, len(rows))
    return total


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def company_row(symbol: str, data: dict) -> tuple:
    payload = {k: v for k, v in data.items() if not (isinstance(v, str) and len(v) > MAX_TEXT)}
    payload = {k: v for k, v in payload.items() if not isinstance(v, dict | list)}
    return (
        symbol,
        data.get("icbCodeLv2"),
        data.get("icbCodeLv4"),
        data.get("sector"),
        data.get("marketCap"),
        data.get("issueShare"),
        _to_date(data.get("listingDate")),
        data.get("maximumForeignPercentage"),
        data.get("foreignerPercentage"),
        data.get("freeFloatPercentage"),
        db.jdump(payload),
    )


COMPANY_COLUMNS = [
    "symbol", "icb_code_lv2", "icb_code_lv4", "sector", "market_cap", "issue_share",
    "listing_date", "max_foreign_pct", "foreigner_pct", "free_float_pct", "payload",
]  # fmt: skip


def pending_symbols(conn, max_age_days: int, limit: int | None) -> list[str]:
    """Mã đang niêm yết chưa có thông tin công ty (hoặc đã cũ); ưu tiên VN30 rồi VN100."""
    rows = conn.execute(
        """
        SELECT s.symbol
        FROM raw.vietcap_symbols s
        LEFT JOIN raw.vietcap_company c ON c.symbol = s.symbol
        LEFT JOIN raw.vietcap_groups g30 ON g30.symbol = s.symbol AND g30.group_name = 'VN30'
        LEFT JOIN raw.vietcap_groups g100 ON g100.symbol = s.symbol AND g100.group_name = 'VN100'
        WHERE s.type = 'STOCK' AND s.board = ANY(%s)
          AND (c.symbol IS NULL OR c.fetched_at < now() - make_interval(days => %s))
        ORDER BY (g30.symbol IS NULL), (g100.symbol IS NULL), s.symbol
        """,
        (list(LISTED_BOARDS), max_age_days),
    ).fetchall()
    symbols = [r[0] for r in rows]
    return symbols[:limit] if limit else symbols


def load_companies(conn, client: Client, max_age_days: int = 30, limit: int | None = None) -> int:
    symbols = pending_symbols(conn, max_age_days, limit)
    log.info("vietcap iQ: %d mã cần lấy", len(symbols))
    done = 0
    for i, symbol in enumerate(symbols, 1):
        try:
            payload = client.get_json(COMPANY_URL.format(symbol=symbol))
            data = payload.get("data")
            if not data:
                log.warning("vietcap iQ %s: không có dữ liệu", symbol)
                continue
            db.copy_upsert(
                conn,
                "raw.vietcap_company",
                COMPANY_COLUMNS,
                [company_row(symbol, data)],
                ["symbol"],
            )
            done += 1
        except HttpError as exc:
            log.error("vietcap iQ %s lỗi: %s", symbol, exc)
        if i % 100 == 0:
            log.info("vietcap iQ: %d/%d", i, len(symbols))
    return done
