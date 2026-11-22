from decimal import Decimal
from pathlib import Path

import pytest

from app.core.exceptions import ParsingError
from app.parsing.chunker import chunk_pages
from app.parsing.pdf_parser import PageText
from app.parsing.rent_roll_parser import parse_rent_roll


def test_chunk_pages_preserves_page_numbers_and_metadata() -> None:
    pages = [
        PageText(page_number=1, text="A" * 1500),
        PageText(page_number=2, text="B" * 500),
    ]
    chunks = chunk_pages(
        pages,
        deal_id="deal-1",
        tenant_name="Acme Corp",
        file_name="acme.pdf",
        chunk_size=1000,
        overlap=200,
    )

    assert len(chunks) == 3
    assert [c.page_number for c in chunks] == [1, 1, 2]
    assert all(c.deal_id == "deal-1" and c.tenant_name == "Acme Corp" for c in chunks)
    assert all(c.file_name == "acme.pdf" for c in chunks)


def test_parse_rent_roll_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "rent_roll.csv"
    csv_file.write_text(
        "Tenant Name,Monthly Rent,RSF,Lease Start,Lease End\n"
        "Acme Corp,\"$12,500.00\",5000,2024-01-01,2029-12-31\n"
        "Beta LLC,$8000,3200,2023-06-01,2028-05-31\n",
        encoding="utf-8",
    )

    rows = parse_rent_roll(csv_file)
    assert len(rows) == 2
    assert rows[0].tenant_name == "Acme Corp"
    assert rows[0].monthly_rent == Decimal("12500.00")
    assert rows[0].annual_rent == Decimal("150000.00")
    assert rows[0].sqft == 5000.0
    assert rows[1].monthly_rent == Decimal("8000.00")


def test_parse_rent_roll_missing_tenant_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("Suite,Rent\n101,5000\n", encoding="utf-8")

    with pytest.raises(ParsingError, match="missing a tenant column"):
        parse_rent_roll(csv_file)