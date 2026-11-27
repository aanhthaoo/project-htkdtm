"""Đối chiếu số liệu khối ngoại trong bài tổng hợp phiên (VnEconomy, Vietstock) với kho dữ liệu (N5).

Bài tổng hợp ghi dạng "khối ngoại bán ròng 1.200 tỷ đồng". Hàm trích số chạy bằng biểu thức chính quy;
độ phủ phụ thuộc số ngày có bài (RSS chỉ giữ vài ngày), nên đây là kiểm tra bổ sung, không phải nguồn chính.

Chạy (từ src/):  python -m etl.news.crosscheck
"""

import re
import sys
import uuid
from dataclasses import dataclass

import yaml

from ingestion import db

# "khối ngoại bán ròng 1.200 tỷ", "khối ngoại mua ròng gần 138,5 tỷ đồng", "khối ngoại bị bán ròng ... 500 tỷ"
FOREIGN_NET = re.compile(
    r"khối ngoại[^.\n]{0,60}?(?P<dir>mua|bán)\s+ròng[^.\n]{0,40}?"
    r"(?P<num>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(?P<unit>tỷ|triệu|nghìn tỷ)",
    re.IGNORECASE,
)
THRESHOLDS = db.ROOT / "src" / "etl" / "config" / "quality_thresholds.yml"


@dataclass(frozen=True)
class Claim:
    direction: int  # +1 mua ròng, -1 bán ròng
    amount_bn: float
    snippet: str

    @property
    def signed_bn(self) -> float:
        return self.direction * self.amount_bn


def parse_vn_number(text: str) -> float:
    """1.200 -> 1200; 138,5 -> 138.5; 1.234,5 -> 1234.5"""
    return float(text.replace(".", "").replace(",", "."))


def extract_foreign_net(text: str) -> list[Claim]:
    claims = []
    for m in FOREIGN_NET.finditer(text):
        value = parse_vn_number(m.group("num"))
        unit = m.group("unit").lower()
        amount_bn = (
            value * 1000 if unit == "nghìn tỷ" else value / 1000 if unit == "triệu" else value
        )
        direction = 1 if m.group("dir").lower() == "mua" else -1
        claims.append(Claim(direction, amount_bn, m.group(0)[:160]))
    return claims


def within_tolerance(claimed: float, actual: float, abs_tol: float, rel_tol: float) -> bool:
    diff = abs(claimed - actual)
    return diff <= abs_tol or diff <= rel_tol * max(abs(actual), 1e-9)


def run(conn) -> list[dict]:
    cfg = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))["cross_check"]
    rows = conn.execute(
        """
        SELECT a.article_id, a.source, a.title, a.content,
               (a.published_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS local_date
        FROM stg.news_article a
        WHERE a.source IN ('vneconomy', 'vietstock') AND a.published_at IS NOT NULL
          AND a.content ILIKE '%%khối ngoại%%' AND a.is_duplicate = false
        """
    ).fetchall()
    # Tổng ròng khối ngoại theo ngày: toàn thị trường và riêng HOSE (chỉ ngày dữ liệu đủ)
    actual = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            """
            SELECT f.trade_date,
                   sum(f.net_value_bn) FILTER (WHERE d.exchange = 'HOSE'),
                   sum(f.net_value_bn)
            FROM dw.fact_money_flow f
            JOIN dw.dim_investor_type it USING (investor_type_key)
            JOIN dw.dim_stock d USING (stock_key)
            WHERE it.code = 'FOREIGN' AND d.security_type = 'STOCK'
            GROUP BY f.trade_date
            """
        )
    }
    results = []
    for article_id, source, title, content, local_date in rows:
        if local_date not in actual:
            continue
        claims = extract_foreign_net(f"{title}\n{content}")
        if not claims:
            continue
        hose, market = actual[local_date]
        best = min(
            claims,
            key=lambda c: min(
                abs(c.signed_bn - float(hose or 0)), abs(c.signed_bn - float(market or 0))
            ),
        )
        ok_hose = within_tolerance(
            best.signed_bn, float(hose or 0), cfg["abs_tolerance_bn"], cfg["rel_tolerance"]
        )
        ok_market = within_tolerance(
            best.signed_bn, float(market or 0), cfg["abs_tolerance_bn"], cfg["rel_tolerance"]
        )
        results.append(
            {
                "date": local_date, "source": source, "claimed_bn": best.signed_bn,
                "hose_bn": float(hose or 0), "market_bn": float(market or 0),
                "match": ok_hose or ok_market, "snippet": best.snippet, "article_id": article_id,
            }
        )  # fmt: skip
    return results


def main() -> int:
    conn = db.connect()
    results = run(conn)
    run_id = uuid.uuid4().hex[:12]
    n = len(results)
    matched = sum(r["match"] for r in results)
    print(f"{n} bài có số liệu so sánh được; khớp {matched}/{n}")
    for r in sorted(results, key=lambda x: x["date"]):
        flag = "KHỚP" if r["match"] else "LỆCH"
        print(
            f"  {r['date']} {r['source']:10} bài: {r['claimed_bn']:>10,.1f}  HOSE: {r['hose_bn']:>10,.1f}  toàn TT: {r['market_bn']:>10,.1f}  {flag}"
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dw.dq_log (run_id, layer, source, check_name, target_table, severity, passed,
                                   metric_value, threshold_value, details)
            VALUES (%s, 'dw', 'news_vs_vndirect', 'foreign_net_vs_summary_articles', 'dw.fact_money_flow',
                    'info', %s, %s, NULL, %s)
            """,
            (
                run_id,
                n == 0 or matched / n >= 0.5,
                matched / n if n else None,
                db.jdump({"compared": n, "matched": matched}),
            ),
        )
    conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
