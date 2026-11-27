"""Kiểm chứng các nguồn tin tức cập nhật: RSS, trang chuyên mục, toàn văn bài, robots.txt (N2).

Chạy:  python src/ingestion/probes/probe_news.py [--out ket_qua.json]
Cần:   pip install feedparser beautifulsoup4
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import feedparser
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from common import USER_AGENT, http_get, polite_sleep  # noqa: E402

RSS_FEEDS = {
    "vneconomy_chung_khoan": "https://vneconomy.vn/chung-khoan.rss",
    "vietstock_co_phieu": "https://vietstock.vn/830/chung-khoan/co-phieu.rss",
    "vietstock_chung_khoan": "https://vietstock.vn/144/chung-khoan.rss",
    "vnexpress_kinh_doanh": "https://vnexpress.net/rss/kinh-doanh.rss",
}
LISTING_PAGES = {
    "cafef_chung_khoan_p1": "https://cafef.vn/chung-khoan.chn",
    "cafef_chung_khoan_p2": "https://cafef.vn/chung-khoan/trang-2.chn",
    "cafef_chung_khoan_p2_html": "https://cafef.vn/chung-khoan/trang-2.html",
    "tnck_home": "https://tinnhanhchungkhoan.vn/",
}
ROBOTS = [
    "https://cafef.vn/robots.txt",
    "https://vneconomy.vn/robots.txt",
    "https://vietstock.vn/robots.txt",
    "https://vnexpress.net/robots.txt",
    "https://tinnhanhchungkhoan.vn/robots.txt",
    "https://nso.gov.vn/robots.txt",
]


def probe_rss(name: str, url: str) -> dict:
    status, body = http_get(url)
    polite_sleep()
    out = {"url": url, "status": status}
    if status != 200:
        return out
    feed = feedparser.parse(body)
    entries = feed.entries
    out["items"] = len(entries)
    if entries:
        first = entries[0]
        out["fields"] = sorted(first.keys())
        out["newest"] = first.get("published", "")
        out["oldest"] = entries[-1].get("published", "")
        out["sample_link"] = first.get("link", "")
        out["sample_title"] = first.get("title", "")
    return out


def article_text(url: str) -> dict:
    status, body = http_get(url)
    polite_sleep()
    if status != 200:
        return {"url": url, "status": status}
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = " ".join(p for p in paragraphs if len(p) > 40)
    return {"url": url, "status": status, "paragraph_chars": len(text), "html_bytes": len(body)}


def probe_listing(name: str, url: str) -> dict:
    status, body = http_get(url)
    polite_sleep()
    out = {"url": url, "status": status, "bytes": len(body)}
    if status == 200:
        host = urlparse(url).netloc
        links = set(re.findall(r'href="(/[^"#?]+\.(?:chn|html))"', body.decode("utf-8", "replace")))
        out["article_like_links"] = len(links)
        out["sample_links"] = sorted(links)[:3]
        out["host"] = host
    return out


def probe_robots(url: str) -> dict:
    status, body = http_get(url)
    polite_sleep()
    text = body.decode("utf-8", "replace") if status == 200 else ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    return {"status": status, "lines": lines[:25]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="news_probe_result.json")
    args = parser.parse_args()
    result: dict = {"user_agent": USER_AGENT, "rss": {}, "listing": {}, "article": {}, "robots": {}}

    for name, url in RSS_FEEDS.items():
        result["rss"][name] = probe_rss(name, url)
        print(
            "RSS", name, {k: v for k, v in result["rss"][name].items() if k != "fields"}, flush=True
        )
        link = result["rss"][name].get("sample_link")
        if link:
            result["article"][name] = article_text(link)
            print("  ARTICLE", result["article"][name], flush=True)

    for name, url in LISTING_PAGES.items():
        result["listing"][name] = probe_listing(name, url)
        print("LISTING", name, result["listing"][name], flush=True)

    for url in ROBOTS:
        result["robots"][url] = probe_robots(url)
        print("ROBOTS", url, result["robots"][url]["status"], flush=True)

    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
