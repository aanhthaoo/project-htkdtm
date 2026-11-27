"""CafeF chuyên mục Chứng khoán: lấy danh sách bài theo trang rồi lấy toàn văn (lấp khoảng 10/2024 – nay).

Hai bước để chạy được lâu và tiếp tục được:
  1. list:  duyệt trang 1, 2, ... lưu liên kết (status = pending), dừng khi bài đã cũ hơn `stop_before`.
  2. fetch: lấy toàn văn các bài pending, mới nhất trước.
"""

import logging
import re
from datetime import UTC, datetime

from ingestion.client import Client
from ingestion.sources import news

log = logging.getLogger(__name__)

SOURCE = "cafef"
SITE = "https://cafef.vn"
LISTING = SITE + "/chung-khoan/trang-{page}.html"
ARTICLE_LINK = re.compile(r'href="(/[^"#?]+-188\d{12,}\.chn)(?:\?[^"#]*)?"')
CONTENT_SELECTOR = "div.detail-content"
MAX_PAGES = 600  # từ khoảng trang 600 trở đi chuyên mục trả rỗng


def extract_links(html: str) -> list[str]:
    """Liên kết bài (bỏ trùng, giữ thứ tự xuất hiện)."""
    seen: dict[str, None] = {}
    for path in ARTICLE_LINK.findall(html):
        seen.setdefault(SITE + path, None)
    return list(seen)


def collect_listing(
    conn, client: Client, stop_before: datetime, start_page: int = 1, max_pages: int = MAX_PAGES
) -> int:
    """Lưu liên kết bài từ trang `start_page` đến khi gặp bài cũ hơn `stop_before`."""
    total = 0
    for page in range(start_page, max_pages + 1):
        status, body = client.get(LISTING.format(page=page))
        links = extract_links(body.decode("utf-8", "replace")) if status == 200 else []
        if not links:
            log.info("cafef list: trang %d rỗng (status %s), dừng", page, status)
            break
        rows = []
        oldest = None
        for url in links:
            published = news.cafef_published_from_url(url)
            oldest = min(oldest, published) if oldest and published else (oldest or published)
            rows.append(
                (
                    url,
                    SOURCE,
                    f"page:{page}",
                    published,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    None,
                )
            )
        # Không ghi đè bài đã có toàn văn: chỉ thêm liên kết mới
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO raw.news_crawl (url, source, list_ref, published_at, status)
                VALUES (%s, %s, %s, %s, 'pending') ON CONFLICT (url) DO NOTHING
                """,
                [(r[0], r[1], r[2], r[3]) for r in rows],
            )
        conn.commit()
        total += len(rows)
        if page % 20 == 0:
            log.info("cafef list: trang %d, bài cũ nhất %s", page, oldest)
        if oldest and oldest < stop_before:
            log.info("cafef list: trang %d đã tới %s, dừng", page, oldest)
            break
    return total


def fetch_pending(conn, client: Client, limit: int | None = None, source: str = SOURCE) -> int:
    """Lấy toàn văn các bài pending, mới nhất trước; commit từng bài để dừng/chạy lại được."""
    rows = conn.execute(
        "SELECT url FROM raw.news_crawl WHERE source = %s AND status = 'pending' "
        "ORDER BY published_at DESC NULLS LAST" + (" LIMIT %s" if limit else ""),
        (source, limit) if limit else (source,),
    ).fetchall()
    urls = [r[0] for r in rows]
    log.info("cafef fetch: %d bài chờ", len(urls))
    done = 0
    for i, url in enumerate(urls, 1):
        status, body = client.get(url)
        if status != 200:
            conn.execute(
                "UPDATE raw.news_crawl SET status='failed', http_status=%s, fetched_at=now() WHERE url=%s",
                (status, url),
            )
            conn.commit()
            continue
        parsed = news.parse_article(body, CONTENT_SELECTOR)
        published = news.parse_local_time(parsed["published_raw"]) or news.cafef_published_from_url(
            url
        )
        row = news.article_row(url, source, parsed, published)
        news.upsert_articles(conn, [row])
        done += 1
        if i % 200 == 0:
            log.info("cafef fetch: %d/%d", i, len(urls))
    return done


def utc_floor(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)
