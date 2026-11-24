from app.audit.citation_verifier import verify_lease_terms
from app.graph.state import LeaseGraphState
from app.schemas.lease_terms import LeaseTermsExtraction


def verify_citations_node(state: LeaseGraphState) -> LeaseGraphState:
    extraction = state.get("extraction") or LeaseTermsExtraction()
    attempt = state.get("attempts", 1)
    verified, failed = verify_lease_terms(
        extraction,
        state["pages_by_number"],
        attempt=attempt,
        previous_verified=state.get("verified_terms"),
    )
    return {
        "verified_terms": verified,
        "failed_fields": failed,
    }