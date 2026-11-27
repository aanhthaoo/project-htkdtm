"""N9: quy tắc khuyến nghị hằng tuần theo ngành, backtest sơ bộ, ghi dw.fact_recommendation.

Khuyến nghị lập vào cuối tuần t cho tuần t+1, chỉ dùng thông tin có đến hết tuần t:
  1. Dự báo chiều dòng tiền tuần t+1 của mô hình N8c (xác suất mua ròng);
  2. Đảo chiều dòng tiền khối ngoại theo phiên (bán ròng nhiều phiên rồi chuyển sang mua ròng, và ngược lại);
  3. Cảm xúc tin ngành chuyển tích cực / tiêu cực so với 4 tuần trước;
  4. Cảnh báo lệch pha: tin tích cực nhưng dòng tiền rút ra, hoặc tin tiêu cực nhưng dòng tiền vào (giảm độ chắc chắn).
Các ngưỡng đặt TRƯỚC khi xem kết quả backtest và không tinh chỉnh theo backtest (xem RULES). Backtest chỉ đo, không dùng để chọn ngưỡng.

Chạy (từ src/):  python -m ml.recommend [--dry-run]
"""

import argparse
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ml import common, forecast, forecast_eval

log = logging.getLogger("ml.recommend")

RULE_VERSION = "1.0"
RULES = {
    # 1. dự báo của mô hình: chỉ tính khi xác suất lệch khỏi 0,5 từ 0,10 trở lên; điểm đầy đủ (±1) khi lệch 0,25
    "forecast_min_edge": 0.10,
    "forecast_full_edge": 0.25,
    "forecast_weight": 1.0,
    # 2. đảo chiều dòng tiền theo phiên: N phiên trước (>= 4 phiên cùng chiều), K phiên gần nhất (>= 2 phiên chiều ngược lại)
    "reversal_prior_sessions": 5,
    "reversal_recent_sessions": 3,
    "reversal_min_prior_days": 4,
    "reversal_min_recent_days": 2,
    "reversal_weight": 0.5,
    # 3. cảm xúc ngành chuyển hướng: trung bình tuần t so với trung bình tối đa 4 tuần trước
    "sentiment_min_articles": 5,
    "sentiment_shift": 0.10,
    "sentiment_lookback_weeks": 4,
    "sentiment_weight": 0.5,
    # 4. lệch pha: cảm xúc tuần t và dòng tiền chuẩn hóa tuần t trái chiều rõ rệt
    "mismatch_sentiment": 0.15,
    "mismatch_flow_scaled": 0.5,
    "mismatch_shrink": 0.5,
    # hành động và độ chắc chắn
    "action_threshold": 0.5,
    "high_confidence_score": 1.25,
    "medium_confidence_score": 0.75,
}
# backtest: chi phí giả định mỗi lần mua hoặc bán (phí giao dịch ~0,15% + chênh lệch giá), không tính thuế chuyển nhượng
COST_PER_SIDE = 0.002
TILT_UP, TILT_DOWN = (
    1.5,
    0.5,
)  # danh mục lệch: nhân trọng số ngành khuyến nghị tăng / giảm rồi chuẩn hóa

DAILY_FLOW_SQL = """
SELECT trade_date, icb_l2_code AS sector, sum(net_value_bn) FILTER (WHERE investor_type = 'FOREIGN') AS net
FROM dw.ds_flow_daily WHERE icb_l2_code ~ '^[0-9]{4}$' GROUP BY 1, 2
"""
PRED_SQL = """
WITH latest AS (SELECT model_key FROM dw.dim_model WHERE task = 'forecast' ORDER BY trained_at DESC LIMIT 1)
SELECT DISTINCT ON (s.icb_l2_code, p.target_week_start_date_key)
       t.date AS target_week, s.icb_l2_code AS sector, p.prob_inflow, p.predicted_net_value_bn AS pred_net, p.made_at
FROM dw.fact_prediction p JOIN latest USING (model_key)
JOIN dw.dim_time t ON t.date_key = p.target_week_start_date_key
JOIN dw.dim_sector s ON s.sector_key = p.sector_key
ORDER BY s.icb_l2_code, p.target_week_start_date_key, p.made_at DESC
"""


