from decimal import Decimal

import pytest

from app.audit.citation_verifier import verify_lease_terms
from app.audit.rent_roll_auditor import audit_lease_against_rent_roll
from app.graph.builder import build_lease_graph
from app.parsing.rent_roll_parser import RentRollRow
from app.schemas.lease_terms import ExtractedField, LeaseTermsExtraction
from app.vectorstore.qdrant_store import RetrievedChunk


class _FakeEmbeddingClient:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeQdrantStore:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.calls: list[tuple[str, str]] = []

    async def search(
        self,
        query_vector: list[float],
        *,
        deal_id: str,
        tenant_name: str,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        self.calls.append((deal_id, tenant_name))
        return self._chunks[:limit]


class _FakeLLMClient:
    def __init__(self, responses: list[LeaseTermsExtraction]) -> None:
        self._responses = responses
        self.call_count = 0

    async def extract_structured(self, **kwargs) -> LeaseTermsExtraction:
        idx = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        return self._responses[idx]


def test_citation_verifier_handles_whitespace_and_detects_hallucination() -> None:
    pages = {
        1: "Tenant shall pay Base Rent of $12,500.00\nper month starting January 1, 2025.",
    }
    extraction = LeaseTermsExtraction(
        base_rent=ExtractedField(
            value="$12,500.00/mo",
            page_number=1,
            quote="Base Rent of $12,500.00 per month",
        ),
        security_deposit=ExtractedField(
            value="$25,000",
            page_number=1,
            quote="Security deposit of $25,000 is non-refundable",
        ),
    )

    verified, failed = verify_lease_terms(extraction, pages, attempt=1)
    assert verified["base_rent"].verified is True
    assert verified["security_deposit"].verified is False
    assert failed == ["security_deposit"]


def test_rent_roll_auditor_flags_mismatch_and_missing_tenant() -> None:
    pages = {1: "Base Rent shall be $12,500.00 per month. Term ends 2030-12-31."}
    extraction = LeaseTermsExtraction(
        base_rent=ExtractedField(
            value="$12,500.00 per month",
            page_number=1,
            quote="Base Rent shall be $12,500.00 per month.",
        ),
        lease_term=ExtractedField(
            value="2025-01-01 to 2030-12-31",
            page_number=1,
            quote="Term ends 2030-12-31.",
        ),
    )
    verified, _ = verify_lease_terms(extraction, pages, attempt=1)

    row = RentRollRow(
        tenant_name="Acme Corp",
        monthly_rent=Decimal("10000.00"),
        annual_rent=Decimal("120000.00"),
        lease_end="2029-12-31",
        raw_row={},
    )
    flags = audit_lease_against_rent_roll(
        tenant_name="Acme Corp",
        verified_terms=verified,
        rent_roll_row=row,
    )
    flag_types = {f.flag_type for f in flags}
    assert flag_types == {"rent_mismatch", "term_mismatch"}

    missing_flags = audit_lease_against_rent_roll(
        tenant_name="Acme Corp",
        verified_terms=verified,
        rent_roll_row=None,
    )
    assert any(f.flag_type == "missing_from_rent_roll" for f in missing_flags)


@pytest.mark.asyncio
async def test_lease_graph_retries_once_and_audits() -> None:
    pages = {
        2: "Monthly Base Rent is $15,000.00 per month. Security Deposit is $30,000.00.",
    }
    chunks = [
        RetrievedChunk(
            deal_id="deal-1",
            tenant_name="Acme Corp",
            file_name="acme.pdf",
            page_number=2,
            text=pages[2],
            score=0.95,
        )
    ]

    # Attempt 1: bad quote on security_deposit; Attempt 2: fixed quote
    attempt_1 = LeaseTermsExtraction(
        base_rent=ExtractedField(
            value="$15,000.00/mo",
            page_number=2,
            quote="Monthly Base Rent is $15,000.00 per month.",
        ),
        security_deposit=ExtractedField(
            value="$30,000.00",
            page_number=2,
            quote="Hallucinated deposit quote",
        ),
    )
    attempt_2 = LeaseTermsExtraction(
        base_rent=attempt_1.base_rent,
        security_deposit=ExtractedField(
            value="$30,000.00",
            page_number=2,
            quote="Security Deposit is $30,000.00.",
        ),
    )

    qdrant = _FakeQdrantStore(chunks)
    llm = _FakeLLMClient([attempt_1, attempt_2])
    graph = build_lease_graph(
        qdrant_store=qdrant,  # type: ignore[arg-type]
        embedding_client=_FakeEmbeddingClient(),  # type: ignore[arg-type]
        llm_client=llm,  # type: ignore[arg-type]
    )

    result = await graph.ainvoke(
        {
            "deal_id": "deal-1",
            "tenant_name": "Acme Corp",
            "pages_by_number": pages,
            "rent_roll_row": RentRollRow(
                tenant_name="Acme Corp",
                monthly_rent=Decimal("15000.00"),
                annual_rent=Decimal("180000.00"),
                raw_row={},
            ),
        }
    )

    assert llm.call_count == 2
    assert result["attempts"] == 2
    assert result["verified_terms"]["base_rent"].verified is True
    assert result["verified_terms"]["security_deposit"].verified is True
    assert result["flags"] == []
    assert all(call == ("deal-1", "Acme Corp") for call in qdrant.calls)


@pytest.mark.asyncio
async def test_lease_graph_caps_retries_at_one_and_flags_unverified() -> None:
    pages = {1: "Monthly Base Rent is $8,000.00 per month."}
    chunks = [
        RetrievedChunk(
            deal_id="deal-1",
            tenant_name="Beta LLC",
            file_name="beta.pdf",
            page_number=1,
            text=pages[1],
            score=0.9,
        )
    ]
    bad = LeaseTermsExtraction(
        base_rent=ExtractedField(
            value="$8,000.00/mo",
            page_number=1,
            quote="Non-existent quote",
        )
    )

    llm = _FakeLLMClient([bad, bad, bad])
    graph = build_lease_graph(
        qdrant_store=_FakeQdrantStore(chunks),  # type: ignore[arg-type]
        embedding_client=_FakeEmbeddingClient(),  # type: ignore[arg-type]
        llm_client=llm,  # type: ignore[arg-type]
    )

    result = await graph.ainvoke(
        {
            "deal_id": "deal-1",
            "tenant_name": "Beta LLC",
            "pages_by_number": pages,
            "rent_roll_row": RentRollRow(
                tenant_name="Beta LLC",
                monthly_rent=Decimal("8000.00"),
                annual_rent=Decimal("96000.00"),
                raw_row={},
            ),
        }
    )

    assert llm.call_count == 2
    assert result["attempts"] == 2
    assert result["verified_terms"]["base_rent"].verified is False
    assert any(f.flag_type == "unverified_citation" for f in result["flags"])