"""Kiểm thử mô hình cảm xúc không cần cơ sở dữ liệu: tệp nhãn, cách tính điểm, trọng số, chia tập theo thời gian."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml import sentiment

LABELS = Path(__file__).resolve().parents[2] / "src" / "ml" / "labels"


def test_tep_nhan_hop_le_va_du_so_luong():
    df = pd.read_csv(LABELS / "sentiment_claude_labels.csv", encoding="utf-8")
    assert len(df) == 1500 and df["sample_id"].is_unique and df["article_id"].is_unique
    assert set(df["label"]) == {"negative", "neutral", "positive"}
    assert set(df["c"]) <= {1, 2, 3}
    shares = df["label"].value_counts(normalize=True)
    assert shares.min() > 0.15 and shares.max() < 0.6, "phân bố nhãn không được lệch cực đoan"
    assert df.groupby("year")["label"].nunique().min() == 3, "mỗi năm phải có đủ 3 lớp"


def test_nhan_duoc_do_nhat_quan_giua_hai_luot_gan_doc_lap():
    agree = json.loads((LABELS / "agreement.json").read_text(encoding="utf-8"))
    assert agree["n"] >= 100
    assert agree["cohen_kappa"] >= 0.6, "nhãn không đủ nhất quán"


def test_diem_cam_xuc_la_p_tich_cuc_tru_p_tieu_cuc_va_nhan_la_lop_lon_nhat():
    classes = ["negative", "neutral", "positive"]
    proba = np.array([[0.7, 0.2, 0.1], [0.1, 0.2, 0.7], [0.2, 0.6, 0.2], [0.3, 0.3, 0.4]])
    score, label, conf = sentiment.score_from_proba(proba, classes)
    assert score.tolist() == pytest.approx([-0.6, 0.6, 0.0, 0.1])
    assert label.tolist() == ["negative", "positive", "neutral", "positive"]
    assert conf.tolist() == pytest.approx([0.7, 0.7, 0.6, 0.4])
    assert (np.abs(score) <= 1).all()
    # nhãn tích cực luôn có điểm > 0 và tiêu cực < 0 (cùng quy tắc với dbt test ml_sentiment_integrity)
    assert (score[label == "positive"] > 0).all() and (score[label == "negative"] < 0).all()


def test_nhan_luong_lu_co_trong_so_thap_hon():
    frame = pd.DataFrame({"c": [1, 2, 3]})
    assert sentiment.sample_weights(frame).tolist() == [sentiment.LOW_CONFIDENCE_WEIGHT, 1.0, 1.0]
    assert 0 < sentiment.LOW_CONFIDENCE_WEIGHT < 1


def test_lam_sach_van_ban_bo_lien_ket_va_so():
    out = sentiment.make_text(
        "VN-Index TĂNG 12,5 điểm", "Xem https://cafef.vn/abc tại đây. Lãi 1.200 tỷ."
    )
    assert "http" not in out and "12,5" not in out and "1.200" not in out and "<số>" in out
    assert out == out.lower() and "  " not in out


def synthetic_labeled(n=240):
    rng = np.random.default_rng(3)
    pos = [
        "lãi kỷ lục tăng trưởng mạnh",
        "chia cổ tức tiền mặt cao",
        "khối ngoại mua ròng tăng điểm",
    ]
    neg = ["lỗ nặng nợ xấu gia tăng", "bán tháo giảm sâu rủi ro", "bị xử phạt khởi tố vi phạm"]
    neu = [
        "thông báo họp đại hội cổ đông",
        "bổ nhiệm tổng giám đốc mới",
        "công bố lịch họp thường niên",
    ]
    rows = []
    dates = pd.date_range("2021-01-01", "2026-06-30", periods=n)
    for i, d in enumerate(dates):
        label = ["positive", "negative", "neutral"][i % 3]
        pool = {"positive": pos, "negative": neg, "neutral": neu}[label]
        rows.append(
            {
                "article_id": str(i),
                "published_date": d,
                "label": label,
                "origin": "v1",
                "c": int(rng.integers(1, 4)),
                "text": sentiment.clean(f"{pool[int(rng.integers(3))]} công ty {i % 7}"),
            }
        )
    return pd.DataFrame(rows)


def fake_embeddings(df, seed=5):
    """Embedding giả: mỗi nhãn một hướng cố định cộng nhiễu (đủ để kiểm tra đường đi của mã, không thay cho embedding thật)."""
    rng = np.random.default_rng(seed)
    centers = {"negative": [1, 0, 0], "neutral": [0, 1, 0], "positive": [0, 0, 1]}
    base = np.array([centers[x] for x in df["label"]], dtype=float)
    return base + rng.normal(0, 0.4, base.shape)


def test_chia_tap_theo_thoi_gian_khong_ro_ri_va_hoc_duoc():
    df = synthetic_labeled()
    result, model = sentiment.train_eval(df, fake_embeddings(df))
    train_end = pd.Timestamp(result["train_range"].split("..")[1])
    test_start = pd.Timestamp(result["test_range"].split("..")[0])
    assert train_end < pd.Timestamp(sentiment.TEST_FROM) <= test_start
    assert result["model"]["accuracy"] > 0.9
    assert result["model"]["accuracy"] > result["baseline_majority"]["accuracy"]
    assert set(model.classes_) == {"negative", "neutral", "positive"}
    assert "baseline_tfidf_only" in result


def test_bai_dot_2_tu_2025_khong_nam_trong_tap_kiem_tra_cung_khong_vao_huan_luyen_danh_gia():
    df = synthetic_labeled()
    late = df["published_date"] >= sentiment.TEST_FROM
    df.loc[late & (df.index % 2 == 0), "origin"] = "v2"
    train, test = sentiment.split(df)
    assert (train["published_date"] < sentiment.TEST_FROM).all()
    assert (test["origin"] == "v1").all() and (test["published_date"] >= sentiment.TEST_FROM).all()
    held_out = df[late & (df["origin"] == "v2")]
    assert len(held_out) > 0 and not set(held_out.index) & (set(train.index) | set(test.index))


def test_huan_luyen_tai_lap_duoc():
    df = synthetic_labeled()
    a = sentiment.fit_model(df).predict_proba(df["text"])
    b = sentiment.fit_model(df).predict_proba(df["text"])
    assert np.allclose(a, b)
    emb = fake_embeddings(df)
    pa = sentiment.Ensemble().fit(df, emb).predict_proba(df["text"], emb)
    pb = sentiment.Ensemble().fit(df, emb).predict_proba(df["text"], emb)
    assert np.allclose(pa, pb) and np.allclose(pa.sum(axis=1), 1.0)


def test_embedding_co_bo_nho_dem_chi_tinh_bai_moi(tmp_path):
    calls = []

    def fake(texts):
        calls.append(list(texts))
        return np.array([[len(t), 1.0] for t in texts], dtype=np.float32)

    cache = tmp_path / "emb.npz"
    ids, texts = ["a", "b", "c"], ["x", "yy", "zzz"]
    first = sentiment.embeddings_for(ids, texts, cache=cache, chunk=2, embedder=fake)
    assert first.shape == (3, 2) and sum(len(c) for c in calls) == 3
    calls.clear()
    again = sentiment.embeddings_for(ids, texts, cache=cache, chunk=2, embedder=fake)
    assert calls == [] and np.allclose(first, again)
    more = sentiment.embeddings_for(
        ["c", "d"], ["zzz", "wwww"], cache=cache, chunk=2, embedder=fake
    )
    assert (
        calls == [["wwww"]]
        and more[0, 0] == pytest.approx(3.0)
        and more[1, 0] == pytest.approx(4.0)
    )


def test_tep_nhan_dot_2_hop_le_neu_co():
    path = LABELS / "sentiment_claude_labels_v2.csv"
    if not path.exists():
        pytest.skip("chưa có nhãn đợt 2")
    v2 = pd.read_csv(path, encoding="utf-8")
    v1 = pd.read_csv(LABELS / "sentiment_claude_labels.csv", encoding="utf-8")
    assert len(v2) == 1500 and v2["article_id"].is_unique
    assert not set(v1["article_id"]) & set(v2["article_id"]), "bài đợt 2 không được trùng đợt 1"
    assert set(v2["label"]) == {"negative", "neutral", "positive"} and set(v2["c"]) <= {1, 2, 3}
    assert set(v2["strategy"]) == {"uncertain", "random"} and set(v2["period"]) == {"pre", "post"}


def validity_frame(n_days=60, n_stocks=12, signal=0.0, seed=2):
    """Mã-phiên giả: lợi suất vượt thị trường cùng phiên = signal * điểm + nhiễu."""
    rng = np.random.default_rng(seed)
    rows = []
    for day in pd.bdate_range("2024-01-02", periods=n_days):
        for s in range(n_stocks):
            score = rng.uniform(-1, 1)
            rows.append(
                {
                    "stock_key": s,
                    "trade_date": day,
                    "score": score,
                    "excess": signal * score + rng.normal(0, 1),
                }
            )
    return pd.DataFrame(rows)


def test_kiem_chung_ngoai_nhan_ic_cao_khi_co_tin_hieu_va_gan_0_khi_khong():
    from ml import sentiment_validity as sv

    strong = sv.validity(validity_frame(signal=2.0))
    assert strong["excess_t0"]["all"]["mean_ic"] > 0.4 and strong["excess_t0"]["all"]["t_stat"] > 5
    assert strong["excess_t0"]["pooled_demeaned"]["significant_95"] is True
    # tin hiệu chỉ có ở cùng phiên: phiên kế tiếp không dự báo được
    assert abs(strong["excess_t1"]["all"]["mean_ic"]) < 0.15
    noise = sv.validity(validity_frame(signal=0.0, n_days=120))
    assert abs(noise["excess_t0"]["all"]["mean_ic"]) < 0.12
    assert noise["excess_t0"]["pooled_demeaned"]["significant_95"] is False


def test_loi_suat_tuong_lai_chi_dung_cac_phien_ke_tiep_cua_cung_ma():
    from ml import sentiment_validity as sv

    df = pd.DataFrame(
        {
            "stock_key": [1, 1, 1, 1, 1, 2, 2],
            "trade_date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
                + ["2024-01-02", "2024-01-03"]
            ),
            "excess": [1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0],
            "score": 0.1,
        }
    )
    out = sv.add_forward_returns(df).set_index(["stock_key", "trade_date"])
    assert out.loc[(1, pd.Timestamp("2024-01-02")), "excess_t1"] == 2.0
    assert out.loc[(1, pd.Timestamp("2024-01-02")), "excess_t1_3"] == 9.0  # 2 + 3 + 4
    assert np.isnan(out.loc[(1, pd.Timestamp("2024-01-05")), "excess_t1_3"])  # chưa đủ 3 phiên kế
    assert out.loc[(2, pd.Timestamp("2024-01-02")), "excess_t1"] == 20.0  # không lẫn sang mã khác
