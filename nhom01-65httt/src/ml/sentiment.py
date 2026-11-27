"""N8a: mô hình cảm xúc tin tức, ghi dw.fact_news_sentiment.

Mô hình: kết hợp (trung bình xác suất) hai bộ phân loại hồi quy logistic cùng học từ nhãn:
  1. TF-IDF 1-2 gram âm tiết,
  2. embedding câu `intfloat/multilingual-e5-small` (chạy được trên CPU, không cần GPU).
Kết hợp hai nguồn cho kết quả tốt hơn từng nguồn riêng lẻ trên tập kiểm tra theo thời gian (xem docs/ml_ket_qua.md).

Nhãn huấn luyện do Claude gán (src/ml/labels/*.csv, chỉ gồm mã bài và nhãn, không có văn bản):
  sentiment_claude_labels.csv     1.500 bài đợt 1 (mẫu phân tầng theo năm và nguồn)
  sentiment_claude_labels_v2.csv  1.500 bài đợt 2 (700 + 150 bài mô hình phân vân nhất, 500 + 150 bài ngẫu nhiên)
Chia tập theo THỜI GIAN: huấn luyện bài trước 2025, kiểm tra bài đợt 1 từ 2025-01-01. Tập kiểm tra cố định từ đợt 1 để so được
với kết quả cũ; bài đợt 2 từ 2025 chỉ dùng cho mô hình cuối cùng (không nằm trong tập kiểm tra đã công bố).

Chạy (từ src/):  python -m ml.sentiment [--dry-run] [--embed-only]
"""

import argparse
import io
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.pipeline import make_pipeline

from ml import common

log = logging.getLogger("ml.sentiment")

LABELS_DIR = Path(__file__).parent / "labels"
LABEL_FILES = [
    ("v1", LABELS_DIR / "sentiment_claude_labels.csv"),
    ("v2", LABELS_DIR / "sentiment_claude_labels_v2.csv"),
]
LABELS_FILE = LABEL_FILES[0][1]  # giữ tên cũ cho mã đã dùng
CLASSES = ["negative", "neutral", "positive"]
TEST_FROM = "2025-01-01"  # tập kiểm tra theo thời gian: bài đợt 1 từ ngày này trở đi
LOW_CONFIDENCE_WEIGHT = 0.5  # nhãn lưỡng lự (c = 1) vẫn dùng nhưng trọng số thấp hơn (chọn trên đoạn 2023-2024, không dùng tập kiểm tra)
C_TFIDF = 4.0  # chọn trên tập chọn 2023-07..2024 (xem sentiment_experiments compare)
C_EMBED = 8.0
VERSION = "0.2.0"
EXCERPT_CHARS = (
    1200  # văn bản dùng cho mô hình: tiêu đề + 1.200 ký tự đầu của bài (giống lúc gán nhãn)
)
EMB_MODEL = "intfloat/multilingual-e5-small"
EMB_CHARS = 450  # embedding dùng tiêu đề + 450 ký tự đầu (nhanh hơn trên CPU)
EMB_MAX_TOKENS = 160
EMB_CACHE = Path(__file__).resolve().parents[2] / "data" / "ml_cache" / "embeddings_e5s.npz"
MODEL_ARTIFACT = (
    Path(__file__).resolve().parents[2] / "data" / "ml_cache" / "sentiment_ensemble.joblib"
)  # backend /ml/sentiment nạp tệp này

TEXT_SQL = """
SELECT a.article_key, a.article_id, a.session_date, a.published_date, a.title,
       left(coalesce(s.content, ''), %(n)s) AS body
FROM dw.dim_article a
JOIN stg.news_article s ON s.article_id = a.article_id
WHERE a.is_market_related AND NOT a.is_duplicate AND a.session_date IS NOT NULL
"""
ENTITY_SQL = """
SELECT b.article_key, b.entity_type, b.entity_code, b.stock_key, b.icb_l2_code
FROM dw.bridge_article_entity b
JOIN dw.dim_article a USING (article_key)
WHERE a.is_market_related AND NOT a.is_duplicate AND a.session_date IS NOT NULL
"""


