"""Thị trường, ngành, top mã gom/xả (module TV3). `market/overview` là router mẫu đọc dữ liệu thật từ dw."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.core.deps import InvestorUser, OptionalUser
from app.core.dw import default_range, latest_trade_date
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import DISCLAIMER, StubFlag

router = APIRouter(tags=["TV3: Thị trường và ngành"])

InvestorType = Literal["FOREIGN", "PROP", "OTHER_DOMESTIC"]


# ---------------- GET /api/market/overview (khách xem được) ----------------
class VnIndex(BaseModel):
    close: float | None
    change: float | None
    change_pct: float | None


class Flow(BaseModel):
    buy_bn: float | None
    sell_bn: float | None
    net_bn: float | None


class MarketOverview(BaseModel):
    date: date
    vnindex: VnIndex
    total_value_bn: float | None
    foreign: Flow
    prop: Flow
    disclaimer: str = DISCLAIMER


@router.get("/api/market/overview", response_model=MarketOverview)
def market_overview(user: OptionalUser, on: Annotated[date | None, Query(alias="date")] = None):
    """KPI một phiên (mặc định phiên mới nhất): VN-Index, tổng giá trị giao dịch, dòng tiền khối ngoại và tự doanh."""
    with get_engine().connect() as conn:
        if on is None:
            on = latest_trade_date(conn)
        k = conn.execute(
            text(
                "SELECT k.trade_date, k.vnindex_close, k.vnindex_pct_change, k.stock_value_bn, "
                "(SELECT p.vnindex_close FROM dw.mv_market_daily_kpi p WHERE p.trade_date < k.trade_date "
                " AND p.vnindex_close IS NOT NULL ORDER BY p.trade_date DESC LIMIT 1) AS prev_close "
                "FROM dw.mv_market_daily_kpi k WHERE k.trade_date = (SELECT max(trade_date) FROM dw.mv_market_daily_kpi "
                "WHERE trade_date <= :d)"
            ),
            {"d": on},
        ).first()
        if k is None:
            raise ApiError(404, "not_found", "Không có dữ liệu thị trường cho ngày này")
        flows = {
            r.code: Flow(buy_bn=r.buy, sell_bn=r.sell, net_bn=r.net)
            for r in conn.execute(
                text(
                    "SELECT it.code, sum(f.buy_value_bn) AS buy, sum(f.sell_value_bn) AS sell, sum(f.net_value_bn) AS net "
                    "FROM dw.fact_money_flow f JOIN dw.dim_investor_type it USING (investor_type_key) "
                    "WHERE f.trade_date = :d AND it.code IN ('FOREIGN', 'PROP') GROUP BY it.code"
                ),
                {"d": k.trade_date},
            )
        }
    empty = Flow(buy_bn=None, sell_bn=None, net_bn=None)
    change = (
        round(k.vnindex_close - k.prev_close, 2)
        if k.vnindex_close is not None and k.prev_close
        else None
    )
    return MarketOverview(
        date=k.trade_date,
        vnindex=VnIndex(close=k.vnindex_close, change=change, change_pct=k.vnindex_pct_change),
        total_value_bn=k.stock_value_bn,
        foreign=flows.get("FOREIGN", empty),
        prop=flows.get("PROP", empty),
    )


# ---------------- GET /api/sectors/flow (nhà đầu tư) ----------------
class SectorSeries(BaseModel):
    icb_l2_code: str
    name_vi: str
    net_bn: list[float | None]


class SectorFlow(BaseModel):
    investor_type: str
    granularity: str
    periods: list[date]
    sectors: list[SectorSeries]


@router.get("/api/sectors/flow", response_model=SectorFlow)
def sectors_flow(
    user: InvestorUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Literal["day", "week", "month"] = "week",
    investor_type: InvestorType = "FOREIGN",
):
    """Ma trận dòng tiền ròng ngành ICB cấp 2 × kỳ (tỷ đồng)."""
    trunc = {"day": "trade_date", "week": "week_start_date", "month": "month_start_date"}[
        granularity
    ]
    with get_engine().connect() as conn:
        d1, d2 = default_range(conn, date_from, date_to, days=120)
        rows = conn.execute(
            text(
                f"SELECT {trunc} AS period, icb_l2_code, icb_l2_name_vi, sum(net_value_bn) AS net "
                "FROM dw.ds_flow_daily WHERE investor_type = :it AND trade_date BETWEEN :d1 AND :d2 "
                "GROUP BY 1, 2, 3 ORDER BY 1, 2"
            ),
            {"it": investor_type, "d1": d1, "d2": d2},
        ).all()
    periods = sorted({r.period for r in rows})
    by_sector: dict[str, dict] = {}
    for r in rows:
        s = by_sector.setdefault(r.icb_l2_code, {"name": r.icb_l2_name_vi, "values": {}})
        s["values"][r.period] = round(r.net, 2) if r.net is not None else None
    return SectorFlow(
        investor_type=investor_type,
        granularity=granularity,
        periods=periods,
        sectors=[
            SectorSeries(
                icb_l2_code=c, name_vi=s["name"], net_bn=[s["values"].get(p) for p in periods]
            )
            for c, s in sorted(by_sector.items())
        ],
    )


# ---------------- GET /api/sectors/{icb_l2_code} (stub) ----------------
class TopStock(BaseModel):
    symbol: str
    net_bn: float


class SectorDetail(StubFlag):
    icb_l2_code: str
    name_vi: str
    net_bn_by_week: list[dict]
    sentiment_label: str | None
    top_stocks: list[TopStock]
    disclaimer: str = DISCLAIMER


@router.get("/api/sectors/{icb_l2_code}", response_model=SectorDetail)
def sector_detail(icb_l2_code: str, user: InvestorUser):
    """STUB: chi tiết ngành (dòng tiền, cảm xúc, top mã). TV3 hoàn thiện; schema đã chốt."""
    return SectorDetail(
        stub=True,
        icb_l2_code=icb_l2_code,
        name_vi="Ngân hàng",
        net_bn_by_week=[{"week_start_date": "2026-11-16", "net_bn": 120.4}],
        sentiment_label=None,
        top_stocks=[TopStock(symbol="VCB", net_bn=85.2)],
    )


# ---------------- GET /api/stocks/top-net ----------------
# Lưu ý: đường dẫn này phải được đăng ký trước /api/stocks/{symbol} (xem main.py).
class TopNetItem(BaseModel):
    symbol: str
    name_vi: str | None
    icb_l2_name_vi: str | None
    net_bn: float
    n_days: int


class TopNet(BaseModel):
    side: str
    investor_type: str
    date_from: date
    date_to: date
    items: list[TopNetItem]


@router.get("/api/stocks/top-net", response_model=TopNet)
def top_net(
    user: InvestorUser,
    side: Literal["buy", "sell"] = "buy",
    investor_type: InvestorType = "FOREIGN",
    period: Annotated[int, Query(ge=1, le=250, description="Số phiên gần nhất")] = 5,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """Top mã được gom (buy) hoặc xả (sell) ròng nhiều nhất trong `period` phiên gần nhất."""
    order = "DESC" if side == "buy" else "ASC"
    with get_engine().connect() as conn:
        days = (
            conn.execute(
                text(
                    "SELECT trade_date FROM dw.mv_market_daily_kpi ORDER BY trade_date DESC LIMIT :n"
                ),
                {"n": period},
            )
            .scalars()
            .all()
        )
        if not days:
            raise ApiError(404, "not_found", "Chưa có dữ liệu")
        rows = conn.execute(
            text(
                "SELECT symbol, name_vi, icb_l2_name_vi, sum(net_value_bn) AS net, count(DISTINCT trade_date) AS n "
                "FROM dw.ds_stock_flow_daily WHERE investor_type = :it AND trade_date >= :d1 AND trade_date <= :d2 "
                f"GROUP BY 1, 2, 3 ORDER BY net {order} LIMIT :lim"
            ),
            {"it": investor_type, "d1": min(days), "d2": max(days), "lim": limit},
        ).all()
    return TopNet(
        side=side,
        investor_type=investor_type,
        date_from=min(days),
        date_to=max(days),
        items=[
            TopNetItem(
                symbol=r.symbol,
                name_vi=r.name_vi,
                icb_l2_name_vi=r.icb_l2_name_vi,
                net_bn=round(r.net, 2),
                n_days=r.n,
            )
            for r in rows
        ],
    )
