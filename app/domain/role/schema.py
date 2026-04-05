from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleRead(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    permissions: list[str] = []

    model_config = ConfigDict(from_attributes=True)