def clean(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"\d+([.,]\d+)?", " <số> ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def make_text(title: str, body: str) -> str:
    return clean(f"{title}. {body}")


def emb_text(title: str, body: str) -> str:
    """Văn bản đưa vào embedding: tiêu đề + EMB_CHARS ký tự đầu của bài, đã làm sạch."""
    return clean(f"{title}. {(body or '')[:EMB_CHARS]}")


# ---------------- Embedding ----------------
_embedder = None


def _load_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(EMB_MODEL, device="cpu")
        _embedder.max_seq_length = EMB_MAX_TOKENS
    return _embedder


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Embedding câu đã chuẩn hóa L2 (tiền tố "query: " theo cách dùng của họ mô hình e5 cho phân loại)."""
    return _load_embedder().encode(
        ["query: " + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def embeddings_for(
    article_ids: list[str],
    texts: list[str],
    cache: Path = EMB_CACHE,
    chunk: int = 2048,
    embedder=embed_texts,
) -> np.ndarray:
    """Embedding của từng bài, có bộ nhớ đệm theo article_id (chỉ tính bài chưa có; lưu định kỳ để chạy lại không mất công)."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    known: dict[str, np.ndarray] = {}
    if cache.exists():
        with np.load(cache, allow_pickle=False) as z:
            known = dict(zip(z["ids"].tolist(), z["vecs"], strict=True))
    todo = [(i, t) for i, t in zip(article_ids, texts, strict=True) if i not in known]
    done = 0
    for start in range(0, len(todo), chunk):
        part = todo[start : start + chunk]
        vecs = embedder([t for _, t in part])
        for (i, _), v in zip(part, vecs, strict=True):
            known[i] = v.astype(np.float16)
        done += len(part)
        log.info("embedding %d/%d bài mới", done, len(todo))
        if (start // chunk) % 8 == 7 or start + chunk >= len(todo):
            ids = np.array(list(known), dtype=str)
            np.savez(cache, ids=ids, vecs=np.stack([known[i] for i in ids]))
    return np.stack([known[i] for i in article_ids]).astype(np.float32)


# ---------------- Mô hình ----------------
def build_model() -> object:
    return make_pipeline(
        TfidfVectorizer(
            ngram_range=(1, 2), min_df=3, max_df=0.9, sublinear_tf=True, max_features=60000
        ),
        LogisticRegression(C=C_TFIDF, max_iter=2000, class_weight="balanced"),
    )


def sample_weights(frame: pd.DataFrame) -> np.ndarray:
    return np.where(frame["c"] <= 1, LOW_CONFIDENCE_WEIGHT, 1.0)


def fit_model(frame: pd.DataFrame):
    """Chỉ nhánh TF-IDF (mô hình cơ sở của phiên bản 0.1.0)."""
    model = build_model()
    model.fit(
        frame["text"], frame["label"], logisticregression__sample_weight=sample_weights(frame)
    )
    return model


class Ensemble:
    """Trung bình xác suất của TF-IDF + hồi quy logistic và embedding + hồi quy logistic."""

    def __init__(self, c_tfidf: float = C_TFIDF, c_embed: float = C_EMBED):
        self.c_tfidf, self.c_embed = c_tfidf, c_embed

    def fit(self, frame: pd.DataFrame, emb: np.ndarray) -> "Ensemble":
        weights = sample_weights(frame)
        self.tfidf = build_model()
        self.tfidf.set_params(logisticregression__C=self.c_tfidf)
        self.tfidf.fit(frame["text"], frame["label"], logisticregression__sample_weight=weights)
        self.emb = LogisticRegression(C=self.c_embed, max_iter=3000, class_weight="balanced")
        self.emb.fit(emb, frame["label"], sample_weight=weights)
        assert list(self.tfidf.classes_) == list(self.emb.classes_)
        self.classes_ = self.tfidf.classes_
        return self

    def predict_proba(self, texts, emb: np.ndarray) -> np.ndarray:
        return (self.tfidf.predict_proba(texts) + self.emb.predict_proba(emb)) / 2

    def predict(self, texts, emb: np.ndarray) -> np.ndarray:
        return self.classes_[self.predict_proba(texts, emb).argmax(axis=1)]


def score_from_proba(
    proba: np.ndarray, classes: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Điểm = P(tích cực) - P(tiêu cực) trong [-1, 1]; nhãn = lớp xác suất cao nhất; độ tin cậy = xác suất đó."""
    idx = {c: i for i, c in enumerate(classes)}
    score = proba[:, idx["positive"]] - proba[:, idx["negative"]]
    label = np.array(classes)[proba.argmax(axis=1)]
    return score, label, proba.max(axis=1)


def evaluate(y_true, y_pred) -> dict:
    p, r, f, support = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, labels=CLASSES, average="macro")),
        "per_class": {
            c: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(support[i]),
            }
            for i, c in enumerate(CLASSES)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
        "n": int(len(y_true)),
    }


def load_labeled(conn) -> pd.DataFrame:
    """Nhãn (đợt 1 và đợt 2 nếu có) ghép với văn bản trong kho; cột `origin` = v1 | v2."""
    parts = []
    for origin, path in LABEL_FILES:
        if path.exists():
            parts.append(pd.read_csv(path, encoding="utf-8").assign(origin=origin))
    labels = pd.concat(parts, ignore_index=True).drop_duplicates("article_id", keep="first")
    texts = common.read_sql(conn, TEXT_SQL, {"n": EXCERPT_CHARS})
    df = labels.merge(texts, on="article_id", how="inner")
    df["text"] = [make_text(t, b) for t, b in zip(df["title"], df["body"], strict=True)]
    df["emb_text"] = [emb_text(t, b) for t, b in zip(df["title"], df["body"], strict=True)]
    df["published_date"] = pd.to_datetime(df["published_date"])
    return df.reset_index(drop=True)


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Huấn luyện: mọi bài trước TEST_FROM. Kiểm tra: bài đợt 1 từ TEST_FROM. Bài đợt 2 từ TEST_FROM không thuộc tập nào (chỉ cho mô hình cuối)."""
    train = df[df["published_date"] < TEST_FROM]
    test = df[(df["published_date"] >= TEST_FROM) & (df["origin"] == "v1")]
    return train, test


def train_eval(df: pd.DataFrame, emb: np.ndarray, seed: int = common.SEED) -> tuple[dict, Ensemble]:
    """Huấn luyện trên bài trước TEST_FROM, đo trên tập kiểm tra; kèm mô hình cơ sở (chỉ TF-IDF) và lớp phổ biến.

    `emb`: ma trận embedding căn theo hàng của `df`.
    """
    train, test = split(df)
    assert (
        train["published_date"].max() < test["published_date"].min()
    )  # không rò rỉ theo thời gian
    model = Ensemble().fit(train, emb[train.index])
    pred = model.predict(test["text"], emb[test.index])
    base = fit_model(train).predict(test["text"])
    majority = train["label"].mode()[0]
    result = {
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "train_range": f"{train['published_date'].min().date()}..{train['published_date'].max().date()}",
        "test_range": f"{test['published_date'].min().date()}..{test['published_date'].max().date()}",
        "model": evaluate(test["label"], pred),
        "baseline_tfidf_only": evaluate(test["label"], base),
        "baseline_majority": {
            "class": majority,
            "accuracy": float((test["label"] == majority).mean()),
        },
        "label_distribution_train": train["label"].value_counts(normalize=True).round(4).to_dict(),
        "label_distribution_test": test["label"].value_counts(normalize=True).round(4).to_dict(),
        "components": {"tfidf_C": C_TFIDF, "embedding_C": C_EMBED, "embedding_model": EMB_MODEL},
    }
    return result, model


def predict_all(conn, model: Ensemble) -> pd.DataFrame:
    texts = common.read_sql(conn, TEXT_SQL, {"n": EXCERPT_CHARS})
    x = [make_text(t, b) for t, b in zip(texts["title"], texts["body"], strict=True)]
    emb = embeddings_for(
        texts["article_id"].tolist(),
        [emb_text(t, b) for t, b in zip(texts["title"], texts["body"], strict=True)],
    )
    classes = list(model.classes_)
    score, label, conf = score_from_proba(model.predict_proba(x, emb), classes)
    return pd.DataFrame(
        {
            "article_key": texts["article_key"],
            "session_date": texts["session_date"],
            "sentiment_score": score,
            "sentiment_label": label,
            "confidence": conf,
        }
    )


def write_fact(conn, scores: pd.DataFrame, model_key: int) -> int:
    """Mỗi bài x mã/ngành được nhắc một dòng. Chỉ giữ kết quả của mô hình cảm xúc mới nhất (xóa kết quả cũ để không đếm trùng)."""
    entities = common.read_sql(conn, ENTITY_SQL)
    fact = entities.merge(scores, on="article_key", how="inner")
    fact["session_date_key"] = (
        pd.to_datetime(fact["session_date"]).dt.strftime("%Y%m%d").astype(int)
    )
    fact["model_key"] = model_key
    fact["stock_key"] = fact["stock_key"].astype(
        "Int64"
    )  # số nguyên cho phép trống (tránh ghi dạng khoa học)
    cols = ["article_key", "session_date_key", "entity_type", "entity_code", "stock_key", "icb_l2_code",
            "sentiment_score", "sentiment_label", "confidence", "model_key"]  # fmt: skip
    buf = io.StringIO()
    fact[cols].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM dw.fact_news_sentiment WHERE model_key IN (SELECT model_key FROM dw.dim_model WHERE task = 'sentiment')"
        )
        with cur.copy(
            "COPY dw.fact_news_sentiment (article_key, session_date_key, entity_type, entity_code, stock_key, icb_l2_code, "
            "sentiment_score, sentiment_label, confidence, model_key) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
        ) as copy:
            copy.write(buf.read())
        cur.execute(
            "UPDATE dw.fact_news_sentiment SET scored_at = now() WHERE model_key = %s", (model_key,)
        )
    conn.commit()
    return len(fact)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Chỉ huấn luyện và đo, không ghi vào dw"
    )
    parser.add_argument(
        "--embed-only",
        action="store_true",
        help="Chỉ tính và lưu embedding cho mọi bài (bộ nhớ đệm), rồi dừng",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with common.connect() as conn:
        if args.embed_only:
            texts = common.read_sql(conn, TEXT_SQL, {"n": EXCERPT_CHARS})
            embeddings_for(
                texts["article_id"].tolist(),
                [emb_text(t, b) for t, b in zip(texts["title"], texts["body"], strict=True)],
            )
            return 0
        df = load_labeled(conn)
        log.info("%d bài có nhãn và có văn bản", len(df))
        emb = embeddings_for(df["article_id"].tolist(), df["emb_text"].tolist())
        result, _ = train_eval(df, emb)
        print(
            f"Huấn luyện {result['train_n']} bài ({result['train_range']}), kiểm tra {result['test_n']} bài ({result['test_range']})"
        )
        print(
            "Mô hình kết hợp:",
            {k: round(v, 4) for k, v in result["model"].items() if isinstance(v, float)},
        )
        print(
            "Cơ sở chỉ TF-IDF:",
            {
                k: round(v, 4)
                for k, v in result["baseline_tfidf_only"].items()
                if isinstance(v, float)
            },
        )
        print("Lớp phổ biến:", result["baseline_majority"])
        print("Theo lớp:", result["model"]["per_class"])
        print(
            "Ma trận nhầm (hàng = thật, cột = dự đoán; neg, neu, pos):",
            result["model"]["confusion_matrix"],
        )
        if args.dry_run:
            return 0
        # Mô hình cuối cùng huấn luyện bằng mọi bài có nhãn (kể cả 2025-2026) để suy luận lên toàn kho
        final = Ensemble().fit(df, emb)
        import joblib

        MODEL_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": final, "version": VERSION}, MODEL_ARTIFACT)
        scores = predict_all(conn, final)
        dist = scores["sentiment_label"].value_counts(normalize=True).round(4).to_dict()
        metrics = common.to_jsonable(
            {
                **result,
                "label_files": {o: int((df["origin"] == o).sum()) for o in df["origin"].unique()},
                "label_distribution_all_articles": dist,
                "n_scored_articles": len(scores),
            }
        )
        model_key = common.register_model(
            conn,
            "tfidf_e5_ensemble_sentiment",
            "sentiment",
            VERSION,
            result["train_range"],
            metrics,
        )
        n = write_fact(conn, scores, model_key)
        print(
            f"model_key {model_key}: chấm {len(scores)} bài, ghi {n} dòng (bài x mã/ngành); phân bố nhãn: {dist}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
