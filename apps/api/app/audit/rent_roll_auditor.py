import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.parsing.rent_roll_parser import RentRollRow
from app.schemas.flag import FlagCreate
from app.schemas.lease_terms import VerifiedField

_MONEY_RE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")
_ANNUAL_HINTS = ("/yr", "/year", "per year", "annually", "annual", "per annum")
_MONTHLY_HINTS = ("/mo", "/month", "per month", "monthly")
_DATE_PATTERNS = (
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"), "%m/%d/%Y"),
    (re.compile(r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b"), "%B %d, %Y"),
    (re.compile(r"\b([A-Za-z]{3}\s+\d{1,2},\s*\d{4})\b"), "%b %d, %Y"),
)

_RENT_TOLERANCE_DOLLARS = Decimal("1.00")


def _parse_money_amount(text: str) -> Decimal | None:
    match = _MONEY_RE.search(text)
    if not match:
        return None
    whole = match.group(1).replace(",", "")
    cents = match.group(2) or "00"
    try:
        return Decimal(f"{whole}.{cents}").quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _extract_dates(text: str) -> list[date]:
    found: list[date] = []
    for pattern, fmt in _DATE_PATTERNS:
        for match in pattern.findall(text):
            cleaned = re.sub(r"\s+", " ", match).strip()
            try:
                parsed = datetime.strptime(cleaned, fmt).date()
                if parsed not in found:
                    found.append(parsed)
            except ValueError:
                continue
    return sorted(found)


def _amounts_match(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= _RENT_TOLERANCE_DOLLARS


def audit_lease_against_rent_roll(
    *,
    tenant_name: str,
    verified_terms: dict[str, VerifiedField],
    rent_roll_row: RentRollRow | None,
) -> list[FlagCreate]:
    """Deterministically audit extracted lease terms against a tenant's Rent Roll row."""
    flags: list[FlagCreate] = []

    # 1. Flag any extracted field whose citation could not be verified
    for field_name, field in verified_terms.items():
        if field.value is not None and not field.verified:
            flags.append(
                FlagCreate(
                    tenant_name=tenant_name,
                    flag_type="unverified_citation",
                    severity="low",
                    lease_value=field.value,
                    rent_roll_value=None,
                    message=f"Extracted '{field_name}' could not be verified on page {field.page_number}.",
                )
            )

    # 2. Check Rent Roll presence
    if rent_roll_row is None:
        flags.append(
            FlagCreate(
                tenant_name=tenant_name,
                flag_type="missing_from_rent_roll",
                severity="high",
                lease_value=None,
                rent_roll_value=None,
                message=f"Tenant '{tenant_name}' was not found in the uploaded Rent Roll.",
            )
        )
        return flags

    # 3. Audit Base Rent
    base_rent_field = verified_terms.get("base_rent")
    if base_rent_field and base_rent_field.value and rent_roll_row.monthly_rent is not None:
        lease_amount = _parse_money_amount(base_rent_field.value)
        if lease_amount is None:
            flags.append(
                FlagCreate(
                    tenant_name=tenant_name,
                    flag_type="rent_unparseable",
                    severity="medium",
                    lease_value=base_rent_field.value,
                    rent_roll_value=f"${rent_roll_row.monthly_rent:,.2f}/mo",
                    message="Could not parse numeric base rent from lease extraction.",
                )
            )
        else:
            lowered = base_rent_field.value.lower()
            is_annual = any(hint in lowered for hint in _ANNUAL_HINTS)
            is_monthly = any(hint in lowered for hint in _MONTHLY_HINTS)

            rr_monthly = rent_roll_row.monthly_rent
            rr_annual = rent_roll_row.annual_rent or (rr_monthly * Decimal(12))

            if is_annual and not is_monthly:
                matched = _amounts_match(lease_amount, rr_annual)
                rr_display = f"${rr_annual:,.2f}/yr"
            elif is_monthly and not is_annual:
                matched = _amounts_match(lease_amount, rr_monthly)
                rr_display = f"${rr_monthly:,.2f}/mo"
            else:
                matched = _amounts_match(lease_amount, rr_monthly) or _amounts_match(
                    lease_amount, rr_annual
                )
                rr_display = f"${rr_monthly:,.2f}/mo (${rr_annual:,.2f}/yr)"

            if not matched:
                flags.append(
                    FlagCreate(
                        tenant_name=tenant_name,
                        flag_type="rent_mismatch",
                        severity="high",
                        lease_value=base_rent_field.value,
                        rent_roll_value=rr_display,
                        message=(
                            f"Base rent mismatch for '{tenant_name}': lease states "
                            f"'{base_rent_field.value}' vs Rent Roll '{rr_display}'."
                        ),
                    )
                )

    # 4. Audit Lease Expiration Date (when both sides have parseable dates)
    term_field = verified_terms.get("lease_term")
    if term_field and term_field.value and rent_roll_row.lease_end:
        lease_dates = _extract_dates(term_field.value)
        rr_end_dates = _extract_dates(rent_roll_row.lease_end)
        if lease_dates and rr_end_dates:
            lease_end = lease_dates[-1]
            rr_end = rr_end_dates[-1]
            if lease_end != rr_end:
                flags.append(
                    FlagCreate(
                        tenant_name=tenant_name,
                        flag_type="term_mismatch",
                        severity="medium",
                        lease_value=lease_end.isoformat(),
                        rent_roll_value=rr_end.isoformat(),
                        message=(
                            f"Lease expiration mismatch for '{tenant_name}': lease ends "
                            f"{lease_end.isoformat()} vs Rent Roll {rr_end.isoformat()}."
                        ),
                    )
                )

    return flags