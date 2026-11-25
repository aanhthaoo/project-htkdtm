"""Đường ống làm sạch tin tức: raw.news_backfill + raw.news_crawl -> stg.news_article, stg.news_mention (N5).

Các bước: chuẩn hóa văn bản -> gán phiên giao dịch (quy tắc 15h) -> nhận diện mã/ngành -> lọc bài liên quan
chứng khoán -> đánh dấu bài trùng (cùng nội dung hoặc cùng tiêu đề và ngày) -> ghi dq_log.

Chạy (từ src/):  python -m etl.news.pipeline [--limit N]
Cần đã chạy dbt (dim_time, dim_stock) để có lịch giao dịch và danh mục mã.
"""

import argparse
import logging
import sys
import uuid
from datetime import datetime

from etl.news import entities, normalize, relevance, session
from ingestion import db

log = logging.getLogger("etl.news")

DDL = """
CREATE TABLE IF NOT EXISTS stg.news_article (
    article_id        TEXT PRIMARY KEY,
    url               TEXT NOT NULL,
    source            TEXT NOT NULL,
    source_type       TEXT NOT NULL,
    title             TEXT,
    summary           TEXT,
    content           TEXT,
    category          TEXT,
    published_at      TIMESTAMPTZ,
    published_date    DATE,
    time_known        BOOLEAN NOT NULL,
    has_date          BOOLEAN NOT NULL,
    session_date      DATE,
    content_hash      TEXT,
    title_key         TEXT,
    content_chars     INTEGER,
    is_market_related BOOLEAN NOT NULL,
    relevance_score   INTEGER,
    relevance_reason  TEXT,
    n_stock_mentions  INTEGER,
    is_duplicate      BOOLEAN NOT NULL DEFAULT false,
    dup_of            TEXT,
    dup_reason        TEXT,
    processed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_news_article_session ON stg.news_article (session_date);
CREATE INDEX IF NOT EXISTS ix_news_article_hash ON stg.news_article (content_hash);
CREATE INDEX IF NOT EXISTS ix_news_article_title ON stg.news_article (title_key, published_date);

CREATE TABLE IF NOT EXISTS stg.news_mention (
    article_id   TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_code  TEXT NOT NULL,
    n_mentions   INTEGER NOT NULL,
    in_title     BOOLEAN NOT NULL,
    method       TEXT NOT NULL,
    PRIMARY KEY (article_id, entity_type, entity_code, method)
);
CREATE INDEX IF NOT EXISTS ix_news_mention_entity ON stg.news_mention (entity_type, entity_code);
"""

ARTICLE_COLUMNS = [
    "article_id", "url", "source", "source_type", "title", "summary", "content", "category",
    "published_at", "published_date", "time_known", "has_date", "session_date", "content_hash",
    "title_key", "content_chars", "is_market_related", "relevance_score", "relevance_reason",
    "n_stock_mentions",
]  # fmt: skip
MENTION_COLUMNS = ["article_id", "entity_type", "entity_code", "n_mentions", "in_title", "method"]
BATCH = 2000
MIN_CONTENT_CHARS = 200  # bài ngắn hơn không đủ để phân tích cảm xúc
ALIAS_MIN_LEN = 6
ALIAS_TOP_N = 250  # chỉ dùng tên công ty cho nhóm mã thanh khoản cao nhất


def load_calendar(conn) -> session.Calendar:
    rows = conn.execute(
        "SELECT date, is_trading_day, session_on_or_after, next_trading_date FROM dw.dim_time"
    ).fetchall()
    return session.Calendar.from_rows(rows)


