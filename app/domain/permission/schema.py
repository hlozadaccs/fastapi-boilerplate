from pydantic import BaseModel


class PermissionRead(BaseModel):
    id: int
    code: str
    description: str | None = None
