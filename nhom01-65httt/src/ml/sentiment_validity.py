"""Kiểm chứng ngoài nhãn: điểm cảm xúc của MÃ có liên hệ với lợi suất thật của mã đó không?

Accuracy trên nhãn LLM chỉ nói mô hình bắt chước nhãn tốt đến đâu, chưa nói điểm số có ý nghĩa thị trường. Ở đây đo trực tiếp:
mỗi phiên, xếp hạng các mã có tin theo điểm cảm xúc trung bình, rồi tính tương quan hạng (Spearman, "IC") với lợi suất vượt VN-Index
của mã (a) cùng phiên (tin và giá phản ứng cùng lúc, kỳ vọng dương), (b) phiên kế tiếp và (c) tổng 3 phiên kế tiếp (có thể dự báo).
IC trung bình các phiên, t-stat = IC trung bình / (độ lệch chuẩn / sqrt(số phiên)). Chỉ dùng phiên có đủ số mã tin (>= MIN_STOCKS).
Bài đăng sau 15h đã được gán vào phiên kế tiếp ở bước làm sạch tin, nên điểm của phiên t không dùng thông tin sau đóng cửa t.

Chạy (từ src/):  python -m ml.sentiment_validity
"""

import json
import logging

import numpy as np
import pandas as pd

from ml import common

log = logging.getLogger("ml.sentiment_validity")

MIN_STOCKS = 5  # số mã tối thiểu có tin trong một phiên để tính IC của phiên đó
MIN_NEWS = 1

SQL = """
WITH m AS (SELECT model_key FROM dw.dim_model WHERE task = 'sentiment' ORDER BY trained_at DESC LIMIT 1),
s AS (
    SELECT f.stock_key, f.session_date_key AS date_key, avg(f.sentiment_score) AS score, count(DISTINCT f.article_key) AS n_news
    FROM dw.fact_news_sentiment f JOIN m USING (model_key)
    WHERE f.entity_type = 'STOCK' AND f.stock_key IS NOT NULL
    GROUP BY 1, 2
),
mkt AS (SELECT trade_date, vnindex_pct_change AS mkt FROM dw.mv_market_daily_kpi),
p AS (
    SELECT p.stock_key, p.date_key, p.trade_date, p.pct_change AS ret
    FROM dw.fact_daily_price p
    WHERE p.has_trading AND NOT p.is_outlier_pct AND p.pct_change IS NOT NULL
)
SELECT p.stock_key, p.trade_date, p.ret - coalesce(mkt.mkt, 0) AS excess, s.score, s.n_news
FROM p JOIN mkt USING (trade_date) LEFT JOIN s ON s.stock_key = p.stock_key AND s.date_key = p.date_key
"""


