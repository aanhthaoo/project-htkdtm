"""Chạy lại ETL và xem nhật ký (admin), webhook nội bộ cho n8n, API mô hình nội bộ (lõi, TV1).

- Bộ chạy ETL là dịch vụ `etl-runner` (src/etl_runner); backend và n8n đều gọi nó, nó ghi app.etl_runs.
- Webhook nội bộ dùng khóa dịch vụ ở header X-Service-Key (không dùng JWT của người dùng).
"""

from datetime import date, datetime
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.core import ml_serving
from app.core.deps import AdminUser, Pagination, ServiceCall
from app.core.errors import ApiError
from app.db import get_engine
from app.schemas.common import DISCLAIMER, Page, StubFlag

JobName = Literal["rss", "daily", "news", "dbt", "quality", "after_close"]

admin = APIRouter(prefix="/api/admin", tags=["Admin: ETL và chất lượng dữ liệu"])
internal = APIRouter(prefix="/api/internal", tags=["Nội bộ (khóa dịch vụ)"])
ml = APIRouter(prefix="/ml", tags=["API mô hình (nội bộ)"])


# ---------------- Admin: ETL ----------------
class EtlRunRequest(BaseModel):
    job: JobName = "after_close"


class EtlRun(BaseModel):
    id: int
    job: str
    trigger_type: str
    status: str
    requested_by: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    steps: list[dict] = []
    log_tail: str | None = None


class EtlRunStarted(BaseModel):
    run_id: int
    job: str
    status: str


@admin.post("/etl/run", response_model=EtlRunStarted, status_code=202)
def run_etl(body: EtlRunRequest, user: AdminUser):
    """Chạy lại một bước ETL hoặc cả chuỗi (`after_close`). Trả ngay mã lần chạy; xem tiến độ ở /etl/runs."""
    s = get_settings()
    try:
        r = httpx.post(
            f"{s.etl_runner_url}/jobs/{body.job}",
            params={"trigger": "admin", "requested_by": user.email},
            headers={"X-Service-Key": s.service_key},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise ApiError(502, "etl_runner_unavailable", "Không kết nối được bộ chạy ETL") from exc
    if r.status_code == 409:
        raise ApiError(409, "etl_busy", "Đang có một lần chạy ETL khác, thử lại sau")
    if not r.is_success:
        raise ApiError(502, "etl_runner_error", f"Bộ chạy ETL trả lỗi {r.status_code}")
    data = r.json()
    return EtlRunStarted(run_id=data["run_id"], job=body.job, status=data["status"])


@admin.get("/etl/runs", response_model=Page[EtlRun])
def list_etl_runs(
    user: AdminUser, p: Pagination, status: Literal["running", "success", "failed"] | None = None
):
    where = "WHERE status = :status" if status else ""
    with get_engine().connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM app.etl_runs {where}"), {"status": status}
        ).scalar_one()
        rows = conn.execute(
            text(
                "SELECT id, job, trigger_type, status, requested_by, started_at, finished_at, steps, log_tail "
                f"FROM app.etl_runs {where} ORDER BY started_at DESC LIMIT :n OFFSET :o"
            ),
            {"status": status, "n": p.page_size, "o": p.offset},
        ).all()
    return Page[EtlRun](
        items=[EtlRun(**r._mapping) for r in rows], page=p.page, page_size=p.page_size, total=total
    )


class DqLogEntry(BaseModel):
    id: int
    logged_at: datetime
    run_id: str | None = None
    layer: str
    source: str | None = None
    check_name: str
    target_table: str | None = None
    business_date: date | None = None
    severity: str
    passed: bool
    metric_value: float | None = None
    threshold_value: float | None = None