# ---------------- Quy tắc (hàm thuần, kiểm thử bằng chuỗi dựng tay) ----------------
def forecast_signal(prob: float | None, rules: dict = RULES) -> float:
    """Điểm từ dự báo trong [-1, 1]: dương nếu dự báo dòng tiền vào. 0 khi không có dự báo hoặc xác suất sát 0,5."""
    if prob is None or pd.isna(prob):
        return 0.0
    edge = float(prob) - 0.5
    if (
        abs(edge) < rules["forecast_min_edge"] - 1e-9
    ):  # sai số số thực: 0,60 - 0,5 phải tính là đủ 0,10
        return 0.0
    return float(np.clip(edge / rules["forecast_full_edge"], -1, 1))


def reversal_signal(daily_net: pd.Series, rules: dict = RULES) -> int:
    """+1 nếu khối ngoại bán ròng nhiều phiên rồi chuyển sang mua ròng; -1 nếu ngược lại; 0 nếu không (hoặc chưa đủ số phiên).

    `daily_net`: dòng tiền ròng khối ngoại của ngành theo phiên, đã sắp theo ngày, chỉ gồm các phiên đến hết tuần t.
    """
    n, k = rules["reversal_prior_sessions"], rules["reversal_recent_sessions"]
    s = daily_net.dropna()
    if len(s) < n + k:
        return 0
    recent, prior = s.iloc[-k:], s.iloc[-(n + k) : -k]
    sell_prior, buy_prior = (prior < 0).sum(), (prior > 0).sum()
    buy_recent, sell_recent = (recent > 0).sum(), (recent < 0).sum()
    if (
        sell_prior >= rules["reversal_min_prior_days"]
        and prior.sum() < 0
        and buy_recent >= rules["reversal_min_recent_days"]
        and recent.sum() > 0
    ):
        return 1
    if (
        buy_prior >= rules["reversal_min_prior_days"]
        and prior.sum() > 0
        and sell_recent >= rules["reversal_min_recent_days"]
        and recent.sum() < 0
    ):
        return -1
    return 0


def sentiment_signal(
    mean_by_week: pd.Series, n_by_week: pd.Series, rules: dict = RULES
) -> tuple[int, float | None]:
    """(+1 | -1 | 0, cảm xúc tuần hiện tại). Tuần hiện tại là tuần cuối của chuỗi; cần đủ số bài.

    +1: cảm xúc tuần này dương và cao hơn trung bình các tuần trước (tối đa 4 tuần có tin) từ `sentiment_shift` trở lên;
    -1: âm và thấp hơn từ ngần ấy. Không đủ bài hoặc không có tuần trước thì 0.
    """
    if len(mean_by_week) == 0:
        return 0, None
    now, n_now = mean_by_week.iloc[-1], n_by_week.iloc[-1]
    if pd.isna(now) or n_now < rules["sentiment_min_articles"]:
        return 0, None if pd.isna(now) else float(now)
    prev = mean_by_week.iloc[:-1].tail(rules["sentiment_lookback_weeks"]).dropna()
    if len(prev) < 2:
        return 0, float(now)
    shift = float(now - prev.mean())
    if now > 0 and shift >= rules["sentiment_shift"]:
        return 1, float(now)
    if now < 0 and shift <= -rules["sentiment_shift"]:
        return -1, float(now)
    return 0, float(now)


def mismatch_signal(
    sent_now: float | None, flow_scaled: float | None, rules: dict = RULES
) -> str | None:
    """Lệch pha giữa tin và dòng tiền; trả mã tín hiệu hoặc None."""
    if sent_now is None or flow_scaled is None or pd.isna(sent_now) or pd.isna(flow_scaled):
        return None
    if sent_now >= rules["mismatch_sentiment"] and flow_scaled <= -rules["mismatch_flow_scaled"]:
        return "positive_news_outflow"
    if sent_now <= -rules["mismatch_sentiment"] and flow_scaled >= rules["mismatch_flow_scaled"]:
        return "negative_news_inflow"
    return None


