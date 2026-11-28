"""Tin tức và vĩ mô (module TV5). Danh sách tin và chuỗi vĩ mô đọc dữ liệu thật từ dw; cảm xúc có sau N8."""

from datetime import date, datetime
from math import isfinite
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import bindparam, text

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
    published_date: date | None = None


class MacroSeries(BaseModel):
    code: str
    name_vi: str
    unit: str | None
    points: list[MacroPoint]


class MacroResponse(BaseModel):
    series: list[MacroSeries]


@router.get("/api/macro/series", response_model=MacroResponse, response_model_exclude_unset=True)
def macro_series(
    user: InvestorUser,
    codes: Annotated[str, Query(description="Mã chỉ số cách nhau bằng dấu phẩy, ví dụ USDVND,DXY")],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    frequency: Literal["daily", "monthly"] = "daily",
):
    """Lọc theo ngày của kỳ quan sát. Chuỗi tháng trả thêm ngày công bố của từng kỳ."""
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise ApiError(422, "validation_error", "Cần ít nhất một mã chỉ số")
    if frequency == "monthly":
        query = text("""
            SELECT i.code AS indicator_code, i.name_vi AS indicator_name, i.unit,
                   m.trade_date, m.value, m.pct_change_prev,
                   to_date(CAST(m.published_date_key AS text), 'YYYYMMDD') AS published_date
            FROM dw.fact_macro_indicator m
            JOIN dw.dim_indicator i ON i.indicator_key = m.indicator_key
            WHERE i.frequency = 'monthly' AND m.source = 'manual_csv'
              AND i.code = ANY(:codes) AND m.trade_date BETWEEN :d1 AND :d2
            ORDER BY i.code, m.trade_date
        """)
    else:
        query = text(
            "SELECT indicator_code, indicator_name, unit, trade_date, value, pct_change_prev FROM dw.ds_macro_daily "
            "WHERE indicator_code = ANY(:codes) AND trade_date BETWEEN :d1 AND :d2 ORDER BY indicator_code, trade_date"
        )
    with get_engine().connect() as conn:
        d1, d2 = default_range(conn, date_from, date_to, days=365)
        rows = conn.execute(query, {"codes": wanted, "d1": d1, "d2": d2}).all()
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
        point = MacroPoint(date=r.trade_date, value=r.value, pct_change_prev=r.pct_change_prev)
        if frequency == "monthly":
            point.published_date = r.published_date
        s.points.append(point)
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
    against: Literal["foreign_net"] = "foreign_net",
    window: Annotated[int, Query(ge=5, le=250)] = 60,
):
    """Tương quan Pearson trên các cặp cùng ngày trong cửa sổ phiên gần nhất.

    Bỏ qua chỉ số nếu thiếu cặp dữ liệu hoặc hệ số không xác định.
    """
    wanted = list(dict.fromkeys(c.strip().upper() for c in codes.split(",") if c.strip()))
    if not wanted:
        raise ApiError(422, "validation_error", "Cần ít nhất một mã chỉ số")
    query = text("""
        WITH sessions AS (
            SELECT trade_date, foreign_net_bn
            FROM dw.mv_market_daily_kpi
            ORDER BY trade_date DESC
            LIMIT :window_size
        )
        SELECT m.indicator_code, corr(m.pct_change_prev, s.foreign_net_bn) AS coefficient
        FROM sessions s
        JOIN dw.ds_macro_daily m ON m.trade_date = s.trade_date
        WHERE m.indicator_code IN :codes
          AND m.pct_change_prev IS NOT NULL AND s.foreign_net_bn IS NOT NULL
        GROUP BY m.indicator_code
    """).bindparams(bindparam("codes", expanding=True))
    with get_engine().connect() as conn:
        catalog = text("SELECT code, frequency FROM dw.dim_indicator WHERE code IN :codes").bindparams(
            bindparam("codes", expanding=True)
        )
        frequencies = dict(conn.execute(catalog, {"codes": wanted}).tuples().all())
        unknown = [code for code in wanted if code not in frequencies]
        if unknown:
            raise ApiError(404, "not_found", f"Không có chỉ số: {', '.join(unknown)}")
        non_daily = [code for code in wanted if frequencies[code] != "daily"]
        if non_daily:
            raise ApiError(422, "validation_error", f"Cần chỉ số theo ngày: {', '.join(non_daily)}")
        rows = conn.execute(query, {"codes": wanted, "window_size": window})
        coefficients = {
            row.indicator_code: row.coefficient
            for row in rows
            if row.coefficient is not None and isfinite(row.coefficient)
        }
    return Correlation(
        stub=False,
        against=against,
        items=[
            CorrelationItem(code=code, correlation=coefficients[code], window=window)
            for code in wanted if code in coefficients
        ],
        disclaimer=(
            "Tương quan không thể hiện quan hệ nhân quả. Chỉ số quốc tế có thể đóng cửa "
            "sau thị trường Việt Nam. " + DISCLAIMER
        ),
    )