@admin.get("/dq-log", response_model=Page[DqLogEntry])
def dq_log(
    user: AdminUser,
    p: Pagination,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    severity: Literal["info", "warning", "error"] | None = None,
    failed_only: bool = False,
):
    """Nhật ký chất lượng dữ liệu (dw.dq_log), mới nhất trước."""
    conds, params = [], {"n": p.page_size, "o": p.offset}
    if date_from:
        conds.append("logged_at >= :d1")
        params["d1"] = date_from
    if date_to:
        conds.append("logged_at < :d2::date + 1")
        params["d2"] = date_to
    if severity:
        conds.append("severity = :sev")
        params["sev"] = severity
    if failed_only:
        conds.append("NOT passed")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    cols = (
        "id, logged_at, run_id, layer, source, check_name, target_table, business_date, severity, passed, "
        "metric_value::float8 AS metric_value, threshold_value::float8 AS threshold_value"
    )
    with get_engine().connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM dw.dq_log {where}"), params).scalar_one()
        rows = conn.execute(
            text(
                f"SELECT {cols} FROM dw.dq_log {where} ORDER BY logged_at DESC, id DESC LIMIT :n OFFSET :o"
            ),
            params,
        ).all()
    return Page[DqLogEntry](
        items=[DqLogEntry(**r._mapping) for r in rows],
        page=p.page,
        page_size=p.page_size,
        total=total,
    )


# ---------------- Webhook nội bộ cho n8n ----------------
class AlertDispatchRequest(BaseModel):
    alert_type: Literal["flow_reversal", "negative_news", "weekly_digest"]
    entity_type: Literal["STOCK", "SECTOR"]
    entity_code: str


class Recipient(BaseModel):
    user_id: int
    email: str
    full_name: str


class AlertDispatchResponse(BaseModel):
    alert_type: str
    entity_type: str
    entity_code: str
    count: int
    recipients: list[Recipient]


