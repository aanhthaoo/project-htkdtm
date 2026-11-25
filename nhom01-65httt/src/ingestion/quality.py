"""Quan sát độ sẵn sàng của dữ liệu các ngày gần nhất và ghi vào dw.dq_log.

Mỗi lần chạy ghi thêm dòng mới (không ghi đè) để theo dõi độ trễ của nguồn theo thời gian:
ví dụ khối ngoại của ngày D có đầy đủ sau bao lâu.
"""

import logging
import uuid

import yaml

from ingestion import db

log = logging.getLogger(__name__)
THRESHOLDS = db.ROOT / "src" / "etl" / "config" / "quality_thresholds.yml"


def thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))


DAILY_COUNTS_SQL = """
SELECT p.trade_date,
       p.n_price,
       p.n_traded,
       COALESCE(f.n_foreign_active, 0) AS n_foreign_active,
       COALESCE(pr.n_prop, 0) AS n_prop
FROM (
    SELECT trade_date, count(*) AS n_price, count(*) FILTER (WHERE nm_value > 0) AS n_traded
    FROM raw.vnd_stock_prices
    WHERE trade_date >= current_date - %s
    GROUP BY 1
) p
LEFT JOIN (
    SELECT trade_date, count(*) FILTER (WHERE buy_val + sell_val > 0) AS n_foreign_active
    FROM raw.vnd_foreigns WHERE trade_date >= current_date - %s GROUP BY 1
) f USING (trade_date)
LEFT JOIN (
    SELECT trade_date, count(*) AS n_prop
    FROM raw.vnd_proprietary WHERE trade_date >= current_date - %s GROUP BY 1
) pr USING (trade_date)
ORDER BY trade_date
"""


def report_latest_days(conn, days: int = 10) -> list[dict]:
    """Ghi vào dq_log: số mã có giao dịch khối ngoại mỗi ngày so với ngưỡng, số dòng tự doanh."""
    min_active = thresholds()["latest_day"]["min_stocks_with_foreign_activity"]
    run_id = uuid.uuid4().hex[:12]
    rows = conn.execute(DAILY_COUNTS_SQL, (days, days, days)).fetchall()
    result = []
    with conn.cursor() as cur:
        for trade_date, n_price, n_traded, n_foreign_active, n_prop in rows:
            passed = n_foreign_active >= min_active
            result.append(
                {
                    "date": trade_date,
                    "prices": n_price,
                    "traded": n_traded,
                    "foreign_active": n_foreign_active,
                    "prop": n_prop,
                    "foreign_ok": passed,
                }
            )
            cur.execute(
                """
                INSERT INTO dw.dq_log
                    (run_id, layer, source, check_name, target_table, business_date,
                     severity, passed, metric_value, threshold_value, details)
                VALUES (%s, 'raw', 'vndirect', 'foreign_active_stocks', 'raw.vnd_foreigns', %s,
                        %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    trade_date,
                    "info" if passed else "warning",
                    passed,
                    n_foreign_active,
                    min_active,
                    db.jdump({"prices": n_price, "traded": n_traded, "prop_rows": n_prop}),
                ),
            )
    conn.commit()
    return result
