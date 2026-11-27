"""Kiểm thử mô hình học máy trên dữ liệu giả lập (không cần cơ sở dữ liệu).

Trọng tâm: không rò rỉ dữ liệu tương lai, walk-forward đúng thứ tự thời gian, tái lập được, tên cụm khớp đặc trưng thực.
"""

import numpy as np
import pandas as pd
import pytest

from ml import clustering, features
from ml import forecast as fc

RNG = np.random.default_rng(7)
SECTORS = ["8300", "8600", "1700", "3500", "7500"]


def synthetic(n_weeks=140, seed=7):
    rng = np.random.default_rng(seed)
    weeks = pd.date_range("2020-09-07", periods=n_weeks, freq="7D")
    flow = pd.DataFrame(
        [
            {
                "week": w,
                "sector": s,
                "net": rng.normal(0, 100),
                "buy": abs(rng.normal(500, 50)),
                "sell": abs(rng.normal(500, 50)),
                "prop_net": np.nan if w < pd.Timestamp("2022-05-17") else rng.normal(0, 30),
            }
            for w in weeks
            for s in SECTORS
        ]
    )
    price = pd.DataFrame(
        [
            {
                "week": w,
                "sector": s,
                "ret": rng.normal(0, 0.02),
                "value": abs(rng.normal(1000, 100)),
            }
            for w in weeks
            for s in SECTORS
        ]
    )
    market = pd.DataFrame(
        {
            "week": weeks,
            "foreign_net": rng.normal(0, 300, n_weeks),
            "vnindex_ret": rng.normal(0, 0.02, n_weeks),
            "vnindex_vol": abs(rng.normal(1, 0.2, n_weeks)),
        }
    )
    macro = pd.DataFrame(
        {
            "week": weeks,
            "USDVND": 25000 + rng.normal(0, 20, n_weeks).cumsum(),
            "DXY": 100 + rng.normal(0, 0.3, n_weeks).cumsum(),
        }
    )
    return flow, price, market, macro


def corrupt_after(frames, cutoff, seed=99):
    """Thay mọi giá trị số của các tuần SAU `cutoff` bằng nhiễu ngẫu nhiên."""
    rng = np.random.default_rng(seed)
    out = []
    for frame in frames:
        f = frame.copy()
        mask = f["week"] > cutoff
        for col in f.columns:
            if col in ("week", "sector"):
                continue
            f.loc[mask, col] = rng.normal(0, 1000, mask.sum()) + 5000
        out.append(f)
    return out


def feature_columns(df):
    return [
        c
        for c in df.columns
        if c not in ("week", "sector") and not c.startswith("y_") and c != "scale"
    ]


def test_dac_trung_tai_tuan_t_khong_doi_khi_du_lieu_sau_t_bi_thay_doi():
    """KIỂM TRA RÒ RỈ: đặc trưng của mọi tuần <= t chỉ phụ thuộc dữ liệu đến hết tuần t."""
    frames = synthetic()
    base = features.build_features(*frames)
    cutoff = pd.Timestamp("2022-12-05")
    changed = features.build_features(*corrupt_after(frames, cutoff))
    cols = feature_columns(base)
    a = base[base["week"] <= cutoff].reset_index(drop=True)
    b = changed[changed["week"] <= cutoff].reset_index(drop=True)
    assert len(a) == len(b) > 0
    for col in cols:
        assert np.allclose(
            a[col].to_numpy(float), b[col].to_numpy(float), equal_nan=True
        ), f"đặc trưng {col} nhìn trước tương lai"


def test_nhan_la_dong_tien_tuan_ke_tiep_va_tuan_cuoi_khong_co_nhan():
    df = features.build_features(*synthetic())
    for _sector, g in df.groupby("sector"):
        g = g.sort_values("week")
        assert np.allclose(g["y_net"].iloc[:-1].to_numpy(), g["net"].iloc[1:].to_numpy())
        assert np.isnan(g["y_net"].iloc[-1]) and np.isnan(g["y_cls"].iloc[-1])
        assert ((g["y_cls"].dropna() == 1) == (g["y_net"].dropna() > 0)).all()


def test_nhan_tuan_t_thay_doi_khi_du_lieu_tuan_t_cong_1_thay_doi():
    """Ngược lại với test rò rỉ: nhãn đúng là phải phụ thuộc tuần t+1 (chứng tỏ test trên có tác dụng)."""
    frames = synthetic()
    base = features.build_features(*frames)
    cutoff = pd.Timestamp("2022-12-05")
    changed = features.build_features(*corrupt_after(frames, cutoff))
    a = base[base["week"] == cutoff]["y_net"].to_numpy()
    b = changed[changed["week"] == cutoff]["y_net"].to_numpy()
    assert not np.allclose(a, b)


