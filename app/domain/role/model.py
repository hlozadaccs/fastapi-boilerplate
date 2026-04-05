from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.permission.model import role_permissions
from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.domain.permission.model import Permission

# Association table for User-Role many-to-many
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary=role_permissions,
        lazy="selectin",
    )
