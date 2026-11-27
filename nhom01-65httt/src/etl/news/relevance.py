"""Lọc bài liên quan chứng khoán/tài chính khỏi tin kinh tế chung (quy tắc từ khóa, chạy nhanh trên 300 nghìn bài)."""

import re
from dataclasses import dataclass

# Từ khóa mạnh: chỉ cần xuất hiện là bài nói về thị trường chứng khoán
STRONG = [
    "chứng khoán", "cổ phiếu", "vn-index", "vnindex", "vn index", "vn30", "khối ngoại", "tự doanh",
    "thanh khoản", "hose", "hnx", "upcom", "cổ tức", "niêm yết", "margin", "room ngoại",
    "phát hành cổ phiếu", "chào bán cổ phiếu", "cổ đông", "etf", "quỹ đầu tư",
]  # fmt: skip
# Từ khóa yếu: cần xuất hiện nhiều
WEAK = [
    "ngân hàng", "lãi suất", "tỷ giá", "bất động sản", "tín dụng", "lạm phát", "trái phiếu",
    "vốn hóa", "xuất khẩu", "fed", "đầu tư công", "gdp",
]  # fmt: skip
STRONG_CATEGORY = (
    "chứng khoán",
    "thị trường",
)  # chuyên mục về thị trường chứng khoán (cafef, vietnamnet)
WEAK_THRESHOLD = 4

_STRONG_RE = re.compile("|".join(re.escape(k) for k in STRONG))
_WEAK_RE = re.compile("|".join(re.escape(k) for k in WEAK))


@dataclass(frozen=True)
class Relevance:
    is_related: bool
    score: int
    reason: str


def score_article(
    title: str, content: str, category: str | None, n_confident_tickers: int
) -> Relevance:
    text = f"{title}\n{content}".lower()
    strong_hits = len(_STRONG_RE.findall(text))
    weak_hits = len(_WEAK_RE.findall(text))
    category_hit = bool(category) and any(c in category.lower() for c in STRONG_CATEGORY)
    score = 3 * n_confident_tickers + 2 * strong_hits + weak_hits + (5 if category_hit else 0)
    if n_confident_tickers >= 1:
        return Relevance(True, score, "ticker")
    if category_hit:
        return Relevance(True, score, "category")
    if strong_hits >= 1:
        return Relevance(True, score, "strong_keyword")
    if weak_hits >= WEAK_THRESHOLD:
        return Relevance(True, score, "weak_keywords")
    return Relevance(False, score, "none")
