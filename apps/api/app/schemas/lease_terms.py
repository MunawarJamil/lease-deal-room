from pydantic import BaseModel, Field

LEASE_TERM_FIELDS: tuple[str, ...] = (
    "base_rent",
    "escalations",
    "lease_term",
    "early_termination",
    "cam_nnn_caps",
    "roof_hvac_responsibility",
    "renewal_options",
    "security_deposit",
)


class ExtractedField(BaseModel):
    """Single extracted lease term with its source citation."""

    value: str | None = Field(default=None, description="Extracted term value, or null if not found")
    page_number: int | None = Field(default=None, ge=1, description="1-based PDF page number")
    quote: str | None = Field(default=None, description="Exact verbatim quote from that page")


class VerifiedField(ExtractedField):
    """Extracted term after deterministic citation verification."""

    verified: bool = False
    attempts: int = 1


class LeaseTermsExtraction(BaseModel):
    """Structured LLM output for the 8 core commercial lease terms."""

    base_rent: ExtractedField = Field(default_factory=ExtractedField)
    escalations: ExtractedField = Field(default_factory=ExtractedField)
    lease_term: ExtractedField = Field(default_factory=ExtractedField)
    early_termination: ExtractedField = Field(default_factory=ExtractedField)
    cam_nnn_caps: ExtractedField = Field(default_factory=ExtractedField)
    roof_hvac_responsibility: ExtractedField = Field(default_factory=ExtractedField)
    renewal_options: ExtractedField = Field(default_factory=ExtractedField)
    security_deposit: ExtractedField = Field(default_factory=ExtractedField)

    def as_dict(self) -> dict[str, ExtractedField]:
        return {field: getattr(self, field) for field in LEASE_TERM_FIELDS}