def build_extractor(conn) -> entities.Extractor:
    rows = conn.execute(
        """
        SELECT d.symbol, s.icb_l2_code, d.short_name, d.avg_value_bn_60d
        FROM dw.dim_stock d JOIN dw.dim_sector s USING (sector_key)
        WHERE d.security_type = 'STOCK'
        """
    ).fetchall()
    symbols = {r[0] for r in rows}
    symbol_sector = {r[0]: r[1] for r in rows if r[1]}
    ranked = sorted(
        (r for r in rows if r[2] and len(r[2]) >= ALIAS_MIN_LEN and r[3]), key=lambda r: -r[3]
    )
    aliases: dict[str, str] = {}
    for symbol, _sector, short_name, _value in ranked[:ALIAS_TOP_N]:
        aliases.setdefault(short_name, symbol)
    # Tên ngắn trùng cho nhiều mã thì bỏ (không phân biệt được)
    counts: dict[str, int] = {}
    for _symbol, _s, short_name, _v in ranked[:ALIAS_TOP_N]:
        counts[short_name] = counts.get(short_name, 0) + 1
    aliases = {a: s for a, s in aliases.items() if counts[a] == 1}
    log.info(
        "danh mục: %d mã, %d tên công ty, %d mã nhập nhằng",
        len(symbols),
        len(aliases),
        len(symbols & entities.COMMON_ACRONYMS),
    )
    return entities.Extractor(symbols, symbol_sector, aliases)


def source_rows(conn, limit: int | None):
    """Sinh (url, source, source_type, title, summary, content, category, published_at, published_date, time_known)."""
    lim = f" LIMIT {int(limit)}" if limit else ""
    with conn.cursor(name="backfill") as cur:
        cur.itersize = 5000
        cur.execute(
            "SELECT url, source, title, content, category, published_date FROM raw.news_backfill"
            + lim
        )
        for url, source, title, content, category, pdate in cur:
            yield (url, source, "BACKFILL", title, None, content, category, None, pdate, False)
    with conn.cursor(name="crawl") as cur:
        cur.itersize = 5000
        cur.execute(
            "SELECT url, source, list_ref, title, summary, content, category, published_at "
            "FROM raw.news_crawl WHERE status = 'done'" + lim
        )
        for url, source, list_ref, title, summary, content, category, published_at in cur:
            source_type = "RSS" if list_ref == "rss" else "CRAWL"
            pdate = published_at.astimezone(session.VN_TZ).date() if published_at else None
            yield (
                url,
                source,
                source_type,
                title,
                summary,
                content,
                category,
                published_at,
                pdate,
                published_at is not None,
            )


def process(record, extractor: entities.Extractor, cal: session.Calendar):
    url, source, source_type, title, summary, content, category, published_at, pdate, time_known = (
        record
    )
    if source == "cafef" and source_type == "CRAWL" and not category:
        category = "Chứng khoán (CafeF)"  # liên kết lấy từ chuyên mục Chứng khoán
    clean_content = normalize.clean_text(content)
    clean_title = normalize.clean_title(title)
    mentions = extractor.extract(clean_title, clean_content)
    rel = relevance.score_article(
        clean_title, clean_content, category, extractor.confident_ticker_count(mentions)
    )
    aid = normalize.article_id(url)
    row = (
        aid, normalize.canonical_url(url), source, source_type, clean_title or None,
        normalize.clean_text(summary) or None, clean_content or None, category,
        published_at, pdate, time_known, pdate is not None,
        session.assign_session(published_at, pdate, time_known, cal),
        normalize.content_hash(clean_content) if clean_content else None,
        normalize.title_key(clean_title) or None, len(clean_content),
        rel.is_related, rel.score, rel.reason,
        sum(1 for m in mentions if m.entity_type == "STOCK"),
    )  # fmt: skip
    mention_rows = [
        (aid, m.entity_type, m.entity_code, m.n, m.in_title, m.method) for m in mentions
    ]
    return row, mention_rows


MARK_DUPLICATES = """
WITH ranked AS (
    SELECT article_id,
           row_number() OVER w_hash AS rn_hash,
           first_value(article_id) OVER w_hash AS keep_hash,
           CASE WHEN length(title_key) >= 20 AND published_date IS NOT NULL
                THEN row_number() OVER w_title END AS rn_title,
           CASE WHEN length(title_key) >= 20 AND published_date IS NOT NULL
                THEN first_value(article_id) OVER w_title END AS keep_title
    FROM stg.news_article
    WHERE content_chars >= %(min_chars)s
    WINDOW
        w_hash AS (PARTITION BY content_hash ORDER BY (time_known) DESC, content_chars DESC, article_id),
        w_title AS (PARTITION BY title_key, published_date ORDER BY (time_known) DESC, content_chars DESC, article_id)
)
UPDATE stg.news_article a
SET is_duplicate = true,
    dup_of = CASE WHEN r.rn_hash > 1 THEN r.keep_hash ELSE r.keep_title END,
    dup_reason = CASE WHEN r.rn_hash > 1 THEN 'same_content' ELSE 'same_title_date' END
FROM ranked r
WHERE a.article_id = r.article_id AND (r.rn_hash > 1 OR coalesce(r.rn_title, 1) > 1)
"""


