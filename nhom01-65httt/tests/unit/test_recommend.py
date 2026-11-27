"""Kiểm thử quy tắc khuyến nghị (N9) trên chuỗi dựng tay, backtest lặp được và không nhìn trước tương lai."""

import json

import numpy as np
import pandas as pd
import pytest

from ml import recommend as rc

DAYS = pd.bdate_range("2024-01-01", periods=30)


def flows(values):
    return pd.Series(values, index=DAYS[-len(values) :], dtype=float)


# ---------------- Đảo chiều dòng tiền ----------------
def test_ban_rong_5_phien_roi_mua_rong_phat_tin_hieu_dao_chieu_len():
    s = flows([-5, -3, -4, -2, -6, 3, 4, 2])
    assert rc.reversal_signal(s) == 1


def test_chua_du_phien_hoac_chua_du_so_phien_ban_thi_khong_phat_tin_hieu():
    assert rc.reversal_signal(flows([-5, -3, -4, 3, 4, 2])) == 0  # chỉ 6 phiên, cần 8
    assert rc.reversal_signal(flows([-5, 4, -4, 5, -6, 3, 4, 2])) == 0  # trước đó chỉ 3 phiên bán
    assert rc.reversal_signal(flows([-5, -3, -4, -2, -6, -1, 4, -2])) == 0  # sau đó mới 1 phiên mua
    assert rc.reversal_signal(flows([-5, -3, -4, -2, -6, 3, 1, -9])) == 0  # tổng gần đây âm


def test_mua_rong_roi_chuyen_ban_rong_phat_tin_hieu_dao_chieu_xuong():
    assert rc.reversal_signal(flows([5, 3, 4, 2, 6, -3, -4, 2])) == -1


def test_tin_hieu_chi_dung_cac_phien_cuoi_chuoi_khong_phu_thuoc_phien_xa_hon():
    base = flows([-5, -3, -4, -2, -6, 3, 4, 2])
    longer = flows([9, 9, 9, 9, -5, -3, -4, -2, -6, 3, 4, 2])
    assert rc.reversal_signal(base) == rc.reversal_signal(longer) == 1


# ---------------- Dự báo, cảm xúc, lệch pha ----------------
def test_diem_du_bao_theo_xac_suat_va_bo_qua_xac_suat_sat_0_5():
    assert rc.forecast_signal(0.55) == 0 and rc.forecast_signal(0.45) == 0
    assert rc.forecast_signal(None) == 0 and rc.forecast_signal(float("nan")) == 0
    assert rc.forecast_signal(0.60) == pytest.approx(0.4)
    assert rc.forecast_signal(0.75) == 1.0 and rc.forecast_signal(0.95) == 1.0  # cắt ở ±1
    assert rc.forecast_signal(0.30) == pytest.approx(-0.8)


def week_series(values, counts=None):
    idx = pd.date_range("2025-01-06", periods=len(values), freq="7D")
    return pd.Series(values, index=idx, dtype=float), pd.Series(
        counts if counts is not None else [10] * len(values), index=idx, dtype=float
    )


def test_cam_xuc_chuyen_tich_cuc_khi_cao_hon_han_cac_tuan_truoc():
    mean, n = week_series([0.0, -0.05, 0.02, 0.0, 0.25])
    sig, now = rc.sentiment_signal(mean, n)
    assert sig == 1 and now == pytest.approx(0.25)
    mean, n = week_series([0.0, 0.05, -0.02, 0.0, -0.25])
    assert rc.sentiment_signal(mean, n)[0] == -1


def test_cam_xuc_khong_phat_tin_hieu_khi_it_bai_it_tuan_truoc_hoac_thay_doi_nho():
    mean, n = week_series([0.0, -0.05, 0.02, 0.0, 0.25], [10, 10, 10, 10, 3])
    assert rc.sentiment_signal(mean, n)[0] == 0  # tuần này chỉ 3 bài
    mean, n = week_series([0.1, 0.25])
    assert rc.sentiment_signal(mean, n)[0] == 0  # chỉ 1 tuần trước
    mean, n = week_series([0.2, 0.22, 0.18, 0.2, 0.25])
    assert rc.sentiment_signal(mean, n)[0] == 0  # dương nhưng tăng chưa đủ 0,10


def test_lech_pha_tin_tot_nhung_tien_rut_ra_va_nguoc_lai():
    assert rc.mismatch_signal(0.3, -0.8) == "positive_news_outflow"
    assert rc.mismatch_signal(-0.3, 0.8) == "negative_news_inflow"
    assert rc.mismatch_signal(0.3, 0.8) is None and rc.mismatch_signal(0.05, -0.8) is None
    assert rc.mismatch_signal(None, -0.8) is None and rc.mismatch_signal(0.3, None) is None


