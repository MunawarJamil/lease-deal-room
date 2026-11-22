from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.flag import Flag
    from app.models.lease import Lease


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    rent_roll_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    leases: Mapped[list[Lease]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
    )
    flags: Mapped[list[Flag]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
    )