def test_tuan_dang_chay_do_bi_loai_khoi_tap_du_bao():
    weeks = list(pd.date_range("2026-10-26", periods=4, freq="7D"))  # 10/26, 11/02, 11/09, 11/16
    latest = pd.Timestamp("2026-11-18")  # tuần 11/16 mới tới thứ Tư: đang chạy dở
    assert features.complete_weeks(weeks, latest) == weeks[:3]
    assert (
        features.complete_weeks(weeks, pd.Timestamp("2026-11-20")) == weeks
    )  # thứ Sáu: tuần đã đủ
    assert features.complete_weeks(weeks, pd.Timestamp("2026-11-23")) == weeks


def test_du_bao_tuan_toi_chi_hop_le_neu_lap_truoc_khi_tuan_do_bat_dau():
    live = pd.DataFrame(
        {"week": [pd.Timestamp("2026-11-16")]}
    )  # dự báo cho tuần bắt đầu 2026-11-23 (giờ Việt Nam)
    before = pd.Timestamp("2026-11-22 12:00", tz="Asia/Ho_Chi_Minh").to_pydatetime()
    after = pd.Timestamp("2026-11-24 09:00", tz="Asia/Ho_Chi_Minh").to_pydatetime()
    assert fc.live_is_valid(live, before) and not fc.live_is_valid(live, after)
    assert not fc.live_is_valid(live.iloc[0:0], before)


def test_streak_dem_tuan_lien_tiep_cung_chieu():
    s = pd.Series([1, 2, -1, -3, -2, 0, 5])
    assert features._streak(s).tolist() == [1, 2, -1, -2, -3, 0, 1]


def test_walk_forward_tap_kiem_tra_luon_sau_tap_huan_luyen(monkeypatch):
    df = features.build_features(*synthetic(n_weeks=180))
    weeks = sorted(df["week"].unique())[:-1]
    calls = []

    def spy(train, test, cols, kind="xgb"):
        calls.append((train["week"].max(), test["week"].min(), test["week"].max()))
        out = test[["week", "sector", "scale", "net", "y_net", "y_cls"]].copy()
        out["prob_inflow"], out["pred_scaled"], out["pred_net"] = 0.5, 0.0, 0.0
        return out

    monkeypatch.setattr(fc, "fit_predict", spy)
    pred = fc.walk_forward(df, features.FLOW_FEATURES, weeks)
    assert calls, "phải có ít nhất một khối kiểm tra"
    for train_max, test_min, _ in calls:
        assert train_max < test_min
        assert train_max <= test_min - pd.Timedelta(
            days=7
        )  # nhãn của dòng huấn luyện cuối đã biết trước khi dự báo
        assert test_min >= fc.FIRST_TEST_WEEK
    assert pred["week"].min() >= fc.FIRST_TEST_WEEK
    starts = [c[1] for c in calls]
    assert starts == sorted(starts) and len(set(starts)) == len(
        starts
    )  # các khối kiểm tra nối tiếp, không chồng lấn
    assert all(calls[i][2] < calls[i + 1][1] for i in range(len(calls) - 1))


def test_du_bao_tai_lap_duoc_voi_cung_hat_giong_va_du_lieu():
    df = features.build_features(*synthetic(n_weeks=150))
    cols = features.FLOW_FEATURES + features.CROSS_FEATURES
    ready = df.dropna(subset=["y_cls", "net_s3", "net_ma8"])
    train, test = ready[ready["week"] < "2022-12-01"], ready[ready["week"] >= "2023-01-01"]
    a = fc.fit_predict(train, test, cols)
    b = fc.fit_predict(train, test, cols)
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert a["prob_inflow"].between(0, 1).all()


def test_danh_gia_so_voi_mo_hinh_co_so():
    df = features.build_features(*synthetic(n_weeks=150))
    pred = pd.DataFrame(
        {
            "week": pd.date_range("2023-01-02", periods=10, freq="7D").repeat(2),
            "sector": ["a", "b"] * 10,
            "net": [1, -1] * 10,
            "y_net": [1, -1] * 10,
            "y_cls": [1.0, 0.0] * 10,
            "prob_inflow": [0.9, 0.1] * 10,
            "pred_net": [1.0, -1.0] * 10,
        }
    )
    r = fc.evaluate(pred, df)
    assert r["model"]["accuracy"] == 1.0 and r["baseline_same_as_last_week"]["accuracy"] == 1.0
    assert r["regression"]["mae_bn"] == 0.0


