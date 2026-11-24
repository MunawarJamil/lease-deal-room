import re

from app.schemas.lease_terms import (
    LEASE_TERM_FIELDS,
    ExtractedField,
    LeaseTermsExtraction,
    VerifiedField,
)

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


def normalize_text(text: str) -> str:
    """Normalize PDF/LLM whitespace and smart punctuation for deterministic substring matching."""
    return _WHITESPACE_RE.sub(" ", text.translate(_PUNCT_MAP)).strip().lower()


def verify_quote_on_page(
    *,
    quote: str | None,
    page_number: int | None,
    pages_by_number: dict[int, str],
) -> bool:
    """Return True iff quote exists verbatim (modulo whitespace/smart-punct) on page_number."""
    if not quote or page_number is None:
        return False
    page_text = pages_by_number.get(page_number)
    if not page_text:
        return False
    norm_quote = normalize_text(quote)
    if len(norm_quote) < 3:
        return False
    return norm_quote in normalize_text(page_text)


def verify_lease_terms(
    extraction: LeaseTermsExtraction,
    pages_by_number: dict[int, str],
    *,
    attempt: int,
    previous_verified: dict[str, VerifiedField] | None = None,
) -> tuple[dict[str, VerifiedField], list[str]]:
    """Verify all 8 extracted terms against raw page text.

    Preserves already-verified fields from earlier attempts and returns
    (verified_map, failed_field_names).
    """
    verified: dict[str, VerifiedField] = {}
    failed_fields: list[str] = []
    prev = previous_verified or {}

    for field_name in LEASE_TERM_FIELDS:
        if field_name in prev and prev[field_name].verified:
            verified[field_name] = prev[field_name]
            continue

        extracted: ExtractedField = getattr(extraction, field_name)
        if extracted.value is None:
            verified[field_name] = VerifiedField(
                value=None,
                page_number=None,
                quote=None,
                verified=False,
                attempts=attempt,
            )
            continue

        is_valid = verify_quote_on_page(
            quote=extracted.quote,
            page_number=extracted.page_number,
            pages_by_number=pages_by_number,
        )
        verified[field_name] = VerifiedField(
            value=extracted.value,
            page_number=extracted.page_number,
            quote=extracted.quote,
            verified=is_valid,
            attempts=attempt,
        )
        if not is_valid:
            failed_fields.append(field_name)

    return verified, failed_fields