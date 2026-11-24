from collections.abc import Awaitable, Callable

from app.graph.state import LeaseGraphState
from app.vectorstore.embeddings import EmbeddingClient
from app.vectorstore.qdrant_store import QdrantStore, RetrievedChunk

_RETRIEVAL_QUERIES: tuple[str, ...] = (
    "base rent monthly annual rent escalations rent increase security deposit",
    "lease term commencement date expiration date early termination option renewal options",
    "CAM NNN operating expenses cap roof HVAC maintenance repair responsibility",
)


def make_retrieve_context_node(
    qdrant_store: QdrantStore,
    embedding_client: EmbeddingClient,
    *,
    limit_per_query: int = 6,
) -> Callable[[LeaseGraphState], Awaitable[LeaseGraphState]]:
    async def retrieve_context(state: LeaseGraphState) -> LeaseGraphState:
        deal_id = state["deal_id"]
        tenant_name = state["tenant_name"]

        vectors = await embedding_client.embed_texts(list(_RETRIEVAL_QUERIES))
        seen: set[tuple[int, str]] = set()
        chunks: list[RetrievedChunk] = []

        for vector in vectors:
            hits = await qdrant_store.search(
                vector,
                deal_id=deal_id,
                tenant_name=tenant_name,
                limit=limit_per_query,
            )
            for hit in hits:
                key = (hit.page_number, hit.text)
                if key not in seen:
                    seen.add(key)
                    chunks.append(hit)

        chunks.sort(key=lambda c: (c.page_number, -c.score))
        return {"retrieved_chunks": chunks}

    return retrieve_context