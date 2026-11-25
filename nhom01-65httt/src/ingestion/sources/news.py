"""Tiện ích chung cho tin tức: bóc tiêu đề, nội dung, thời điểm đăng; ghi vào raw.news_crawl."""

import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from ingestion import db

VN_TZ = timezone(timedelta(hours=7))
NEWS_COLUMNS = [
    "url", "source", "list_ref", "published_at", "title", "summary", "content", "category",
    "http_status", "status", "content_chars",
]  # fmt: skip
MIN_PARAGRAPH = 40  # đoạn ngắn hơn (menu, chú thích) bị bỏ


def meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return tag.get("content") if tag and tag.get("content") else None


def parse_article(html: bytes | str, content_selector: str | None = None) -> dict:
    """Trả title, content, category, published_raw (chuỗi meta, nếu có)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    scope = soup.select_one(content_selector) if content_selector else None
    nodes = (scope or soup).find_all("p")
    paragraphs = [p.get_text(" ", strip=True) for p in nodes]
    content = "\n".join(p for p in paragraphs if len(p) >= MIN_PARAGRAPH)
    h1 = soup.find("h1")
    title = meta(soup, "og:title") or (h1.get_text(" ", strip=True) if h1 else None)
    return {
        "title": db.clean_text(title),
        "summary": db.clean_text(meta(soup, "og:description")),
        "content": db.clean_text(content),
        "category": meta(soup, "article:section"),
        "published_raw": meta(soup, "article:published_time"),
    }


def parse_local_time(value: str | None) -> datetime | None:
    """Chuỗi ISO; nếu thiếu múi giờ thì hiểu là GMT+7."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=VN_TZ)


def upsert_articles(conn, rows: list[tuple]) -> int:
    return db.copy_upsert(conn, "raw.news_crawl", NEWS_COLUMNS, rows, ["url"])


def article_row(
    url: str,
    source: str,
    parsed: dict,
    published_at: datetime | None,
    list_ref: str | None = None,
    http_status: int = 200,
) -> tuple:
    content = parsed.get("content") or ""
    status = "done" if content else "failed"
    return (
        url,
        source,
        list_ref,
        published_at,
        parsed.get("title"),
        parsed.get("summary"),
        content or None,
        parsed.get("category"),
        http_status,
        status,
        len(content),
    )


CAFEF_ID = re.compile(r"-188(\d{12})\d*\.chn$")


def cafef_published_from_url(url: str) -> datetime | None:
    """Mã bài CafeF: `188` + YYMMDDHHMMSS + 3 chữ số; thời điểm theo GMT+7."""
    m = CAFEF_ID.search(url)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%y%m%d%H%M%S").replace(tzinfo=VN_TZ)
    except ValueError:
        return None
