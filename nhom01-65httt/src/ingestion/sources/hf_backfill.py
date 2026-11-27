"""EconVNNews (Hugging Face): tải 4 tệp JSON lớn và nạp theo luồng vào raw.news_backfill."""

import logging
import urllib.request
from datetime import date, datetime
from pathlib import Path

from ingestion import db
from ingestion.client import USER_AGENT

log = logging.getLogger(__name__)

REPO = "khoalnd/EconVNNews"
FILES = [
    "cafebizcrawler_articles_2020-09-01_2024-09-30.json",
    "vietnamnetcrawler_articles_2020-09-01_2024-09-30.json",
    "vnexpresscrawler_articles_2020-09-01_2024-09-30_clean.json",
    "cafefcrawler_articles_2020-09-01_2024-09-30.json",
]
URL = f"https://huggingface.co/datasets/{REPO}/resolve/main/{{name}}"
DATA_DIR = db.ROOT / "data" / "hf"
COLUMNS = [
    "url", "source", "source_file", "title", "content", "published_date", "author", "category",
]  # fmt: skip
BATCH = 2000


def remote_size(name: str) -> int:
    """Kích thước tệp: HEAD bị từ chối nên hỏi 1 byte đầu và đọc Content-Range."""
    req = urllib.request.Request(
        URL.format(name=name), headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        content_range = resp.headers.get("Content-Range", "")  # bytes 0-0/TOTAL
    return int(content_range.rsplit("/", 1)[1])


def download(name: str) -> Path:
    """Tải tệp (có thể tiếp tục nếu bị ngắt); trả đường dẫn."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / name
    part = dest.with_suffix(dest.suffix + ".part")
    size = remote_size(name)
    if dest.exists() and dest.stat().st_size == size:
        log.info("hf: %s đã có đủ (%d byte)", name, size)
        return dest
    have = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(URL.format(name=name), headers=headers)
    log.info("hf: tải %s (%d/%d byte)", name, have, size)
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "ab") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    part.rename(dest)
    return dest


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def record_row(name: str, rec: dict) -> tuple | None:
    url = rec.get("url")
    if not url:
        return None
    return (
        db.clean_text(url),
        rec.get("source"),
        name,
        db.clean_text(rec.get("title")),
        db.clean_text(rec.get("content")),
        parse_date(rec.get("published_date")),
        db.clean_text(rec.get("author")),
        db.clean_text(rec.get("category")),
    )


def load_file(conn, path: Path) -> int:
    """Đọc mảng JSON theo luồng, nạp từng lô."""
    import ijson

    name = path.name
    total = 0
    batch: list[tuple] = []
    with open(path, "rb") as fh:
        for rec in ijson.items(fh, "item"):
            row = record_row(name, rec)
            if row:
                batch.append(row)
            if len(batch) >= BATCH:
                total += db.copy_upsert(conn, "raw.news_backfill", COLUMNS, batch, ["url"])
                batch = []
                if total % 50000 < BATCH:
                    log.info("hf %s: %d bài", name, total)
    total += db.copy_upsert(conn, "raw.news_backfill", COLUMNS, batch, ["url"])
    db.mark_run(conn, "hf_econvnnews", "load", name, "done", rows_loaded=total)
    log.info("hf %s: xong %d bài", name, total)
    return total