@internal.post("/alerts/dispatch", response_model=AlertDispatchResponse, dependencies=[ServiceCall])
def alerts_dispatch(body: AlertDispatchRequest):
    """n8n gọi khi cần gửi cảnh báo: trả danh sách người dùng đã đăng ký nhận loại cảnh báo này cho mã/ngành này."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT u.id AS user_id, u.email, u.full_name FROM app.alert_subscriptions s "
                "JOIN app.users u ON u.id = s.user_id "
                "WHERE s.is_active AND u.is_active AND s.alert_type = :t AND s.entity_type = :et AND s.entity_code = :ec "
                "ORDER BY u.id"
            ),
            {"t": body.alert_type, "et": body.entity_type, "ec": body.entity_code},
        ).all()
    recipients = [Recipient(**r._mapping) for r in rows]
    return AlertDispatchResponse(
        alert_type=body.alert_type,
        entity_type=body.entity_type,
        entity_code=body.entity_code,
        count=len(recipients),
        recipients=recipients,
    )


class EtlEvent(BaseModel):
    job: str
    status: Literal["success", "failed"]
    message: str = ""


class EtlEventOut(BaseModel):
    run_id: int


@internal.post(
    "/etl/events", response_model=EtlEventOut, status_code=201, dependencies=[ServiceCall]
)
def etl_event(body: EtlEvent):
    """n8n ghi một sự kiện ETL (ví dụ nguồn lỗi) vào nhật ký chạy."""
    with get_engine().begin() as conn:
        run_id = conn.execute(
            text(
                "INSERT INTO app.etl_runs (job, trigger_type, status, requested_by, finished_at, log_tail) "
                "VALUES (:job, 'n8n', :status, 'n8n', now(), :msg) RETURNING id"
            ),
            {"job": body.job, "status": body.status, "msg": body.message[-4000:]},
        ).scalar_one()
    return EtlEventOut(run_id=run_id)


# ---------------- API mô hình (nội bộ, khóa dịch vụ) ----------------
class SentimentRequest(BaseModel):
    texts: list[str]


class SentimentResult(BaseModel):
    label: Literal["negative", "neutral", "positive"]
    score: float
    confidence: float


class SentimentResponse(StubFlag):
    model_version: str
    results: list[SentimentResult]


@ml.post("/sentiment", response_model=SentimentResponse, dependencies=[ServiceCall])
def ml_sentiment(body: SentimentRequest):
    """Chấm cảm xúc văn bản (điểm = P(tích cực) - P(tiêu cực) trong [-1, 1]).

    Điểm thật khi mô hình và thư viện học máy có mặt trong tiến trình backend; nếu không trả dữ liệu mẫu `stub: true`
    (image backend hiện chưa có thư viện học máy, xem app/core/ml_serving.py).
    """
    if len(body.texts) > 100:
        raise ApiError(422, "validation_error", "Tối đa 100 văn bản mỗi lần gọi")
    if ml_serving.sentiment_available():
        version, results = ml_serving.score_texts(body.texts)
        return SentimentResponse(
            stub=False, model_version=version, results=[SentimentResult(**r) for r in results]
        )
    return SentimentResponse(
        stub=True,
        model_version="0.0.0-stub",
        results=[SentimentResult(label="neutral", score=0.0, confidence=0.0) for _ in body.texts],
    )


class PredictRequest(BaseModel):
    target_week_start: date
    horizon_weeks: int = 1


class PredictItem(BaseModel):
    icb_l2_code: str
    predicted_class: Literal["INFLOW", "OUTFLOW"]
    prob_inflow: float
    predicted_net_bn: float


class PredictResponse(StubFlag):
    model_version: str
    items: list[PredictItem]
    disclaimer: str = DISCLAIMER


@ml.post("/predict", response_model=PredictResponse, dependencies=[ServiceCall])
def ml_predict(body: PredictRequest):
    """Dự báo chiều dòng tiền khối ngoại của 19 ngành cho tuần bắt đầu `target_week_start` (mô hình dự báo mới nhất trong dw)."""
    if body.horizon_weeks != 1:
        raise ApiError(404, "not_found", "Chỉ có dự báo chân trời 1 tuần")
    with get_engine().connect() as conn:
        model = conn.execute(
            text(
                "SELECT model_key, name, version FROM dw.dim_model WHERE task = 'forecast' ORDER BY trained_at DESC LIMIT 1"
            )
        ).first()
        if model is None:
            raise ApiError(404, "not_found", "Chưa có mô hình dự báo")
        rows = conn.execute(
            text(
                "SELECT DISTINCT ON (s.icb_l2_code) s.icb_l2_code, p.predicted_class, p.prob_inflow, p.predicted_net_value_bn "
                "FROM dw.fact_prediction p JOIN dw.dim_sector s USING (sector_key) "
                "WHERE p.model_key = :m AND p.horizon_weeks = 1 AND p.target_week_start_date_key = :k "
                "ORDER BY s.icb_l2_code, p.made_at DESC"
            ),
            {"m": model.model_key, "k": int(body.target_week_start.strftime("%Y%m%d"))},
        ).all()
    if not rows:
        raise ApiError(404, "not_found", "Không có dự báo cho tuần này")
    return PredictResponse(
        stub=False,
        model_version=f"{model.name} {model.version}",
        items=[
            PredictItem(
                icb_l2_code=r.icb_l2_code,
                predicted_class=r.predicted_class,
                prob_inflow=r.prob_inflow,
                predicted_net_bn=r.predicted_net_value_bn,
            )
            for r in rows
        ],
    )


class ClusterRequest(BaseModel):
    symbols: list[str]


class ClusterItem(BaseModel):
    symbol: str
    cluster_label: str


class ClusterResponse(StubFlag):
    model_version: str
    items: list[ClusterItem]


@ml.post("/cluster", response_model=ClusterResponse, dependencies=[ServiceCall])
def ml_cluster(body: ClusterRequest):
    """Nhãn cụm hành vi dòng tiền của từng mã (`unknown` nếu mã không có trong kho)."""
    if len(body.symbols) > 500:
        raise ApiError(422, "validation_error", "Tối đa 500 mã mỗi lần gọi")
    symbols = [s.strip().upper() for s in body.symbols]
    with get_engine().connect() as conn:
        model = conn.execute(
            text(
                "SELECT name, version FROM dw.dim_model WHERE task = 'cluster' ORDER BY trained_at DESC LIMIT 1"
            )
        ).first()
        rows = conn.execute(
            text(
                "SELECT symbol, cluster_label FROM dw.dim_stock WHERE symbol = ANY(:s) AND cluster_label IS NOT NULL"
            ),
            {"s": symbols},
        ).all()
    if model is None:
        raise ApiError(404, "not_found", "Chưa có mô hình phân cụm")
    found = {r.symbol: r.cluster_label for r in rows}
    return ClusterResponse(
        stub=False,
        model_version=f"{model.name} {model.version}",
        items=[ClusterItem(symbol=s, cluster_label=found.get(s, "unknown")) for s in symbols],
    )
