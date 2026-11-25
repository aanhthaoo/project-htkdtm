"""RSS: tin mới của VnEconomy, Vietstock, VnExpress, Tin nhanh Chứng khoán (RSS chỉ giữ vài ngày)."""

import calendar
import logging
from datetime import UTC, datetime

import feedparser

from ingestion.client import Client
from ingestion.sources import news

log = logging.getLogger(__name__)

FEEDS = {
    "vneconomy": ["https://vneconomy.vn/chung-khoan.rss"],
    "vietstock": [
        "https://vietstock.vn/830/chung-khoan/co-phieu.rss",
        "https://vietstock.vn/144/chung-khoan.rss",
    ],
    "vnexpress": ["https://vnexpress.net/rss/kinh-doanh.rss"],
    "tnck": ["https://www.tinnhanhchungkhoan.vn/rss/home.rss"],
}


def entry_published(entry) -> datetime | None:
    """feedparser đã chuẩn hóa về UTC (kể cả VnEconomy dùng GMT và các nguồn khác +0700)."""
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)


def read_feed(client: Client, url: str) -> list[dict]:
    status, body = client.get(url)
    if status != 200:
        log.warning("RSS %s: HTTP %s", url, status)
        return []
    items = []
    for e in feedparser.parse(body).entries:
        if e.get("link"):
            items.append(
                {
                    "url": e["link"].strip(),
                    "title": e.get("title"),
                    "summary": e.get("summary"),
                    "published_at": entry_published(e),
                }
            )
    return items


def known_urls(conn, urls: list[str]) -> set[str]:
    if not urls:
        return set()
    rows = conn.execute(
        "SELECT url FROM raw.news_crawl WHERE url = ANY(%s) AND status = 'done'", (urls,)
    ).fetchall()
    return {r[0] for r in rows}


def load_all(conn, client: Client) -> int:
    """Đọc mọi feed, lấy toàn văn các bài chưa có."""
    total = 0
    for source, urls in FEEDS.items():
        items: dict[str, dict] = {}
        for feed_url in urls:
            for item in read_feed(client, feed_url):
                items.setdefault(item["url"], item)
        have = known_urls(conn, list(items))
        todo = [i for u, i in items.items() if u not in have]
        log.info("rss %s: %d bài trong feed, %d bài mới", source, len(items), len(todo))
        for item in todo:
            status, body = client.get(item["url"])
            if status != 200:
                log.warning("rss %s: HTTP %s %s", source, status, item["url"][:100])
                continue
            parsed = news.parse_article(body)
            parsed["title"] = parsed["title"] or item["title"]
            parsed["summary"] = parsed["summary"] or item["summary"]
            news.upsert_articles(
                conn,
                [
                    news.article_row(
                        item["url"], source, parsed, item["published_at"], list_ref="rss"
                    )
                ],
            )
            total += 1
    return total
