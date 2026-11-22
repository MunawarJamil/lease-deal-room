import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from app.core.exceptions import ParsingError

_TENANT_COLS = ("tenant", "tenant_name", "lessee", "occupant", "name")
_MONTHLY_RENT_COLS = ("monthly_rent", "base_rent_monthly", "monthly_base_rent", "base_rent", "rent")
_ANNUAL_RENT_COLS = ("annual_rent", "annual_base_rent", "yearly_rent")
_SQFT_COLS = ("sqft", "sf", "rsf", "square_feet", "area")
_START_COLS = ("lease_start", "start_date", "commencement_date", "start")
_END_COLS = ("lease_end", "end_date", "expiration_date", "expiry", "end")


class RentRollRow(BaseModel):
    tenant_name: str
    monthly_rent: Decimal | None = None
    annual_rent: Decimal | None = None
    sqft: float | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    raw_row: dict[str, str]


def _normalize_col(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _find_column(columns: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return columns[candidate]
    return None


def _parse_money(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _parse_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_str(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def parse_rent_roll(file_path: str | Path) -> list[RentRollRow]:
    """Parse a CSV or Excel rent roll into normalized RentRollRow records."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ParsingError(f"Rent roll file not found: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        else:
            raise ParsingError(f"Unsupported rent roll format '{suffix}'. Use CSV or Excel.")
    except ParsingError:
        raise
    except Exception as exc:
        raise ParsingError(f"Failed to read rent roll '{path.name}': {exc}") from exc

    if df.empty:
        raise ParsingError(f"Rent roll '{path.name}' is empty")

    col_map = {_normalize_col(col): str(col) for col in df.columns}
    tenant_col = _find_column(col_map, _TENANT_COLS)
    if not tenant_col:
        raise ParsingError(
            f"Rent roll '{path.name}' is missing a tenant column. Found: {list(df.columns)}"
        )

    monthly_col = _find_column(col_map, _MONTHLY_RENT_COLS)
    annual_col = _find_column(col_map, _ANNUAL_RENT_COLS)
    sqft_col = _find_column(col_map, _SQFT_COLS)
    start_col = _find_column(col_map, _START_COLS)
    end_col = _find_column(col_map, _END_COLS)

    rows: list[RentRollRow] = []
    for _, row in df.iterrows():
        tenant = _parse_str(row[tenant_col])
        if not tenant:
            continue

        monthly = _parse_money(row[monthly_col]) if monthly_col else None
        annual = _parse_money(row[annual_col]) if annual_col else None
        if monthly is None and annual is not None:
            monthly = (annual / Decimal(12)).quantize(Decimal("0.01"))
        elif annual is None and monthly is not None:
            annual = (monthly * Decimal(12)).quantize(Decimal("0.01"))

        raw = {str(k): "" if pd.isna(v) else str(v) for k, v in row.items()}
        rows.append(
            RentRollRow(
                tenant_name=tenant,
                monthly_rent=monthly,
                annual_rent=annual,
                sqft=_parse_float(row[sqft_col]) if sqft_col else None,
                lease_start=_parse_str(row[start_col]) if start_col else None,
                lease_end=_parse_str(row[end_col]) if end_col else None,
                raw_row=raw,
            )
        )

    return rows