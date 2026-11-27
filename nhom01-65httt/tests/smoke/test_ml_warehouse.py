"""Kiểm thử kết quả mô hình trong kho thật (cần đã chạy: python -m ml.clustering và python -m ml.forecast từ thư mục src/).

Không ép mô hình phải "thắng" mô hình cơ sở (kết quả được báo cáo trung thực); chỉ kiểm tra tính đúng đắn, nhất quán và không rò rỉ.
"""

import numpy as np
import pandas as pd
import psycopg
import pytest

from ingestion import db

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def conn():
    try:
        connection = db.connect()
    except psycopg.OperationalError:
        pytest.skip("Không kết nối được PostgreSQL")
    yield connection
    connection.close()


def one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()


@pytest.fixture(scope="module")
def forecast_model(conn):
    row = one(
        conn,
        "SELECT model_key, metrics FROM dw.dim_model WHERE task = 'forecast' ORDER BY trained_at DESC LIMIT 1",
    )
    if not row:
        pytest.skip("Chưa chạy python -m ml.forecast")
    return {"key": row[0], "metrics": row[1]}


@pytest.fixture(scope="module")
def cluster_model(conn):
    row = one(
        conn,
        "SELECT model_key, metrics FROM dw.dim_model WHERE task = 'cluster' ORDER BY trained_at DESC LIMIT 1",
    )
    if not row:
        pytest.skip("Chưa chạy python -m ml.clustering")
    return {"key": row[0], "metrics": row[1]}


# ---------------- Phân cụm ----------------
def test_moi_co_phieu_deu_co_nhan_cum(conn, cluster_model):
    missing = one(
        conn,
        "SELECT count(*) FROM dw.dim_stock WHERE security_type = 'STOCK' AND cluster_label IS NULL",
    )[0]
    assert missing == 0
    total = one(conn, "SELECT count(*) FROM dw.dim_stock WHERE security_type = 'STOCK'")[0]
    m = cluster_model["metrics"]
    assert (
        sum(m["rule_labeled"].values()) + m["n_clustered"] + m.get("n_tail_clustered", 0) == total
    )


def test_cum_hoc_duoc_khong_qua_nho(conn, cluster_model):
    sizes = cluster_model["metrics"]["cluster_sizes"]
    assert min(sizes.values()) / sum(sizes.values()) >= 0.01


def test_nhom_phu_va_nhan_quy_tac_con_lai(conn, cluster_model):
    m = cluster_model["metrics"]
    if not m.get("tail"):
        pytest.skip("Chưa có nhóm phụ (chạy lại python -m ml.clustering)")
    prefixed = one(
        conn,
        "SELECT count(*) FROM dw.dim_stock WHERE security_type = 'STOCK' AND cluster_label LIKE 'phu!_%%' ESCAPE '!'",
    )[0]
    assert prefixed == m["n_tail_clustered"]
    sizes = m["tail"]["cluster_sizes"]
    assert min(sizes.values()) / sum(sizes.values()) >= 0.01
    # nhãn quy tắc `thanh_khoan_thap`/`it_khoi_ngoai` chỉ còn ở mã không đủ phiên để phân cụm
    left = m["rule_labeled"]
    assert left.get("chua_du_du_lieu", 0) > 0 and left.get("it_khoi_ngoai", 0) < 20


def test_k_duoc_chon_theo_do_ben_theo_thoi_gian_trong_cac_k_hop_le(cluster_model):
    m = cluster_model["metrics"]
    if "temporal_ari_by_k" not in m:
        pytest.skip("Mô hình cũ chưa có độ bền theo thời gian")
    valid = [
        r
        for r in m["k_report"]
        if r["smallest_share"] >= 0.01
        and r["stability_ari"] >= 0.6
        and r.get("temporal_ari") is not None
    ]
    assert max(valid, key=lambda r: r["temporal_ari"])["k"] == m["k"]
    assert (
        "prop_net_ratio" not in m["features"]
        or m["feature_persistence_corr"]["prop_net_ratio"] >= 0.2
    )


def test_chon_k_hop_ly_va_on_dinh(cluster_model):
    m = cluster_model["metrics"]
    report = {r["k"]: r for r in m["k_report"]}
    assert report[m["k"]]["smallest_share"] >= 0.01
    assert report[m["k"]]["stability_ari"] >= 0.6, "K được chọn phải ổn định giữa các seed"
    assert m["silhouette"] == pytest.approx(report[m["k"]]["silhouette"])


def test_ten_cum_khop_dac_trung_trung_binh_trong_kho(cluster_model):
    centers = pd.DataFrame(cluster_model["metrics"]["cluster_centers"]).T
    for name, row in centers.iterrows():
        if "ngoai_gom_rong" in name:
            assert row["foreign_net_ratio"] > centers["foreign_net_ratio"].mean(), name
        if "ngoai_xa_rong" in name:
            assert row["foreign_net_ratio"] < centers["foreign_net_ratio"].mean(), name
        if "noi_dia_chu_dao" in name:
            assert row["foreign_share"] < centers["foreign_share"].mean(), name
        if "thanh_khoan_cao" in name:
            assert row["log_value"] > centers["log_value"].mean(), name
        if "tu_doanh_chu_dao" in name:
            assert row["prop_share"] > centers["prop_share"].mean(), name


