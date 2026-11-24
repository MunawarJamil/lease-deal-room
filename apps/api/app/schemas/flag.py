from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

FlagSeverity = Literal["low", "medium", "high"]


class FlagCreate(BaseModel):
    tenant_name: str | None = None
    flag_type: str
    severity: FlagSeverity = "medium"
    lease_value: str | None = None
    rent_roll_value: str | None = None
    message: str


class FlagRead(FlagCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    lease_id: UUID | None = None
    created_at: datetime