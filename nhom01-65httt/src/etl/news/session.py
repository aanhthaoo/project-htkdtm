"""Gán tin vào phiên giao dịch: tin đăng từ 15h trở đi thuộc phiên kế tiếp.

Quy tắc (giờ GMT+7):
- Biết giờ đăng:
    ngày D là ngày giao dịch và đăng trước 15h  -> phiên D
    ngày D là ngày giao dịch và đăng từ 15h     -> phiên giao dịch kế tiếp sau D
    ngày D không phải ngày giao dịch            -> phiên giao dịch đầu tiên sau D
- Chỉ biết ngày (dữ liệu backfill): phiên giao dịch đầu tiên từ D trở đi (không biết bài đăng trước hay sau 15h
  nên chọn cách không đẩy sang ngày sau).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))
CLOSE_TIME = time(15, 0)


@dataclass(frozen=True)
class Calendar:
    trading_days: frozenset[date]
    session_on_or_after: dict[date, date | None]
    next_trading: dict[date, date | None]

    @classmethod
    def from_rows(cls, rows) -> "Calendar":
        """rows: (date, is_trading_day, session_on_or_after, next_trading_date)"""
        trading, on_or_after, nxt = set(), {}, {}
        for d, is_trading, soa, ntd in rows:
            if is_trading:
                trading.add(d)
            on_or_after[d] = soa
            nxt[d] = ntd
        return cls(frozenset(trading), on_or_after, nxt)


def assign_session(
    published_at: datetime | None, published_date: date | None, time_known: bool, cal: Calendar
):
    """Trả ngày phiên giao dịch (hoặc None nếu chưa xác định được, ví dụ tin mới hơn phiên cuối cùng)."""
    if time_known and published_at is not None:
        local = published_at.astimezone(VN_TZ)
        day = local.date()
        if day in cal.trading_days and local.time() >= CLOSE_TIME:
            return cal.next_trading.get(day)
        return cal.session_on_or_after.get(day)
    if published_date is None:
        return None
    return cal.session_on_or_after.get(published_date)
