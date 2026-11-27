"""Nạp số liệu nhập tay từ CSV (vĩ mô theo tháng, nhà đầu tư cá nhân theo tuần, dòng vốn ETF theo tháng) vào schema `raw`.

Chạy từ `src/`:   python -m ingestion.cli load-csv <macro|individual|etf> <tệp.csv> [--dry-run] [--allow-sample]
Sau đó đưa vào dw:  python dbt_dw/run.py run --select stg_macro_manual+ stg_individual_weekly+ stg_etf_monthly+

Quy tắc kiểm tra (một dòng sai bị loại và báo lý do; nếu CÓ dòng sai thì không ghi gì, để tránh nạp dở):
  - đúng tiêu đề cột, đúng kiểu số và ngày, không trùng khóa trong cùng tệp;
  - kỳ phải kết thúc (không nhập tương lai); vĩ mô: ngày công bố >= cuối kỳ (không nhìn trước tương lai khi huấn luyện mô hình);
  - dòng có ghi chú chứa "Mẫu minh họa" là dữ liệu mẫu và bị từ chối trừ khi dùng --allow-sample.
Nạp lại cùng khóa thì ghi đè (chạy lại không nhân đôi). Mọi lần nạp ghi một dòng vào dw.dq_log (layer = 'raw').
"""

import calendar
import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from ingestion import db

log = logging.getLogger(__name__)

SAMPLE_MARK = "mẫu minh họa"
MACRO_CODES = {
    "CPI_YOY": "%",
    "IIP_YOY": "%",
    "EXPORT_USD_BN": "tỷ USD",
    "IMPORT_USD_BN": "tỷ USD",
}


@dataclass
class Spec:
    table: str
    required: list[str]
    key: list[str]
    columns: list[str]


SPECS = {
    "macro": Spec(
        "raw.manual_macro_monthly",
        ["period_end", "indicator_code", "value", "unit", "source", "published_date"],
        ["period_end", "indicator_code"],
        ["period_end", "indicator_code", "value", "unit", "source", "published_date", "note"],
    ),
    "individual": Spec(
        "raw.manual_individual_weekly",
        ["week_start_date", "buy_value_bn", "sell_value_bn", "source"],
        ["week_start_date"],
        ["week_start_date", "buy_value_bn", "sell_value_bn", "source", "note"],
    ),
    "etf": Spec(
        "raw.manual_etf_monthly",
        ["month_start_date", "etf_name", "net_flow_bn", "source"],
        ["month_start_date", "etf_name"],
        ["month_start_date", "etf_name", "net_flow_bn", "source", "note"],
    ),
}


@dataclass
class Result:
    kind: str
    rows: list[tuple] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rejected_samples: int = 0


