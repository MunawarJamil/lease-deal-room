from app.audit.rent_roll_auditor import audit_lease_against_rent_roll
from app.graph.state import LeaseGraphState


def audit_rent_roll_node(state: LeaseGraphState) -> LeaseGraphState:
    flags = audit_lease_against_rent_roll(
        tenant_name=state["tenant_name"],
        verified_terms=state.get("verified_terms", {}),
        rent_roll_row=state.get("rent_roll_row"),
    )
    return {"flags": flags}