"""VNDirect finfo API (nguồn chính): giá, khối ngoại, tự doanh cho cả thị trường theo tháng."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from ingestion import db
from ingestion.client import Client

log = logging.getLogger(__name__)

BASE = "https://api-finfo.vndirect.com.vn/v4/"
SOURCE = "vndirect"
FIRST_DATE = date(2020, 9, 1)
REFETCH_DAYS = 10  # các tháng chạm cửa sổ này luôn lấy lại (dữ liệu ngày mới nhất cập nhật trễ)
KEEP_TYPE = "STOCK"


@dataclass(frozen=True)
class Spec:
    endpoint: str
    date_key: str  # tên trường ngày trong API (cũng dùng trong điều kiện lọc)
    table: str
    fields: dict[str, str]  # cột -> trường API


SPECS: dict[str, Spec] = {
    "prices": Spec(
        "stock_prices",
        "date",
        "raw.vnd_stock_prices",
        {
            "quote_time": "time",
            "basic_price": "basicPrice",
            "ceiling_price": "ceilingPrice",
            "floor_price": "floorPrice",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "average": "average",
            "ad_open": "adOpen",
            "ad_high": "adHigh",
            "ad_low": "adLow",
            "ad_close": "adClose",
            "ad_average": "adAverage",
            "nm_volume": "nmVolume",
            "nm_value": "nmValue",
            "pt_volume": "ptVolume",
            "pt_value": "ptValue",
            "change": "change",
            "ad_change": "adChange",
            "pct_change": "pctChange",
        },
    ),
    "foreign": Spec(
        "foreigns",
        "tradingDate",
        "raw.vnd_foreigns",
        {
            "buy_val": "buyVal",
            "sell_val": "sellVal",
            "net_val": "netVal",
            "buy_vol": "buyVol",
            "sell_vol": "sellVol",
            "net_vol": "netVol",
            "total_room": "totalRoom",
            "current_room": "currentRoom",
        },
    ),
    "prop": Spec(
        "proprietary_trading",
        "date",
        "raw.vnd_proprietary",
        {
            "buying_vol": "buyingVol",
            "buying_vol_pct": "buyingVolPct",
            "selling_vol": "sellingVol",
            "selling_vol_pct": "sellingVolPct",
            "buying_val": "buyingVal",
            "buying_val_pct": "buyingValPct",
            "selling_val": "sellingVal",
            "selling_val_pct": "sellingValPct",
            "net_val": "netVal",
            "net_vol": "netVol",
        },
    ),
}
BASE_COLUMNS = ["code", "trade_date", "floor", "type"]


def columns(spec: Spec) -> list[str]:
    return [*BASE_COLUMNS, *spec.fields, "extra"]


def parse_rows(spec: Spec, api_rows: list[dict]) -> tuple[list[tuple], int]:
    """Chuyển dòng API sang tuple theo thứ tự `columns(spec)`. Chỉ giữ type = STOCK.

    Trả (các dòng, số dòng bị bỏ do khác loại).
    """
    mapped_api_keys = set(spec.fields.values()) | {"code", "floor", "type", spec.date_key}
    out: list[tuple] = []
    skipped = 0
    for row in api_rows:
        if row.get("type") != KEEP_TYPE:
            skipped += 1
            continue
        extra = {k: v for k, v in row.items() if k not in mapped_api_keys}
        values = [row.get(api_key) for api_key in spec.fields.values()]
        out.append(
            (
                row["code"],
                row[spec.date_key],
                row.get("floor"),
                row.get("type"),
                *values,
                db.jdump(extra),
            )
        )
    return out, skipped


def fetch_window(client: Client, spec: Spec, start: date, end: date) -> list[dict]:
    """Lấy cả thị trường trong [start, end] bằng một lần gọi; kiểm tra không bị cắt bớt."""
    q = f"{spec.date_key}:gte:{start.isoformat()}~{spec.date_key}:lte:{end.isoformat()}"
    url = f"{BASE}{spec.endpoint}?q={q}&size=100000&sort={spec.date_key}:asc"
    payload = client.get_json(url)
    rows = payload.get("data", [])
    total = payload.get("totalElements")
    if total is not None and total != len(rows):
        raise RuntimeError(
            f"{spec.endpoint} {start}..{end}: nhận {len(rows)}/{total} dòng, tăng size"
        )
    return rows


def backfill(
    conn,
    client: Client,
    start: date = FIRST_DATE,
    end: date | None = None,
    kinds: tuple[str, ...] = ("prices", "foreign", "prop"),
    force: bool = False,
) -> int:
    """Nạp theo từng tháng; bỏ qua tháng đã xong trừ các tháng gần đây (lấy lại)."""
    end = end or date.today()
    recent_cut = date.today() - timedelta(days=REFETCH_DAYS)
    loaded_total = 0
    for first, last in db.month_windows(start, end):
        for kind in kinds:
            spec = SPECS[kind]
            key = f"{first:%Y-%m}"
            if not force and last < recent_cut and db.is_done(conn, SOURCE, kind, key):
                continue
            db.mark_run(conn, SOURCE, kind, key, "running")
            try:
                api_rows = fetch_window(client, spec, first, last)
                rows, skipped = parse_rows(spec, api_rows)
                n = db.copy_upsert(
                    conn,
                    spec.table,
                    columns(spec),
                    rows,
                    ["code", "trade_date"],
                )
                db.mark_run(conn, SOURCE, kind, key, "done", rows_loaded=n)
                loaded_total += n
                log.info("vndirect %s %s: %d dòng (bỏ %d khác loại)", kind, key, n, skipped)
            except Exception as exc:  # noqa: BLE001 - ghi lỗi rồi tiếp tục tháng sau
                conn.rollback()
                db.mark_run(conn, SOURCE, kind, key, "failed", error=str(exc)[:500])
                log.error("vndirect %s %s lỗi: %s", kind, key, exc)
    return loaded_total
