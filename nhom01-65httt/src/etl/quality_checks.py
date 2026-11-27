"""Kiểm tra chất lượng và đối chiếu chéo dữ liệu có cấu trúc; ghi kết quả vào dw.dq_log (N3).

Chạy (từ src/):  python -m etl.quality_checks
Mỗi lần chạy có một run_id; mã thoát 1 nếu có kiểm tra mức `error` không đạt.
Các bài kiểm tra theo từng dòng dữ liệu (khóa, đơn vị, miền giá trị) nằm ở dbt test; đây là các kiểm tra
cần so sánh nhiều bảng hoặc nhiều nguồn.
"""

import logging
import sys
import uuid
from dataclasses import dataclass, field

import yaml

from ingestion import db

log = logging.getLogger("etl.quality")
THRESHOLDS = db.ROOT / "src" / "etl" / "config" / "quality_thresholds.yml"


@dataclass
class Result:
    check_name: str
    layer: str
    source: str
    target_table: str
    severity: str  # info | warning | error
    passed: bool
    metric: float | None = None
    threshold: float | None = None
    business_date: object = None
    details: dict = field(default_factory=dict)


def load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))


def scalar(conn, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


# ---------------------------------------------------------------- các kiểm tra


def check_reconciliation(conn) -> list[Result]:
    """Số liệu đi qua ETL không bị mất hoặc nhân đôi: raw -> stg -> dw."""
    out = []
    raw_foreign = scalar(
        conn,
        """
        SELECT sum(f.net_val) / 1e9 FROM raw.vnd_foreigns f
        JOIN stg.stg_day_quality q ON q.trade_date = f.trade_date AND q.is_foreign_complete
        JOIN stg.stg_stock_master m ON m.symbol = f.code
        """,
    )
    dw_foreign = scalar(
        conn,
        "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f "
        "JOIN dw.dim_investor_type it USING (investor_type_key) WHERE it.code = 'FOREIGN'",
    )
    diff = abs((raw_foreign or 0) - (dw_foreign or 0))
    out.append(
        Result("reconcile_foreign_net", "dw", "vndirect", "dw.fact_money_flow", "error", diff < 0.01,
               diff, 0.01, details={"raw_bn": raw_foreign, "dw_bn": dw_foreign})
    )  # fmt: skip
    raw_value = scalar(
        conn,
        """
        SELECT sum(p.nm_value + p.pt_value) / 1e9 FROM raw.vnd_stock_prices p
        JOIN stg.stg_calendar c ON c.trade_date = p.trade_date
        WHERE p.floor IN ('HOSE','HNX','UPCOM')
        """,
    )
    dw_value = scalar(
        conn,
        "SELECT sum(p.total_value_bn) FROM dw.fact_daily_price p "
        "JOIN dw.dim_stock d USING (stock_key) WHERE d.security_type = 'STOCK'",
    )
    diff = abs((raw_value or 0) - (dw_value or 0))
    out.append(
        Result("reconcile_trading_value", "dw", "vndirect", "dw.fact_daily_price", "error", diff < 0.01,
               diff, 0.01, details={"raw_bn": raw_value, "dw_bn": dw_value})
    )  # fmt: skip
    return out


def check_index_cross_source(conn, cfg: dict) -> list[Result]:
    """Đối chiếu hai nguồn độc lập: tổng giá trị KHỚP LỆNH các mã HOSE (VNDirect) và giá trị khớp lệnh VN-Index (CafeF).

    Cổ phiếu chiếm phần lớn nhưng không phải toàn bộ (còn chứng quyền, ETF, trái phiếu) nên tỷ lệ nằm dưới 1.
    Chỉ so sánh khớp lệnh vì thỏa thuận lớn thất thường (ví dụ 14/10/2020 có 6.800 tỷ ở phía chỉ số).
    """
    lo = cfg["cross_check"]["index_matched_value_ratio"]["min"]
    hi = cfg["cross_check"]["index_matched_value_ratio"]["max"]
    min_ratio_days = cfg["cross_check"]["index_match_min_days_ratio"]
    rows = conn.execute(
        """
        WITH h AS (
            SELECT trade_date, sum(matched_value_bn) AS stock_matched
            FROM stg.stg_price_daily WHERE exchange = 'HOSE' GROUP BY 1
        )
        SELECT h.trade_date, h.stock_matched, i.matched_value_bn,
               h.stock_matched / NULLIF(i.matched_value_bn, 0) AS ratio
        FROM h JOIN stg.stg_index_daily i USING (trade_date)
        ORDER BY 1
        """
    ).fetchall()
    bad = [r for r in rows if r[3] is None or not (lo <= r[3] <= hi)]
    share_ok = 1 - len(bad) / len(rows) if rows else 0
    out = [
        Result("index_matched_value_ratio", "dw", "vndirect+cafef", "stg.stg_price_daily", "warning",
               share_ok >= min_ratio_days, share_ok, min_ratio_days,
               details={"days_compared": len(rows), "days_out_of_range": len(bad), "range": [lo, hi]})
    ]  # fmt: skip
    for trade_date, stock, idx, ratio in bad:
        out.append(
            Result("index_matched_value_ratio_day", "dw", "vndirect+cafef", "stg.stg_price_daily", "warning",
                   False, float(ratio) if ratio is not None else None, hi, trade_date,
                   {"stock_matched_bn": float(stock), "index_matched_bn": float(idx or 0)})
        )  # fmt: skip
    return out


def check_calendar(conn) -> list[Result]:
    rows = conn.execute(
        """
        SELECT trade_date, in_vndirect, in_vnindex FROM stg.stg_calendar
        WHERE in_vndirect <> in_vnindex AND trade_date <= (SELECT max(trade_date) FROM stg.stg_price_daily)
        ORDER BY 1
        """
    ).fetchall()
    out = [
        Result("calendar_sources_agree", "stg", "vndirect+cafef", "stg.stg_calendar", "warning",
               len(rows) <= 5, len(rows), 5, details={"days": [str(r[0]) for r in rows]})
    ]  # fmt: skip
    for trade_date, in_vnd, in_idx in rows:
        out.append(
            Result("calendar_day_only_in_one_source", "stg", "vndirect+cafef", "stg.stg_calendar", "info",
                   False, None, None, trade_date, {"in_vndirect": in_vnd, "in_vnindex": in_idx})
        )  # fmt: skip
    return out


def check_foreign_gaps(conn) -> list[Result]:
    min_active = load_thresholds()["latest_day"]["min_stocks_with_foreign_activity"]
    rows = conn.execute(
        "SELECT trade_date, n_foreign_active, n_traded FROM stg.stg_day_quality "
        "WHERE NOT is_foreign_complete AND n_priced > 0 ORDER BY 1"
    ).fetchall()
    total = scalar(conn, "SELECT count(*) FROM stg.stg_day_quality WHERE n_priced > 0")
    out = [
        Result("foreign_incomplete_days", "stg", "vndirect", "stg.stg_day_quality", "warning",
               (len(rows) / total) <= 0.02 if total else True, len(rows) / total if total else 0, 0.02,
               details={"days": len(rows), "of": total})
    ]  # fmt: skip
    for trade_date, active, traded in rows:
        out.append(
            Result("foreign_active_stocks", "stg", "vndirect", "raw.vnd_foreigns", "warning", False,
                   active, min_active, trade_date, {"n_traded": traded})
        )  # fmt: skip
    return out


def check_prop_gaps(conn) -> list[Result]:
    rows = conn.execute(
        "SELECT trade_date, n_traded FROM stg.stg_day_quality WHERE is_prop_missing AND n_priced > 0 ORDER BY 1"
    ).fetchall()
    total = scalar(
        conn, "SELECT count(*) FROM stg.stg_day_quality WHERE is_prop_expected AND n_priced > 0"
    )
    out = [
        Result("prop_missing_days", "stg", "vndirect", "stg.stg_day_quality", "warning",
               (len(rows) / total) <= 0.02 if total else True, len(rows) / total if total else 0, 0.02,
               details={"days": len(rows), "of": total})
    ]  # fmt: skip
    for trade_date, traded in rows:
        out.append(
            Result("prop_day_missing", "stg", "vndirect", "raw.vnd_proprietary", "warning", False,
                   0, 1, trade_date, {"n_traded": traded})
        )  # fmt: skip
    return out


def check_other_domestic(conn, cfg: dict) -> list[Result]:
    limit = cfg["money_flow"]["max_other_negative_rate"]
    rate = scalar(
        conn,
        """
        SELECT count(*) FILTER (WHERE f.is_clipped)::numeric / NULLIF(count(*), 0)
        FROM dw.fact_money_flow f JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE it.code = 'OTHER_DOMESTIC'
        """,
    )
    return [
        Result("other_domestic_clipped_rate", "dw", "vndirect", "dw.fact_money_flow", "error",
               rate is not None and rate <= limit, float(rate or 0), limit)
    ]  # fmt: skip


def check_price_completeness(conn, cfg: dict) -> list[Result]:
    """Tỷ lệ ô (mã x ngày giao dịch) thiếu giá, tính theo vòng đời niêm yết của từng mã."""
    limit = cfg["completeness"]["max_missing_price_rate"]
    row = conn.execute(
        """
        WITH expected AS (
            SELECT d.symbol, c.trade_date
            FROM dw.dim_stock d
            JOIN stg.stg_calendar c
              ON c.trade_date BETWEEN d.first_trade_date AND coalesce(d.delisted_date, d.last_trade_date)
            WHERE d.security_type = 'STOCK' AND c.in_vndirect
        )
        SELECT count(*) AS expected, count(p.symbol) AS present
        FROM expected e
        LEFT JOIN stg.stg_price_daily p ON p.symbol = e.symbol AND p.trade_date = e.trade_date
        """
    ).fetchone()
    expected, present = row
    rate = 1 - present / expected if expected else 0
    return [
        Result("missing_price_rate", "stg", "vndirect", "stg.stg_price_daily", "warning", rate <= limit,
               float(rate), limit, details={"expected": expected, "present": present})
    ]  # fmt: skip


def check_sector_coverage(conn) -> list[Result]:
    row = conn.execute(
        """
        SELECT count(*) FILTER (WHERE s.sector_code = 'UNCLASSIFIED'),
               count(*) FILTER (WHERE s.sector_code LIKE '%\\_NA'),
               count(*)
        FROM dw.dim_stock d JOIN dw.dim_sector s USING (sector_key)
        WHERE d.security_type = 'STOCK' AND d.is_active
        """
    ).fetchone()
    unclassified, only_lv2, total = row
    return [
        Result("stock_sector_coverage", "dw", "vietcap", "dw.dim_stock", "warning",
               unclassified / total <= 0.05, unclassified / total, 0.05,
               details={"unclassified": unclassified, "only_icb_lv2": only_lv2, "active_stocks": total})
    ]  # fmt: skip


# ---------------------------------------------------------------- chạy và ghi nhật ký


def write_results(conn, run_id: str, results: list[Result]) -> None:
    with conn.cursor() as cur:
        for r in results:
            cur.execute(
                """
                INSERT INTO dw.dq_log
                    (run_id, layer, source, check_name, target_table, business_date,
                     severity, passed, metric_value, threshold_value, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (run_id, r.layer, r.source, r.check_name, r.target_table, r.business_date,
                 r.severity, r.passed, r.metric, r.threshold, db.jdump(r.details)),
            )  # fmt: skip
    conn.commit()


def run_all(conn) -> tuple[str, list[Result]]:
    cfg = load_thresholds()
    run_id = uuid.uuid4().hex[:12]
    results: list[Result] = []
    for fn in (
        check_reconciliation,
        check_calendar,
        check_foreign_gaps,
        check_prop_gaps,
    ):
        results += fn(conn)
    results += check_index_cross_source(conn, cfg)
    results += check_other_domestic(conn, cfg)
    results += check_price_completeness(conn, cfg)
    results += check_sector_coverage(conn)
    write_results(conn, run_id, results)
    return run_id, results


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    conn = db.connect()
    run_id, results = run_all(conn)
    summary = [r for r in results if r.business_date is None]
    detail_count = len(results) - len(summary)
    print(
        f"run_id {run_id}: {len(summary)} kiểm tra tổng hợp, {detail_count} dòng chi tiết theo ngày\n"
    )
    print(f"{'kiểm tra':34} {'mức':8} {'kết quả':8} {'giá trị':>12} {'ngưỡng':>10}")
    for r in summary:
        metric = "" if r.metric is None else f"{r.metric:.5g}"
        threshold = "" if r.threshold is None else f"{r.threshold:.5g}"
        print(
            f"{r.check_name:34} {r.severity:8} {'ĐẠT' if r.passed else 'KHÔNG':8} {metric:>12} {threshold:>10}"
        )
    failed_errors = [r for r in results if r.severity == "error" and not r.passed]
    return 1 if failed_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
