"""Kiểm thử cảm xúc trong kho thật (cần đã chạy: python -m ml.sentiment từ thư mục src/)."""

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


@pytest.fixture(scope="module")
def model(conn):
    row = conn.execute(
        "SELECT model_key, metrics FROM dw.dim_model WHERE task = 'sentiment' ORDER BY trained_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("Chưa chạy python -m ml.sentiment")
    return {"key": row[0], "metrics": row[1]}


def test_moi_bai_da_gan_ma_nganh_deu_co_dong_cam_xuc(conn, model):
    missing = conn.execute(
        "SELECT count(*) FROM dw.bridge_article_entity b JOIN dw.dim_article a USING (article_key) "
        "LEFT JOIN dw.fact_news_sentiment f ON f.article_key = b.article_key AND f.entity_type = b.entity_type "
        "AND f.entity_code = b.entity_code WHERE a.is_market_related AND NOT a.is_duplicate "
        "AND a.session_date IS NOT NULL AND f.article_key IS NULL"
    ).fetchone()[0]
    assert missing == 0


def test_chi_giu_ket_qua_cua_mo_hinh_cam_xuc_moi_nhat(conn, model):
    keys = [
        r[0]
        for r in conn.execute("SELECT DISTINCT model_key FROM dw.fact_news_sentiment").fetchall()
    ]
    assert keys == [model["key"]]


def test_mot_bai_cung_mot_diem_so_cho_moi_ma_nganh(conn, model):
    """Cảm xúc ở mức bài: mọi mã/ngành của cùng một bài có cùng điểm."""
    bad = conn.execute(
        "SELECT count(*) FROM (SELECT article_key FROM dw.fact_news_sentiment GROUP BY article_key "
        "HAVING count(DISTINCT sentiment_score) > 1) x"
    ).fetchone()[0]
    assert bad == 0


def test_phan_bo_nhan_khong_lech_cuc_doan(model):
    dist = model["metrics"]["label_distribution_all_articles"]
    assert set(dist) == {"negative", "neutral", "positive"}
    assert all(0.05 <= v <= 0.8 for v in dist.values()), dist


def test_chi_so_vuot_xa_lop_pho_bien_va_chia_theo_thoi_gian(model):
    m = model["metrics"]
    assert m["model"]["accuracy"] > m["baseline_majority"]["accuracy"] + 0.15
    assert m["model"]["f1_macro"] > 0.5
    assert (
        m["train_range"].split("..")[1] < m["test_range"].split("..")[0]
    ), "tập kiểm tra phải sau tập huấn luyện"
    assert m["test_n"] >= 300


def test_mo_hinh_ket_hop_khong_te_hon_co_so_tfidf_tren_tap_kiem_tra(model):
    m = model["metrics"]
    if "baseline_tfidf_only" not in m:
        pytest.skip("Mô hình cũ chưa có so sánh với cơ sở TF-IDF")
    assert m["model"]["accuracy"] >= m["baseline_tfidf_only"]["accuracy"] - 0.02


def test_nhan_nhat_quan_voi_vai_vi_du_tay(conn):
    from ml import sentiment

    df = sentiment.load_labeled(conn)
    emb = sentiment.embeddings_for(df["article_id"].tolist(), df["emb_text"].tolist())
    final = sentiment.Ensemble().fit(df, emb)
    cases = {
        "positive": [
            "Công ty báo lãi kỷ lục, doanh thu tăng mạnh và chia cổ tức tiền mặt 20%",
            "Khối ngoại mua ròng mạnh, VN-Index tăng điểm, thanh khoản cải thiện",
            "Cổ phiếu tăng trần sau khi doanh nghiệp công bố lợi nhuận quý vượt kế hoạch",
        ],
        "negative": [
            "Cổ phiếu bị bán tháo, VN-Index giảm sâu, khối ngoại bán ròng mạnh",
            "Công ty báo lỗ nặng, nợ xấu tăng vọt, bị xử phạt và đình chỉ giao dịch",
            "Lãnh đạo doanh nghiệp bị khởi tố vì vi phạm quy định về công bố thông tin",
        ],
    }
    wrong = []
    for expected, texts in cases.items():
        pred = final.predict(
            [sentiment.make_text(t, "") for t in texts],
            sentiment.embed_texts([sentiment.emb_text(t, "") for t in texts]),
        )
        wrong += [(t, p) for t, p in zip(texts, pred, strict=True) if p != expected]
    assert len(wrong) <= 1, f"quá nhiều ví dụ tay bị sai: {wrong}"


def test_phien_cua_bai_khong_som_hon_ngay_dang(conn):
    """Bài đăng sau 15h được gán phiên kế tiếp: phiên của bài không bao giờ nhỏ hơn ngày đăng."""
    bad = conn.execute(
        "SELECT count(*) FROM dw.dim_article WHERE session_date < published_date AND session_date IS NOT NULL"
    ).fetchone()[0]
    assert bad == 0