REASON_TEXT = {
    "forecast_inflow": "mô hình dự báo dòng tiền khối ngoại vào ngành tuần tới (xác suất {p:.0%})",
    "forecast_outflow": "mô hình dự báo dòng tiền khối ngoại rút khỏi ngành tuần tới (xác suất mua ròng {p:.0%})",
    "reversal_up": "khối ngoại vừa chuyển từ bán ròng sang mua ròng",
    "reversal_down": "khối ngoại vừa chuyển từ mua ròng sang bán ròng",
    "sentiment_up": "cảm xúc tin ngành chuyển tích cực so với các tuần trước",
    "sentiment_down": "cảm xúc tin ngành chuyển tiêu cực so với các tuần trước",
    "positive_news_outflow": "lệch pha: tin tích cực nhưng dòng tiền khối ngoại đang rút ra",
    "negative_news_inflow": "lệch pha: tin tiêu cực nhưng dòng tiền khối ngoại đang vào",
}


def combine(
    prob: float | None,
    reversal: int,
    sentiment: int,
    mismatch: str | None,
    rules: dict = RULES,
) -> dict:
    """Gộp các tín hiệu thành khuyến nghị: điểm, hành động (increase | decrease | hold), độ chắc chắn, danh sách tín hiệu, lý do."""
    f = forecast_signal(prob, rules)
    score = (
        f * rules["forecast_weight"]
        + reversal * rules["reversal_weight"]
        + sentiment * rules["sentiment_weight"]
    )
    if mismatch:
        score *= rules[
            "mismatch_shrink"
        ]  # tin và dòng tiền trái chiều: giảm độ tin cậy của kết luận
    thr = rules["action_threshold"]
    action = "increase" if score >= thr else "decrease" if score <= -thr else "hold"
    signals = []
    if f > 0:
        signals.append("forecast_inflow")
    elif f < 0:
        signals.append("forecast_outflow")
    if reversal:
        signals.append("reversal_up" if reversal > 0 else "reversal_down")
    if sentiment:
        signals.append("sentiment_up" if sentiment > 0 else "sentiment_down")
    if mismatch:
        signals.append(mismatch)
    if action == "hold":
        confidence = "low"
    elif abs(score) >= rules["high_confidence_score"] and not mismatch:
        confidence = "high"
    elif abs(score) >= rules["medium_confidence_score"]:
        confidence = "medium"
    else:
        confidence = "low"
    parts = [REASON_TEXT[s].format(p=float(prob) if prob is not None else 0.0) for s in signals]
    verb = {
        "increase": "Nên tăng tỷ trọng",
        "decrease": "Nên giảm tỷ trọng",
        "hold": "Giữ nguyên tỷ trọng",
    }[action]
    reason = f"{verb}: " + "; ".join(parts) + "." if parts else f"{verb}: chưa có tín hiệu rõ."
    shown = (
        "mismatch" if mismatch else "reversal" if reversal else "none"
    )  # trường `signal` của API: ưu tiên cảnh báo lệch pha
    return {
        "score": float(score),
        "action": action,
        "confidence": confidence,
        "signals": signals,
        "signal": shown,
        "reason": reason,
    }