def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Cột excess_t0 (cùng phiên), excess_t1 (phiên kế), excess_t1_3 (tổng 3 phiên kế) theo từng mã, theo thứ tự phiên giao dịch."""
    df = df.sort_values(["stock_key", "trade_date"]).copy()
    g = df.groupby("stock_key")["excess"]
    df["excess_t0"] = df["excess"]
    df["excess_t1"] = g.shift(-1)
    df["excess_t1_3"] = (g.shift(-1) + g.shift(-2) + g.shift(-3)).where(
        g.shift(-3).notna()
    )  # cần đủ 3 phiên kế
    return df


def daily_ic(df: pd.DataFrame, target: str, min_stocks: int = MIN_STOCKS) -> pd.Series:
    """Spearman giữa điểm cảm xúc và `target` theo từng phiên (chỉ phiên có đủ mã có tin)."""
    out = {}
    for day, g in df.dropna(subset=["score", target]).groupby("trade_date"):
        if len(g) >= min_stocks and g["score"].nunique() > 1 and g[target].nunique() > 1:
            out[day] = g["score"].rank().corr(g[target].rank())
    return pd.Series(out, dtype=float)


def summarize_ic(ic: pd.Series) -> dict:
    if ic.empty:
        return {"days": 0}
    se = ic.std(ddof=1) / np.sqrt(len(ic)) if len(ic) > 1 else float("nan")
    return {
        "days": int(len(ic)),
        "mean_ic": float(ic.mean()),
        "t_stat": float(ic.mean() / se) if se and se > 0 else float("nan"),
        "share_positive_days": float((ic > 0).mean()),
    }


def quantile_spread(df: pd.DataFrame, target: str, q: int = 3) -> dict:
    """Lợi suất vượt trung bình của nhóm điểm cao nhất trừ nhóm thấp nhất, mỗi phiên chia q nhóm (phiên đủ mã)."""
    spreads = []
    for _, g in df.dropna(subset=["score", target]).groupby("trade_date"):
        if len(g) < max(MIN_STOCKS, q * 3) or g["score"].nunique() < q:
            continue
        bucket = pd.qcut(g["score"].rank(method="first"), q, labels=False)
        spreads.append(g.loc[bucket == q - 1, target].mean() - g.loc[bucket == 0, target].mean())
    s = pd.Series(spreads, dtype=float)
    if s.empty:
        return {"days": 0}
    se = s.std(ddof=1) / np.sqrt(len(s))
    return {"days": int(len(s)), "mean_spread_pct": float(s.mean()), "t_stat": float(s.mean() / se)}


def pooled_ic(df: pd.DataFrame, target: str, n_boot: int = 1000, seed: int = 11) -> dict:
    """IC gộp mọi mã-phiên có tin: tương quan giữa điểm và `target` sau khi trừ trung bình của chính phiên đó (loại hiệu ứng thị trường chung).

    Khoảng tin cậy bằng bootstrap theo PHIÊN (các mã cùng phiên không độc lập). Dùng khi số mã có tin mỗi phiên quá ít để tính IC từng phiên.
    """
    d = df.dropna(subset=["score", target]).copy()
    lo, hi = d[target].quantile([0.01, 0.99])
    d[target] = d[target].clip(lo, hi)
    d["n_day"] = d.groupby("trade_date")["score"].transform("size")
    d = d[d["n_day"] >= 2]
    d["x"] = d["score"] - d.groupby("trade_date")["score"].transform("mean")
    d["y"] = d[target] - d.groupby("trade_date")[target].transform("mean")
    if len(d) < 30 or d["x"].std() == 0:
        return {"n": int(len(d))}
    corr = float(d["x"].corr(d["y"]))
    days = d["trade_date"].unique()
    groups = {k: g[["x", "y"]].to_numpy() for k, g in d.groupby("trade_date")}
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        pick = rng.choice(len(days), len(days))
        m = np.concatenate([groups[days[i]] for i in pick])
        boot.append(np.corrcoef(m[:, 0], m[:, 1])[0, 1] if m[:, 0].std() > 0 else np.nan)
    lo_b, hi_b = np.nanpercentile(boot, [2.5, 97.5])
    return {
        "n": int(len(d)),
        "days": int(len(days)),
        "corr": corr,
        "ci95": [float(lo_b), float(hi_b)],
        "significant_95": bool(lo_b > 0 or hi_b < 0),
    }


def validity(df: pd.DataFrame) -> dict:
    df = add_forward_returns(df)
    out = {"n_stock_days_with_news": int(df["score"].notna().sum())}
    for target in ("excess_t0", "excess_t1", "excess_t1_3"):
        out[target] = {
            "all": summarize_ic(daily_ic(df, target)),
            "pooled_demeaned": pooled_ic(df, target),
            "spread_top_vs_bottom_tercile": quantile_spread(df, target),
        }
        ic = daily_ic(df, target)
        out[target]["by_year"] = {
            str(y): summarize_ic(g) for y, g in ic.groupby(pd.to_datetime(ic.index).year)
        }
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with common.connect() as conn:
        df = common.read_sql(conn, SQL)
        model = common.read_sql(
            conn,
            "SELECT name, version FROM dw.dim_model WHERE task = 'sentiment' ORDER BY trained_at DESC LIMIT 1",
        )
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    for c in ("excess", "score", "n_news"):
        df[c] = df[c].astype(float)
    result = {"model": model.iloc[0].to_dict(), **validity(df)}
    print(json.dumps(common.to_jsonable(result), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
