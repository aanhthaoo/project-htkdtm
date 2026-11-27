"""N9: số liệu cho bản nháp insight (docs/insight_nhap.md). Mọi con số trong bản nháp lấy từ đây hoặc từ dim_model.metrics.

Chỉ đọc dw. In JSON để dán vào tài liệu và để nhóm kiểm tra lại. Nhóm chưa chốt insight: đây là phát hiện sơ bộ, sẽ cập nhật ở giai đoạn 3.

Chạy (từ src/):  python -m ml.insights
"""

import json
import logging

import pandas as pd

from ml import common

log = logging.getLogger("ml.insights")

SECTOR_YEAR_SQL = """
SELECT year, icb_l2_code, icb_l2_name_vi, sum(net_value_bn) AS net_bn
FROM dw.ds_flow_daily WHERE investor_type = 'FOREIGN' AND icb_l2_code ~ '^[0-9]{4}$'
GROUP BY 1, 2, 3
"""
MARKET_YEAR_SQL = """
SELECT extract(year FROM trade_date)::int AS year, sum(foreign_net_bn) AS foreign_net_bn,
       round(avg(vnindex_pct_change)::numeric, 3) AS avg_daily_vnindex_pct
FROM dw.mv_market_daily_kpi GROUP BY 1 ORDER BY 1
"""
MODEL_SQL = "SELECT task, name, version, metrics FROM dw.dim_model WHERE (task, trained_at) IN (SELECT task, max(trained_at) FROM dw.dim_model GROUP BY task)"


def top_bottom(sector_year: pd.DataFrame, year: int, k: int = 3) -> dict:
    g = sector_year[sector_year["year"] == year].sort_values("net_bn", ascending=False)
    row = lambda r: {"sector": r.icb_l2_name_vi, "net_bn": round(float(r.net_bn), 0)}  # noqa: E731
    return {
        "top_buy": [row(r) for r in g.head(k).itertuples()],
        "top_sell": [row(r) for r in g.tail(k).iloc[::-1].itertuples()],
    }


def rotation(sector_year: pd.DataFrame) -> list[dict]:
    """Ngành đổi chiều dòng tiền khối ngoại giữa hai năm liền kề (mua ròng năm trước, bán ròng năm sau hoặc ngược lại), kèm biên độ."""
    p = sector_year.pivot(index="icb_l2_name_vi", columns="year", values="net_bn")
    out = []
    years = sorted(p.columns)
    for a, b in zip(years[:-1], years[1:], strict=True):
        flip = p[(p[a] * p[b]) < 0].dropna(subset=[a, b])
        for name, r in flip.iterrows():
            out.append(
                {
                    "from": int(a),
                    "to": int(b),
                    "sector": name,
                    "net_from_bn": round(float(r[a])),
                    "net_to_bn": round(float(r[b])),
                }
            )
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with common.connect() as conn:
        sy = common.read_sql(conn, SECTOR_YEAR_SQL)
        market = common.read_sql(conn, MARKET_YEAR_SQL)
        models = common.read_sql(conn, MODEL_SQL)
    sy["net_bn"] = sy["net_bn"].astype(float)
    sy["year"] = sy["year"].astype(int)
    market["foreign_net_bn"] = market["foreign_net_bn"].astype(float).round(0)
    metrics = {r.task: r.metrics for r in models.itertuples()}
    years = sorted(sy["year"].unique())
    out = {
        "foreign_net_by_year_market_bn": market.set_index("year")["foreign_net_bn"].to_dict(),
        "sector_extremes": {int(y): top_bottom(sy, int(y)) for y in years[-3:]},
        "sector_flips_between_years": rotation(sy[sy["year"].isin(years[-4:])]),
        "forecast": {
            k: metrics["forecast"].get(k)
            for k in ("baseline_same_as_last_week", "model", "abnormal", "bootstrap", "ranking")
        }
        if "forecast" in metrics
        else None,
        "clustering": {
            k: metrics["cluster"].get(k)
            for k in (
                "k",
                "silhouette",
                "features_dropped_not_persistent",
                "cluster_sizes",
                "n_clustered",
                "n_tail_clustered",
                "rule_labeled",
            )
        }
        if "cluster" in metrics
        else None,
        "sentiment": {
            k: metrics["sentiment"].get(k) for k in ("model", "baseline_tfidf_only", "test_n")
        }
        if "sentiment" in metrics
        else None,
        "recommendation": {
            k: metrics["recommendation"].get(k)
            for k in ("by_action", "backtest_test_2024_plus", "stats")
        }
        if "recommendation" in metrics
        else None,
    }
    print(json.dumps(common.to_jsonable(out), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