# ---------------- Dựng khuyến nghị theo tuần ----------------
class Inputs:
    """Dữ liệu đầu vào đã sắp sẵn; mọi truy vấn theo thời gian đều bị chặn ở cuối tuần t (không nhìn trước)."""

    def __init__(self, daily: pd.DataFrame, features: pd.DataFrame, preds: pd.DataFrame):
        self.daily = {
            s: g.set_index("trade_date")["net"].sort_index() for s, g in daily.groupby("sector")
        }
        self.features = features.set_index(["week", "sector"])
        self.preds = preds.set_index(["target_week", "sector"])
        self.sectors = sorted(features["sector"].unique())

    def recommend(self, week: pd.Timestamp, sector: str, rules: dict = RULES) -> dict:
        end = week + pd.Timedelta(days=6)  # hết tuần t (Chủ nhật)
        daily = self.daily.get(sector, pd.Series(dtype=float))
        daily = daily.loc[daily.index <= end]
        feat = self.features.loc[self.features.index.get_level_values("week") <= week]
        feat = (
            feat.xs(sector, level="sector")
            if sector in feat.index.get_level_values("sector")
            else feat.iloc[0:0]
        )
        mean = feat["sent_mean0"] if "sent_mean0" in feat else pd.Series(dtype=float)
        count = feat["sent_n0"] if "sent_n0" in feat else pd.Series(dtype=float)
        sent_sig, sent_now = sentiment_signal(mean, count, rules)
        flow_scaled = feat["net_s0"].iloc[-1] if len(feat) else None
        key = (week + pd.Timedelta(days=7), sector)
        prob = self.preds["prob_inflow"].get(key) if key in self.preds.index else None
        out = combine(
            prob,
            reversal_signal(daily, rules),
            sent_sig,
            mismatch_signal(sent_now, flow_scaled, rules),
            rules,
        )
        return {"week": week, "sector": sector, "prob_inflow": prob, **out}


def build_recommendations(
    inputs: Inputs, weeks: list[pd.Timestamp], rules: dict = RULES
) -> pd.DataFrame:
    rows = [inputs.recommend(w, s, rules) for w in weeks for s in inputs.sectors]
    out = pd.DataFrame(rows)
    out["signals"] = out["signals"].apply(lambda x: ",".join(x))
    return out


# ---------------- Backtest ----------------
def portfolio_weights(actions: pd.Series, tilt: bool = True) -> pd.Series:
    """Trọng số danh mục của một tuần từ khuyến nghị của 19 ngành.

    tilt=True: bắt đầu từ trọng số đều, nhân TILT_UP cho ngành tăng, TILT_DOWN cho ngành giảm, chuẩn hóa.
    tilt=False: chỉ mua đều các ngành khuyến nghị tăng; nếu không có ngành nào thì giữ trọng số đều.
    """
    n = len(actions)
    if tilt:
        w = actions.map({"increase": TILT_UP, "decrease": TILT_DOWN}).fillna(1.0)
        return w / w.sum()
    up = actions == "increase"
    return (up / up.sum()) if up.any() else pd.Series(1.0 / n, index=actions.index)


def max_drawdown(returns: pd.Series) -> float:
    curve = (1 + returns).cumprod()
    return float((curve / curve.cummax() - 1).min())


def perf(returns: pd.Series) -> dict:
    sd = returns.std(ddof=1)
    return {
        "cumulative": float((1 + returns).prod() - 1),
        "mean_weekly_pct": float(returns.mean() * 100),
        "sharpe": float(returns.mean() / sd * np.sqrt(52)) if sd > 0 else float("nan"),
        "max_drawdown": max_drawdown(returns),
    }


