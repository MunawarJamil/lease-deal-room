from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.exceptions import VectorStoreError


class EmbeddingClient:
    """Thin async wrapper around an OpenAI-compatible embedding provider."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.resolved_embedding_api_key
        self._base_url = base_url if base_url is not None else settings.embedding_base_url
        self._model = model or settings.embedding_model
        self._dimensions = dimensions or settings.embedding_dimensions
        if not self._api_key:
            raise VectorStoreError("EMBEDDING_API_KEY (or LLM_API_KEY / OPENAI_API_KEY) is required")
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url or None,
        )

    @property
    def vector_size(self) -> int:
        return self._dimensions

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