from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes.audit_rent_roll import audit_rent_roll_node
from app.graph.nodes.extract_terms import make_extract_terms_node
from app.graph.nodes.retrieve_context import make_retrieve_context_node
from app.graph.nodes.verify_citations import verify_citations_node
from app.graph.state import LeaseGraphState
from app.llm.client import LLMClient
from app.vectorstore.embeddings import EmbeddingClient
from app.vectorstore.qdrant_store import QdrantStore

MAX_EXTRACTION_ATTEMPTS = 2  # 1 initial attempt + max 1 retry


def _route_after_verification(state: LeaseGraphState) -> Literal["retry", "audit"]:
    failed = state.get("failed_fields", [])
    attempts = state.get("attempts", 1)
    if failed and attempts < MAX_EXTRACTION_ATTEMPTS:
        return "retry"
    return "audit"


def build_lease_graph(
    *,
    qdrant_store: QdrantStore,
    embedding_client: EmbeddingClient,
    llm_client: LLMClient,
) -> CompiledStateGraph:
    """Build the 4-node per-lease extraction & audit LangGraph."""
    graph = StateGraph(LeaseGraphState)

    graph.add_node(
        "retrieve_context",
        make_retrieve_context_node(qdrant_store, embedding_client),
    )
    graph.add_node("extract_terms", make_extract_terms_node(llm_client))
    graph.add_node("verify_citations", verify_citations_node)
    graph.add_node("audit_rent_roll", audit_rent_roll_node)

    graph.add_edge(START, "retrieve_context")
    graph.add_edge("retrieve_context", "extract_terms")
    graph.add_edge("extract_terms", "verify_citations")
    graph.add_conditional_edges(
        "verify_citations",
        _route_after_verification,
        {"retry": "extract_terms", "audit": "audit_rent_roll"},
    )
    graph.add_edge("audit_rent_roll", END)

    return graph.compile()