def test_nhan_cum_trong_dim_stock_khop_stock_cluster(conn, cluster_model):
    mismatch = one(
        conn,
        "SELECT count(*) FROM dw.dim_stock d JOIN dw.stock_cluster c ON c.symbol = d.symbol AND c.model_key = %s "
        "WHERE d.security_type = 'STOCK' AND d.cluster_label <> c.cluster_label",
        cluster_model["key"],
    )[0]
    assert mismatch == 0


# ---------------- Dự báo ----------------
def predictions(conn, model_key):
    return pd.read_sql(
        "SELECT * FROM dw.fact_prediction WHERE model_key = %(m)s", conn, params={"m": model_key}
    )


def test_du_bao_dung_cau_truc_va_xac_suat_hop_le(conn, forecast_model):
    p = predictions(conn, forecast_model["key"])
    assert len(p) > 3000 and p["sector_key"].nunique() == 19
    assert p["prob_inflow"].between(0, 1).all()
    assert ((p["prob_inflow"] >= 0.5) == (p["predicted_class"] == "INFLOW")).all()
    assert (p["horizon_weeks"] == 1).all()
    per_week = p.groupby("target_week_start_date_key")["sector_key"].nunique()
    assert (per_week == 19).all(), "mỗi tuần mục tiêu phải có đủ 19 ngành"


def test_khong_nhin_truoc_du_bao_lap_truoc_tuan_muc_tieu(conn, forecast_model):
    p = predictions(conn, forecast_model["key"])
    target_start = pd.to_datetime(
        p["target_week_start_date_key"].astype(str), format="%Y%m%d"
    ).dt.tz_localize("Asia/Ho_Chi_Minh")
    assert (pd.to_datetime(p["made_at"]) < target_start).all()
    assert (target_start.dt.dayofweek == 0).all(), "tuần mục tiêu phải bắt đầu vào thứ Hai"


def test_chi_so_trong_dim_model_khop_tinh_lai_tu_fact_prediction(conn, forecast_model):
    p = predictions(conn, forecast_model["key"])
    done = p[p["actual_class"].notna()]
    accuracy = float((done["predicted_class"] == done["actual_class"]).mean())
    assert accuracy == pytest.approx(forecast_model["metrics"]["model"]["accuracy"], abs=1e-9)
    assert len(done) == forecast_model["metrics"]["n"]


def test_gia_tri_thuc_te_khop_du_lieu_dong_tien(conn, forecast_model):
    """Giá trị thực của dự báo phải bằng khối ngoại ròng của ngành trong tuần mục tiêu lấy từ fact_money_flow."""
    row = one(
        conn,
        "SELECT p.sector_key, p.target_week_start_date_key, p.actual_net_value_bn FROM dw.fact_prediction p "
        "WHERE p.model_key = %s AND p.actual_class IS NOT NULL ORDER BY p.target_week_start_date_key DESC LIMIT 1",
        forecast_model["key"],
    )
    sector_key, key, actual = row
    week = pd.Timestamp(str(key)).date()
    direct = one(
        conn,
        "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f JOIN dw.dim_time t USING (date_key) "
        "JOIN dw.dim_stock d USING (stock_key) JOIN dw.dim_sector s ON s.sector_key = d.sector_key "
        "JOIN dw.dim_investor_type it USING (investor_type_key) "
        "WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN' AND t.week_start_date = %s "
        "AND s.icb_l2_code = (SELECT icb_l2_code FROM dw.dim_sector WHERE sector_key = %s)",
        week,
        sector_key,
    )[0]
    assert actual == pytest.approx(direct, abs=0.01)


def test_mo_hinh_khong_hong(forecast_model):
    m = forecast_model["metrics"]
    assert (
        m["model"]["accuracy"] > 0.55 and m["model"]["auc"] > 0.55
    ), "mô hình kém hơn đoán lớp phổ biến, có lỗi"
    assert m["model"]["accuracy"] > m["baseline_majority"]["accuracy"] - 0.01
    assert set(m["ablation"]) >= {"xgb flow_only", "logit flow+cross"}
    assert m["first_test_week"] >= "2023-01-01"


def test_du_bao_tai_lap_tren_du_lieu_that(conn):
    from ml import features, forecast

    df, latest = forecast.load(conn)
    weeks = forecast.usable_weeks(df, latest)
    cols = features.feature_groups(df)["flow"]
    ready = df[df["week"].isin(weeks)].dropna(subset=["y_cls", "net_s3", "net_ma8"])
    train = ready[ready["week"] < "2024-01-01"]
    test = ready[(ready["week"] >= "2024-01-08") & (ready["week"] < "2024-04-01")]
    a = forecast.fit_predict(train, test, cols)
    b = forecast.fit_predict(train, test, cols)
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert not np.isnan(a["prob_inflow"]).any()


def test_dac_trung_khong_dung_tuan_dang_chay_do(conn):
    from ml import forecast

    df, latest = forecast.load(conn)
    weeks = forecast.usable_weeks(df, latest)
    assert max(weeks) + pd.Timedelta(days=4) <= latest, "tuần đủ phải đã tới thứ Sáu"
