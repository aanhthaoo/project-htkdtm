"""Tin tức và vĩ mô (module TV5). Danh sách tin và chuỗi vĩ mô đọc dữ liệu thật từ dw; cảm xúc có sau N8."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.core.deps import InvestorUser, OptionalUser, Pagination
from app.core.dw import default_range
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import DISCLAIMER, Page, StubFlag

router = APIRouter(tags=["TV5: Tin tức và vĩ mô"])

# Cảm xúc của bài (mức bài, cùng điểm cho mọi mã/ngành) từ mô hình cảm xúc mới nhất; NULL nếu bài chưa được chấm
SENTIMENT_JOIN = (
    "LEFT JOIN LATERAL (SELECT sentiment_label, sentiment_score FROM dw.fact_news_sentiment f "
    "WHERE f.article_key = a.article_key LIMIT 1) ss ON true"
)
GUEST_NEWS_LIMIT = 5  # khách chỉ xem tối đa ngần này tin, không phân trang


class NewsItem(BaseModel):
    title: str
    source: str
    published_at: datetime | None
    session_date: date
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    url: str


def _news_row(r) -> NewsItem:
    return NewsItem(
        title=r.title,
        source=r.publisher,
        published_at=r.published_at,
        session_date=r.session_date,
        sentiment_label=r.sentiment_label,
        sentiment_score=r.sentiment_score,
        url=r.url,
    )


@router.get("/api/news", response_model=Page[NewsItem])
def news(
    user: OptionalUser,
    p: Pagination,
    symbol: str | None = None,
    sector: Annotated[str | None, Query(description="Mã ICB cấp 2")] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    """Tin liên quan chứng khoán (đã loại trùng): tiêu đề, nguồn, đường dẫn bài gốc, không trả toàn văn.
    Khách chỉ xem tối đa 5 tin mới nhất; nhà đầu tư xem đầy đủ và phân trang."""
    page, size = (1, min(p.page_size, GUEST_NEWS_LIMIT)) if user is None else (p.page, p.page_size)
    conds = ["a.is_market_related", "NOT a.is_duplicate", "a.session_date IS NOT NULL"]
    params: dict = {}
    if symbol:
        conds.append(
            "EXISTS (SELECT 1 FROM dw.bridge_article_entity b JOIN dw.dim_stock d USING (stock_key) "
            "WHERE b.article_key = a.article_key AND b.entity_type = 'STOCK' AND d.symbol = :sym)"
        )
        params["sym"] = symbol.upper()
    if sector:
        conds.append(
            "EXISTS (SELECT 1 FROM dw.bridge_article_entity b WHERE b.article_key = a.article_key "
            "AND b.entity_type = 'SECTOR' AND b.entity_code = :sec)"
        )
        params["sec"] = sector
    if date_from:
        conds.append("a.session_date >= :d1")
        params["d1"] = date_from
    if date_to:
        conds.append("a.session_date <= :d2")
        params["d2"] = date_to
    where = " AND ".join(conds)
    with get_engine().connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM dw.dim_article a WHERE {where}"), params
        ).scalar_one()
        rows = conn.execute(
            text(
                "SELECT a.title, a.publisher, a.published_at, a.session_date, a.url, ss.sentiment_label, ss.sentiment_score "
                f"FROM dw.dim_article a {SENTIMENT_JOIN} WHERE {where} ORDER BY a.session_date DESC, a.published_at DESC NULLS LAST, a.article_key "
                "LIMIT :n OFFSET :o"
            ),
            {**params, "n": size, "o": (page - 1) * size},
        ).all()
    return Page[NewsItem](
        items=[_news_row(r) for r in rows], page=page, page_size=size, total=total
    )


class Highlights(BaseModel):
    items: list[NewsItem]
    disclaimer: str = DISCLAIMER


@router.get("/api/news/highlights", response_model=Highlights)
def news_highlights(user: OptionalUser):
    """Tin nổi bật: bài gần đây nhắc nhiều mã nhất (khách xem được)."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.title, a.publisher, a.published_at, a.session_date, a.url, ss.sentiment_label, ss.sentiment_score "
                f"FROM dw.dim_article a {SENTIMENT_JOIN} "
                "WHERE a.is_market_related AND NOT a.is_duplicate AND a.session_date IS NOT NULL "
                "AND a.session_date >= (SELECT max(session_date) - 3 FROM dw.dim_article WHERE NOT is_duplicate) "
                "ORDER BY a.n_stock_mentions DESC, a.session_date DESC, a.article_key LIMIT :n"
            ),
            {"n": GUEST_NEWS_LIMIT},
        ).all()
    return Highlights(items=[_news_row(r) for r in rows])


# ---------------- Vĩ mô ----------------
class MacroPoint(BaseModel):
    date: date
    value: float | None
    pct_change_prev: float | None


class MacroSeries(BaseModel):
    code: str
    name_vi: str
    unit: str | None
    points: list[MacroPoint]


class MacroResponse(BaseModel):
    series: list[MacroSeries]


@router.get("/api/macro/series", response_model=MacroResponse)
def macro_series(
    user: InvestorUser,
    codes: Annotated[str, Query(description="Mã chỉ số cách nhau bằng dấu phẩy, ví dụ USDVND,DXY")],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise ApiError(422, "validation_error", "Cần ít nhất một mã chỉ số")
    with get_engine().connect() as conn:
        d1, d2 = default_range(conn, date_from, date_to, days=365)
        rows = conn.execute(
            text(
                "SELECT indicator_code, indicator_name, unit, trade_date, value, pct_change_prev FROM dw.ds_macro_daily "
                "WHERE indicator_code = ANY(:codes) AND trade_date BETWEEN :d1 AND :d2 ORDER BY indicator_code, trade_date"
            ),
            {"codes": wanted, "d1": d1, "d2": d2},
        ).all()
    unknown = set(wanted) - {r.indicator_code for r in rows}
    if unknown:
        with get_engine().connect() as conn:
            known = set(conn.execute(text("SELECT code FROM dw.dim_indicator")).scalars())
        bad = sorted(unknown - known)
        if bad:
            raise ApiError(404, "not_found", f"Không có chỉ số: {', '.join(bad)}")
    series: dict[str, MacroSeries] = {}
    for r in rows:
        s = series.setdefault(
            r.indicator_code,
            MacroSeries(code=r.indicator_code, name_vi=r.indicator_name, unit=r.unit, points=[]),
        )
        s.points.append(
            MacroPoint(date=r.trade_date, value=r.value, pct_change_prev=r.pct_change_prev)
        )
    return MacroResponse(series=list(series.values()))


class CorrelationItem(BaseModel):
    code: str
    correlation: float
    window: int


class Correlation(StubFlag):
    against: str
    items: list[CorrelationItem]
    disclaimer: str = DISCLAIMER


@router.get("/api/macro/correlation", response_model=Correlation)
def macro_correlation(
    user: InvestorUser,
    codes: str = "USDVND,DXY",
    against: str = "foreign_net",
    window: Annotated[int, Query(ge=5, le=250)] = 60,
):
    """STUB: tương quan cuốn chiếu giữa chỉ số vĩ mô và dòng tiền khối ngoại. TV5 hoàn thiện; schema đã chốt."""
    return Correlation(
        stub=True,
        against=against,
        items=[
            CorrelationItem(code=c.strip().upper(), correlation=0.0, window=window)
            for c in codes.split(",")
            if c.strip()
        ],
    )
