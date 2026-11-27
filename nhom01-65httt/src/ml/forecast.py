"""N8c: dự báo chiều dòng tiền khối ngoại của ngành ICB cấp 2 trong tuần kế tiếp (XGBoost, walk-forward).

Nhãn chính: tuần t+1 khối ngoại mua ròng (INFLOW) hay bán ròng (OUTFLOW) ngành đó; nhãn phụ: giá trị ròng (tỷ đồng, hồi quy).
Mô hình so với hai mô hình cơ sở: "tuần sau giống tuần này" và "luôn đoán lớp phổ biến". Kết quả được báo cáo đúng như đo được,
kể cả khi không vượt mô hình cơ sở.

Chạy (từ src/):  python -m ml.forecast [--dry-run]
"""

import argparse
import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

from ml import common, features, forecast_eval

log = logging.getLogger("ml.forecast")

FIRST_TEST_WEEK = pd.Timestamp("2023-01-02")
BLOCK_WEEKS = 13  # tập kiểm tra theo quý; huấn luyện lại ở đầu mỗi quý
VERSION = "0.2.0"
DEV_END = pd.Timestamp("2023-12-31")  # chọn cấu hình chỉ bằng 2023; 2024 trở đi chỉ để báo cáo
SELECT_MIN_ACC_GAIN = (
    0.010  # nhóm đặc trưng chỉ được thêm nếu cải thiện accuracy tập chọn >= 1 điểm
)
SELECT_MIN_AUC_GAIN = 0.005  # và AUC tập chọn >= 0,005
PARAMS = dict(
    n_estimators=200,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=10,
    reg_lambda=5.0,
    tree_method="hist",
    n_jobs=1,  # n_jobs = 1 để kết quả tái lập được
    random_state=common.SEED,
)

