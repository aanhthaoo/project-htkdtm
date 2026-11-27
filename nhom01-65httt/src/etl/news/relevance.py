"""Lọc bài liên quan chứng khoán/tài chính khỏi tin kinh tế chung (quy tắc từ khóa, chạy nhanh trên 300 nghìn bài).

Đã chỉnh theo 100 bài gán nhãn thủ công (36% kết luận sai ở bản đầu):
- Chuyên mục "Thị trường" của CafeF/Vietnamnet rất rộng (xe, hàng tiêu dùng, Grab...), không còn tính là tín hiệu;
  chỉ chuyên mục có chữ "chứng khoán" mới tính.
- Từ khóa mạnh đơn lẻ (vd "cổ phiếu" trong tin nước ngoài) không đủ: cần từ 2 lần.
- Từ khóa yếu cần nhiều hơn (PR ngân hàng, bài bất động sản chung bị lọt).
- Thêm nhóm từ khóa vĩ mô/ngành có ảnh hưởng thị trường (giá xăng, khu công nghiệp, chính sách thuế) cần từ 2 lần.
"""

import re
from dataclasses import dataclass

# Từ khóa mạnh: xuất hiện từ STRONG_MIN lần thì bài nói về thị trường chứng khoán
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
# Vĩ mô/ngành tác động tới doanh nghiệp niêm yết
MACRO = [
    "giá xăng", "giá dầu", "khu công nghiệp", "gói hỗ trợ", "giảm thuế", "miễn thuế", "lãi suất điều hành",
    "chính sách tiền tệ", "thuế, phí", "thuế phí",
]  # fmt: skip
STRONG_CATEGORY = ("chứng khoán",)  # chuyên mục về thị trường chứng khoán
STRONG_MIN = 2
WEAK_THRESHOLD = 8
MACRO_MIN = 2

_STRONG_RE = re.compile("|".join(re.escape(k) for k in STRONG))
_WEAK_RE = re.compile("|".join(re.escape(k) for k in WEAK))
_MACRO_RE = re.compile("|".join(re.escape(k) for k in MACRO))


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
    macro_hits = len(_MACRO_RE.findall(text))
    category_hit = bool(category) and any(c in category.lower() for c in STRONG_CATEGORY)
    score = (
        3 * n_confident_tickers
        + 2 * strong_hits
        + weak_hits
        + macro_hits
        + (5 if category_hit else 0)
    )
    if n_confident_tickers >= 1:
        return Relevance(True, score, "ticker")
    if category_hit:
        return Relevance(True, score, "category")
    if strong_hits >= STRONG_MIN:
        return Relevance(True, score, "strong_keyword")
    if macro_hits >= MACRO_MIN:
        return Relevance(True, score, "macro_keywords")
    if weak_hits >= WEAK_THRESHOLD:
        return Relevance(True, score, "weak_keywords")
    return Relevance(False, score, "none")
