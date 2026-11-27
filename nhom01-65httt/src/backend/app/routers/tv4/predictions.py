"""Dự báo, độ chính xác (đọc dw.fact_prediction, N8) và khuyến nghị (đọc dw.fact_recommendation, N9)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.deps import InvestorUser
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import DISCLAIMER, StubFlag

router = APIRouter(tags=["TV4: Dự báo và khuyến nghị"])


class ModelRef(BaseModel):
    name: str
    version: str


class PredictionItem(BaseModel):
    icb_l2_code: str
    name_vi: str
    predicted_class: Literal["INFLOW", "OUTFLOW"]
    prob_inflow: float
    predicted_net_bn: float
    rank: int = Field(
        description="Thứ hạng ngành theo giá trị ròng dự báo (1 = dự báo mua ròng mạnh nhất trong tuần). Cách đọc khác của cùng dự báo hồi quy, không phải mô hình riêng"
    )
    actual_class: Literal["INFLOW", "OUTFLOW"] | None = Field(
        default=None, description="Chiều dòng tiền thực tế (có khi tuần mục tiêu đã kết thúc)"
    )
    actual_net_bn: float | None = None


class Predictions(StubFlag):
    target_week_start: date
    horizon_weeks: int
    model: ModelRef
    evaluated: bool = Field(description="true nếu tuần mục tiêu đã kết thúc và có giá trị thực tế")
    items: list[PredictionItem]
    disclaimer: str = DISCLAIMER


FORECAST_MODEL_SQL = "SELECT model_key, name, version FROM dw.dim_model WHERE task = 'forecast' ORDER BY trained_at DESC LIMIT 1"


@router.get("/api/predictions", response_model=Predictions)
def predictions(
    user: InvestorUser,
    week: date | None = None,
    horizon: Annotated[int, Query(ge=1, le=4)] = 1,
):
    """Dự báo chiều dòng tiền khối ngoại của ngành ICB cấp 2 cho tuần bắt đầu `week` (mặc định tuần mới nhất có dự báo).
    Dự báo trong quá khứ là dự báo ngoài mẫu (walk-forward) và có kèm giá trị thực tế."""
    with get_engine().connect() as conn:
        model = conn.execute(text(FORECAST_MODEL_SQL)).first()
        if model is None:
            raise ApiError(404, "not_found", "Chưa có mô hình dự báo")
        key = int(week.strftime("%Y%m%d")) if week else None
        rows = conn.execute(
            text(
                "SELECT DISTINCT ON (s.icb_l2_code) p.target_week_start_date_key AS k, s.icb_l2_code, s.icb_l2_name_vi, "
                "p.predicted_class, p.prob_inflow, p.predicted_net_value_bn, p.actual_class, p.actual_net_value_bn "
                "FROM dw.fact_prediction p JOIN dw.dim_sector s USING (sector_key) "
                "WHERE p.model_key = :m AND p.horizon_weeks = :h AND p.target_week_start_date_key = "
                "coalesce(:k, (SELECT max(target_week_start_date_key) FROM dw.fact_prediction WHERE model_key = :m)) "
                "ORDER BY s.icb_l2_code, p.made_at DESC"
            ),
            {"m": model.model_key, "h": horizon, "k": key},
        ).all()
    if not rows:
        raise ApiError(404, "not_found", "Không có dự báo cho tuần và chân trời này")
    target = date(rows[0].k // 10000, rows[0].k // 100 % 100, rows[0].k % 100)
    order = sorted(rows, key=lambda r: (-r.predicted_net_value_bn, r.icb_l2_code))
    rank = {r.icb_l2_code: i + 1 for i, r in enumerate(order)}
    return Predictions(
        stub=False,
        target_week_start=target,
        horizon_weeks=horizon,
        model=ModelRef(name=model.name, version=model.version),
        evaluated=all(r.actual_class is not None for r in rows),
        items=[
            PredictionItem(
                icb_l2_code=r.icb_l2_code,
                name_vi=r.icb_l2_name_vi,
                predicted_class=r.predicted_class,
                prob_inflow=r.prob_inflow,
                predicted_net_bn=r.predicted_net_value_bn,
                rank=rank[r.icb_l2_code],
                actual_class=r.actual_class,
                actual_net_bn=r.actual_net_value_bn,
            )
            for r in rows
        ],
    )


class AccuracyPoint(BaseModel):
    week_start_date: date
    accuracy: float
    baseline_accuracy: float | None = Field(description="Mô hình cơ sở: tuần sau giống tuần này")
    n_sectors: int


class Accuracy(StubFlag):
    weeks: int
    overall_accuracy: float
    overall_baseline_accuracy: float
    points: list[AccuracyPoint]
    disclaimer: str = DISCLAIMER


@router.get("/api/predictions/accuracy", response_model=Accuracy)
def predictions_accuracy(user: InvestorUser, weeks: Annotated[int, Query(ge=1, le=260)] = 12):
    """Độ chính xác dự báo (đúng chiều dòng tiền) theo từng tuần mục tiêu, so với mô hình cơ sở "tuần sau giống tuần này"."""
    with get_engine().connect() as conn:
        model = conn.execute(text(FORECAST_MODEL_SQL)).first()
        if model is None:
            raise ApiError(404, "not_found", "Chưa có mô hình dự báo")
        rows = conn.execute(
            text(
                "WITH r AS (SELECT p.target_week_start_date_key AS k, p.sector_key, p.predicted_class = p.actual_class AS hit, "
                "  lag(p.actual_class) OVER (PARTITION BY p.sector_key ORDER BY p.target_week_start_date_key) AS prev_actual, "
                "  p.actual_class FROM dw.fact_prediction p WHERE p.model_key = :m AND p.horizon_weeks = 1 "
                "  AND p.actual_class IS NOT NULL) "
                "SELECT k, avg(hit::int) AS acc, avg((prev_actual = actual_class)::int) AS base, count(*) AS n "
                "FROM r GROUP BY k ORDER BY k"
            ),
            {"m": model.model_key},
        ).all()
    if not rows:
        raise ApiError(404, "not_found", "Chưa có dự báo đã kiểm chứng")
    total = sum(r.n for r in rows)
    base_rows = [r for r in rows if r.base is not None]
    recent = rows[-weeks:]
    return Accuracy(
        stub=False,
        weeks=len(recent),
        overall_accuracy=sum(r.acc * r.n for r in rows) / total,
        overall_baseline_accuracy=sum(r.base * r.n for r in base_rows)
        / sum(r.n for r in base_rows),
        points=[
            AccuracyPoint(
                week_start_date=date(r.k // 10000, r.k // 100 % 100, r.k % 100),
                accuracy=r.acc,
                baseline_accuracy=r.base,
                n_sectors=r.n,
            )
            for r in recent
        ],
    )


class Recommendation(BaseModel):
    icb_l2_code: str
    name_vi: str
    action: Literal["increase", "decrease", "hold"]
    signal: Literal["none", "reversal", "mismatch"]
    reason: str
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="Độ chắc chắn theo số tín hiệu cùng chiều và có lệch pha hay không",
    )
    score: float = Field(
        default=0.0, description="Điểm tổng hợp các tín hiệu; >= 0,5 tăng, <= -0,5 giảm"
    )
    signals: list[str] = Field(
        default_factory=list,
        description="Mã các tín hiệu đã kích hoạt: forecast_inflow, forecast_outflow, reversal_up, reversal_down, "
        "sentiment_up, sentiment_down, positive_news_outflow, negative_news_inflow",
    )
    prob_inflow: float | None = Field(
        default=None, description="Xác suất mua ròng của mô hình dự báo tuần này"
    )


class Recommendations(StubFlag):
    week: date
    rule_version: str | None = None
    items: list[Recommendation]
    disclaimer: str = DISCLAIMER


REC_MODEL_SQL = "SELECT model_key, version FROM dw.dim_model WHERE task = 'recommendation' ORDER BY trained_at DESC LIMIT 1"


@router.get("/api/recommendations", response_model=Recommendations)
def recommendations(user: InvestorUser, week: date | None = None):
    """Khuyến nghị tăng/giảm tỷ trọng 19 ngành cho tuần bắt đầu `week` (mặc định tuần mới nhất), kèm tín hiệu đảo chiều,
    cảnh báo lệch pha và độ chắc chắn. Quy tắc cố định và công khai (`docs/ml_ket_qua.md` mục 5); đây không phải lời khuyên đầu tư."""
    with get_engine().connect() as conn:
        model = conn.execute(text(REC_MODEL_SQL)).first()
        if model is None:
            raise ApiError(404, "not_found", "Chưa có khuyến nghị")
        key = int(week.strftime("%Y%m%d")) if week else None
        rows = conn.execute(
            text(
                "SELECT r.week_start_date_key AS k, s.icb_l2_code, s.icb_l2_name_vi, r.action, r.confidence, r.score, r.signals, "
                "r.reason, r.prob_inflow FROM dw.fact_recommendation r JOIN dw.dim_sector s USING (sector_key) "
                "WHERE r.model_key = :m AND r.week_start_date_key = "
                "coalesce(:k, (SELECT max(week_start_date_key) FROM dw.fact_recommendation WHERE model_key = :m)) "
                "ORDER BY r.score DESC, s.icb_l2_code"
            ),
            {"m": model.model_key, "k": key},
        ).all()
    if not rows:
        raise ApiError(404, "not_found", "Không có khuyến nghị cho tuần này")
    target = date(rows[0].k // 10000, rows[0].k // 100 % 100, rows[0].k % 100)

    def shown(signals: list[str]) -> str:
        if any(x in ("positive_news_outflow", "negative_news_inflow") for x in signals):
            return "mismatch"
        return "reversal" if any(x.startswith("reversal") for x in signals) else "none"

    return Recommendations(
        stub=False,
        week=target,
        rule_version=model.version,
        items=[
            Recommendation(
                icb_l2_code=r.icb_l2_code,
                name_vi=r.icb_l2_name_vi,
                action=r.action,
                signal=shown(r.signals.split(",") if r.signals else []),
                reason=r.reason,
                confidence=r.confidence,
                score=r.score,
                signals=r.signals.split(",") if r.signals else [],
                prob_inflow=r.prob_inflow,
            )
            for r in rows
        ],
    )
