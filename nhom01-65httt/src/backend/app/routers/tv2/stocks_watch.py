"""Chi tiết mã, theo dõi, cảnh báo, chatbot (module TV2). Phần tra cứu mã đọc dữ liệu thật từ dw."""

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.deps import InvestorUser, Pagination
from app.core.dw import default_range
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import DISCLAIMER, Page, StubFlag

router = APIRouter(tags=["TV2: Mã, theo dõi, cảnh báo, chatbot"])
EntityType = Literal["STOCK", "SECTOR"]


# ---------------- Tra cứu mã ----------------
class StockSummary(BaseModel):
    symbol: str
    name_vi: str | None
    exchange: str | None
    icb_l2_code: str | None
    icb_l2_name_vi: str | None


class StockDetail(StockSummary):
    icb_l4_name: str | None
    market_cap_bn: float | None
    cap_group: str | None
    is_vn30: bool | None
    cluster_label: str | None = Field(
        default=None, description="Nhãn cụm hành vi (có sau khi chạy mô hình phân cụm)"
    )
    listing_date: date | None


@router.get("/api/stocks", response_model=Page[StockSummary])
def search_stocks(
    user: InvestorUser,
    p: Pagination,
    query: Annotated[str | None, Query(description="Một phần mã hoặc tên")] = None,
    exchange: Literal["HOSE", "HNX", "UPCOM"] | None = None,
    sector: Annotated[str | None, Query(description="Mã ICB cấp 2")] = None,
):
    conds, params = ["d.security_type = 'STOCK'"], {"n": p.page_size, "o": p.offset}
    if query:
        conds.append("(d.symbol ILIKE :q OR d.name_vi ILIKE :q2)")
        params.update(q=f"{query}%", q2=f"%{query}%")
    if exchange:
        conds.append("d.exchange = :ex")
        params["ex"] = exchange
    if sector:
        conds.append("s.icb_l2_code = :sec")
        params["sec"] = sector
    where = " AND ".join(conds)
    base = "FROM dw.dim_stock d LEFT JOIN dw.dim_sector s USING (sector_key) WHERE " + where
    with get_engine().connect() as conn:
        total = conn.execute(text(f"SELECT count(*) {base}"), params).scalar_one()
        rows = conn.execute(
            text(
                "SELECT d.symbol, d.name_vi, d.exchange, s.icb_l2_code, s.icb_l2_name_vi "
                f"{base} ORDER BY d.symbol LIMIT :n OFFSET :o"
            ),
            params,
        ).all()
    return Page[StockSummary](
        items=[StockSummary(**r._mapping) for r in rows],
        page=p.page,
        page_size=p.page_size,
        total=total,
    )


@router.get("/api/stocks/{symbol}", response_model=StockDetail)
def stock_detail(symbol: str, user: InvestorUser):
    with get_engine().connect() as conn:
        r = conn.execute(
            text(
                "SELECT d.symbol, d.name_vi, d.exchange, s.icb_l2_code, s.icb_l2_name_vi, s.icb_l4_name, d.market_cap_bn, "
                "d.cap_group, d.is_vn30, d.cluster_label, d.listing_date "
                "FROM dw.dim_stock d LEFT JOIN dw.dim_sector s USING (sector_key) "
                "WHERE d.symbol = :s AND d.security_type = 'STOCK'"
            ),
            {"s": symbol.upper()},
        ).first()
    if r is None:
        raise ApiError(404, "not_found", f"Không có mã {symbol.upper()}")
    return StockDetail(**r._mapping)


class PricePoint(BaseModel):
    date: date
    open_vnd: float | None
    high_vnd: float | None
    low_vnd: float | None
    close_vnd: float | None
    pct_change: float | None
    total_value_bn: float | None


class PriceSeries(BaseModel):
    symbol: str
    items: list[PricePoint]


@router.get("/api/stocks/{symbol}/prices", response_model=PriceSeries)
def stock_prices(
    symbol: str,
    user: InvestorUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    """Lịch sử giá (đồng). Mặc định 90 ngày gần nhất."""
    sym = symbol.upper()
    with get_engine().connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM dw.dim_stock WHERE symbol = :s"), {"s": sym}
        ).first()
        if not exists:
            raise ApiError(404, "not_found", f"Không có mã {sym}")
        d1, d2 = default_range(conn, date_from, date_to)
        rows = conn.execute(
            text(
                "SELECT p.trade_date AS date, p.open_price * 1000 AS open_vnd, p.high_price * 1000 AS high_vnd, "
                "p.low_price * 1000 AS low_vnd, p.close_price * 1000 AS close_vnd, p.pct_change, p.total_value_bn "
                "FROM dw.fact_daily_price p JOIN dw.dim_stock d USING (stock_key) "
                "WHERE d.symbol = :s AND p.has_trading AND p.trade_date BETWEEN :d1 AND :d2 ORDER BY p.trade_date"
            ),
            {"s": sym, "d1": d1, "d2": d2},
        ).all()
    return PriceSeries(symbol=sym, items=[PricePoint(**r._mapping) for r in rows])


class FlowPoint(BaseModel):
    date: date
    investor_type: str
    buy_bn: float
    sell_bn: float
    net_bn: float


class FlowSeries(BaseModel):
    symbol: str
    items: list[FlowPoint]