def backtest(recs: pd.DataFrame, returns: pd.DataFrame, cost: float = COST_PER_SIDE) -> dict:
    """Danh mục ngành theo khuyến nghị so với mua đều 19 ngành và VN-Index, giữ từng tuần.

    `recs`: week (tuần t), sector, action. `returns`: week (tuần t), sector, y_ret (lợi suất tuần t+1), y_vnindex.
    Mua đều 19 ngành là mốc chính vì danh mục lệch/khuyến nghị chỉ là phân bổ lại giữa các ngành.
    Chi phí: cost x tổng |thay đổi trọng số| mỗi tuần (cả bán và mua), danh mục mua đều không đổi nên không mất phí.
    """
    m = recs.merge(returns, on=["week", "sector"], how="inner").dropna(subset=["y_ret"])
    weeks = sorted(m["week"].unique())
    rows, prev = [], {}
    for week in weeks:
        g = m[m["week"] == week].set_index("sector").sort_index()
        row = {"week": week, "equal_weight": g["y_ret"].mean(), "vnindex": g["y_vnindex"].iloc[0]}
        for name, tilt in (("tilt", True), ("only_increase", False)):
            w = portfolio_weights(g["action"], tilt)
            turnover = (w - prev[name]).abs().sum() if name in prev else 0.0
            prev[name] = w
            row[f"{name}_turnover"] = float(turnover)
            row[f"{name}_gross"] = float((w * g["y_ret"]).sum())
            row[name] = row[f"{name}_gross"] - cost * turnover
        rows.append(row)
    t = pd.DataFrame(rows).set_index("week")
    out = {"weeks": int(len(t)), "cost_per_side": cost}
    for col in ("tilt", "only_increase", "equal_weight", "vnindex"):
        out[col] = perf(t[col])
    out["tilt_gross"], out["only_increase_gross"] = (
        perf(t["tilt_gross"]),
        perf(t["only_increase_gross"]),
    )
    out["mean_weekly_turnover"] = {
        c: float(t[f"{c}_turnover"].mean()) for c in ("tilt", "only_increase")
    }
    for col in ("tilt", "only_increase"):
        out[f"{col}_vs_equal_weight"] = forecast_eval.paired_bootstrap(
            t[col].reset_index(drop=True),
            t["equal_weight"].reset_index(drop=True),
            pd.Series(range(len(t))),
        )
        out[f"{col}_weeks_beating_equal_weight"] = float((t[col] > t["equal_weight"]).mean())
        out[f"{col}_weeks_beating_vnindex"] = float((t[col] > t["vnindex"]).mean())
    return out


def by_action(recs: pd.DataFrame, returns: pd.DataFrame) -> dict:
    """Lợi suất vượt trung bình 19 ngành của tuần kế tiếp, theo hành động và theo độ chắc chắn (kiểm tra khuyến nghị có phân biệt được không)."""
    m = recs.merge(returns, on=["week", "sector"], how="inner").dropna(subset=["y_ret"])
    m["excess"] = m["y_ret"] - m.groupby("week")["y_ret"].transform("mean")
    m["action_confidence"] = m["action"] + "/" + m["confidence"]
    out = {"all": {"n": int(len(m)), "next_week_foreign_inflow_rate": float(m["y_cls"].mean())}}
    for key in ("action", "action_confidence"):
        for name, g in m.groupby(key):
            by_week = g.groupby("week")["excess"].mean()
            se = by_week.std(ddof=1) / np.sqrt(len(by_week)) if len(by_week) > 1 else float("nan")
            out[f"{key}:{name}"] = {
                "n": int(len(g)),
                "weeks": int(len(by_week)),
                "next_week_foreign_inflow_rate": float(g["y_cls"].mean()),
                "mean_excess_pct": float(g["excess"].mean() * 100),
                "t_stat": float(by_week.mean() / se) if se and se > 0 else float("nan"),
            }
    return out


def signal_stats(recs: pd.DataFrame) -> dict:
    sig = recs["signals"].str.split(",").explode()
    return {
        "actions": recs["action"].value_counts(normalize=True).round(4).to_dict(),
        "confidence": recs["confidence"].value_counts(normalize=True).round(4).to_dict(),
        "signal_frequency": sig[sig != ""].value_counts(normalize=True).round(4).to_dict(),
    }