# ---------------- Gộp tín hiệu ----------------
def test_hanh_dong_theo_diem_va_ngưỡng_0_5():
    assert rc.combine(0.75, 0, 0, None)["action"] == "increase"  # điểm 1,0
    assert rc.combine(0.20, 0, 0, None)["action"] == "decrease"
    assert rc.combine(0.52, 0, 0, None)["action"] == "hold"  # xác suất sát 0,5
    only_rev = rc.combine(0.5, 1, 0, None)  # chỉ đảo chiều: 0,5 vừa đủ ngưỡng
    assert only_rev["action"] == "increase" and only_rev["confidence"] == "low"


def test_do_chac_chan_tang_khi_nhieu_tin_hieu_cung_chieu_va_giam_khi_lech_pha():
    full = rc.combine(0.80, 1, 1, None)  # 1 + 0,5 + 0,5 = 2
    assert full["action"] == "increase" and full["confidence"] == "high"
    assert full["signals"] == ["forecast_inflow", "reversal_up", "sentiment_up"]
    warned = rc.combine(0.80, 1, 1, "positive_news_outflow")  # điểm giảm một nửa còn 1,0
    assert warned["score"] == pytest.approx(1.0) and warned["confidence"] == "medium"
    assert warned["signal"] == "mismatch" and "lệch pha" in warned["reason"]
    mixed = rc.combine(0.80, -1, 0, None)  # dự báo vào nhưng khối ngoại vừa đảo chiều ra: 1 - 0,5
    assert mixed["score"] == pytest.approx(0.5) and mixed["action"] == "increase"


def test_khong_co_tin_hieu_thi_giu_nguyen_va_co_ly_do():
    out = rc.combine(None, 0, 0, None)
    assert out["action"] == "hold" and out["confidence"] == "low" and out["signals"] == []
    assert "Giữ nguyên" in out["reason"] and out["signal"] == "none"


# ---------------- Dựng theo tuần: không nhìn trước ----------------
SECTORS = ["8300", "8600", "1700", "3500"]
WEEKS = list(pd.date_range("2024-01-01", periods=30, freq="7D"))


