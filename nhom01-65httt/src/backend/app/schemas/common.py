"""Schema dùng chung. Mọi response trả dự báo/khuyến nghị phải có trường `disclaimer`."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DISCLAIMER = "Thông tin chỉ phục vụ học tập, không phải khuyến nghị đầu tư."

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class StubFlag(BaseModel):
    """Endpoint chưa có dữ liệu thật trả mẫu đúng schema và đặt stub = true."""

    stub: bool = Field(
        default=False, description="true nếu đây là dữ liệu mẫu, không phải dữ liệu thật"
    )


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
