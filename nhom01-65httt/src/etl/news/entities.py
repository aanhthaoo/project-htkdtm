"""Nhận diện mã cổ phiếu và ngành được nhắc tới trong bài báo.

Hướng ưu tiên độ chính xác:
- Mã (3 ký tự in hoa) chỉ tính khi có trong danh mục cổ phiếu. Mã trùng từ viết tắt thông dụng (CEO, USD...)
  chỉ tính khi đi kèm ngữ cảnh: "(CEO)", "mã CEO", "cổ phiếu CEO".
- Tên ngắn công ty (Vinamilk, Hòa Phát...) tính cho các mã thuộc nhóm lớn (cấp qua tham số).
- Ngành: từ mã (mã -> ngành ICB cấp 2) và từ khóa ngành.
"""

import re
from dataclasses import dataclass

TICKER = re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{2}(?![A-Za-z0-9])")
PAREN = re.compile(r"\(([A-Z][A-Z0-9]{2})\)")
CONTEXT = re.compile(
    r"(?i:mã cổ phiếu|mã chứng khoán|mã|cổ phiếu|CP)\s+([A-Z][A-Z0-9]{2})(?![A-Za-z0-9])"
)

# Từ viết tắt thông dụng có thể trùng với mã cổ phiếu
COMMON_ACRONYMS = frozenset(
    "CEO CFO CTO COO USD VND EUR JPY GDP CPI PMI IPO ETF FDI VAT FED ECB IMF WTO ESG OPEC ASEAN AI IT PR HR "
    "SME ODA PPP BOT BOO EVN CPTPP TPP FTA UBND HĐQT ĐHCĐ CTCP VCCI".split()
)  # fmt: skip

# Từ khóa ngành -> mã ICB cấp 2 (siêu ngành)
SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "8300": ("ngân hàng", "tín dụng ngân hàng", "nợ xấu"),
    "8600": ("bất động sản", "địa ốc", "nhà ở xã hội", "dự án nhà ở"),
    "8700": ("công ty chứng khoán", "môi giới chứng khoán", "bảo lãnh phát hành"),
    "8500": ("bảo hiểm",),
    "1700": ("thép", "quặng sắt", "tôn mạ", "nhôm", "khai khoáng", "cao su", "giấy"),
    "0500": ("dầu khí", "xăng dầu", "giá dầu", "khí đốt"),
    "1300": ("hóa chất", "phân bón", "nhựa"),
    "2300": ("xi măng", "vật liệu xây dựng", "xây dựng", "đầu tư công", "hạ tầng giao thông"),
    "2700": ("logistics", "cảng biển", "vận tải", "khu công nghiệp", "kho vận"),
    "3500": ("thủy sản", "thực phẩm", "sữa", "đồ uống", "bia", "đường", "nông sản"),
    "3700": ("dệt may", "may mặc", "giày da", "đồ gỗ", "nội thất"),
    "3300": ("ô tô", "xe máy", "phụ tùng ô tô"),
    "4500": ("dược phẩm", "dược", "bệnh viện", "y tế", "thiết bị y tế"),
    "5300": ("bán lẻ", "siêu thị", "chuỗi cửa hàng", "thương mại điện tử"),
    "5500": ("truyền thông", "quảng cáo", "truyền hình"),
    "5700": ("hàng không", "du lịch", "khách sạn", "nhà hàng", "lưu trú"),
    "6500": ("viễn thông", "nhà mạng", "5g"),
    "7500": ("nhiệt điện", "thủy điện", "điện gió", "điện mặt trời", "điện lực", "năng lượng tái tạo", "cấp nước"),
    "9500": ("công nghệ thông tin", "phần mềm", "chuyển đổi số", "trí tuệ nhân tạo", "bán dẫn", "dịch vụ công nghệ"),
}  # fmt: skip
KEYWORD_MIN_IN_CONTENT = (
    2  # từ khóa ngành chỉ tính nếu có trong tiêu đề, hoặc xuất hiện từ ngần này lần trong bài
)


