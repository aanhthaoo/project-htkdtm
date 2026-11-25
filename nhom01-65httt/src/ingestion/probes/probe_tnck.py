"""Kiểm chứng việc lấy tin từ Tin nhanh Chứng khoán (N2).

Kết quả đã quan sát:
  - RSS `/rss/home.rss` trả 50 bài mới nhất (khoảng 2 ngày), múi giờ +07:00.
  - Trang chuyên mục `?page=N` KHÔNG phân trang (cùng một tập bài với mọi N).
  - Truy cập bài bằng mã số: `/<slug-bất-kỳ>-post<ID>.html` trả đúng bài của ID đó.
    ID tăng dần theo thời gian (250000 ≈ 09/2020, 360000 ≈ 12/2024, 402000 ≈ 11/2026)
    và gồm cả tin ngoài chứng khoán.
  - Thời điểm đăng đọc từ thẻ meta `article:published_time`, chuyên mục từ `article:section`.

Chạy:  python src/ingestion/probes/probe_tnck.py
Cần:   pip install feedparser beautifulsoup4
"""

import re
import sys
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from common import http_get, polite_sleep  # noqa: E402

HOST = "https://www.tinnhanhchungkhoan.vn"
CALIBRATION_IDS = (250000, 300000, 360000, 402000)


def article_meta(post_id: int) -> dict:
    status, body = http_get(f"{HOST}/x-post{post_id}.html")
    polite_sleep(2)
    soup = BeautifulSoup(body, "html.parser")

    def meta(prop: str) -> str | None:
        tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content") if tag else None

    text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    return {
        "id": post_id,
        "status": status,
        "published": meta("article:published_time"),
        "section": meta("article:section"),
        "title": (meta("og:title") or "")[:70],
        "paragraph_chars": len(text),
    }


def main() -> None:
    status, body = http_get(f"{HOST}/rss/home.rss")
    polite_sleep(2)
    feed = feedparser.parse(body)
    print("RSS", status, "items", len(feed.entries))
    if feed.entries:
        print(
            "  newest",
            feed.entries[0].get("published"),
            "| oldest",
            feed.entries[-1].get("published"),
        )
        match = re.search(r"post(\d+)\.html", feed.entries[0]["link"])
        print("  newest post id", match.group(1) if match else None)
    for post_id in CALIBRATION_IDS:
        print(article_meta(post_id))


if __name__ == "__main__":
    main()