# ---------------- Ghi vào dw ----------------
def write(conn, recs: pd.DataFrame, model_key: int, live_week: pd.Timestamp | None) -> int:
    """Ghi khuyến nghị lịch sử (walk-forward) và, nếu có dự báo trực tiếp hợp lệ, khuyến nghị cho tuần tới. Xóa kết quả của các lần chạy cũ."""
    sector_key = dict(common.read_sql(conn, forecast.SECTOR_SQL).itertuples(index=False, name=None))
    now = datetime.now(UTC)
    rows = []
    for r in recs.itertuples():
        target = r.week + pd.Timedelta(days=7)
        made = (
            now
            if live_week is not None and r.week == live_week
            else (r.week + pd.Timedelta(days=5)).tz_localize("Asia/Ho_Chi_Minh").to_pydatetime()
        )
        rows.append(
            (
                sector_key[r.sector], int(target.strftime("%Y%m%d")), model_key, r.action, r.confidence,
                float(r.score), r.signals, r.reason, None if pd.isna(r.prob_inflow) else float(r.prob_inflow), made,
            )
        )  # fmt: skip
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM dw.fact_recommendation WHERE model_key IN "
            "(SELECT model_key FROM dw.dim_model WHERE task = 'recommendation')"
        )
        cur.executemany(
            "INSERT INTO dw.fact_recommendation (sector_key, week_start_date_key, model_key, action, confidence, score, "
            "signals, reason, prob_inflow, made_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    conn.commit()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kết quả, không ghi vào dw")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with common.connect() as conn:
        df, latest = forecast.load(conn)
        daily = common.read_sql(conn, DAILY_FLOW_SQL)
        preds = common.read_sql(conn, PRED_SQL)
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    daily["net"] = daily["net"].astype(float)
    preds["target_week"] = pd.to_datetime(preds["target_week"])
    preds[["prob_inflow", "pred_net"]] = preds[["prob_inflow", "pred_net"]].astype(float)
    weeks_all = forecast.usable_weeks(df, latest)
    # tuần quyết định: tuần t sao cho đã có dự báo cho tuần t+1 (dự báo ngoài mẫu từ 2023 và dự báo trực tiếp nếu có)
    have = {w - pd.Timedelta(days=7) for w in preds["target_week"].unique()}
    weeks = [w for w in weeks_all if w in have]
    inputs = Inputs(daily, df, preds)
    recs = build_recommendations(inputs, weeks)
    returns = forecast.returns_table(df)
    # khuyến nghị trực tiếp: chỉ khi tuần mục tiêu CHƯA bắt đầu (cùng quy tắc với dự báo trực tiếp của ml.forecast)
    live_week = (
        weeks[-1]
        if weeks
        and weeks[-1] == weeks_all[-1]
        and forecast.live_is_valid(pd.DataFrame({"week": [weeks[-1]]}))
        else None
    )
    done = recs[
        recs["week"].map(lambda w: (w + pd.Timedelta(days=7)) in set(df["week"]))
    ]  # có lợi suất tuần t+1
    results = {
        "rule_version": RULE_VERSION,
        "rules": RULES,
        "weeks": [str(weeks[0].date()), str(weeks[-1].date())],
        "stats": signal_stats(recs),
        "by_action": by_action(done, returns),
        "backtest_all": backtest(done, returns),
        "backtest_test_2024_plus": backtest(done[done["week"] > forecast.DEV_END], returns),
    }
    metrics = common.to_jsonable(results)
    print("Quy tắc:", RULE_VERSION, "| tuần", metrics["weeks"], "| phân bố:", metrics["stats"])
    for name in ("backtest_all", "backtest_test_2024_plus"):
        b = metrics[name]
        print(
            name,
            {
                k: {m: round(v, 4) for m, v in b[k].items()}
                for k in ("tilt", "only_increase", "equal_weight", "vnindex")
            },
        )
        print("  vòng quay trung bình mỗi tuần:", b["mean_weekly_turnover"])
        print(
            "  chưa trừ phí:",
            {k: round(b[k]["cumulative"], 4) for k in ("tilt_gross", "only_increase_gross")},
        )
        print(
            "  so với mua đều:",
            {k: b[k] for k in ("tilt_vs_equal_weight", "only_increase_vs_equal_weight")},
        )
    print("Theo hành động / độ chắc chắn:", metrics["by_action"])
    if args.dry_run:
        print("--dry-run: không ghi vào dw")
        return 0
    with common.connect() as conn:
        model_key = common.register_model(
            conn, "weekly_sector_rules", "recommendation", RULE_VERSION,
            f"{weeks[0].date()}..{weeks[-1].date()}", metrics,
        )  # fmt: skip
        n = write(conn, recs, model_key, live_week)
    print(
        f"model_key {model_key}: ghi {n} khuyến nghị (tuần trực tiếp: {live_week.date() + pd.Timedelta(days=7) if live_week is not None else 'không có'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
