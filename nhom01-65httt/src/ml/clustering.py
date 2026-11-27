"""N8b: phân cụm hành vi dòng tiền của cổ phiếu (K-Means), ghi nhãn vào dw.stock_cluster.

Đặc trưng theo mã trong giai đoạn có đủ cả khối ngoại và tự doanh (từ 17/05/2022), chuẩn hóa theo giá trị giao dịch
của chính mã để so sánh được giữa mã lớn và nhỏ; tỷ lệ theo ngày được cắt trong [-1, 1] để mã nhỏ không bị ngoại lệ chi phối.
Mọi mã cổ phiếu đều có nhãn: mã đủ dữ liệu và đủ hoạt động của khối ngoại được K-Means phân cụm; mã còn lại nhận nhãn quy tắc
(`thanh_khoan_thap`, `it_khoi_ngoai`, `chua_du_du_lieu`) vì không đủ dữ liệu để nói về hành vi dòng tiền.

Chạy (từ src/):  python -m ml.clustering
"""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score
from sklearn.preprocessing import StandardScaler

from ml import common

log = logging.getLogger("ml.clustering")

MIN_DAYS = 200  # số phiên tối thiểu trong giai đoạn đặc trưng
MIN_MEDIAN_VALUE_BN = 0.1  # giá trị giao dịch trung vị ngày tối thiểu (tỷ đồng)
MIN_FOREIGN_ACTIVE_SHARE = 0.3  # tỷ lệ phiên có khối ngoại giao dịch tối thiểu
K_RANGE = range(3, 9)
MIN_CLUSTER_SHARE = 0.01  # cụm nhỏ hơn 1% số mã bị loại khi chọn K
MIN_STABILITY = 0.6  # ARI trung bình giữa các seed tối thiểu
N_SEEDS = 10
MIN_FEATURE_PERSISTENCE = 0.2  # đặc trưng có tương quan nửa đầu-nửa sau thấp hơn mức này bị loại (xem persistent_features)

FEATURES = [
    "foreign_net_ratio",
    "foreign_share",
    "foreign_net_buy_day_share",
    "foreign_flow_vol",
    "foreign_weekly_persistence",
    "foreign_active_share",
    "prop_net_ratio",
    "prop_share",
    "price_vol",
    "log_value",
]

# tên theo đặc trưng nổi bật nhất của cụm: (đặc trưng, dấu) -> tên
NAME_BY_FEATURE = {
    ("foreign_net_ratio", 1): "ngoai_gom_rong",
    ("foreign_net_ratio", -1): "ngoai_xa_rong",
    ("foreign_share", 1): "ngoai_chu_dao",
    ("foreign_share", -1): "noi_dia_chu_dao",
    ("foreign_net_buy_day_share", 1): "ngoai_mua_deu",
    ("foreign_net_buy_day_share", -1): "ngoai_ban_deu",
    ("foreign_flow_vol", 1): "dong_tien_bat_on",
    ("foreign_flow_vol", -1): "dong_tien_on_dinh",
    ("foreign_weekly_persistence", 1): "dong_tien_theo_xu_huong",
    ("foreign_weekly_persistence", -1): "dong_tien_dao_chieu",
    ("foreign_active_share", 1): "ngoai_giao_dich_deu",
    ("foreign_active_share", -1): "ngoai_giao_dich_thua",
    ("prop_net_ratio", 1): "tu_doanh_gom",
    ("prop_net_ratio", -1): "tu_doanh_xa",
    ("prop_share", 1): "tu_doanh_chu_dao",
    ("prop_share", -1): "tu_doanh_it",
    ("price_vol", 1): "gia_bien_dong_manh",
    ("price_vol", -1): "gia_it_bien_dong",
    ("log_value", 1): "thanh_khoan_cao",
    ("log_value", -1): "thanh_khoan_vua",
}
TAIL_FEATURES = [
    "price_vol", "log_value", "beta", "amihud", "ret_autocorr", "up_day_share", "pv_corr", "skew",
]  # fmt: skip
NAME_BY_TAIL_FEATURE = {
    ("price_vol", 1): "gia_bien_dong_manh",
    ("price_vol", -1): "gia_it_bien_dong",
    ("log_value", 1): "thanh_khoan_kha",
    ("log_value", -1): "thanh_khoan_nho",
    ("beta", 1): "nhay_thi_truong",
    ("beta", -1): "it_nhay_thi_truong",
    ("amihud", 1): "tac_dong_gia_lon",
    ("amihud", -1): "tac_dong_gia_nho",
    ("ret_autocorr", 1): "gia_theo_xu_huong",
    ("ret_autocorr", -1): "gia_hoi_quy",
    ("up_day_share", 1): "nhieu_phien_tang",
    ("up_day_share", -1): "it_phien_tang",
    ("pv_corr", 1): "bien_dong_theo_khoi_luong",
    ("pv_corr", -1): "bien_dong_doc_lap_khoi_luong",
    ("skew", 1): "lech_duong",
    ("skew", -1): "lech_am",
}
TAIL_PREFIX = "phu_"  # nhóm phụ: mã ít khối ngoại hoặc thanh khoản thấp, phân cụm bằng đặc trưng không cần khối ngoại
TAIL_RULES = ("thanh_khoan_thap", "it_khoi_ngoai")
NEUTRAL_Z = 0.35  # mọi đặc trưng lệch dưới ngưỡng này (đơn vị độ lệch chuẩn) thì cụm là "can_bang"

