"""Thí nghiệm cải thiện phân cụm cổ phiếu (không ghi vào dw). In kết quả và lưu JSON vào `--out`.

  persistence : phân cụm bằng 05/2022-06/2024, gán cụm cho 07/2024-nay bằng tâm cũ; đo mã giữ cụm và cụm có dự đoán được hành vi sau đó không
  gmm         : Gaussian Mixture (độ thuộc mềm) so với K-Means: BIC, độ thuộc, độ ổn định theo thời gian
  hdbscan     : tìm nhóm ngoại lai thật (mã không thuộc cụm nào)
  yearly      : gán từng mã-năm vào cụm của mô hình toàn kỳ, đếm số mã chuyển cụm giữa các năm
  tail        : phân cụm riêng nhóm mã ít khối ngoại / thanh khoản thấp bằng đặc trưng không phụ thuộc khối ngoại

Chạy (từ src/):  python -m ml.clustering_experiments --out <thư mục>
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from ml import clustering as cl
from ml import common

log = logging.getLogger("ml.clustering_experiments")

START = "2022-05-17"
SPLIT = "2024-07-01"
MARKET_SQL = "SELECT trade_date, vnindex_pct_change AS mkt FROM dw.mv_market_daily_kpi"
TAIL_FEATURES = cl.TAIL_FEATURES


class Prep:
    """Cắt đuôi 1%-99% và chuẩn hóa, học trên một giai đoạn rồi áp dụng nguyên cho giai đoạn khác (không học lại)."""

    def __init__(self, x: np.ndarray):
        self.lo, self.hi = np.percentile(x, 1, axis=0), np.percentile(x, 99, axis=0)
        self.scaler = StandardScaler().fit(np.clip(x, self.lo, self.hi))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.scaler.transform(np.clip(x, self.lo, self.hi))


def eligible(daily: pd.DataFrame, min_days: int = cl.MIN_DAYS) -> pd.DataFrame:
    feats = cl.stock_features(daily)
    ok, _ = cl.split_universe(feats, feats["symbol"].tolist())
    return ok[ok["n_days"] >= min_days].reset_index(drop=True)


def _expected_agreement(a: np.ndarray, b: np.ndarray) -> float:
    pa, pb = np.bincount(a) / len(a), np.bincount(b) / len(b)
    k = max(len(pa), len(pb))
    pa, pb = np.pad(pa, (0, k - len(pa))), np.pad(pb, (0, k - len(pb)))
    return float((pa * pb).sum())


def eta_squared(values: pd.Series, groups: np.ndarray) -> float:
    """Tỷ lệ phương sai của `values` được giải thích bởi nhóm (R^2 của mô hình chỉ có nhóm)."""
    total = ((values - values.mean()) ** 2).sum()
    if total == 0:
        return 0.0
    within = values.groupby(groups).transform(
        lambda v: ((v - v.mean()) ** 2).sum() * 0 + (v - v.mean()) ** 2
    )
    return float(1 - within.sum() / total)


def persistence(daily: pd.DataFrame, k: int, features: list[str] | None = None) -> dict:
    features = features or cl.FEATURES
    p1 = daily[daily["trade_date"] < pd.Timestamp(SPLIT).date()]
    p2 = daily[daily["trade_date"] >= pd.Timestamp(SPLIT).date()]
    f1, f2 = eligible(p1), eligible(p2, min_days=150)
    common_syms = sorted(set(f1["symbol"]) & set(f2["symbol"]))
    a = f1.set_index("symbol").loc[common_syms]
    b = f2.set_index("symbol").loc[common_syms]
    prep = Prep(a[features].to_numpy(float))
    x1, x2 = prep(a[features].to_numpy(float)), prep(b[features].to_numpy(float))
    km = KMeans(k, n_init=10, random_state=common.SEED).fit(x1)
    l1, l2 = km.labels_, km.predict(x2)
    own2 = KMeans(k, n_init=10, random_state=common.SEED).fit_predict(
        x2
    )  # phân cụm độc lập giai đoạn 2
    rng = np.random.default_rng(common.SEED)
    shuffled = [float((rng.permutation(l2) == l1).mean()) for _ in range(200)]
    feat_corr = {f: float(np.corrcoef(a[f], b[f])[0, 1]) for f in features}
    # cụm của giai đoạn 1 giải thích bao nhiêu phương sai của đặc trưng giai đoạn 2
    r2 = {}
    for f in features:
        v = b[f].reset_index(drop=True)
        group_mean = v.groupby(l1).transform("mean")
        r2[f] = float(1 - ((v - group_mean) ** 2).sum() / ((v - v.mean()) ** 2).sum())
    # so sánh: dự đoán bằng chính giá trị đặc trưng đó ở giai đoạn 1 (hồi quy tuyến tính đơn)
    r2_own = {f: feat_corr[f] ** 2 for f in features}
    return {
        "k": k,
        "n_stocks": len(common_syms),
        "retention_rate": float((l1 == l2).mean()),
        "retention_if_independent": _expected_agreement(l1, l2),
        "retention_shuffled_mean": float(np.mean(shuffled)),
        "ari_period1_assigned_vs_period2_assigned": float(adjusted_rand_score(l1, l2)),
        "ari_period1_vs_independent_period2_fit": float(adjusted_rand_score(l1, own2)),
        "feature_correlation_p1_p2": feat_corr,
        "r2_p2_feature_explained_by_p1_cluster": r2,
        "r2_p2_feature_explained_by_own_p1_value": r2_own,
        "mean_r2_cluster": float(np.mean(list(r2.values()))),
        "mean_r2_own_value": float(np.mean(list(r2_own.values()))),
    }


def gmm_experiment(daily: pd.DataFrame, k_kmeans: int) -> dict:
    ok = eligible(daily)
    x = cl.prepare_matrix(ok)
    out = {"bic": {}}
    for k in range(2, 9):
        for cov in ("diag", "full"):
            g = GaussianMixture(k, covariance_type=cov, n_init=5, random_state=common.SEED).fit(x)
            out["bic"][f"{cov}_{k}"] = float(g.bic(x))
    for cov in ("diag", "full"):
        keys = {k: out["bic"][f"{cov}_{k}"] for k in range(2, 9)}
        out[f"best_k_{cov}"] = int(min(keys, key=keys.get))
    kbest = k_kmeans
    g = GaussianMixture(kbest, covariance_type="diag", n_init=10, random_state=common.SEED).fit(x)
    proba = g.predict_proba(x)
    km = KMeans(kbest, n_init=10, random_state=common.SEED).fit_predict(x)
    top = proba.max(axis=1)
    out.update(
        {
            "gmm_k": kbest,
            "covariance": "diag",
            "mean_max_membership": float(top.mean()),
            "share_membership_below_0.6": float((top < 0.6).mean()),
            "share_membership_above_0.9": float((top >= 0.9).mean()),
            "ari_vs_kmeans": float(adjusted_rand_score(km, proba.argmax(axis=1))),
            "cluster_sizes_hard": np.bincount(proba.argmax(axis=1), minlength=kbest).tolist(),
            "silhouette_hard": float(silhouette_score(x, proba.argmax(axis=1))),
        }
    )
    return out


def hdbscan_experiment(daily: pd.DataFrame) -> dict:
    try:
        import hdbscan
    except ImportError:
        return {"skipped": "chưa cài hdbscan"}
    ok = eligible(daily)
    x = cl.prepare_matrix(ok)
    z = PCA(n_components=5, random_state=common.SEED).fit_transform(x)
    out = {
        "explained_variance_5pc": float(
            PCA(5, random_state=common.SEED).fit(x).explained_variance_ratio_.sum()
        )
    }
    for mcs in (8, 15, 25):
        h = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=5).fit(z)
        lab = h.labels_
        clustered = lab >= 0
        out[f"min_cluster_size_{mcs}"] = {
            "n_clusters": int(lab.max() + 1),
            "noise_share": float((~clustered).mean()),
            "sizes": np.bincount(lab[clustered]).tolist() if clustered.any() else [],
            "silhouette_excl_noise": float(silhouette_score(z[clustered], lab[clustered]))
            if len(set(lab[clustered])) > 1
            else None,
        }
    return out


def yearly_transitions(daily: pd.DataFrame, k: int, features: list[str] | None = None) -> dict:
    features = features or cl.FEATURES
    ok = eligible(daily)
    prep = Prep(ok[features].to_numpy(float))
    km = KMeans(k, n_init=10, random_state=common.SEED).fit(prep(ok[features].to_numpy(float)))
    years = {}
    daily = daily.assign(year=pd.to_datetime(daily["trade_date"]).dt.year)
    for year, g in daily.groupby("year"):
        feats = cl.stock_features(g)
        feats = feats[
            (feats["n_days"] >= 100) & (feats["median_value_bn"] >= cl.MIN_MEDIAN_VALUE_BN)
        ]
        feats = feats[feats["foreign_active_share"] >= cl.MIN_FOREIGN_ACTIVE_SHARE]
        feats = feats[feats["symbol"].isin(ok["symbol"])]
        if len(feats):
            years[int(year)] = pd.Series(
                km.predict(prep(feats[features].to_numpy(float))),
                index=feats["symbol"].to_numpy(),
            )
    out = {"years": sorted(years), "transitions": {}}
    ys = sorted(years)
    for a, b in zip(ys[:-1], ys[1:], strict=True):
        both = years[a].index.intersection(years[b].index)
        same = float((years[a][both] == years[b][both]).mean())
        mat = pd.crosstab(years[a][both], years[b][both]).reindex(
            index=range(k), columns=range(k), fill_value=0
        )
        out["transitions"][f"{a}->{b}"] = {
            "n": int(len(both)),
            "stay_share": same,
            "matrix": mat.values.tolist(),
        }
    return out


def tail_experiment(daily: pd.DataFrame, market: pd.DataFrame, rule_labels: dict[str, str]) -> dict:
    tail_syms = [
        s for s, lab in rule_labels.items() if lab in ("thanh_khoan_thap", "it_khoi_ngoai")
    ]
    f = cl.tail_features(daily[daily["symbol"].isin(tail_syms)], market)
    out = {"n_candidates": len(tail_syms), "n_with_enough_data": len(f)}
    if len(f) < 60:
        return out
    x = f[TAIL_FEATURES].to_numpy(float)
    lo, hi = np.percentile(x, 1, axis=0), np.percentile(x, 99, axis=0)
    xs = StandardScaler().fit_transform(np.clip(x, lo, hi))
    k, report = cl.choose_k(xs, common.SEED)
    labels = KMeans(k, n_init=10, random_state=common.SEED).fit_predict(xs)
    centers = f[TAIL_FEATURES].groupby(labels).mean()
    z = (centers - f[TAIL_FEATURES].mean()) / f[TAIL_FEATURES].std()
    out.update(
        {
            "k": k,
            "k_report": report,
            "silhouette": float(silhouette_score(xs, labels)),
            "sizes": np.bincount(labels).tolist(),
            "centers_z": z.round(2).to_dict(orient="index"),
            "mixed_rule_labels": pd.crosstab(
                labels, pd.Series([rule_labels[s] for s in f["symbol"]])
            ).to_dict(),
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with common.connect() as conn:
        daily = common.read_sql(conn, cl.FEATURE_SQL, {"start": START})
        market = common.read_sql(conn, MARKET_SQL)
        symbols = common.read_sql(
            conn, "SELECT symbol FROM dw.dim_stock WHERE security_type = 'STOCK' ORDER BY symbol"
        )["symbol"].tolist()
    feats = cl.stock_features(daily)
    ok, rule_labels = cl.split_universe(feats, symbols)
    k = 6  # K của mô hình hiện tại (chọn theo Silhouette và độ ổn định, xem docs/ml_ket_qua.md)
    # chọn đặc trưng bền chỉ bằng nửa đầu - nửa sau của giai đoạn thiết kế (trước SPLIT); đo trên giai đoạn sau SPLIT
    design = daily[daily["trade_date"] < pd.Timestamp(SPLIT).date()]
    kept, feature_corr = cl.persistent_features(design)
    results = {
        "feature_persistence_design_period": {"correlation": feature_corr, "kept": kept},
        "persistence": persistence(daily, k),
        "persistence_selected_features": persistence(daily, k, kept),
        "gmm": gmm_experiment(daily, k),
        "hdbscan": hdbscan_experiment(daily),
        "yearly": yearly_transitions(
            daily, 4, cl.persistent_features(daily)[0]
        ),  # cấu hình sản xuất
        "tail": tail_experiment(daily, market, rule_labels),
    }
    (out_dir / "clustering_experiments.json").write_text(
        json.dumps(common.to_jsonable(results), indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(common.to_jsonable(results), indent=1, ensure_ascii=False)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
