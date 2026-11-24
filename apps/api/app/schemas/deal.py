from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.flag import FlagRead


class DealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lease_id: UUID
    field_name: str
    value: str | None = None
    page_number: int | None = None
    quote: str | None = None
    verified: bool
    attempts: int


class LeaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    tenant_name: str
    file_name: str
    page_count: int | None = None
    status: str
    error_message: str | None = None
    extractions: list[ExtractionRead] = Field(default_factory=list)


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    rent_roll_file_path: str | None = None
    created_at: datetime
    updated_at: datetime


class DealDetailRead(DealRead):
    leases: list[LeaseRead] = Field(default_factory=list)
    flags: list[FlagRead] = Field(default_factory=list)