# ---------------- Phân cụm ----------------
def daily_frame(symbol, f_ratio, f_share, value=10.0, n=300, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2022-06-01", periods=n)
    val = np.full(n, value) * rng.uniform(0.8, 1.2, n)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": days,
            "week_start_date": days.to_period("W").start_time,
            "total_value_bn": val,
            "pct_change": rng.normal(0, 2, n),
            "is_outlier_pct": False,
            "f_net": val * f_ratio * rng.uniform(0.5, 1.5, n),
            "f_turn": val * f_share * 2,
            "p_net": 0.0,
            "p_turn": 0.0,
        }
    )


def test_dac_trung_ma_do_dung_huong_dong_tien():
    buy = clustering.stock_features(daily_frame("MUA", 0.1, 0.3)).iloc[0]
    sell = clustering.stock_features(daily_frame("BAN", -0.1, 0.3)).iloc[0]
    assert buy["foreign_net_ratio"] > 0.05 > -0.05 > sell["foreign_net_ratio"]
    assert buy["foreign_share"] == pytest.approx(0.3, abs=0.01)
    assert 0 <= buy["foreign_active_share"] <= 1


def test_moi_ma_deu_co_nhan_ke_ca_ma_it_du_lieu_hoac_thanh_khoan_thap():
    frames = [
        daily_frame(f"M{i:02d}", r, sh, seed=i)
        for i, (r, sh) in enumerate([(0.1, 0.4)] * 15 + [(-0.1, 0.05)] * 15 + [(0.0, 0.2)] * 15)
    ]
    frames.append(daily_frame("THAP", 0.0, 0.3, value=0.01))  # thanh khoản quá thấp
    frames.append(daily_frame("NGAN", 0.0, 0.3, n=50))  # quá ít phiên
    frames.append(daily_frame("KHOI", 0.0, 0.0))  # khối ngoại không giao dịch
    daily = pd.concat(frames, ignore_index=True)
    symbols = sorted(set(daily["symbol"]) | {"KHONGCO"})
    result = clustering.fit(clustering.stock_features(daily), symbols)
    labels = result["labels"].set_index("symbol")["cluster_label"]
    assert set(labels.index) == set(symbols)
    assert labels["THAP"] == "thanh_khoan_thap" and labels["NGAN"] == "chua_du_du_lieu"
    assert labels["KHOI"] == "it_khoi_ngoai" and labels["KHONGCO"] == "chua_du_du_lieu"
    assert result["sizes"].min() / result["n_clustered"] >= clustering.MIN_CLUSTER_SHARE


def test_ten_cum_khop_dac_trung_trung_binh_that_cua_cum():
    frames = [
        daily_frame(f"M{i:02d}", r, sh, seed=i)
        for i, (r, sh) in enumerate([(0.15, 0.4)] * 20 + [(-0.15, 0.4)] * 20 + [(0.0, 0.03)] * 20)
    ]
    result = clustering.fit(
        clustering.stock_features(pd.concat(frames, ignore_index=True)),
        [f"M{i:02d}" for i in range(60)],
    )
    centers = result["centers"]
    for name, row in centers.iterrows():
        if "ngoai_gom_rong" in name:
            assert row["foreign_net_ratio"] > centers["foreign_net_ratio"].mean()
        if "ngoai_xa_rong" in name:
            assert row["foreign_net_ratio"] < centers["foreign_net_ratio"].mean()
        if "noi_dia_chu_dao" in name:
            assert row["foreign_share"] < centers["foreign_share"].mean()
    assert any("gom_rong" in n or "mua_deu" in n for n in centers.index)
    assert any("xa_rong" in n or "ban_deu" in n for n in centers.index)


def test_ten_cum_la_duy_nhat():
    centers = pd.DataFrame(
        [{f: 0.0 for f in clustering.FEATURES} for _ in range(3)], index=[0, 1, 2]
    )
    sizes = pd.Series([50, 30, 20], index=[0, 1, 2])
    pop_mean = pd.Series({f: 0.0 for f in clustering.FEATURES})
    pop_std = pd.Series({f: 1.0 for f in clustering.FEATURES})
    names = clustering.name_clusters(centers, sizes, pop_mean, pop_std)
    assert len(set(names.values())) == 3 and names[0].endswith("_1")