FEATURE_SQL = """
WITH base AS (
    SELECT d.symbol, p.trade_date, t.week_start_date, p.total_value_bn, p.pct_change, p.is_outlier_pct,
           coalesce(sum(f.net_value_bn) FILTER (WHERE it.code = 'FOREIGN'), 0) AS f_net,
           coalesce(sum(f.buy_value_bn + f.sell_value_bn) FILTER (WHERE it.code = 'FOREIGN'), 0) AS f_turn,
           coalesce(sum(f.net_value_bn) FILTER (WHERE it.code = 'PROP'), 0) AS p_net,
           coalesce(sum(f.buy_value_bn + f.sell_value_bn) FILTER (WHERE it.code = 'PROP'), 0) AS p_turn
    FROM dw.fact_daily_price p
    JOIN dw.dim_stock d USING (stock_key)
    JOIN dw.dim_time t ON t.date_key = p.date_key
    LEFT JOIN dw.fact_money_flow f ON f.stock_key = p.stock_key AND f.trade_date = p.trade_date
    LEFT JOIN dw.dim_investor_type it ON it.investor_type_key = f.investor_type_key
    WHERE d.security_type = 'STOCK' AND p.has_trading AND p.trade_date >= %(start)s
    GROUP BY d.symbol, p.trade_date, t.week_start_date, p.total_value_bn, p.pct_change, p.is_outlier_pct
)
SELECT * FROM base ORDER BY symbol, trade_date
"""


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 4 or a.std() == 0 or b.std() == 0:
        return 0.0
    value = np.corrcoef(a, b)[0, 1]
    return float(value) if np.isfinite(value) else 0.0


def stock_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng mỗi mã từ dữ liệu ngày (cột: symbol, trade_date, week_start_date, total_value_bn, pct_change,
    is_outlier_pct, f_net, f_turn, p_net, p_turn)."""
    rows = []
    for symbol, g in daily.groupby("symbol", sort=True):
        value = g["total_value_bn"].to_numpy(dtype=float)
        total = value.sum()
        f_net, f_turn = g["f_net"].to_numpy(float), g["f_turn"].to_numpy(float)
        p_net, p_turn = g["p_net"].to_numpy(float), g["p_turn"].to_numpy(float)
        pct = g.loc[~g["is_outlier_pct"].astype(bool), "pct_change"].astype(float)
        # tỷ lệ ròng theo ngày, cắt [-1, 1]: ngày giá trị rất nhỏ không được chi phối
        ratio = np.clip(np.divide(f_net, value, out=np.zeros_like(f_net), where=value > 0), -1, 1)
        active = f_turn > 0
        weekly = (
            g.assign(f_net=f_net, value=value).groupby("week_start_date")[["f_net", "value"]].sum()
        )
        weekly_ratio = np.clip(
            (weekly["f_net"] / weekly["value"].where(weekly["value"] > 0)).fillna(0).to_numpy(),
            -1,
            1,
        )
        rows.append(
            {
                "symbol": symbol,
                "n_days": len(g),
                "median_value_bn": float(np.median(value)),
                "foreign_net_ratio": f_net.sum() / total if total > 0 else 0.0,
                "foreign_share": f_turn.sum() / (2 * total) if total > 0 else 0.0,
                "foreign_net_buy_day_share": float((f_net[active] > 0).mean())
                if active.any()
                else 0.5,
                "foreign_flow_vol": float(ratio.std()),
                "foreign_weekly_persistence": _safe_corr(weekly_ratio[:-1], weekly_ratio[1:]),
                "foreign_active_share": float(active.mean()),
                "prop_net_ratio": p_net.sum() / total if total > 0 else 0.0,
                "prop_share": p_turn.sum() / (2 * total) if total > 0 else 0.0,
                "price_vol": float(pct.std()) if len(pct) > 2 else 0.0,
                "log_value": float(np.log1p(np.mean(value))),
            }
        )
    return pd.DataFrame(rows)


def split_universe(
    feats: pd.DataFrame, all_symbols: list[str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Mã đủ điều kiện để phân cụm; các mã còn lại nhận nhãn quy tắc."""
    rule: dict[str, str] = {s: "chua_du_du_lieu" for s in all_symbols}
    enough = feats["n_days"] >= MIN_DAYS
    illiquid = enough & (feats["median_value_bn"] < MIN_MEDIAN_VALUE_BN)
    no_foreign = enough & ~illiquid & (feats["foreign_active_share"] < MIN_FOREIGN_ACTIVE_SHARE)
    for s in feats.loc[illiquid, "symbol"]:
        rule[s] = "thanh_khoan_thap"
    for s in feats.loc[no_foreign, "symbol"]:
        rule[s] = "it_khoi_ngoai"
    ok = feats[enough & ~illiquid & ~no_foreign].copy()
    for s in ok["symbol"]:
        rule.pop(s, None)
    return ok, rule


