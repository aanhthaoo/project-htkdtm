"""Chuẩn hóa văn bản tin tức: làm sạch, khóa nhận diện, khóa chống trùng."""

import hashlib
import html
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

_TAG = re.compile(r"<[^>]+>")
_INLINE_WS = re.compile(r"[ \t ​‌‍﻿]+")
_NON_ALNUM = re.compile(r"[^0-9a-zà-ỹ]+", re.IGNORECASE)

# Dòng rác thường gặp ở cuối hoặc giữa bài (chỉ bỏ khi ngắn, để không mất nội dung thật)
_BOILERPLATE = [
    re.compile(r"^(nguồn|theo)\s*[:：].{0,60}$", re.IGNORECASE),
    re.compile(r"^(xem thêm|đọc thêm|tin liên quan|bài liên quan|bình luận|đăng ký nhận|theo dõi).{0,80}$", re.IGNORECASE),
    re.compile(r"^ảnh\s*[:：].{0,80}$", re.IGNORECASE),
    re.compile(r"^(tags?|từ khóa)\s*[:：].{0,120}$", re.IGNORECASE),
]  # fmt: skip
MIN_LINE = 20  # dòng ngắn hơn (menu, chú thích ảnh) bị bỏ


def clean_text(text: str | None) -> str:
    """Bỏ thẻ HTML còn sót, giải mã ký tự đặc biệt, chuẩn hóa Unicode (NFC) và khoảng trắng, bỏ dòng rác."""
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG.sub(" ", text)
    text = unicodedata.normalize("NFC", text).replace("\x00", "")
    lines = []
    for raw in text.splitlines():
        line = _INLINE_WS.sub(" ", raw).strip()
        if len(line) < MIN_LINE:
            continue
        if any(p.match(line) for p in _BOILERPLATE):
            continue
        lines.append(line)
    return "\n".join(lines)


def clean_title(title: str | None) -> str:
    if not title:
        return ""
    title = unicodedata.normalize("NFC", html.unescape(_TAG.sub(" ", title)))
    return _INLINE_WS.sub(" ", title).strip()


def title_key(title: str | None) -> str:
    """Khóa so khớp tiêu đề: chữ thường, bỏ dấu câu, giữ dấu tiếng Việt."""
    return _NON_ALNUM.sub(" ", clean_title(title).lower()).strip()


def content_hash(text: str, n_chars: int = 1500) -> str:
    """Băm n ký tự chữ-số đầu của nội dung; bài đăng lại giữa các nguồn thường trùng phần đầu."""
    key = _NON_ALNUM.sub("", text.lower())[:n_chars]
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, "", ""))


def article_id(url: str) -> str:
    return hashlib.md5(canonical_url(url).encode("utf-8")).hexdigest()
