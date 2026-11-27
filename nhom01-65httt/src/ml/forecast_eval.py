"""Đánh giá bổ sung cho mô hình dự báo dòng tiền ngành (không đổi bài toán gốc: phân lớp chiều + hồi quy giá trị).

Dùng lại đúng các dự báo ngoài mẫu của walk-forward, chỉ đọc chúng theo cách khác:
  - rank_metrics      : xếp hạng 19 ngành mỗi tuần theo giá trị ròng dự báo (Spearman, precision@k) so với cơ sở "giống tuần này"
  - abnormal_metrics  : dòng tiền tuần sau LỆCH bao nhiêu so với tuần này (chiều thay đổi, bắt đảo chiều)
  - paired_bootstrap  : khoảng tin cậy 95% cho chênh lệch mô hình so với cơ sở (lấy mẫu lại theo TUẦN vì các ngành cùng tuần tương quan)
  - sector_backtest   : mua đều k ngành xếp đầu mỗi tuần, so với mua đều mọi ngành và với VN-Index (chưa tính phí, backtest sơ bộ)

Mọi hàm nhận bảng dự báo có cột: week, sector, scale, net, y_net, y_cls, prob_inflow, pred_scaled, pred_net.
"""

import numpy as np
import pandas as pd

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20261127


def _rank_corr(a: pd.Series, b: pd.Series) -> float:
    """Hệ số Spearman (tương quan của hạng). NaN nếu một vế không đổi."""
    if a.nunique() < 2 or b.nunique() < 2:
        return float("nan")
    return float(a.rank().corr(b.rank()))


def weekly_rank_table(pred: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """Mỗi tuần một dòng: Spearman và precision@k của mô hình và của cơ sở, theo giá trị chuẩn hóa và theo tỷ đồng.

    - "chuẩn hóa": giá trị ròng chia cho độ lớn thường lệ của ngành (so sánh công bằng giữa ngành lớn và nhỏ).
    - "tỷ đồng": giá trị tuyệt đối (ngành lớn như Ngân hàng chiếm ưu thế tự nhiên).
    Cơ sở: xếp theo dòng tiền tuần này (quán tính).
    """
    rows = []
    for week, g in pred.groupby("week"):
        n = len(g)
        kk = min(k, n)
        actual_scaled = g["y_net"] / g["scale"]
        naive_scaled = g["net"] / g["scale"]
        row = {"week": week, "n": n}
        for tag, score, truth in (
            ("scaled", g["pred_scaled"], actual_scaled),
            ("bn", g["pred_net"], g["y_net"]),
        ):
            top_true = set(truth.nlargest(kk).index)
            row[f"model_{tag}_rho"] = _rank_corr(score, truth)
            row[f"model_{tag}_pk"] = len(set(score.nlargest(kk).index) & top_true) / kk
            base = naive_scaled if tag == "scaled" else g["net"]
            row[f"naive_{tag}_rho"] = _rank_corr(base, truth)
            row[f"naive_{tag}_pk"] = len(set(base.nlargest(kk).index) & top_true) / kk
        row["random_pk"] = kk / n
        rows.append(row)
    return pd.DataFrame(rows)


def rank_metrics(pred: pd.DataFrame, k: int = 5) -> dict:
    t = weekly_rank_table(pred.reset_index(drop=True), k)
    out = {"k": k, "weeks": int(len(t)), "random_precision_at_k": float(t["random_pk"].mean())}
    for tag in ("scaled", "bn"):
        out[tag] = {
            "model_spearman": float(t[f"model_{tag}_rho"].mean()),
            "naive_spearman": float(t[f"naive_{tag}_rho"].mean()),
            "model_precision_at_k": float(t[f"model_{tag}_pk"].mean()),
            "naive_precision_at_k": float(t[f"naive_{tag}_pk"].mean()),
        }
    return out


def abnormal_metrics(pred: pd.DataFrame) -> dict:
    """Phần "bất thường": thay đổi dòng tiền so với tuần này (y_net - net), và các lần đảo chiều.

    Cơ sở "giống tuần này" luôn dự báo thay đổi bằng 0 và không bao giờ bắt được đảo chiều, nên đây là phần mô hình
    phải tự chứng minh giá trị. Cơ sở thứ hai "quay về 0": dự đoán thay đổi ngược dấu với dòng tiền hiện tại.
    """
    net, y_net = pred["net"].to_numpy(), pred["y_net"].to_numpy()
    d_true = y_net - net
    d_pred = pred["pred_net"].to_numpy() - net
    d_revert = -net  # quay về 0
    pred_dir = np.sign(d_pred)
    mask = d_true != 0
    reversal = np.sign(net) != np.sign(y_net)  # tuần sau đổi chiều so với tuần này
    model_cls = (pred["prob_inflow"].to_numpy() >= 0.5).astype(int)
    now_cls = (net > 0).astype(int)
    predicted_reversal = model_cls != now_cls
    tp = int((predicted_reversal & reversal).sum())
    return {
        "n": int(len(pred)),
        "delta_spearman_model": _rank_corr(pd.Series(d_pred), pd.Series(d_true)),
        "delta_direction_accuracy_model": float((pred_dir[mask] == np.sign(d_true[mask])).mean()),
        "delta_direction_accuracy_revert_to_zero": float(
            (np.sign(d_revert[mask]) == np.sign(d_true[mask])).mean()
        ),
        "delta_mae_model_bn": float(np.abs(d_true - d_pred).mean()),
        "delta_mae_no_change_bn": float(np.abs(d_true).mean()),
        "delta_mae_revert_to_zero_bn": float(np.abs(d_true - d_revert).mean()),
        "reversal_share": float(reversal.mean()),
        "reversal_recall_model": float(tp / max(int(reversal.sum()), 1)),
        "reversal_recall_naive": 0.0,
        "reversal_precision_model": float(tp / max(int(predicted_reversal.sum()), 1)),
        "reversal_predicted_share": float(predicted_reversal.mean()),
    }


def paired_bootstrap(
    values_model: pd.Series, values_base: pd.Series, weeks: pd.Series, higher_is_better: bool = True
) -> dict:
    """Chênh lệch trung bình (mô hình - cơ sở) và khoảng tin cậy 95% bằng bootstrap lấy mẫu lại theo tuần.

    `p_better` = tỷ lệ lần lấy mẫu mà mô hình tốt hơn cơ sở (không phải p-value kiểm định hai phía).
    """
    diff = (values_model.to_numpy(float) - values_base.to_numpy(float)) * (
        1 if higher_is_better else -1
    )
    per_week = pd.Series(diff).groupby(weeks.to_numpy()).mean().to_numpy()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(per_week), size=(BOOTSTRAP_N, len(per_week)))
    boot = per_week[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "mean_diff": float(per_week.mean()),
        "ci95": [float(lo), float(hi)],
        "p_better": float((boot > 0).mean()),
        "weeks": int(len(per_week)),
        "significant_95": bool(lo > 0 or hi < 0),
    }