def _date(value: str, name: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{name} '{value}' không phải ngày YYYY-MM-DD") from exc


def _number(value: str, name: str, non_negative: bool = False) -> float:
    try:
        number = float(value.strip().replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{name} '{value}' không phải số") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} không hữu hạn")
    if non_negative and number < 0:
        raise ValueError(f"{name} không được âm")
    return number


def _is_month_end(d: date) -> bool:
    return d.day == calendar.monthrange(d.year, d.month)[1]


def _parse_macro(row: dict, today: date) -> tuple:
    period_end = _date(row["period_end"], "period_end")
    if not _is_month_end(period_end):
        raise ValueError(f"period_end {period_end} không phải ngày cuối tháng")
    if period_end > today:
        raise ValueError(f"period_end {period_end} chưa kết thúc (tương lai)")
    code = row["indicator_code"].strip()
    if code not in MACRO_CODES:
        raise ValueError(
            f"indicator_code '{code}' không hợp lệ, chọn một trong {sorted(MACRO_CODES)}"
        )
    value = _number(row["value"], "value")
    published = _date(row["published_date"], "published_date")
    if published < period_end:
        raise ValueError(
            f"published_date {published} sớm hơn cuối kỳ {period_end} (số liệu chưa thể được công bố)"
        )
    if published > today:
        raise ValueError(f"published_date {published} là tương lai")
    return (
        period_end,
        code,
        value,
        row["unit"].strip() or MACRO_CODES[code],
        row["source"].strip(),
        published,
        row.get("note", "").strip(),
    )


def _parse_individual(row: dict, today: date) -> tuple:
    week = _date(row["week_start_date"], "week_start_date")
    if week.weekday() != 0:
        raise ValueError(f"week_start_date {week} không phải thứ Hai")
    if week + timedelta(days=6) > today:
        raise ValueError(f"tuần {week} chưa kết thúc")
    buy = _number(row["buy_value_bn"], "buy_value_bn", True)
    sell = _number(row["sell_value_bn"], "sell_value_bn", True)
    return (week, buy, sell, row["source"].strip(), row.get("note", "").strip())


def _parse_etf(row: dict, today: date) -> tuple:
    month = _date(row["month_start_date"], "month_start_date")
    if month.day != 1:
        raise ValueError(f"month_start_date {month} không phải ngày 1")
    next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    if next_month > today + timedelta(days=1):
        raise ValueError(f"tháng {month:%Y-%m} chưa kết thúc")
    name = row["etf_name"].strip()
    if not name:
        raise ValueError("etf_name trống")
    return (
        month,
        name,
        _number(row["net_flow_bn"], "net_flow_bn"),
        row["source"].strip(),
        row.get("note", "").strip(),
    )


PARSERS = {"macro": _parse_macro, "individual": _parse_individual, "etf": _parse_etf}


def parse_file(
    kind: str, path: Path, allow_sample: bool = False, today: date | None = None
) -> Result:
    """Đọc và kiểm tra tệp CSV; không chạm cơ sở dữ liệu."""
    if kind not in SPECS:
        raise ValueError(f"loại '{kind}' không hợp lệ, chọn một trong {sorted(SPECS)}")
    spec, today = SPECS[kind], today or date.today()
    result = Result(kind)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in spec.required if c not in header]
        if missing:
            result.errors.append(f"Thiếu cột bắt buộc: {missing} (tiêu đề tệp: {header})")
            return result
        seen: dict[tuple, int] = {}
        for line_no, raw in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "") for k, v in raw.items()}
            if not any(v.strip() for v in row.values()):
                continue  # dòng trống
            if not allow_sample and SAMPLE_MARK in row.get("note", "").lower():
                result.rejected_samples += 1
                result.errors.append(
                    f"Dòng {line_no}: là dữ liệu mẫu (ghi chú 'Mẫu minh họa'); thay bằng số liệu thật hoặc dùng --allow-sample"
                )
                continue
            try:
                parsed = PARSERS[kind](row, today)
            except (KeyError, ValueError) as exc:
                result.errors.append(f"Dòng {line_no}: {exc}")
                continue
            key = tuple(parsed[spec.columns.index(c)] for c in spec.key)
            if key in seen:
                result.errors.append(f"Dòng {line_no}: trùng khóa {key} với dòng {seen[key]}")
                continue
            seen[key] = line_no
            result.rows.append(parsed)
    if not result.rows and not result.errors:
        result.errors.append("Tệp không có dòng dữ liệu nào")
    return result


def log_dq(conn, result: Result, path: Path, loaded: int, dry_run: bool) -> None:
    """Một dòng dw.dq_log cho mỗi lần nạp (kể cả thất bại)."""
    passed = not result.errors
    conn.execute(
        "INSERT INTO dw.dq_log (layer, source, check_name, target_table, severity, passed, metric_value, details) "
        "VALUES ('raw', 'manual_csv', 'load_csv', %s, %s, %s, %s, %s)",
        (
            SPECS[result.kind].table,
            "info" if passed else "error",
            passed,
            loaded,
            json.dumps(
                {
                    "file": path.name,
                    "valid_rows": len(result.rows),
                    "errors": result.errors[:20],
                    "dry_run": dry_run,
                },
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()


def load(kind: str, path: Path, allow_sample: bool = False, dry_run: bool = False) -> Result:
    """Kiểm tra rồi ghi vào raw (upsert theo khóa). Có dòng sai thì không ghi gì."""
    result = parse_file(kind, path, allow_sample)
    spec = SPECS[kind]
    with db.connect() as conn:
        loaded = 0
        if not result.errors and not dry_run:
            db.apply_ddl(conn)
            loaded = db.copy_upsert(conn, spec.table, spec.columns, result.rows, spec.key)
        log_dq(conn, result, path, loaded, dry_run)
    return result