# ---------------- Phân cụm: đặc trưng bền, nhóm phụ, độ bền theo thời gian ----------------
def persistent_universe(n_per_group=20):
    """Ba nhóm mã: tỷ trọng khối ngoại cố định theo từng nhóm (bền), hướng mua/bán ròng đổi ngẫu nhiên giữa hai nửa (không bền)."""
    rng = np.random.default_rng(11)
    days = pd.bdate_range("2022-06-01", periods=320)
    half = days[160]
    frames = []
    for g, share in enumerate([0.05, 0.25, 0.45]):
        for i in range(n_per_group):
            val = rng.uniform(8, 12, len(days)) * (1 + g)
            sign = np.where(days < half, rng.choice([-1, 1]), rng.choice([-1, 1]))
            frames.append(
                pd.DataFrame(
                    {
                        "symbol": f"G{g}{i:02d}",
                        "trade_date": days,
                        "week_start_date": days.to_period("W").start_time,
                        "total_value_bn": val,
                        "pct_change": rng.normal(0, 2, len(days)),
                        "is_outlier_pct": False,
                        "f_net": sign * val * 0.1 * rng.uniform(0.5, 1.5, len(days)),
                        "f_turn": val * share * 2 * rng.uniform(0.9, 1.1, len(days)),
                        "p_net": 0.0,
                        "p_turn": 0.0,
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


def test_dac_trung_khong_ben_bi_loai_va_dac_trung_ben_duoc_giu():
    kept, corr = clustering.persistent_features(persistent_universe())
    assert "foreign_share" in kept and corr["foreign_share"] > 0.8
    assert "foreign_net_ratio" not in kept
    assert corr["foreign_net_ratio"] < clustering.MIN_FEATURE_PERSISTENCE


def test_do_ben_theo_thoi_gian_cao_khi_cum_la_tinh_chat_cua_ma():
    kept, _ = clustering.persistent_features(persistent_universe())
    ari = clustering.temporal_ari_by_k(persistent_universe(), kept, ks=[3])
    assert ari[3] > 0.5, "cụm tách theo tỷ trọng khối ngoại cố định phải giữ nguyên qua hai nửa"


def tail_daily(n_stocks=90, n=260):
    rng = np.random.default_rng(5)
    days = pd.bdate_range("2023-01-02", periods=n)
    frames = []
    for i in range(n_stocks):
        vol = [1.0, 3.0, 6.0][i % 3]
        val = rng.uniform(0.01, 0.05, n) * (1 + i % 3)
        frames.append(
            pd.DataFrame(
                {
                    "symbol": f"T{i:03d}",
                    "trade_date": days,
                    "total_value_bn": val,
                    "pct_change": rng.normal(0, vol, n),
                    "is_outlier_pct": False,
                }
            )
        )
    market = pd.DataFrame({"trade_date": days, "mkt": rng.normal(0, 1, n)})
    return pd.concat(frames, ignore_index=True), market


def test_nhom_phu_phan_cum_ma_chi_co_nhan_quy_tac_va_dat_ten_co_tien_to():
    daily, market = tail_daily()
    rules = {s: "thanh_khoan_thap" for s in daily["symbol"].unique()}
    rules["T000"] = "it_khoi_ngoai"
    tail = clustering.fit_tail(daily, market, rules)
    assert tail is not None and tail["n_clustered"] == 90
    assert set(tail["labels"]["symbol"]) == set(rules)
    assert all(n.startswith(clustering.TAIL_PREFIX) for n in tail["labels"]["cluster_label"])
    # chỉ phân cụm các mã nhận nhãn quy tắc thuộc TAIL_RULES
    only = clustering.fit_tail(daily, market, {**rules, "T001": "chua_du_du_lieu"})
    assert "T001" not in set(only["labels"]["symbol"])


def test_ghep_nhan_nhom_phu_thay_nhan_quy_tac_va_giu_nhan_khac():
    result = {
        "labels": pd.DataFrame(
            {
                "symbol": ["A", "B", "C", "D"],
                "cluster_label": ["cum1", "thanh_khoan_thap", "it_khoi_ngoai", "chua_du_du_lieu"],
                "silhouette": [0.2, np.nan, np.nan, np.nan],
            }
        )
    }
    tail = {
        "labels": pd.DataFrame(
            {"symbol": ["B", "C"], "cluster_label": ["phu_x", "phu_y"], "silhouette": [0.1, 0.1]}
        )
    }
    labels, rules = clustering.combine_labels(result, tail)
    got = labels.set_index("symbol")["cluster_label"].to_dict()
    assert got == {"A": "cum1", "B": "phu_x", "C": "phu_y", "D": "chua_du_du_lieu"}
    assert rules == {"chua_du_du_lieu": 1}
    labels2, rules2 = clustering.combine_labels(result, None)
    assert len(labels2) == 4 and rules2 == {
        "thanh_khoan_thap": 1,
        "it_khoi_ngoai": 1,
        "chua_du_du_lieu": 1,
    }