FLOW_SQL = """
SELECT week_start_date AS week, icb_l2_code AS sector,
       sum(net_value_bn) FILTER (WHERE investor_type = 'FOREIGN') AS net,
       sum(buy_value_bn) FILTER (WHERE investor_type = 'FOREIGN') AS buy,
       sum(sell_value_bn) FILTER (WHERE investor_type = 'FOREIGN') AS sell,
       sum(net_value_bn) FILTER (WHERE investor_type = 'PROP' AND trade_date >= %(prop_start)s) AS prop_net
FROM dw.ds_flow_daily
WHERE icb_l2_code ~ '^[0-9]{4}$'
GROUP BY 1, 2
"""
PRICE_SQL = """
WITH d AS (
    SELECT trade_date, icb_l2_code AS sector,
           sum(LEAST(GREATEST(pct_change, -15), 15) * total_value_bn) / nullif(sum(total_value_bn), 0) AS ret_pct,
           sum(total_value_bn) AS value
    FROM dw.ds_stock_daily
    WHERE icb_l2_code ~ '^[0-9]{4}$' AND pct_change IS NOT NULL
    GROUP BY 1, 2
)
SELECT date_trunc('week', trade_date)::date AS week, sector,
       exp(sum(ln(1 + coalesce(ret_pct, 0) / 100.0))) - 1 AS ret, sum(value) AS value
FROM d GROUP BY 1, 2
"""
# Lợi suất ngành CÓ THỂ ĐẦU TƯ: rổ trọng số theo giá trị giao dịch của TUẦN TRƯỚC (biết trước khi mua), giữ trong tuần.
# Khác PRICE_SQL (trọng số cùng ngày, chỉ dùng làm đặc trưng quá khứ) vốn thiên lệch lên vì ngày khối lượng lớn thường là ngày tăng.
INVESTABLE_SQL = """
WITH sw AS (
    SELECT date_trunc('week', trade_date)::date AS week, icb_l2_code AS sector, symbol,
           exp(sum(ln(1 + LEAST(GREATEST(pct_change, -15), 15) / 100.0))) - 1 AS r,
           sum(total_value_bn) AS v
    FROM dw.ds_stock_daily
    WHERE icb_l2_code ~ '^[0-9]{4}$' AND pct_change IS NOT NULL
    GROUP BY 1, 2, 3
), w AS (
    SELECT week, sector, r, lag(v) OVER (PARTITION BY symbol ORDER BY week) AS prev_v FROM sw
)
SELECT week, sector, sum(r * prev_v) / nullif(sum(prev_v), 0) AS ret_inv
FROM w WHERE prev_v > 0 GROUP BY 1, 2
"""
MARKET_SQL = """
SELECT date_trunc('week', trade_date)::date AS week,
       sum(foreign_net_bn) AS foreign_net,
       exp(sum(ln(1 + coalesce(vnindex_pct_change, 0) / 100.0))) - 1 AS vnindex_ret,
       coalesce(stddev_samp(vnindex_pct_change), 0) AS vnindex_vol
FROM dw.mv_market_daily_kpi GROUP BY 1
"""
MACRO_SQL = """
SELECT DISTINCT ON (date_trunc('week', trade_date), indicator_code)
       date_trunc('week', trade_date)::date AS week, indicator_code, value
FROM dw.ds_macro_daily
ORDER BY date_trunc('week', trade_date), indicator_code, trade_date DESC
"""
# Khóa ngành của dự báo = dòng đại diện cấp 2 `<mã cấp 2>_NA` trong dim_sector (mỗi ngành cấp 2 đúng một dòng)
SENTIMENT_SQL = """
WITH m AS (SELECT model_key FROM dw.dim_model WHERE task = 'sentiment' ORDER BY trained_at DESC LIMIT 1),
a AS (
    SELECT DISTINCT f.article_key, coalesce(f.icb_l2_code, f.entity_code) AS sector, f.session_date_key, f.sentiment_score
    FROM dw.fact_news_sentiment f JOIN m USING (model_key)
    WHERE coalesce(f.icb_l2_code, f.entity_code) ~ '^[0-9]{4}$'
)
SELECT t.week_start_date AS week, a.sector, avg(a.sentiment_score) AS sent_mean0, count(*) AS sent_n0
FROM a JOIN dw.dim_time t ON t.date_key = a.session_date_key GROUP BY 1, 2
"""
ROOM_SQL = """
WITH s AS (
    SELECT d.trade_date, d.icb_l2_code AS sector, d.total_value_bn AS val,
           LEAST(GREATEST(1 - f.current_room / f.total_room, 0), 1) AS fill
    FROM dw.ds_stock_daily d
    JOIN raw.vnd_foreigns f ON f.code = d.symbol AND f.trade_date = d.trade_date
    WHERE f.total_room > 0 AND f.current_room IS NOT NULL AND d.total_value_bn > 0
      AND d.icb_l2_code ~ '^[0-9]{4}$'
)
SELECT date_trunc('week', trade_date)::date AS week, sector,
       sum(fill * val) / sum(val) AS room_fill,
       coalesce(sum(val) FILTER (WHERE fill >= 0.9) / sum(val), 0) AS room_tight
FROM s GROUP BY 1, 2
"""
SECTOR_SQL = "SELECT icb_l2_code AS code, sector_key FROM dw.dim_sector WHERE sector_code = icb_l2_code || '_NA'"


