"""Xuất các tập mẫu cho bước gán nhãn và kiểm tra thủ công (N5).

Tạo trong data/samples/ (không đưa vào git):
  - sentiment_llm_sample.csv        ~4.000 bài phân tầng theo năm x nguồn, để LLM gán nhãn sơ bộ (N8)
  - sentiment_validation_sample.csv 400 bài tách riêng cho người kiểm tra nhãn (TV5), không trùng tập LLM
  - review_mentions_sample.csv      100 bài để người xem nhận diện mã có đúng không
  - review_relevance_sample.csv     100 bài (50 giữ + 50 loại) để người xem lọc bài liên quan có đúng không

Chạy (từ src/):  python -m etl.news.samples
"""

import csv
import random
import shutil
from datetime import datetime
from pathlib import Path

from ingestion import db

OUT = db.ROOT / "data" / "samples"
SEED = 20261125
EXCERPT = 1200


def _backup_existing(path: Path) -> None:
    """Người dùng có thể đã điền nhãn vào tệp cũ: không bao giờ ghi đè mà không sao lưu."""
    if path.exists() and path.stat().st_size > 0:
        stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
        shutil.copy2(path, backup)
        print(f"Đã sao lưu tệp cũ: {backup.name}")


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_existing(path)
    with open(
        path, "w", encoding="utf-8-sig", newline=""
    ) as fh:  # utf-8-sig để Excel mở đúng tiếng Việt
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Đã ghi {len(rows)} dòng: {path}")


def _entities(conn, ids: list[str]) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT article_id,
               string_agg(entity_code || CASE WHEN entity_type = 'SECTOR' THEN '*' ELSE '' END, ' ' ORDER BY n_mentions DESC)
        FROM stg.news_mention WHERE article_id = ANY(%s) AND (entity_type = 'STOCK' OR method = 'ticker_to_sector')
        GROUP BY article_id
        """,
        (ids,),
    ).fetchall()
    return dict(rows)


def usable_pool(conn):
    """Bài dùng được: liên quan chứng khoán, không trùng, có ngày, đủ dài."""
    return conn.execute(
        """
        SELECT article_id, url, source, source_type, published_date, title, left(content, %s), category
        FROM stg.news_article
        WHERE is_market_related AND NOT is_duplicate AND has_date AND content_chars >= 300
        ORDER BY article_id
        """,
        (EXCERPT,),
    ).fetchall()


def stratified(rows, n: int, rng: random.Random):
    """Lấy mẫu chia đều theo (năm, nguồn); ô nhỏ hơn hạn mức thì lấy hết."""
    strata: dict[tuple, list] = {}
    for r in rows:
        strata.setdefault((r[4].year, r[2]), []).append(r)
    per = max(1, n // len(strata))
    picked = []
    for key in sorted(strata):
        items = strata[key]
        rng.shuffle(items)
        picked.extend(items[:per])
    rng.shuffle(picked)
    return picked[:n]


def export_sentiment(conn) -> None:
    rng = random.Random(SEED)
    pool = usable_pool(conn)
    validation = stratified(pool, 400, rng)
    taken = {r[0] for r in validation}
    llm = stratified([r for r in pool if r[0] not in taken], 4000, rng)
    header = ["sample_id", "article_id", "url", "source", "published_date", "title", "excerpt", "entities",
              "label_llm", "label_human", "note"]  # fmt: skip
    for name, rows in (
        ("sentiment_validation_sample.csv", validation),
        ("sentiment_llm_sample.csv", llm),
    ):
        ents = _entities(conn, [r[0] for r in rows])
        out = [
            [f"S{i:05d}", r[0], r[1], r[2], r[4], r[5], r[6], ents.get(r[0], ""), "", "", ""]
            for i, r in enumerate(rows, 1)
        ]
        _write(OUT / name, header, out)


def export_review(conn) -> None:
    rng = random.Random(SEED + 1)
    ments = conn.execute(
        """
        SELECT a.article_id, a.url, a.title, left(a.content, 600)
        FROM stg.news_article a
        WHERE a.is_market_related AND NOT a.is_duplicate AND a.has_date AND a.n_stock_mentions > 0
        ORDER BY a.article_id
        """
    ).fetchall()
    rng.shuffle(ments)
    ments = ments[:100]
    ents = _entities(conn, [r[0] for r in ments])
    _write(
        OUT / "review_mentions_sample.csv",
        [
            "article_id",
            "url",
            "title",
            "excerpt",
            "tickers_found(*=ngành suy ra)",
            "dung_sai(đúng/sai)",
            "ghi_chu",
        ],
        [[r[0], r[1], r[2], r[3], ents.get(r[0], ""), "", ""] for r in ments],
    )
    kept = conn.execute(
        "SELECT article_id, url, title, left(content, 400), category, relevance_reason, is_market_related "
        "FROM stg.news_article WHERE is_market_related AND NOT is_duplicate AND has_date ORDER BY article_id"
    ).fetchall()
    dropped = conn.execute(
        "SELECT article_id, url, title, left(content, 400), category, relevance_reason, is_market_related "
        "FROM stg.news_article WHERE NOT is_market_related AND NOT is_duplicate AND has_date ORDER BY article_id"
    ).fetchall()
    rng.shuffle(kept)
    rng.shuffle(dropped)
    sample = kept[:50] + dropped[:50]
    rng.shuffle(sample)
    _write(
        OUT / "review_relevance_sample.csv",
        [
            "article_id",
            "url",
            "title",
            "excerpt",
            "category",
            "ly_do_he_thong",
            "he_thong_ket_luan_lien_quan",
            "dung_sai(đúng/sai)",
            "ghi_chu",
        ],  # fmt: skip
        [[r[0], r[1], r[2], r[3], r[4], r[5], "có" if r[6] else "không", "", ""] for r in sample],
    )


def main() -> int:
    conn = db.connect()
    export_sentiment(conn)
    export_review(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
