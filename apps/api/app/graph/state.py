from typing import TypedDict

from app.parsing.rent_roll_parser import RentRollRow
from app.schemas.flag import FlagCreate
from app.schemas.lease_terms import LeaseTermsExtraction, VerifiedField
from app.vectorstore.qdrant_store import RetrievedChunk


class LeaseGraphState(TypedDict, total=False):
    deal_id: str
    tenant_name: str
    pages_by_number: dict[int, str]
    rent_roll_row: RentRollRow | None

    retrieved_chunks: list[RetrievedChunk]
    extraction: LeaseTermsExtraction | None
    verified_terms: dict[str, VerifiedField]
    failed_fields: list[str]
    attempts: int
    flags: list[FlagCreate]