import json
from collections.abc import Awaitable, Callable

from app.graph.state import LeaseGraphState
from app.llm.client import LLMClient
from app.schemas.lease_terms import LEASE_TERM_FIELDS, LeaseTermsExtraction

_SYSTEM_PROMPT = """You are a senior commercial real estate lease abstractor.
Extract ONLY from the provided lease excerpts for this single tenant.
Never guess or invent numbers, dates, or quotes.

Return ONLY a valid JSON object with these exact 8 top-level keys:
- base_rent
- escalations
- lease_term
- early_termination
- cam_nnn_caps
- roof_hvac_responsibility
- renewal_options
- security_deposit

Each key MUST map to an object with:
{
  "value": "<concise extracted term or null if not stated>",
  "page_number": <integer page number from the [Page N] header or null>,
  "quote": "<exact verbatim substring copied directly from that page or null>"
}

Rules:
1. If a term is not present in the excerpts, set value, page_number, and quote to null.
2. Every non-null value MUST have an exact verbatim quote copied from the cited [Page N].
3. Output raw JSON only, with no prose before or after."""


def _format_chunks(state: LeaseGraphState) -> str:
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return "(No lease excerpts retrieved.)"
    return "\n\n".join(f"[Page {c.page_number}]\n{c.text}" for c in chunks)


def make_extract_terms_node(
    llm_client: LLMClient,
) -> Callable[[LeaseGraphState], Awaitable[LeaseGraphState]]:
    async def extract_terms(state: LeaseGraphState) -> LeaseGraphState:
        attempt = state.get("attempts", 0) + 1
        failed_fields = state.get("failed_fields", [])
        context = _format_chunks(state)

        retry_note = ""
        if attempt > 1 and failed_fields:
            retry_note = (
                f"\n\nRETRY NOTICE: The previous attempt failed exact quote verification for: "
                f"{json.dumps(failed_fields)}. Re-check the excerpts carefully and provide an "
                f"EXACT verbatim quote and matching page_number for those fields (or null if absent)."
            )

        user_prompt = (
            f"Tenant: {state['tenant_name']}\n"
            f"Required fields: {', '.join(LEASE_TERM_FIELDS)}\n"
            f"{retry_note}\n\n"
            f"Lease Excerpts:\n{context}"
        )

        extraction = await llm_client.extract_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=LeaseTermsExtraction,
        )
        return {"extraction": extraction, "attempts": attempt}

    return extract_terms