def load(conn) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Đọc dữ liệu thô từ dw và dựng bảng đặc trưng; trả (bảng, ngày giao dịch mới nhất)."""
    flow = common.read_sql(conn, FLOW_SQL, {"prop_start": "2022-05-17"})
    price = common.read_sql(conn, PRICE_SQL)
    inv = common.read_sql(conn, INVESTABLE_SQL)
    inv["week"] = pd.to_datetime(inv["week"])
    inv["ret_inv"] = inv["ret_inv"].astype(float)
    market = common.read_sql(conn, MARKET_SQL)
    macro_long = common.read_sql(conn, MACRO_SQL)
    latest = pd.Timestamp(
        common.read_sql(conn, "SELECT max(trade_date) AS d FROM dw.mv_market_daily_kpi")["d"][0]
    )
    for frame in (flow, price, market, macro_long):
        frame["week"] = pd.to_datetime(frame["week"])
    price = price.merge(inv, on=["week", "sector"], how="left")
    for frame, cols in (
        (flow, ["net", "buy", "sell", "prop_net"]),
        (price, ["ret", "value"]),
        (market, ["foreign_net", "vnindex_ret", "vnindex_vol"]),
    ):
        for c in cols:
            frame[c] = frame[c].astype(float)
    macro = (
        macro_long.pivot(index="week", columns="indicator_code", values="value")
        .astype(float)
        .reset_index()
    )
    macro.columns.name = None
    sentiment = None
    weekly_sent = common.read_sql(conn, SENTIMENT_SQL)
    if not weekly_sent.empty:  # chỉ có sau khi chạy python -m ml.sentiment
        weekly_sent["week"] = pd.to_datetime(weekly_sent["week"])
        weekly_sent[["sent_mean0", "sent_n0"]] = weekly_sent[["sent_mean0", "sent_n0"]].astype(
            float
        )
        grid = pd.DataFrame({"week": sorted(set(flow["week"]))}).merge(
            pd.DataFrame({"sector": sorted(set(flow["sector"]))}), how="cross"
        )
        sentiment = features.sentiment_features(
            grid.merge(weekly_sent, on=["week", "sector"], how="left")
        )
    room = common.read_sql(conn, ROOM_SQL)
    room["week"] = pd.to_datetime(room["week"])
    room[["room_fill", "room_tight"]] = room[["room_fill", "room_tight"]].astype(float)
    return features.build_features(flow, price, market, macro, sentiment, room), latest


def returns_table(df: pd.DataFrame) -> pd.DataFrame:
    """Lợi suất tuần kế tiếp của ngành và của VN-Index, dùng cho backtest ngành."""
    mk = df.drop_duplicates("week")[["week", "vnindex_ret0"]].copy()
    mk["week"] = mk["week"] - pd.Timedelta(
        days=7
    )  # lợi suất VN-Index của tuần t+1 gắn vào dòng tuần t
    mk = mk.rename(columns={"vnindex_ret0": "y_vnindex"})
    return df[["week", "sector", "y_ret", "y_cls"]].merge(mk, on="week", how="left")


def usable_weeks(df: pd.DataFrame, latest: pd.Timestamp) -> list[pd.Timestamp]:
    return features.complete_weeks(sorted(df["week"].unique()), latest)


def fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, cols: list[str], kind: str = "xgb"
) -> pd.DataFrame:
    """Huấn luyện trên `train` và dự báo `test`. Trả bảng có prob_inflow, pred_scaled.

    kind = "xgb" (mô hình chính) hoặc "logit" (hồi quy logistic đơn giản, dùng làm mốc so sánh).
    """
    if kind == "logit":
        clf = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=0.5, max_iter=500),
        )
        reg = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=0.5, max_iter=500),
        )
        clf.fit(train[cols], train["y_cls"].astype(int))
        out = test[["week", "sector", "scale", "net", "y_net", "y_cls"]].copy()
        out["prob_inflow"] = clf.predict_proba(test[cols])[:, 1]
        out["pred_scaled"] = np.nan
        out["pred_net"] = np.nan
        return out
    clf = XGBClassifier(objective="binary:logistic", eval_metric="logloss", **PARAMS)
    reg = XGBRegressor(objective="reg:squarederror", **PARAMS)
    clf.fit(train[cols], train["y_cls"].astype(int))
    reg.fit(train[cols], train["y_scaled"])
    out = test[["week", "sector", "scale", "net", "y_net", "y_cls"]].copy()
    out["prob_inflow"] = clf.predict_proba(test[cols])[:, 1]
    out["pred_scaled"] = reg.predict(test[cols])
    out["pred_net"] = out["pred_scaled"] * out["scale"]
    return out


def walk_forward(
    df: pd.DataFrame, cols: list[str], weeks: list[pd.Timestamp], kind: str = "xgb"
) -> pd.DataFrame:
    """Mở rộng cửa sổ huấn luyện theo thời gian; mỗi khối kiểm tra dài BLOCK_WEEKS tuần.

    Dòng tuần t dùng nhãn tuần t+1, nên khi dự báo cho khối bắt đầu ở T0 chỉ được huấn luyện bằng các dòng t <= T0 - 1 tuần
    (nhãn của chúng, tuần t+1 <= T0, đã biết). Tập kiểm tra luôn sau tập huấn luyện.
    """
    ready = df[df["week"].isin(weeks)].dropna(subset=["y_cls", "net_s3", "net_ma8"])
    test_weeks = [w for w in weeks if w >= FIRST_TEST_WEEK]
    preds = []
    for i in range(0, len(test_weeks), BLOCK_WEEKS):
        block = test_weeks[i : i + BLOCK_WEEKS]
        t0 = block[0]
        train = ready[ready["week"] <= t0 - pd.Timedelta(days=7)]
        test = ready[ready["week"].isin(block)]
        if len(train) < 500 or test.empty:
            continue
        assert train["week"].max() < test["week"].min()  # kiểm tra tập kiểm tra sau tập huấn luyện
        preds.append(fit_predict(train, test, cols, kind))
    return pd.concat(preds, ignore_index=True)


def evaluate(pred: pd.DataFrame, df: pd.DataFrame) -> dict:
    """Chỉ số tổng hợp trên toàn bộ dự báo ngoài mẫu và so với hai mô hình cơ sở."""
    y = pred["y_cls"].astype(int).to_numpy()
    prob = pred["prob_inflow"].to_numpy()
    yhat = (prob >= 0.5).astype(int)
    naive = (pred["net"] > 0).astype(int).to_numpy()  # tuần sau giống tuần này
    majority = int(round(df.loc[df["week"] < FIRST_TEST_WEEK, "y_cls"].dropna().mean()))
    maj = np.full_like(y, majority)
    real = pred["y_net"].to_numpy()
    return {
        "n": int(len(pred)),
        "weeks": int(pred["week"].nunique()),
        "model": {
            "accuracy": float(accuracy_score(y, yhat)),
            "f1_macro": float(f1_score(y, yhat, average="macro")),
            "auc": float(roc_auc_score(y, prob)),
            "log_loss": float(log_loss(y, np.clip(prob, 1e-6, 1 - 1e-6))),
        },
        "baseline_same_as_last_week": {
            "accuracy": float(accuracy_score(y, naive)),
            "f1_macro": float(f1_score(y, naive, average="macro")),
        },
        "baseline_majority": {"class": majority, "accuracy": float(accuracy_score(y, maj))},
        "regression": {
            "mae_bn": float(mean_absolute_error(real, pred["pred_net"])),
            "mae_naive_last_week_bn": float(mean_absolute_error(real, pred["net"])),
            "mae_zero_bn": float(mean_absolute_error(real, np.zeros_like(real))),
        },
        "by_year": {
            str(year): {
                "accuracy": float(
                    accuracy_score(g["y_cls"].astype(int), (g["prob_inflow"] >= 0.5).astype(int))
                ),
                "baseline": float(
                    accuracy_score(g["y_cls"].astype(int), (g["net"] > 0).astype(int))
                ),
                "n": int(len(g)),
            }
            for year, g in pred.groupby(pred["week"].dt.year)
        },
    }


def summarize(pred: pd.DataFrame) -> dict:
    """Accuracy, F1, AUC và accuracy cơ sở, tách tập chọn (<= 2023) và tập báo cáo (2024 trở đi)."""
    y = pred["y_cls"].astype(int)
    hat = (pred["prob_inflow"] >= 0.5).astype(int)
    naive = (pred["net"] > 0).astype(int)
    out = {
        "accuracy": float(accuracy_score(y, hat)),
        "f1_macro": float(f1_score(y, hat, average="macro")),
        "auc": float(roc_auc_score(y, pred["prob_inflow"])),
        "accuracy_baseline_same_as_last_week": float(accuracy_score(y, naive)),
    }
    for tag, mask in (("dev", pred["week"] <= DEV_END), ("test", pred["week"] > DEV_END)):
        if mask.sum():
            out[f"{tag}_accuracy"] = float(accuracy_score(y[mask], hat[mask]))
            out[f"{tag}_auc"] = float(roc_auc_score(y[mask], pred.loc[mask, "prob_inflow"]))
            out[f"{tag}_baseline"] = float(accuracy_score(y[mask], naive[mask]))
    return out


def candidate_configs(df: pd.DataFrame) -> dict[str, tuple[str, list[str]]]:
    groups = features.feature_groups(df)
    base = groups["flow"] + groups["cross"]
    combos = {
        "xgb flow_only": ("xgb", groups["flow"]),
        "xgb flow+cross": ("xgb", base),
        "xgb flow+price+cross": ("xgb", base + groups["price"]),
        "xgb flow+price+market+cross": ("xgb", base + groups["price"] + groups["market"]),
        "xgb flow+price+market+macro+cross": (
            "xgb",
            base + groups["price"] + groups["market"] + groups["macro"],
        ),
        "xgb flow+cross+prop (tự doanh)": ("xgb", base + groups["prop"]),
        "logit flow+cross": ("logit", base),
        "xgb flow+cross+calendar": ("xgb", base + groups["calendar"]),
        "logit flow+cross+calendar": ("logit", base + groups["calendar"]),
    }
    if "room" in groups:
        combos["xgb flow+cross+room"] = ("xgb", base + groups["room"])
        combos["xgb flow+cross+calendar+room"] = ("xgb", base + groups["calendar"] + groups["room"])
        combos["logit flow+cross+room"] = ("logit", base + groups["room"])
    if "sentiment" in groups:  # chỉ có sau khi chạy python -m ml.sentiment
        combos["xgb flow+cross+sentiment"] = ("xgb", base + groups["sentiment"])
        combos["logit flow+cross+sentiment"] = ("logit", base + groups["sentiment"])
    return combos


def ablation(df: pd.DataFrame, weeks: list[pd.Timestamp]) -> dict:
    """So sánh các nhóm đặc trưng và hai kiểu mô hình (accuracy tách tập chọn / tập báo cáo, kèm cơ sở)."""
    out = {}
    for name, (kind, cols) in candidate_configs(df).items():
        out[name] = {"n_features": len(cols), **summarize(walk_forward(df, cols, weeks, kind))}
    return out


def select_config(abl: dict, df: pd.DataFrame) -> tuple[str, list[str], str]:
    """Chọn nhóm đặc trưng chỉ bằng tập chọn (2023), quy tắc đặt trước: cấu hình gọn nhất `xgb flow+cross`, và chỉ thêm
    nhóm mới (lịch, room) nếu cải thiện accuracy >= 1 điểm VÀ AUC >= 0,005 trên tập chọn. Trả (tên, cột, lý do)."""
    base_name = "xgb flow+cross"
    base = abl[base_name]
    best = base_name
    best_acc = base["dev_accuracy"]
    for name in ("xgb flow+cross+calendar", "xgb flow+cross+room", "xgb flow+cross+calendar+room"):
        row = abl.get(name)
        if row is None:
            continue
        gain_acc = row["dev_accuracy"] - base["dev_accuracy"]
        gain_auc = row["dev_auc"] - base["dev_auc"]
        if (
            gain_acc >= SELECT_MIN_ACC_GAIN
            and gain_auc >= SELECT_MIN_AUC_GAIN
            and row["dev_accuracy"] > best_acc
        ):
            best, best_acc = name, row["dev_accuracy"]
    cols = candidate_configs(df)[best][1]
    reason = (
        f"giữ cấu hình gọn nhất ({base_name}): không nhóm mới nào cải thiện tập chọn >= {SELECT_MIN_ACC_GAIN:.0%} accuracy "
        f"và >= {SELECT_MIN_AUC_GAIN} AUC"
        if best == base_name
        else f"{best} cải thiện tập chọn (2023) so với {base_name}"
    )
    return best, cols, reason


def importance(df: pd.DataFrame, cols: list[str], weeks: list[pd.Timestamp]) -> dict:
    ready = df[df["week"].isin(weeks)].dropna(subset=["y_cls", "net_s3", "net_ma8"])
    clf = XGBClassifier(objective="binary:logistic", eval_metric="logloss", **PARAMS).fit(
        ready[cols], ready["y_cls"].astype(int)
    )
    imp = pd.Series(clf.feature_importances_, index=cols).sort_values(ascending=False)
    return {k: float(v) for k, v in imp.head(15).items()}


def live_prediction(df: pd.DataFrame, weeks: list[pd.Timestamp], cols: list[str]) -> pd.DataFrame:
    """Dự báo cho tuần kế tiếp sau tuần đủ gần nhất, huấn luyện bằng mọi dòng đã biết nhãn."""
    last = weeks[-1]
    ready = df[df["week"].isin(weeks)].dropna(subset=["y_cls", "net_s3", "net_ma8"])
    train = ready[ready["week"] <= last - pd.Timedelta(days=7)]
    test = df[(df["week"] == last)].dropna(subset=["net_s3", "net_ma8"])
    return fit_predict(train, test, cols)


def live_is_valid(live: pd.DataFrame, now: datetime | None = None) -> bool:
    """Dự báo tuần tới chỉ hợp lệ nếu được lập TRƯỚC khi tuần mục tiêu bắt đầu (giờ Việt Nam)."""
    if live.empty:
        return False
    now = now or datetime.now(UTC)
    target_start = (live["week"].max() + pd.Timedelta(days=7)).tz_localize("Asia/Ho_Chi_Minh")
    return now < target_start.to_pydatetime()


def write(
    conn, df: pd.DataFrame, backtest: pd.DataFrame, live: pd.DataFrame, model_key: int
) -> tuple[int, int]:
    sector_key = dict(common.read_sql(conn, SECTOR_SQL).itertuples(index=False, name=None))
    made_live = datetime.now(UTC)

    def key(d: pd.Timestamp) -> int:
        return int(d.strftime("%Y%m%d"))

    rows = []
    for r in backtest.itertuples():
        rows.append(
            (
                sector_key[r.sector], key(r.week + pd.Timedelta(days=7)), model_key, 1,
                "INFLOW" if r.prob_inflow >= 0.5 else "OUTFLOW", float(r.prob_inflow), float(r.pred_net),
                float(r.y_net), "INFLOW" if r.y_cls == 1 else "OUTFLOW",
                (r.week + pd.Timedelta(days=5)).tz_localize("Asia/Ho_Chi_Minh").to_pydatetime(),  # cuối tuần t
            )
        )  # fmt: skip
    n_back = len(rows)
    for r in live.itertuples():
        if not live_is_valid(live):
            break
        rows.append(
            (
                sector_key[r.sector], key(r.week + pd.Timedelta(days=7)), model_key, 1,
                "INFLOW" if r.prob_inflow >= 0.5 else "OUTFLOW", float(r.prob_inflow), float(r.pred_net),
                None, None, made_live,
            )
        )  # fmt: skip
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dw.fact_prediction (sector_key, target_week_start_date_key, model_key, horizon_weeks, "
            "predicted_class, prob_inflow, predicted_net_value_bn, actual_net_value_bn, actual_class, made_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    conn.commit()
    return n_back, len(rows) - n_back


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kết quả, không ghi vào dw")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with common.connect() as conn:
        df, latest = load(conn)
        weeks = usable_weeks(df, latest)
        abl = ablation(df, weeks)
        chosen, cols, reason = select_config(abl, df)
        log.info(
            "%d tuần đủ, %d ngành; cấu hình chọn: %s (%d đặc trưng)",
            len(weeks), df["sector"].nunique(), chosen, len(cols),
        )  # fmt: skip
        backtest = walk_forward(df, cols, weeks)
        result = evaluate(backtest, df)
        imp = importance(df, cols, weeks)
        live = live_prediction(df, weeks, cols)
        returns = returns_table(df)
        after_dev = backtest[backtest["week"] > DEV_END]
        extra = {
            "ranking": {
                "all": forecast_eval.rank_metrics(backtest),
                "test_2024_plus": forecast_eval.rank_metrics(after_dev),
            },
            "abnormal": forecast_eval.abnormal_metrics(backtest),
            "bootstrap": {
                "all": forecast_eval.bootstrap_vs_baseline(backtest),
                "test_2024_plus": forecast_eval.bootstrap_vs_baseline(after_dev),
            },
            "sector_backtest": {
                "all": forecast_eval.sector_backtest(backtest, returns),
                "test_2024_plus": forecast_eval.sector_backtest(after_dev, returns),
            },
        }
        metrics = common.to_jsonable(
            {
                **result,
                **extra,
                "ablation": abl,
                "selected_config": chosen,
                "selection_reason": reason,
                "feature_importance_top15": imp,
                "n_features": len(cols),
                "n_sectors": df["sector"].nunique(),
                "first_test_week": str(FIRST_TEST_WEEK.date()),
                "dev_end": str(DEV_END.date()),
                "last_complete_week": str(weeks[-1].date()),
                "params": PARAMS,
                "target": "foreign_net_sign_next_week",
                "note": "dự báo ngoài mẫu walk-forward (huấn luyện lại mỗi quý); chưa có đặc trưng CPI, ETF. Độ chính xác xấp xỉ mô hình cơ sở: các biến thể chênh nhau trong nhiễu thống kê.",
            }
        )
        print("Cấu hình:", chosen, "-", reason)
        print(
            f"Walk-forward {result['weeks']} tuần x {result['n'] // result['weeks']} ngành = {result['n']} dự báo"
        )
        print("Mô hình:", {k: round(v, 4) for k, v in result["model"].items()})
        print(
            "Cơ sở 'giống tuần trước':",
            {k: round(v, 4) for k, v in result["baseline_same_as_last_week"].items()},
        )
        print("Cơ sở 'lớp phổ biến':", result["baseline_majority"])
        print("Hồi quy:", {k: round(v, 2) for k, v in result["regression"].items()})
        print(
            "Theo năm:",
            {
                y: (round(v["accuracy"], 3), round(v["baseline"], 3))
                for y, v in result["by_year"].items()
            },
        )
        print("Ablation:")
        print(pd.DataFrame(abl).T.round(4).to_string())
        print("Đặc trưng quan trọng:", {k: round(v, 3) for k, v in list(imp.items())[:8]})
        print("Xếp hạng (2024+):", extra["ranking"]["test_2024_plus"])
        print("Bất thường:", {k: round(v, 3) for k, v in extra["abnormal"].items()})
        print("Bootstrap (2024+):", extra["bootstrap"]["test_2024_plus"])
        print("Backtest ngành (2024+):", extra["sector_backtest"]["test_2024_plus"])
        if args.dry_run:
            print("--dry-run: không ghi vào dw")
            return 0
        train_range = f"{df['week'].min().date()}..{weeks[-1].date()}"
        model_key = common.register_model(
            conn, "xgb_sector_flow", "forecast", VERSION, train_range, metrics
        )
        n_back, n_live = write(conn, df, backtest, live, model_key)
        target = (live["week"].max() + pd.Timedelta(days=7)).date()
        print(
            f"model_key {model_key}: ghi {n_back} dự báo ngoài mẫu + {n_live} dự báo tuần tới (tuần bắt đầu {target})"
        )
        if n_live == 0:
            print(
                f"Không ghi dự báo cho tuần {target}: tuần đó đã bắt đầu, dự báo lúc này không còn là dự báo trước."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