@router.get("/api/stocks/{symbol}/flow", response_model=FlowSeries)
def stock_flow(
    symbol: str,
    user: InvestorUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    investor_type: Literal["FOREIGN", "PROP", "OTHER_DOMESTIC"] | None = None,
):
    sym = symbol.upper()
    with get_engine().connect() as conn:
        if not conn.execute(
            text("SELECT 1 FROM dw.dim_stock WHERE symbol = :s"), {"s": sym}
        ).first():
            raise ApiError(404, "not_found", f"Không có mã {sym}")
        d1, d2 = default_range(conn, date_from, date_to)
        rows = conn.execute(
            text(
                "SELECT trade_date AS date, investor_type, buy_value_bn AS buy_bn, sell_value_bn AS sell_bn, "
                "net_value_bn AS net_bn FROM dw.ds_stock_flow_daily "
                "WHERE symbol = :s AND trade_date BETWEEN :d1 AND :d2 AND (CAST(:it AS text) IS NULL OR investor_type = :it) "
                "ORDER BY trade_date, investor_type"
            ),
            {"s": sym, "d1": d1, "d2": d2, "it": investor_type},
        ).all()
    return FlowSeries(symbol=sym, items=[FlowPoint(**r._mapping) for r in rows])


# ---------------- Danh sách theo dõi ----------------
class WatchItem(BaseModel):
    id: int
    entity_type: EntityType
    entity_code: str
    created_at: datetime


class WatchAdd(BaseModel):
    entity_type: EntityType
    entity_code: str = Field(min_length=1, max_length=20)


def _entity_exists(conn, entity_type: str, code: str) -> bool:
    if entity_type == "STOCK":
        sql = "SELECT 1 FROM dw.dim_stock WHERE symbol = :c AND security_type = 'STOCK'"
    else:
        sql = "SELECT 1 FROM dw.dim_sector WHERE icb_l2_code = :c LIMIT 1"
    return conn.execute(text(sql), {"c": code}).first() is not None


@router.get("/api/watchlist", response_model=list[WatchItem])
def get_watchlist(user: InvestorUser):
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, entity_type, entity_code, created_at FROM app.watchlist WHERE user_id = :u "
                "ORDER BY created_at DESC, id DESC"
            ),
            {"u": user.id},
        ).all()
    return [WatchItem(**r._mapping) for r in rows]


@router.post("/api/watchlist", response_model=WatchItem, status_code=201)
def add_watchlist(body: WatchAdd, user: InvestorUser):
    code = body.entity_code.upper() if body.entity_type == "STOCK" else body.entity_code
    with get_engine().begin() as conn:
        if not _entity_exists(conn, body.entity_type, code):
            raise ApiError(404, "not_found", "Không có mã hoặc ngành này")
        try:
            row = conn.execute(
                text(
                    "INSERT INTO app.watchlist (user_id, entity_type, entity_code) VALUES (:u, :t, :c) "
                    "RETURNING id, entity_type, entity_code, created_at"
                ),
                {"u": user.id, "t": body.entity_type, "c": code},
            ).one()
        except IntegrityError as exc:
            raise ApiError(409, "already_watching", "Đã có trong danh sách theo dõi") from exc
    return WatchItem(**row._mapping)


@router.delete("/api/watchlist/{item_id}", status_code=204)
def delete_watchlist(item_id: int, user: InvestorUser):
    with get_engine().begin() as conn:
        n = conn.execute(
            text("DELETE FROM app.watchlist WHERE id = :i AND user_id = :u"),
            {"i": item_id, "u": user.id},
        ).rowcount
    if not n:
        raise ApiError(404, "not_found", "Không có mục này trong danh sách theo dõi")
    return Response(status_code=204)


# ---------------- Đăng ký cảnh báo email ----------------
class AlertSubscribe(BaseModel):
    entity_type: EntityType
    entity_code: str = Field(min_length=1, max_length=20)
    alert_type: Literal["flow_reversal", "negative_news", "weekly_digest"]


class AlertSubscription(BaseModel):
    id: int
    entity_type: EntityType
    entity_code: str
    alert_type: str
    channel: str
    is_active: bool


@router.post("/api/alerts/subscriptions", response_model=AlertSubscription, status_code=201)
def subscribe_alert(body: AlertSubscribe, user: InvestorUser):
    code = body.entity_code.upper() if body.entity_type == "STOCK" else body.entity_code
    with get_engine().begin() as conn:
        if not _entity_exists(conn, body.entity_type, code):
            raise ApiError(404, "not_found", "Không có mã hoặc ngành này")
        try:
            row = conn.execute(
                text(
                    "INSERT INTO app.alert_subscriptions (user_id, entity_type, entity_code, alert_type) "
                    "VALUES (:u, :t, :c, :a) RETURNING id, entity_type, entity_code, alert_type, channel, is_active"
                ),
                {"u": user.id, "t": body.entity_type, "c": code, "a": body.alert_type},
            ).one()
        except IntegrityError as exc:
            raise ApiError(409, "already_subscribed", "Đã đăng ký cảnh báo này") from exc
    return AlertSubscription(**row._mapping)


@router.delete("/api/alerts/subscriptions/{sub_id}", status_code=204)
def unsubscribe_alert(sub_id: int, user: InvestorUser):
    with get_engine().begin() as conn:
        n = conn.execute(
            text("DELETE FROM app.alert_subscriptions WHERE id = :i AND user_id = :u"),
            {"i": sub_id, "u": user.id},
        ).rowcount
    if not n:
        raise ApiError(404, "not_found", "Không có đăng ký cảnh báo này")
    return Response(status_code=204)


# ---------------- Chatbot (stub) ----------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatSource(BaseModel):
    title: str
    url: str | None = None


class ChatResponse(StubFlag):
    answer: str
    sources: list[ChatSource]
    disclaimer: str = DISCLAIMER


@router.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: InvestorUser):
    """STUB: chatbot LLM + RAG do TV2 hoàn thiện; schema đã chốt."""
    return ChatResponse(
        stub=True,
        answer="Chatbot chưa được kích hoạt. Đây là câu trả lời mẫu đúng định dạng.",
        sources=[ChatSource(title="Mẫu nguồn", url=None)],
    )
