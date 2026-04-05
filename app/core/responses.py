from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str
    message: str
    details: dict | list | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class PaginatedData[T](BaseModel):
    """Paginated data wrapper."""

    items: list[T]
    pagination: PaginationMeta


class ApiResponse[T](BaseModel):
    """Standard API response wrapper."""

    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