def bootstrap_vs_baseline(pred: pd.DataFrame) -> dict:
    """Khoảng tin cậy cho accuracy và MAE của mô hình so với cơ sở 'giống tuần này'."""
    y = pred["y_cls"].astype(int)
    model_ok = ((pred["prob_inflow"] >= 0.5).astype(int) == y).astype(float)
    naive_ok = (((pred["net"] > 0).astype(int)) == y).astype(float)
    err_model = (pred["y_net"] - pred["pred_net"]).abs()
    err_naive = (pred["y_net"] - pred["net"]).abs()
    return {
        "accuracy_diff_vs_naive": paired_bootstrap(model_ok, naive_ok, pred["week"]),
        "mae_diff_vs_naive_bn": paired_bootstrap(
            err_model, err_naive, pred["week"], higher_is_better=False
        ),
    }


def sector_backtest(pred: pd.DataFrame, returns: pd.DataFrame, k: int = 3) -> dict:
    """Mỗi tuần mua đều k ngành có giá trị ròng chuẩn hóa dự báo cao nhất, giữ một tuần (tuần mục tiêu).

    `returns`: bảng (week, sector, y_ret, y_vnindex) với y_ret là lợi suất ngành tuần t+1 và y_vnindex là lợi suất VN-Index
    tuần t+1. So với: mua đều mọi ngành, mua k ngành có dòng tiền tuần này cao nhất (quán tính), VN-Index; thêm chênh lệch
    k ngành đầu - k ngành cuối. Chưa tính phí, không cho bán khống: chỉ để đánh giá sơ bộ ý nghĩa kinh tế của dự báo.
    """
    m = pred.merge(returns, on=["week", "sector"], how="inner").dropna(subset=["y_ret"])
    rows = []
    for week, g in m.groupby("week"):
        kk = min(k, len(g))
        top = g.nlargest(kk, "pred_scaled")
        bottom = g.nsmallest(kk, "pred_scaled")
        naive = g.assign(s=g["net"] / g["scale"]).nlargest(kk, "s")
        rows.append(
            {
                "week": week,
                "model_top": top["y_ret"].mean(),
                "model_bottom": bottom["y_ret"].mean(),
                "naive_top": naive["y_ret"].mean(),
                "all_equal": g["y_ret"].mean(),
                "vnindex": g["y_vnindex"].iloc[0],
            }
        )
    t = pd.DataFrame(rows).sort_values("week")
    cum = lambda s: float((1 + s).prod() - 1)  # noqa: E731
    boot = paired_bootstrap(t["model_top"], t["all_equal"], t["week"])
    boot_naive = paired_bootstrap(t["model_top"], t["naive_top"], t["week"])
    return {
        "k": k,
        "weeks": int(len(t)),
        "cumulative_return": {
            "model_top_k": cum(t["model_top"]),
            "naive_top_k": cum(t["naive_top"]),
            "all_sectors_equal": cum(t["all_equal"]),
            "vnindex": cum(t["vnindex"]),
            "model_bottom_k": cum(t["model_bottom"]),
        },
        "mean_weekly_return_pct": {
            c: float(t[c].mean() * 100)
            for c in ("model_top", "naive_top", "all_equal", "vnindex", "model_bottom")
        },
        "weeks_model_beats_equal_weight": float((t["model_top"] > t["all_equal"]).mean()),
        "excess_vs_equal_weight": boot,
        "excess_vs_naive_top_k": boot_naive,
        "top_minus_bottom_mean_weekly_pct": float(
            (t["model_top"] - t["model_bottom"]).mean() * 100
        ),
        "note": "chưa tính phí giao dịch, không bán khống; ngành là rổ đều theo trọng số giá trị giao dịch; chỉ là kiểm tra sơ bộ",
    }