def run(conn, limit: int | None = None) -> dict:
    conn.execute(DDL)
    conn.execute("TRUNCATE stg.news_mention, stg.news_article")
    conn.commit()
    cal = load_calendar(conn)
    extractor = build_extractor(conn)
    articles: list[tuple] = []
    mentions: list[tuple] = []
    total = 0
    reader = db.connect()  # kết nối riêng: con trỏ phía máy chủ bị đóng khi conn.commit()
    for record in source_rows(reader, limit):
        row, m_rows = process(record, extractor, cal)
        articles.append(row)
        mentions.extend(m_rows)
        if len(articles) >= BATCH:
            total += _flush(conn, articles, mentions)
            articles, mentions = [], []
            if total % 20000 < BATCH:
                log.info("đã xử lý %d bài", total)
    total += _flush(conn, articles, mentions)
    reader.close()
    conn.execute(MARK_DUPLICATES, {"min_chars": MIN_CONTENT_CHARS})
    conn.execute("ANALYZE stg.news_article")
    conn.commit()
    return summarize(conn)


def _flush(conn, articles: list[tuple], mentions: list[tuple]) -> int:
    n = db.copy_upsert(conn, "stg.news_article", ARTICLE_COLUMNS, articles, ["article_id"])
    seen: dict[tuple, tuple] = {}
    for m in mentions:
        seen[(m[0], m[1], m[2], m[5])] = m
    db.copy_upsert(
        conn,
        "stg.news_mention",
        MENTION_COLUMNS,
        list(seen.values()),
        ["article_id", "entity_type", "entity_code", "method"],
    )
    return n


def summarize(conn) -> dict:
    row = conn.execute(
        """
        SELECT count(*),
               count(*) FILTER (WHERE has_date),
               count(*) FILTER (WHERE is_duplicate),
               count(*) FILTER (WHERE content_chars < %s),
               count(*) FILTER (WHERE is_market_related),
               count(*) FILTER (WHERE is_market_related AND NOT is_duplicate AND has_date AND content_chars >= %s),
               count(*) FILTER (WHERE session_date IS NULL AND has_date)
        FROM stg.news_article
        """,
        (MIN_CONTENT_CHARS, MIN_CONTENT_CHARS),
    ).fetchone()
    keys = [
        "total",
        "has_date",
        "duplicates",
        "too_short",
        "market_related",
        "usable",
        "no_session",
    ]
    return dict(zip(keys, row, strict=True))


def write_dq(conn, stats: dict) -> str:
    run_id = uuid.uuid4().hex[:12]
    total = stats["total"] or 1
    checks = [
        ("news_total_articles", stats["total"], None, True),
        ("news_duplicate_rate", stats["duplicates"] / total, None, True),
        (
            "news_missing_date_rate",
            1 - stats["has_date"] / total,
            0.01,
            (1 - stats["has_date"] / total) <= 0.01,
        ),
        ("news_market_related_rate", stats["market_related"] / total, None, True),
        ("news_usable_articles", stats["usable"], None, True),
        (
            "news_no_session_rate",
            stats["no_session"] / total,
            0.01,
            stats["no_session"] / total <= 0.01,
        ),
    ]
    with conn.cursor() as cur:
        for name, metric, threshold, passed in checks:
            cur.execute(
                """
                INSERT INTO dw.dq_log (run_id, layer, source, check_name, target_table, severity, passed,
                                       metric_value, threshold_value, details)
                VALUES (%s, 'stg', 'news', %s, 'stg.news_article', %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    name,
                    "info" if threshold is None else "warning",
                    passed,
                    metric,
                    threshold,
                    db.jdump(stats),
                ),
            )
    conn.commit()
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=None, help="Giới hạn số bài mỗi nguồn (để thử)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
    conn = db.connect()
    started = datetime.now()
    stats = run(conn, args.limit)
    write_dq(conn, stats)
    print(f"Xong sau {datetime.now() - started}: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
