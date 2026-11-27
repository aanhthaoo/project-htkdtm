"""Kiểm tra nhãn cảm xúc do người gán (TV5) và đo mô hình trên tập chuẩn của con người.

Đầu vào: `data/samples/sentiment_validation_sample.csv` đã điền cột `label_human` (positive | neutral | negative).
Bước 1: kiểm tra tệp (đủ dòng, nhãn hợp lệ, không bỏ trống; báo cáo từng dòng sai).
Bước 2: so với điểm của mô hình trong dw.fact_news_sentiment (bài nào có dòng mã/ngành thì có điểm): accuracy, F1, Cohen kappa,
        ma trận nhầm. Tập này KHÔNG nằm trong nhãn huấn luyện (đã kiểm tra: 0 bài trùng) nên là kiểm tra độc lập.
Nếu cột `label_llm` được điền (một lượt gán khác, hoặc người thứ hai) thì thêm độ nhất quán giữa hai lượt gán.

Chạy (từ src/):  python -m ml.sentiment_check [đường dẫn tệp] [--json kết_quả.json] [--no-db]
"""

import argparse
import csv
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score

DEFAULT = (
    Path(__file__).resolve().parents[2] / "data" / "samples" / "sentiment_validation_sample.csv"
)
CLASSES = ["negative", "neutral", "positive"]
ALIASES = {
    "tích cực": "positive",
    "tiêu cực": "negative",
    "trung lập": "neutral",
    "pos": "positive",
    "neg": "negative",
    "neu": "neutral",
}


def normalize(value: str | None) -> str:
    v = (value or "").strip().lower()
    return ALIASES.get(v, v)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Trả (bảng đã chuẩn hóa nhãn, danh sách lỗi theo dòng). Lỗi: thiếu nhãn hoặc nhãn không hợp lệ."""
    errors = []
    df = df.copy()
    df["label_human"] = df["label_human"].map(normalize)
    for row in df.itertuples():
        line = row.Index + 2  # dòng trong tệp (tiêu đề là dòng 1)
        if row.label_human == "":
            errors.append(f"Dòng {line} ({row.sample_id}): chưa điền label_human")
        elif row.label_human not in CLASSES:
            errors.append(
                f"Dòng {line} ({row.sample_id}): nhãn '{row.label_human}' không hợp lệ "
                "(chọn positive, neutral hoặc negative)"
            )
    if "label_llm" in df.columns:
        df["label_llm"] = df["label_llm"].map(normalize)
    return df, errors


def compare(human: pd.Series, other: pd.Series) -> dict:
    """Chỉ số so hai chuỗi nhãn cùng độ dài."""
    return {
        "n": int(len(human)),
        "accuracy": float(accuracy_score(human, other)),
        "f1_macro": float(f1_score(human, other, labels=CLASSES, average="macro", zero_division=0)),
        "cohen_kappa": float(cohen_kappa_score(human, other, labels=CLASSES)),
        "confusion_matrix_rows_human_cols_other": confusion_matrix(
            human, other, labels=CLASSES
        ).tolist(),
        "order": CLASSES,
    }


def model_labels(conn, article_ids: list[str]) -> pd.Series:
    """Nhãn của mô hình mới nhất cho từng bài (mức bài; NaN nếu bài không nhắc mã/ngành nên không có điểm)."""
    rows = conn.execute(
        "SELECT a.article_id, max(f.sentiment_label) AS label FROM dw.fact_news_sentiment f "
        "JOIN dw.dim_article a USING (article_key) JOIN (SELECT model_key FROM dw.dim_model "
        "WHERE task = 'sentiment' ORDER BY trained_at DESC LIMIT 1) m USING (model_key) "
        "WHERE a.article_id = ANY(%s) GROUP BY 1",
        (article_ids,),
    ).fetchall()
    return pd.Series({r[0]: r[1] for r in rows}).reindex(article_ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=str(DEFAULT))
    parser.add_argument("--json")
    parser.add_argument(
        "--no-db", action="store_true", help="Chỉ kiểm tra tệp, không so với mô hình"
    )
    args = parser.parse_args()
    with open(args.file, encoding="utf-8-sig", newline="") as fh:
        df = pd.DataFrame(list(csv.DictReader(fh)))
    df, errors = validate(df)
    print(f"{len(df)} dòng; {len(errors)} lỗi")
    for e in errors[:50]:
        print("  LỖI:", e)
    if errors:
        return 1
    dist = df["label_human"].value_counts(normalize=True).round(3).to_dict()
    print("Phân bố nhãn người:", dist)
    result = {"n": len(df), "distribution": dist}
    if "label_llm" in df.columns and (df["label_llm"] != "").all():
        result["human_vs_second_labeler"] = compare(df["label_human"], df["label_llm"])
        m = result["human_vs_second_labeler"]
        print(f"Hai lượt gán: khớp {m['accuracy']:.3f}, Cohen kappa {m['cohen_kappa']:.3f}")
    if not args.no_db:
        from ml import common

        with common.connect() as conn:
            pred = model_labels(conn, df["article_id"].tolist())
        has = pred.notna().to_numpy()
        result["articles_with_model_score"] = int(has.sum())
        if has.sum() >= 30:
            result["human_vs_model"] = compare(
                df.loc[has, "label_human"].reset_index(drop=True), pred[has].reset_index(drop=True)
            )
            m = result["human_vs_model"]
            print(
                f"Người so với mô hình ({m['n']} bài có điểm): accuracy {m['accuracy']:.3f}, "
                f"F1 {m['f1_macro']:.3f}, kappa {m['cohen_kappa']:.3f}"
            )
            print(
                "Ma trận nhầm (hàng = người; neg, neu, pos):",
                m["confusion_matrix_rows_human_cols_other"],
            )
        else:
            print(f"Chỉ {int(has.sum())} bài có điểm của mô hình: không đủ để so sánh")
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
