from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (minimum 1)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (1-100)")