def persistent_features(
    daily: pd.DataFrame,
    min_corr: float = MIN_FEATURE_PERSISTENCE,
    features: list[str] | None = None,
) -> tuple[list[str], dict[str, float]]:
    """Giữ đặc trưng có tính bền: tương quan giữa nửa đầu và nửa sau của giai đoạn (theo ngày giữa) >= min_corr.

    Đặc trưng không bền (mã mua ròng ở nửa đầu không còn mua ròng ở nửa sau) chỉ mô tả nhiễu, không mô tả tính chất của mã.
    """
    features = features or FEATURES
    dates = sorted(daily["trade_date"].unique())
    mid = dates[len(dates) // 2]
    first, second = daily[daily["trade_date"] < mid], daily[daily["trade_date"] >= mid]
    a = stock_features(first).set_index("symbol")
    b = stock_features(second).set_index("symbol")
    ok = a[
        (a["n_days"] >= MIN_DAYS // 2) & (a["median_value_bn"] >= MIN_MEDIAN_VALUE_BN)
    ].index.intersection(
        b[(b["n_days"] >= MIN_DAYS // 2) & (b["median_value_bn"] >= MIN_MEDIAN_VALUE_BN)].index
    )
    corr = {f: float(np.corrcoef(a.loc[ok, f], b.loc[ok, f])[0, 1]) for f in features}
    return [f for f in features if corr[f] >= min_corr], corr


def temporal_ari_by_k(
    daily: pd.DataFrame, features: list[str], ks=K_RANGE, seed: int = common.SEED
) -> dict[int, float]:
    """Độ bền theo thời gian của cụm: phân cụm nửa đầu, gán nửa sau bằng tâm cũ, đo ARI giữa nhãn hai nửa.

    ARI cao nghĩa là mã giữ hành vi (cụm) qua thời gian, tức cụm mô tả tính chất của mã chứ không phải nhiễu của một giai đoạn.
    """
    dates = sorted(daily["trade_date"].unique())
    mid = dates[len(dates) // 2]
    a = stock_features(daily[daily["trade_date"] < mid]).set_index("symbol")
    b = stock_features(daily[daily["trade_date"] >= mid]).set_index("symbol")

    def ok(f):
        return f[
            (f["n_days"] >= MIN_DAYS // 2)
            & (f["median_value_bn"] >= MIN_MEDIAN_VALUE_BN)
            & (f["foreign_active_share"] >= MIN_FOREIGN_ACTIVE_SHARE)
        ].index

    both = ok(a).intersection(ok(b))
    xa, xb = a.loc[both, features].to_numpy(float), b.loc[both, features].to_numpy(float)
    lo, hi = np.percentile(xa, 1, axis=0), np.percentile(xa, 99, axis=0)
    scaler = StandardScaler().fit(np.clip(xa, lo, hi))
    za, zb = scaler.transform(np.clip(xa, lo, hi)), scaler.transform(np.clip(xb, lo, hi))
    out = {}
    for k in ks:
        km = KMeans(k, n_init=10, random_state=seed).fit(za)
        out[int(k)] = float(adjusted_rand_score(km.labels_, km.predict(zb)))
    return out


def prepare_matrix(ok: pd.DataFrame, features: list[str] | None = None) -> np.ndarray:
    """Cắt đuôi 1%-99% từng đặc trưng (giảm ảnh hưởng ngoại lệ) rồi chuẩn hóa."""
    x = ok[features or FEATURES].to_numpy(dtype=float)
    lo, hi = np.percentile(x, 1, axis=0), np.percentile(x, 99, axis=0)
    return StandardScaler().fit_transform(np.clip(x, lo, hi))


def choose_k(x: np.ndarray, seed: int) -> tuple[int, list[dict]]:
    """Chọn K theo Silhouette; loại K có cụm nhỏ hơn MIN_CLUSTER_SHARE hoặc kém ổn định (ARI giữa các seed)."""
    report = []
    for k in K_RANGE:
        labels0 = KMeans(k, n_init=10, random_state=seed).fit_predict(x)
        sil = float(silhouette_score(x, labels0))
        smallest = float(np.bincount(labels0).min() / len(x))
        others = [
            KMeans(k, n_init=10, random_state=seed + i).fit_predict(x) for i in range(1, N_SEEDS)
        ]
        stability = float(np.mean([adjusted_rand_score(labels0, o) for o in others]))
        report.append(
            {"k": k, "silhouette": sil, "smallest_share": smallest, "stability_ari": stability}
        )
    valid = [
        r
        for r in report
        if r["smallest_share"] >= MIN_CLUSTER_SHARE and r["stability_ari"] >= MIN_STABILITY
    ]
    pool = valid or [r for r in report if r["smallest_share"] >= MIN_CLUSTER_SHARE] or report
    return max(pool, key=lambda r: r["silhouette"])["k"], report


def name_clusters(
    centers: pd.DataFrame,
    sizes: pd.Series,
    pop_mean: pd.Series,
    pop_std: pd.Series,
    features: list[str] | None = None,
    name_map: dict | None = None,
) -> dict:
    """Đặt tên cụm theo đặc trưng nổi bật nhất so với toàn bộ mã được phân cụm (độ lệch chuẩn z của giá trị trung bình cụm).

    Tên gồm tối đa hai đặc trưng nổi bật nhất (nối bằng dấu +); cụm mà mọi đặc trưng lệch dưới NEUTRAL_Z là `can_bang`. Tên trùng được đánh số theo kích thước cụm giảm dần.
    """
    features = features or FEATURES
    z = (centers[features] - pop_mean[features]) / pop_std[features].replace(0, np.nan)
    original = {}
    for cid, row in z.iterrows():
        top = row.abs().sort_values(ascending=False)
        parts = [
            (name_map or NAME_BY_FEATURE)[(feature, 1 if row[feature] > 0 else -1)]
            for feature in top.index[:2]
            if top[feature] >= NEUTRAL_Z
        ]
        original[cid] = "+".join(parts) if parts else "can_bang"
    counts = pd.Series(original).value_counts()
    seen: dict[str, int] = {}
    names = dict(original)
    for cid in sizes.sort_values(ascending=False).index:
        base = original[cid]
        seen[base] = seen.get(base, 0) + 1
        if counts[base] > 1:
            names[cid] = f"{base}_{seen[base]}"
    return names


def fit(
    feats: pd.DataFrame,
    all_symbols: list[str],
    seed: int = common.SEED,
    features: list[str] | None = None,
    temporal_ari: dict[int, float] | None = None,
) -> dict:
    """Phân cụm. K chọn theo Silhouette; nếu có `temporal_ari` thì chọn theo độ bền theo thời gian trong các K hợp lệ."""
    features = features or FEATURES
    ok, rule_labels = split_universe(feats, all_symbols)
    x = prepare_matrix(ok, features)
    k, report = choose_k(x, seed)
    if temporal_ari:
        for r in report:
            r["temporal_ari"] = temporal_ari.get(r["k"])
        valid = [
            r
            for r in report
            if r["smallest_share"] >= MIN_CLUSTER_SHARE
            and r["stability_ari"] >= MIN_STABILITY
            and r.get("temporal_ari") is not None
        ]
        if valid:
            k = max(valid, key=lambda r: r["temporal_ari"])["k"]
    model = KMeans(k, n_init=10, random_state=seed).fit(x)
    labels = model.labels_
    centers = ok[features].groupby(labels).mean()
    sizes = pd.Series(labels).value_counts().sort_index()
    names = name_clusters(centers, sizes, ok[features].mean(), ok[features].std(), features)
    assigned = pd.DataFrame(
        {
            "symbol": ok["symbol"].to_numpy(),
            "cluster_label": [names[c] for c in labels],
            "silhouette": silhouette_samples(x, labels),
        }
    )
    rules = pd.DataFrame(
        {
            "symbol": list(rule_labels),
            "cluster_label": list(rule_labels.values()),
            "silhouette": np.nan,
        }
    )
    return {
        "labels": pd.concat([assigned, rules], ignore_index=True),
        "k": k,
        "k_report": report,
        "centers": centers.rename(index=names),
        "sizes": sizes.rename(index=names),
        "silhouette": float(silhouette_score(x, labels)),
        "n_clustered": len(ok),
        "features": features,
        "rule_counts": pd.Series(rule_labels).value_counts().to_dict(),
    }


MARKET_SQL = "SELECT trade_date, vnindex_pct_change AS mkt FROM dw.mv_market_daily_kpi"


def tail_features(daily: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng không cần khối ngoại: biến động, thanh khoản, beta so với VN-Index, tác động giá (Amihud),
    tự tương quan lợi suất, tỷ lệ phiên tăng, tương quan |lợi suất| với khối lượng, độ lệch."""
    m = market.set_index("trade_date")["mkt"].astype(float)
    rows = []
    for symbol, g in daily.groupby("symbol", sort=True):
        g = g[~g["is_outlier_pct"].astype(bool)].dropna(subset=["pct_change"])
        if len(g) < MIN_DAYS:
            continue
        r = g["pct_change"].astype(float).to_numpy()
        v = g["total_value_bn"].astype(float).to_numpy()
        mk = m.reindex(g["trade_date"]).to_numpy(float)
        ok = np.isfinite(mk)
        var = mk[ok].var()
        rows.append(
            {
                "symbol": symbol,
                "n_days": len(g),
                "median_value_bn": float(np.median(v)),
                "price_vol": float(r.std()),
                "log_value": float(np.log1p(v.mean())),
                "beta": float(np.cov(r[ok], mk[ok])[0, 1] / var)
                if var > 0 and ok.sum() > 30
                else 0.0,
                "amihud": float(np.log1p(np.mean(np.abs(r) / np.maximum(v, 1e-3)))),
                "ret_autocorr": _safe_corr(r[:-1], r[1:]),
                "up_day_share": float((r > 0).mean()),
                "pv_corr": _safe_corr(np.abs(r), np.log1p(v)),
                "skew": float(pd.Series(r).skew()),
            }
        )
    return pd.DataFrame(rows)


def fit_tail(
    daily: pd.DataFrame, market: pd.DataFrame, rule_labels: dict[str, str], seed: int = common.SEED
) -> dict | None:
    """Phân cụm riêng các mã đang chỉ có nhãn quy tắc `thanh_khoan_thap` / `it_khoi_ngoai` (và đủ >= MIN_DAYS phiên)."""
    candidates = [s for s, lab in rule_labels.items() if lab in TAIL_RULES]
    f = tail_features(daily[daily["symbol"].isin(candidates)], market)
    if len(f) < 60:
        return None
    x = f[TAIL_FEATURES].to_numpy(dtype=float)
    lo, hi = np.percentile(x, 1, axis=0), np.percentile(x, 99, axis=0)
    xs = StandardScaler().fit_transform(np.clip(x, lo, hi))
    k, report = choose_k(xs, seed)
    labels = KMeans(k, n_init=10, random_state=seed).fit_predict(xs)
    centers = f[TAIL_FEATURES].groupby(labels).mean()
    sizes = pd.Series(labels).value_counts().sort_index()
    names = name_clusters(
        centers,
        sizes,
        f[TAIL_FEATURES].mean(),
        f[TAIL_FEATURES].std(),
        TAIL_FEATURES,
        NAME_BY_TAIL_FEATURE,
    )
    names = {cid: TAIL_PREFIX + n for cid, n in names.items()}
    assigned = pd.DataFrame(
        {
            "symbol": f["symbol"].to_numpy(),
            "cluster_label": [names[c] for c in labels],
            "silhouette": silhouette_samples(xs, labels),
        }
    )
    return {
        "labels": assigned,
        "k": k,
        "k_report": report,
        "centers": centers.rename(index=names),
        "sizes": sizes.rename(index=names),
        "silhouette": float(silhouette_score(xs, labels)),
        "n_clustered": len(f),
        "features": TAIL_FEATURES,
    }


def combine_labels(result: dict, tail: dict | None) -> tuple[pd.DataFrame, dict[str, int]]:
    """Nhãn cuối cùng: cụm chính + cụm nhóm phụ; mã còn lại giữ nhãn quy tắc. Trả (bảng nhãn, số mã nhãn quy tắc còn lại)."""
    labels = result["labels"]
    if tail is not None:
        in_tail = set(tail["labels"]["symbol"])
        labels = pd.concat(
            [labels[~labels["symbol"].isin(in_tail)], tail["labels"]], ignore_index=True
        )
    rule_counts = labels.loc[
        labels["cluster_label"].isin(RULE_LABELS), "cluster_label"
    ].value_counts()
    return labels, {k: int(v) for k, v in rule_counts.items()}


RULE_LABELS = ("thanh_khoan_thap", "it_khoi_ngoai", "chua_du_du_lieu")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kết quả, không ghi vào dw")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    start = "2022-05-17"
    with common.connect() as conn:
        daily = common.read_sql(conn, FEATURE_SQL, {"start": start})
        market = common.read_sql(conn, MARKET_SQL)
        symbols = common.read_sql(
            conn, "SELECT symbol FROM dw.dim_stock WHERE security_type = 'STOCK' ORDER BY symbol"
        )["symbol"].tolist()
        end = str(daily["trade_date"].max())
        features, feature_corr = persistent_features(daily)
        dropped = [f for f in FEATURES if f not in features]
        temporal = temporal_ari_by_k(daily, features)
        result = fit(stock_features(daily), symbols, features=features, temporal_ari=temporal)
        _, rule_labels = split_universe(stock_features(daily), symbols)
        tail = fit_tail(daily, market, rule_labels)
        labels, rule_counts = combine_labels(result, tail)
        metrics = common.to_jsonable(
            {
                "k": result["k"],
                "silhouette": result["silhouette"],
                "temporal_ari_by_k": temporal,
                "n_clustered": result["n_clustered"],
                "n_tail_clustered": 0 if tail is None else tail["n_clustered"],
                "rule_labeled": rule_counts,
                "k_report": result["k_report"],
                "cluster_sizes": result["sizes"].to_dict(),
                "cluster_centers": result["centers"][features].to_dict(orient="index"),
                "features": features,
                "features_dropped_not_persistent": dropped,
                "feature_persistence_corr": feature_corr,
                "tail": None
                if tail is None
                else {
                    "k": tail["k"],
                    "silhouette": tail["silhouette"],
                    "k_report": tail["k_report"],
                    "cluster_sizes": tail["sizes"].to_dict(),
                    "cluster_centers": tail["centers"][TAIL_FEATURES].to_dict(orient="index"),
                    "features": TAIL_FEATURES,
                },
            }
        )
        print("ARI theo thời gian theo K:", {k: round(v, 3) for k, v in temporal.items()})
        print(
            f"K = {result['k']}, silhouette = {result['silhouette']:.3f}; đặc trưng bỏ do không bền: {dropped}"
        )
        print(
            f"Phân cụm chính {result['n_clustered']} mã; nhóm phụ {metrics['n_tail_clustered']} mã; nhãn quy tắc còn lại: {rule_counts}"
        )
        print(result["sizes"].to_string())
        print(result["centers"][features].round(4).to_string())
        if tail is not None:
            print(f"Nhóm phụ: K = {tail['k']}, silhouette = {tail['silhouette']:.3f}")
            print(tail["sizes"].to_string())
            print(tail["centers"][TAIL_FEATURES].round(3).to_string())
        if args.dry_run:
            print("--dry-run: không ghi vào dw")
            return 0
        model_key = common.register_model(
            conn, "kmeans_stock_flow", "cluster", "0.2.0", f"{start}..{end}", metrics
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO dw.stock_cluster (symbol, model_key, cluster_label, silhouette, assigned_at) "
                "VALUES (%s, %s, %s, %s, now())",
                [
                    (
                        r.symbol,
                        model_key,
                        r.cluster_label,
                        None if pd.isna(r.silhouette) else float(r.silhouette),
                    )
                    for r in labels.itertuples()
                ],
            )
        conn.commit()
        print(f"model_key {model_key}: ghi {len(labels)} nhãn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
