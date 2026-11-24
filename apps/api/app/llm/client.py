import re
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.exceptions import LLMError

T = TypeVar("T", bound=BaseModel)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _extract_json_payload(raw_text: str) -> str:
    """Strip markdown code fences and isolate the outer JSON object if needed."""
    cleaned = _JSON_FENCE_RE.sub("", raw_text.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


class LLMClient:
    """Thin async LLM wrapper (OpenRouter / OpenAI compatible; swappable in one place)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self._provider = provider or settings.llm_provider
        self._api_key = api_key or settings.resolved_llm_api_key
        self._base_url = base_url if base_url is not None else settings.llm_base_url
        self._model = model or settings.llm_model
        if not self._api_key:
            raise LLMError("LLM_API_KEY (or OPENAI_API_KEY) is required")
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url or None,
        )

    async def extract_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call the configured LLM and validate its JSON response against a Pydantic model."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            raise LLMError(f"LLM completion failed ({self._provider}/{self._model}): {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMError("LLM returned an empty response")

        payload = _extract_json_payload(content)
        try:
            return response_model.model_validate_json(payload)
        except ValidationError as exc:
            raise LLMError(f"LLM output failed schema validation: {exc}") from exc