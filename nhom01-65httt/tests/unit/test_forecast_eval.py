"""Kiểm thử đặc trưng lịch, room và các hàm đánh giá bổ sung của mô hình dự báo (xếp hạng, bất thường, bootstrap, backtest)."""

import numpy as np
import pandas as pd
import pytest
from tests.unit.test_ml import corrupt_after, synthetic

from ml import features
from ml import forecast_eval as fe


def test_dac_trung_lich_la_thuoc_tinh_cua_tuan_muc_tieu():
    cal = features.calendar_features(
        pd.to_datetime(["2023-01-09", "2023-01-16", "2024-01-29"])
    ).set_index("week")
    # tuần 16/01/2023 (mục tiêu 23/01-27/01): sát Tết (mùng 1 = 22/01/2023, tức trước tuần mục tiêu 1 ngày)
    assert cal.loc["2023-01-09", "cal_tet_dist_next"] in (-1, 0)
    assert cal.loc["2023-01-16", "cal_tet_dist_next"] == -1  # tuần mục tiêu ngay sau Tết
    # tuần mục tiêu 05-09/02/2024: Tết 10/02/2024 nằm sau tuần đó
    assert (
        cal.loc["2024-01-29", "cal_tet_dist_next"] == 0
        or cal.loc["2024-01-29", "cal_tet_dist_next"] == 1
    )
    assert (cal["cal_month"] >= 1).all() and (cal["cal_month"] <= 12).all()


def test_dao_han_la_thu_nam_thu_ba_cua_thang():
    # tháng 11/2026: thứ Năm thứ ba = 19/11. Tuần mục tiêu bắt đầu 16/11 -> tuần t = 09/11
    weeks = pd.to_datetime(["2026-11-02", "2026-11-09", "2026-11-16"])
    cal = features.calendar_features(weeks).set_index("week")
    assert cal["cal_expiry_next"].tolist() == [0, 1, 0]


def test_dac_trung_lich_khong_phu_thuoc_du_lieu_nen_khong_ro_ri():
    weeks = pd.date_range("2022-01-03", periods=60, freq="7D")
    a = features.calendar_features(weeks)
    b = features.calendar_features(weeks)
    pd.testing.assert_frame_equal(a, b)
    # đổi hoàn toàn dữ liệu sau một tuần cắt không làm đổi đặc trưng lịch
    flow, price, market, macro = synthetic(n_weeks=100)
    base = features.build_features(flow, price, market, macro)
    changed = features.build_features(
        *corrupt_after((flow, price, market, macro), pd.Timestamp("2022-06-06"))
    )
    for col in features.CALENDAR_FEATURES:
        assert np.array_equal(base[col].to_numpy(), changed[col].to_numpy())


def test_dac_trung_room_chi_dung_du_lieu_den_het_tuan_t():
    flow, price, market, macro = synthetic(n_weeks=80)
    weeks = sorted(flow["week"].unique())
    rng = np.random.default_rng(3)
    sectors = sorted(flow["sector"].unique())
    room = pd.DataFrame(
        [
            {
                "week": w,
                "sector": s,
                "room_fill": rng.uniform(0, 1),
                "room_tight": rng.uniform(0, 1),
            }
            for w in weeks
            for s in sectors
        ]
    )
    base = features.build_features(flow, price, market, macro, room=room)
    cutoff = pd.Timestamp(weeks[40])
    room2 = room.copy()
    room2.loc[room2["week"] > cutoff, ["room_fill", "room_tight"]] = 0.5
    changed = features.build_features(flow, price, market, macro, room=room2)
    a, b = base[base["week"] <= cutoff], changed[changed["week"] <= cutoff]
    for col in features.ROOM_FEATURES:
        assert np.allclose(a[col].to_numpy(float), b[col].to_numpy(float), equal_nan=True), col
    assert set(features.ROOM_FEATURES) <= set(features.feature_groups(base)["room"])


