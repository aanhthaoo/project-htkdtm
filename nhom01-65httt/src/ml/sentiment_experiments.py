"""Thí nghiệm cải thiện mô hình cảm xúc (không ghi vào dw). Kết quả in ra và lưu JSON vào thư mục `--out`.

  curve  : đường cong học (huấn luyện 25/50/75/100% số nhãn, lặp 5 lần) để biết thêm nhãn có còn giúp được không
  select : chọn mẫu bài cần gán nhãn thêm (active learning: bài mô hình phân vân, ưu tiên vùng trung lập), trước 2025
  compare: so các biến thể (TF-IDF gốc, tách từ, n-gram ký tự, embedding, ngưỡng lớp trung lập) trên cùng tập kiểm tra

Chạy (từ src/):  python -m ml.sentiment_experiments curve|select|compare --out <thư mục>
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ml import common, sentiment

log = logging.getLogger("ml.sentiment_experiments")


def curve(df: pd.DataFrame) -> dict:
    train_all = df[df["published_date"] < sentiment.TEST_FROM]
    test = df[df["published_date"] >= sentiment.TEST_FROM]
    out = {}
    for frac in (0.25, 0.5, 0.75, 1.0):
        accs, f1s = [], []
        for rep in range(5 if frac < 1 else 1):
            sub = train_all.sample(frac=frac, random_state=common.SEED + rep)
            m = sentiment.fit_model(sub)
            res = sentiment.evaluate(test["label"], m.predict(test["text"]))
            accs.append(res["accuracy"])
            f1s.append(res["f1_macro"])
        out[str(frac)] = {
            "n_train": int(len(train_all) * frac),
            "accuracy_mean": float(np.mean(accs)),
            "accuracy_sd": float(np.std(accs)),
            "f1_macro_mean": float(np.mean(f1s)),
        }
    return out


DEV_FROM = "2023-07-01"  # tập chọn cấu hình = bài từ ngày này tới hết 2024 (trong tập huấn luyện gốc); không dùng tập kiểm tra 2025+
EMB_CHARS = 450  # tiêu đề + 450 ký tự đầu cho embedding (nhanh hơn trên CPU)
NEUTRAL_WEIGHTS = (1.0, 1.2, 1.5, 2.0, 2.5)


def segment(text: str) -> str:
    """Tách từ tiếng Việt (pyvi): từ ghép nối bằng dấu gạch dưới, ví dụ "cổ_phiếu", "khối_ngoại"."""
    from pyvi import ViTokenizer

    return ViTokenizer.tokenize(text)


def embed(texts: list[str], model_name: str, cache: Path) -> np.ndarray:
    """Embedding câu (đã chuẩn hóa L2), lưu cache để không tính lại."""
    if cache.exists():
        return np.load(cache)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu")
    model.max_seq_length = 160
    out = model.encode(
        ["query: " + t for t in texts],
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    np.save(cache, out)
    return out


def tfidf_lr(analyzer="word", ngram=(1, 2), c=4.0, min_df=3, max_features=60000):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    return make_pipeline(
        TfidfVectorizer(
            analyzer=analyzer,
            ngram_range=ngram,
            min_df=min_df,
            max_df=0.9,
            sublinear_tf=True,
            max_features=max_features,
        ),
        LogisticRegression(C=c, max_iter=3000, class_weight="balanced"),
    )


def fit_proba(kind, train, test, emb, c=4.0) -> np.ndarray:
    """Xác suất 3 lớp (cột theo sentiment.CLASSES) của một biến thể mô hình cho `test`.

    kind: tfidf | tfidf_seg | tfidf_char | emb:<tên embedding>. `train`, `test` giữ chỉ số hàng gốc để tra embedding.
    """
    from sklearn.linear_model import LogisticRegression

    w = sentiment.sample_weights(train)
    if kind.startswith("tfidf"):
        col = {"tfidf": "text", "tfidf_seg": "seg", "tfidf_char": "text"}[kind]
        model = tfidf_lr("char_wb", (2, 5), c, 3, 120000) if kind == "tfidf_char" else tfidf_lr(c=c)
        model.fit(train[col], train["label"], logisticregression__sample_weight=w)
        order = [list(model.classes_).index(k) for k in sentiment.CLASSES]
        return model.predict_proba(test[col])[:, order]
    name = kind.split(":")[1]
    clf = LogisticRegression(C=c, max_iter=3000, class_weight="balanced")
    clf.fit(emb[name][train.index], train["label"], sample_weight=w)
    order = [list(clf.classes_).index(k) for k in sentiment.CLASSES]
    return clf.predict_proba(emb[name][test.index])[:, order]


def decide(proba: np.ndarray, neutral_weight: float = 1.0) -> np.ndarray:
    """Nhãn = lớp có xác suất lớn nhất sau khi nhân xác suất lớp trung lập với `neutral_weight` (bù recall thấp của lớp này)."""
    p = proba.copy()
    p[:, 1] *= neutral_weight
    return np.array(sentiment.CLASSES)[p.argmax(axis=1)]


def bootstrap_acc_diff(y, a, b, n=2000, seed=7) -> dict:
    rng = np.random.default_rng(seed)
    d = (np.asarray(a) == np.asarray(y)).astype(float) - (np.asarray(b) == np.asarray(y)).astype(
        float
    )
    boot = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "mean_diff": float(d.mean()),
        "ci95": [float(lo), float(hi)],
        "p_better": float((boot > 0).mean()),
    }


def compare(df: pd.DataFrame, out_dir: Path) -> dict:
    """So các biến thể bằng cùng một quy trình: chọn C và trọng số trung lập trên tập chọn (2023-07..2024), đo trên tập kiểm tra 2025+."""
    df = df.reset_index(drop=True)
    df["seg"] = [segment(t) for t in df["text"]]
    emb_text = [
        sentiment.clean(f"{t}. {b[:EMB_CHARS]}")
        for t, b in zip(df["title"], df["body"], strict=True)
    ]
    emb = {
        name: embed(emb_text, model_name, out_dir / f"emb_{name}.npy")
        for name, model_name in (
            ("e5s", "intfloat/multilingual-e5-small"),
            ("e5b", "intfloat/multilingual-e5-base"),
        )
    }
    train_all = df[df["published_date"] < sentiment.TEST_FROM]
    test = df[df["published_date"] >= sentiment.TEST_FROM]
    dev_tr = train_all[train_all["published_date"] < DEV_FROM]
    dev = train_all[train_all["published_date"] >= DEV_FROM]
    log.info(
        "chọn: huấn luyện %d, chọn %d; cuối: huấn luyện %d, kiểm tra %d",
        len(dev_tr),
        len(dev),
        len(train_all),
        len(test),
    )
    grid = {
        "tfidf": [1, 4, 16],
        "tfidf_seg": [1, 4, 16],
        "tfidf_char": [1, 4, 16],
        "emb:e5s": [0.5, 2, 8, 32],
        "emb:e5b": [0.5, 2, 8, 32],
    }
    dev_rows, dev_proba = [], {}
    for v, cs in grid.items():
        for c in cs:
            p = fit_proba(v, dev_tr, dev, emb, c)
            dev_proba[(v, c)] = p
            res = sentiment.evaluate(dev["label"], decide(p))
            dev_rows.append(
                {
                    "variant": v,
                    "C": c,
                    "dev_acc": res["accuracy"],
                    "dev_f1": res["f1_macro"],
                    "dev_neutral_recall": res["per_class"]["neutral"]["recall"],
                }
            )
    dev_tab = pd.DataFrame(dev_rows)
    print("TẬP CHỌN (theo C):")
    print(dev_tab.round(3).to_string(index=False))
    best_c = {
        v: float(g.sort_values("dev_f1", ascending=False).iloc[0]["C"])
        for v, g in dev_tab.groupby("variant")
    }
    final = {v: fit_proba(v, train_all, test, emb, best_c[v]) for v in grid}
    dev_best = {v: dev_proba[(v, best_c[v] if v in best_c else 1)] for v in grid}
    for tf in ("tfidf", "tfidf_seg", "tfidf_char"):
        for e in ("emb:e5s", "emb:e5b"):
            name = f"ens({tf}+{e})"
            final[name] = (final[tf] + final[e]) / 2
            dev_best[name] = (dev_best[tf] + dev_best[e]) / 2
    weight = {}
    for name, p in dev_best.items():
        scores = {
            w: sentiment.evaluate(dev["label"], decide(p, w))["f1_macro"] for w in NEUTRAL_WEIGHTS
        }
        weight[name] = max(scores, key=lambda w: (round(scores[w], 6), -w))
    y = test["label"].to_numpy()
    base = decide(final["tfidf"])
    results = {}
    for name, p in final.items():
        plain, weighted = decide(p), decide(p, weight[name])
        r, rw = sentiment.evaluate(y, plain), sentiment.evaluate(y, weighted)
        results[name] = {
            "C": best_c.get(name),
            "neutral_weight": weight[name],
            "acc": r["accuracy"],
            "f1": r["f1_macro"],
            "neutral_recall": r["per_class"]["neutral"]["recall"],
            "acc_w": rw["accuracy"],
            "f1_w": rw["f1_macro"],
            "neutral_recall_w": rw["per_class"]["neutral"]["recall"],
            "acc_diff_vs_tfidf": bootstrap_acc_diff(y, plain, base),
            "acc_diff_vs_tfidf_w": bootstrap_acc_diff(y, weighted, base),
        }
    tab = pd.DataFrame(results).T[
        ["C", "neutral_weight", "acc", "f1", "neutral_recall", "acc_w", "f1_w", "neutral_recall_w"]
    ]
    print(
        "TẬP KIỂM TRA 2025+ (C và trọng số trung lập chọn trên tập chọn; hậu tố _w = có trọng số trung lập):"
    )
    print(tab.astype(float).round(3).to_string())
    return {
        "dev": dev_tab.to_dict("records"),
        "test": results,
        "n": {"train": len(train_all), "dev": len(dev), "test": len(test)},
    }


N_UNCERTAIN_PRE, N_RANDOM_PRE, N_UNCERTAIN_POST, N_RANDOM_POST = 700, 500, 150, 150
BATCH_SIZE = 100


def select_for_labeling(conn, df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Chọn 1.500 bài cần gán nhãn thêm: bài mô hình (TF-IDF + embedding) phân vân nhất (active learning) trộn với bài ngẫu nhiên.

    Bài trước 2025: 700 phân vân + 500 ngẫu nhiên (dùng để huấn luyện và đo, tập kiểm tra 2025+ giữ nguyên).
    Bài từ 2025: 150 phân vân + 150 ngẫu nhiên (chỉ dùng cho mô hình cuối cùng, không đưa vào tập kiểm tra đã công bố).
    Loại bài đã có nhãn và bài trong tập kiểm chứng của TV5. Phân vân = chênh lệch xác suất giữa hai lớp đầu nhỏ nhất, chia đều theo năm.
    """
    texts = common.read_sql(conn, sentiment.TEXT_SQL, {"n": sentiment.EXCERPT_CHARS})
    ents = common.read_sql(conn, sentiment.ENTITY_SQL)
    ent_str = ents.groupby("article_key")["entity_code"].apply(
        lambda s: ", ".join(sorted(set(s))[:6])
    )
    texts["entities"] = texts["article_key"].map(ent_str).fillna("")
    skip = set(df["article_id"])
    gold = (
        Path(__file__).resolve().parents[2] / "data" / "samples" / "sentiment_validation_sample.csv"
    )
    if gold.exists():
        skip |= set(pd.read_csv(gold, encoding="utf-8-sig")["article_id"].astype(str))
    texts = texts[~texts["article_id"].isin(skip)].copy()
    texts["published_date"] = pd.to_datetime(texts["published_date"])
    rng = np.random.default_rng(common.SEED)
    pre = texts[texts["published_date"] < sentiment.TEST_FROM]
    post = texts[texts["published_date"] >= sentiment.TEST_FROM]
    pool = pd.concat(
        [
            pre.iloc[rng.permutation(len(pre))[:8000]].assign(period="pre"),
            post.iloc[rng.permutation(len(post))[:1500]].assign(period="post"),
        ],
        ignore_index=True,
    )
    pool["text"] = [
        sentiment.make_text(t, b) for t, b in zip(pool["title"], pool["body"], strict=True)
    ]
    emb_text = [
        sentiment.clean(f"{t}. {b[:EMB_CHARS]}")
        for t, b in zip(pool["title"], pool["body"], strict=True)
    ]
    labeled = df.reset_index(drop=True)
    lab_emb_text = [
        sentiment.clean(f"{t}. {b[:EMB_CHARS]}")
        for t, b in zip(labeled["title"], labeled["body"], strict=True)
    ]
    model_name = "intfloat/multilingual-e5-small"
    emb_lab = embed(lab_emb_text, model_name, out_dir / "emb_e5s.npy")
    emb_pool = embed(emb_text, model_name, out_dir / "emb_pool_e5s.npy")
    from sklearn.linear_model import LogisticRegression

    w = sentiment.sample_weights(labeled)
    tf = tfidf_lr(c=4.0).fit(labeled["text"], labeled["label"], logisticregression__sample_weight=w)
    lr = LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced").fit(
        emb_lab, labeled["label"], sample_weight=w
    )
    p = (tf.predict_proba(pool["text"]) + lr.predict_proba(emb_pool)) / 2
    top2 = np.sort(p, axis=1)[:, -2:]
    pool["margin"] = top2[:, 1] - top2[:, 0]
    pool["year"] = pool["published_date"].dt.year
    picked = []
    for period, n_unc, n_rnd in (
        ("pre", N_UNCERTAIN_PRE, N_RANDOM_PRE),
        ("post", N_UNCERTAIN_POST, N_RANDOM_POST),
    ):
        part = pool[pool["period"] == period]
        # phân vân nhất, chia theo năm tỷ lệ với số bài của năm trong nhóm
        unc_idx = []
        counts = part["year"].value_counts()
        for year, cnt in counts.items():
            take = int(round(n_unc * cnt / len(part)))
            unc_idx += list(part[part["year"] == year].nsmallest(take, "margin").index)
        unc = part.loc[unc_idx[:n_unc]].assign(strategy="uncertain")
        rest = part.drop(unc.index)
        rnd = rest.iloc[rng.permutation(len(rest))[:n_rnd]].assign(strategy="random")
        picked += [unc, rnd]
    sel = pd.concat(picked).iloc[lambda d: rng.permutation(len(d))].reset_index(drop=True)
    sel["sample_id"] = [f"N{i + 1:05d}" for i in range(len(sel))]
    sel["excerpt"] = sel["body"].str.replace(r"\s+", " ", regex=True).str[:900]
    sel["batch"] = sel.index // BATCH_SIZE + 1
    lab_dir = out_dir / "labeling2"
    lab_dir.mkdir(exist_ok=True)
    for b, g in sel.groupby("batch"):
        g[["sample_id", "title", "excerpt", "entities"]].to_csv(
            lab_dir / f"in_{b:02d}.csv", index=False, encoding="utf-8"
        )
    sel[
        [
            "sample_id",
            "article_id",
            "published_date",
            "year",
            "period",
            "strategy",
            "margin",
            "batch",
        ]
    ].to_csv(lab_dir / "picked_index.csv", index=False, encoding="utf-8")
    return sel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["curve", "select", "compare"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with common.connect() as conn:
        df = sentiment.load_labeled(conn)
        if args.what == "select":
            sel = select_for_labeling(conn, df, out_dir)
            print(
                sel.groupby(["period", "strategy"])
                .agg(n=("sample_id", "size"), margin=("margin", "mean"))
                .round(3)
            )
            print(sel["batch"].value_counts().sort_index().to_dict())
        if args.what == "compare":
            result = compare(df, out_dir)
            (out_dir / "compare.json").write_text(
                json.dumps(common.to_jsonable(result), indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
        if args.what == "curve":
            result = curve(df)
            print(pd.DataFrame(result).T.round(4).to_string())
            (out_dir / "curve.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
