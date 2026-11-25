"""Điểm vào của backend FastAPI (khung ban đầu, N1)."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import db

app = FastAPI(title="HTKDTM Nhom 01 - Backend", version="0.1.0")


@app.get("/health")
def health():
    """Kiểm tra dịch vụ và kết nối cơ sở dữ liệu."""
    try:
        db.check_database()
    except Exception as exc:  # noqa: BLE001 - trả trạng thái lỗi thay vì làm sập dịch vụ
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "down", "detail": type(exc).__name__},
        )
    return {"status": "ok", "database": "ok"}