def synthetic_inputs(seed=3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(WEEKS[0], WEEKS[-1] + pd.Timedelta(days=6))
    daily = pd.DataFrame(
        [{"trade_date": d, "sector": s, "net": rng.normal(0, 50)} for d in days for s in SECTORS]
    )
    feats = pd.DataFrame(
        [
            {
                "week": w,
                "sector": s,
                "sent_mean0": rng.uniform(-0.4, 0.4),
                "sent_n0": float(rng.integers(0, 20)),
                "net_s0": rng.normal(0, 1),
            }
            for w in WEEKS
            for s in SECTORS
        ]
    )
    preds = pd.DataFrame(
        [
            {
                "target_week": w + pd.Timedelta(days=7),
                "sector": s,
                "prob_inflow": rng.uniform(0.2, 0.8),
            }
            for w in WEEKS
            for s in SECTORS
        ]
    )
    return daily, feats, preds


def test_khuyen_nghi_tuan_t_khong_doi_khi_du_lieu_sau_tuan_t_bi_thay_doi():
    """KIỂM TRA NHÌN TRƯỚC: đổi mọi dữ liệu dòng tiền, cảm xúc, dòng tiền chuẩn hóa sau tuần t (trừ dự báo của chính tuần t+1)."""
    daily, feats, preds = synthetic_inputs()
    cutoff = WEEKS[15]
    base = rc.build_recommendations(rc.Inputs(daily, feats, preds), WEEKS[:16])
    d2, f2, p2 = daily.copy(), feats.copy(), preds.copy()
    d2.loc[d2["trade_date"] > cutoff + pd.Timedelta(days=6), "net"] = 12345.0
    f2.loc[f2["week"] > cutoff, ["sent_mean0", "sent_n0", "net_s0"]] = [0.9, 99.0, 9.0]
    p2.loc[p2["target_week"] > cutoff + pd.Timedelta(days=7), "prob_inflow"] = 0.99
    changed = rc.build_recommendations(rc.Inputs(d2, f2, p2), WEEKS[:16])
    pd.testing.assert_frame_equal(base, changed)
    # đối chứng: đổi dữ liệu TRƯỚC tuần t thì khuyến nghị phải đổi (test trên có tác dụng)
    d3 = daily.copy()
    tue = cutoff + pd.Timedelta(days=1)
    d3.loc[d3["trade_date"] <= tue, "net"] = -50.0  # bán ròng đến hết thứ Ba của tuần t
    d3.loc[
        (d3["trade_date"] > tue) & (d3["trade_date"] <= cutoff + pd.Timedelta(days=6)), "net"
    ] = 80.0  # rồi mua ròng 3 phiên
    other = rc.build_recommendations(rc.Inputs(d3, feats, preds), [cutoff])
    assert other["signals"].str.contains("reversal_up").all()
    assert not base[base["week"] == cutoff]["signals"].str.contains("reversal_up").all()


def test_dung_khuyen_nghi_lap_lai_cho_cung_ket_qua():
    daily, feats, preds = synthetic_inputs()
    a = rc.build_recommendations(rc.Inputs(daily, feats, preds), WEEKS)
    b = rc.build_recommendations(rc.Inputs(daily, feats, preds), WEEKS)
    pd.testing.assert_frame_equal(a, b)
    assert set(a["action"]) <= {"increase", "decrease", "hold"}
    assert len(a) == len(WEEKS) * len(SECTORS)


# ---------------- Backtest ----------------
def returns_frame(seed=1, n_weeks=40):
    rng = np.random.default_rng(seed)
    weeks = list(pd.date_range("2024-01-01", periods=n_weeks, freq="7D"))
    return pd.DataFrame(
        [
            {
                "week": w,
                "sector": s,
                "y_ret": rng.normal(0.002, 0.03),
                "y_vnindex": 0.002,
                "y_cls": float(rng.integers(0, 2)),
            }
            for w in weeks
            for s in SECTORS
        ]
    )


def recs_from(returns, action_fn):
    out = returns[["week", "sector", "y_ret"]].copy()
    out["action"] = [action_fn(r) for r in out.itertuples()]
    out["confidence"] = "medium"
    return out.drop(columns="y_ret")


def test_trong_so_danh_muc_tong_bang_1_va_lech_theo_khuyen_nghi():
    actions = pd.Series(["increase", "decrease", "hold", "hold"], index=SECTORS)
    w = rc.portfolio_weights(actions, tilt=True)
    assert w.sum() == pytest.approx(1.0) and w["8300"] > w["1700"] > w["8600"]
    only = rc.portfolio_weights(actions, tilt=False)
    assert only["8300"] == 1.0 and only.sum() == pytest.approx(1.0)
    none = rc.portfolio_weights(pd.Series(["hold"] * 4, index=SECTORS), tilt=False)
    assert none.tolist() == [0.25] * 4  # không ngành nào tăng: giữ mua đều


def test_khong_co_khuyen_nghi_nao_thi_danh_muc_bang_mua_deu_va_khong_mat_phi():
    r = returns_frame()
    recs = recs_from(r, lambda _: "hold")
    out = rc.backtest(recs, r)
    assert out["tilt"]["cumulative"] == pytest.approx(out["equal_weight"]["cumulative"])
    assert out["tilt_gross"]["cumulative"] == pytest.approx(out["tilt"]["cumulative"])


def test_nhin_thay_tuong_lai_thi_thang_va_chi_phi_lam_giam_ket_qua():
    r = returns_frame(n_weeks=60)
    # lợi suất lấy từ chính cột y_ret của tuần đó nên danh mục "biết trước" (chỉ để kiểm tra mã) phải thắng mua đều
    oracle = r[["week", "sector"]].copy()
    oracle["action"] = np.where(
        r["y_ret"] == r.groupby("week")["y_ret"].transform("max"), "increase", "hold"
    )
    oracle["confidence"] = "medium"
    out = rc.backtest(oracle, r, cost=0.0)
    assert out["only_increase"]["cumulative"] > out["equal_weight"]["cumulative"]
    costly = rc.backtest(oracle, r, cost=0.01)
    assert costly["only_increase"]["cumulative"] < out["only_increase"]["cumulative"]
    assert costly["only_increase_gross"]["cumulative"] == pytest.approx(
        out["only_increase"]["cumulative"]
    )


def test_backtest_lap_lai_cho_cung_ket_qua_va_so_voi_vnindex_cung_khoang_thoi_gian():
    r = returns_frame()
    recs = recs_from(r, lambda x: "increase" if x.sector in ("8300", "8600") else "decrease")
    a, b = rc.backtest(recs, r), rc.backtest(recs, r)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)  # NaN không so == được
    assert a["weeks"] == r["week"].nunique()
    expected = float((1 + r.drop_duplicates("week")["y_vnindex"]).prod() - 1)
    assert a["vnindex"]["cumulative"] == pytest.approx(expected)


def test_thong_ke_theo_hanh_dong_co_ti_le_dong_tien_vao_tuan_sau():
    r = returns_frame(n_weeks=80)
    recs = recs_from(r, lambda x: "increase" if x.sector == "8300" else "hold")
    stats = rc.by_action(recs, r)
    assert stats["action:increase"]["n"] == 80 and stats["action:hold"]["n"] == 240
    assert 0 <= stats["action:increase"]["next_week_foreign_inflow_rate"] <= 1