def make_pred(n_weeks=20, n_sec=8, skill=0.0, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for w in pd.date_range("2024-01-01", periods=n_weeks, freq="7D"):
        for s in range(n_sec):
            net = rng.normal(0, 100)
            y_net = rng.normal(0, 100)
            rows.append(
                {
                    "week": w, "sector": str(s), "scale": 100.0, "net": net, "y_net": y_net,
                    "y_cls": float(y_net > 0), "pred_net": y_net * skill + rng.normal(0, 100) * (1 - skill),
                }
            )  # fmt: skip
    p = pd.DataFrame(rows)
    p["pred_scaled"] = p["pred_net"] / p["scale"]
    p["prob_inflow"] = 1 / (1 + np.exp(-p["pred_net"] / 50))
    return p


def test_xep_hang_hoan_hao_cho_spearman_1_va_precision_1():
    p = make_pred(skill=1.0)
    r = fe.rank_metrics(p, k=3)
    assert r["bn"]["model_spearman"] == pytest.approx(1.0)
    assert r["bn"]["model_precision_at_k"] == pytest.approx(1.0)
    assert r["random_precision_at_k"] == pytest.approx(3 / 8)


def test_xep_hang_ngau_nhien_gan_muc_ngau_nhien():
    r = fe.rank_metrics(make_pred(n_weeks=300, skill=0.0, seed=4), k=3)
    assert abs(r["bn"]["model_spearman"]) < 0.1
    assert r["bn"]["model_precision_at_k"] == pytest.approx(3 / 8, abs=0.06)


def test_bat_thuong_co_so_khong_bao_gio_bat_duoc_dao_chieu():
    p = make_pred(skill=1.0)
    a = fe.abnormal_metrics(p)
    assert a["reversal_recall_naive"] == 0.0
    assert a["reversal_recall_model"] == pytest.approx(1.0)  # mô hình hoàn hảo bắt hết đảo chiều
    assert a["delta_mae_model_bn"] == pytest.approx(0.0)
    assert a["delta_mae_no_change_bn"] > 0
    assert 0 < a["reversal_share"] < 1


def test_bootstrap_khoang_tin_cay_chua_0_khi_hai_mo_hinh_nhu_nhau_va_loai_0_khi_khac_ro():
    weeks = pd.Series(np.repeat(np.arange(80), 5))
    rng = np.random.default_rng(2)
    a = pd.Series(rng.integers(0, 2, len(weeks)).astype(float))
    same = fe.paired_bootstrap(a, a.copy(), weeks)
    assert same["mean_diff"] == 0 and not same["significant_95"]
    better = fe.paired_bootstrap(
        pd.Series(np.ones(len(weeks))), pd.Series(np.zeros(len(weeks))), weeks
    )
    assert better["significant_95"] and better["ci95"][0] > 0 and better["p_better"] == 1.0
    lower = fe.paired_bootstrap(
        pd.Series(np.ones(len(weeks))),
        pd.Series(np.zeros(len(weeks))),
        weeks,
        higher_is_better=False,
    )
    assert lower["mean_diff"] < 0
    assert fe.paired_bootstrap(a, 1 - a, weeks) == fe.paired_bootstrap(
        a, 1 - a, weeks
    )  # tái lập được


def test_backtest_nganh_mua_ngành_du_bao_tot_nhat_va_so_voi_mua_deu():
    p = make_pred(n_weeks=30, n_sec=8, skill=1.0)
    rets = p[["week", "sector"]].copy()
    # lợi suất ngành tuần sau tỷ lệ thuận với dòng tiền thực tế (mô hình hoàn hảo sẽ thắng mua đều)
    rets["y_ret"] = p["y_net"].to_numpy() / 10000
    rets["y_vnindex"] = 0.001
    out = fe.sector_backtest(p, rets, k=3)
    assert out["mean_weekly_return_pct"]["model_top"] > out["mean_weekly_return_pct"]["all_equal"]
    assert (
        out["mean_weekly_return_pct"]["model_bottom"] < out["mean_weekly_return_pct"]["all_equal"]
    )
    assert out["weeks_model_beats_equal_weight"] > 0.9
    assert out["weeks"] == 30
