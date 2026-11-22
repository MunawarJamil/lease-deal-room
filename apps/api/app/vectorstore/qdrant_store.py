import uuid

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.core.exceptions import VectorStoreError
from app.parsing.chunker import DocumentChunk


class RetrievedChunk(BaseModel):
    deal_id: str
    tenant_name: str
    file_name: str
    page_number: int
    text: str
    score: float


def _chunk_point_id(chunk: DocumentChunk) -> str:
    key = f"{chunk.deal_id}:{chunk.tenant_name}:{chunk.file_name}:{chunk.page_number}:{chunk.chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class QdrantStore:
    """Single-collection Qdrant wrapper with mandatory deal_id + tenant_name isolation."""

    def __init__(self, *, url: str | None = None, collection_name: str | None = None) -> None:
        settings = get_settings()
        self._collection = collection_name or settings.qdrant_collection
        self._client = AsyncQdrantClient(url=url or settings.qdrant_url)

    async def close(self) -> None:
        await self._client.close()

    async def ensure_collection(self, vector_size: int = 1536) -> None:
        try:
            exists = await self._client.collection_exists(self._collection)
            if not exists:
                await self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
            for field in ("deal_id", "tenant_name"):
                await self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        except Exception as exc:
            raise VectorStoreError(f"Failed to ensure Qdrant collection: {exc}") from exc

    async def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> int:
        if len(chunks) != len(vectors):
            raise VectorStoreError("Chunks and vectors length mismatch")
        if not chunks:
            return 0

        points = [
            models.PointStruct(
                id=_chunk_point_id(chunk),
                vector=vector,
                payload={
                    "deal_id": chunk.deal_id,
                    "tenant_name": chunk.tenant_name,
                    "file_name": chunk.file_name,
                    "page_number": chunk.page_number,
                    "text": chunk.text,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        try:
            await self._client.upsert(collection_name=self._collection, points=points)
            return len(points)
        except Exception as exc:
            raise VectorStoreError(f"Failed to upsert chunks to Qdrant: {exc}") from exc

    async def search(
        self,
        query_vector: list[float],
        *,
        deal_id: str,
        tenant_name: str,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        """Search chunks strictly filtered by deal_id and tenant_name."""
        if not deal_id or not tenant_name:
            raise VectorStoreError("Both deal_id and tenant_name are required for retrieval")

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="deal_id",
                    match=models.MatchValue(value=deal_id),
                ),
                models.FieldCondition(
                    key="tenant_name",
                    match=models.MatchValue(value=tenant_name),
                ),
            ]
        )

        try:
            response = await self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"Qdrant search failed: {exc}") from exc

        results: list[RetrievedChunk] = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                RetrievedChunk(
                    deal_id=str(payload["deal_id"]),
                    tenant_name=str(payload["tenant_name"]),
                    file_name=str(payload["file_name"]),
                    page_number=int(payload["page_number"]),
                    text=str(payload["text"]),
                    score=float(point.score),
                )
            )
        return results

    async def delete_lease_chunks(self, *, deal_id: str, tenant_name: str) -> None:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(key="deal_id", match=models.MatchValue(value=deal_id)),
                models.FieldCondition(
                    key="tenant_name", match=models.MatchValue(value=tenant_name)
                ),
            ]
        )
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=models.FilterSelector(filter=query_filter),
            )
        except Exception as exc:
            raise VectorStoreError(f"Failed to delete lease chunks: {exc}") from exc