@dataclass(frozen=True)
class Mention:
    entity_type: str  # STOCK | SECTOR
    entity_code: str  # mã cổ phiếu hoặc mã ICB cấp 2
    n: int
    in_title: bool
    method: str  # ticker | ticker_context | alias | ticker_to_sector | keyword


class Extractor:
    def __init__(
        self,
        symbols: set[str],
        symbol_sector: dict[str, str] | None = None,
        aliases: dict[str, str] | None = None,
    ):
        self.symbols = symbols
        self.symbol_sector = symbol_sector or {}
        self.ambiguous = symbols & COMMON_ACRONYMS
        aliases = aliases or {}
        self.aliases = {a.lower(): s for a, s in aliases.items()}
        self._alias_re = (
            re.compile(
                r"(?<!\w)("
                + "|".join(sorted(map(re.escape, self.aliases), key=len, reverse=True))
                + r")(?!\w)"
            )
            if self.aliases
            else None
        )
        self._kw = {
            code: re.compile("|".join(re.escape(k) for k in kws))
            for code, kws in SECTOR_KEYWORDS.items()
        }

    def _tickers(self, text: str) -> dict[str, tuple[int, bool]]:
        """symbol -> (số lần, có ngữ cảnh rõ). Mã trùng từ viết tắt chỉ tính khi có ngữ cảnh."""
        context = set(PAREN.findall(text)) | set(CONTEXT.findall(text))
        found: dict[str, list[int]] = {}
        for token in TICKER.findall(text):
            if token not in self.symbols:
                continue
            if token in self.ambiguous and token not in context:
                continue
            counts = found.setdefault(token, [0, 0])
            counts[0] += 1
            counts[1] = int(token in context)
        return {s: (c[0], bool(c[1])) for s, c in found.items()}

    def extract(self, title: str, content: str) -> list[Mention]:
        in_title = self._tickers(title)
        in_body = self._tickers(content)
        out: list[Mention] = []
        for symbol in set(in_title) | set(in_body):
            n = in_title.get(symbol, (0, False))[0] + in_body.get(symbol, (0, False))[0]
            ctx = in_title.get(symbol, (0, False))[1] or in_body.get(symbol, (0, False))[1]
            out.append(
                Mention(
                    "STOCK", symbol, n, symbol in in_title, "ticker_context" if ctx else "ticker"
                )
            )
        seen = {m.entity_code for m in out}
        if self._alias_re:
            low_title, low_body = title.lower(), content.lower()
            counts: dict[str, int] = {}
            for name in self._alias_re.findall(f"{low_title}\n{low_body}"):
                counts[self.aliases[name]] = counts.get(self.aliases[name], 0) + 1
            for symbol, n in counts.items():
                if symbol not in seen:
                    in_t = any(a in low_title for a, s in self.aliases.items() if s == symbol)
                    out.append(Mention("STOCK", symbol, n, in_t, "alias"))
        # Ngành suy ra từ mã
        sector_counts: dict[str, int] = {}
        for m in out:
            sector = self.symbol_sector.get(m.entity_code)
            if sector:
                sector_counts[sector] = sector_counts.get(sector, 0) + m.n
        for sector, n in sector_counts.items():
            out.append(Mention("SECTOR", sector, n, False, "ticker_to_sector"))
        # Ngành từ từ khóa
        low_title, low_body = title.lower(), content.lower()
        for code, pattern in self._kw.items():
            n_title = len(pattern.findall(low_title))
            n_body = len(pattern.findall(low_body))
            if n_title >= 1 or n_body >= KEYWORD_MIN_IN_CONTENT:
                out.append(Mention("SECTOR", code, n_title + n_body, n_title >= 1, "keyword"))
        return out

    @staticmethod
    def confident_ticker_count(mentions: list[Mention]) -> int:
        """Số mã được nhắc đủ chắc chắn: có ngữ cảnh, là tên công ty, hoặc xuất hiện ở tiêu đề / từ 2 lần."""
        return sum(
            1
            for m in mentions
            if m.entity_type == "STOCK"
            and (m.method in ("ticker_context", "alias") or m.in_title or m.n >= 2)
        )
