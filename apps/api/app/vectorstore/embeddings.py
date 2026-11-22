from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.exceptions import VectorStoreError

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class EmbeddingClient:
    """Thin async wrapper around the embedding provider."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.embedding_model
        if not self._api_key:
            raise VectorStoreError("OPENAI_API_KEY is required for embeddings")
        self._client = AsyncOpenAI(api_key=self._api_key)

    @property
    def vector_size(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1536)

    async def embed_texts(self, texts: list[str], *, batch_size: int = 100) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors: list[list[float]] = []
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                response = await self._client.embeddings.create(model=self._model, input=batch)
                vectors.extend(item.embedding for item in response.data)
            return vectors
        except Exception as exc:
            raise VectorStoreError(f"Embedding generation failed: {exc}") from exc

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]