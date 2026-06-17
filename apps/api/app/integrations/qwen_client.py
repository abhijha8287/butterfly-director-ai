from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.core.exceptions import ProviderUnavailableError

logger = get_logger(__name__)

_RETRYABLE_EXCEPTIONS = (httpx.TransportError, httpx.HTTPStatusError)
_CHAT_COMPLETIONS_PATH = "/compatible-mode/v1/chat/completions"


class QwenClient:
    """Real Qwen client via DashScope's OpenAI-compatible chat completions endpoint.

    Verified against https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.dashscope_base_url
        self._api_key = self._settings.dashscope_api_key

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        reraise=True,
    )
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY is not configured")

        body: dict[str, Any] = {
            "model": model or self._settings.qwen_model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(base_url=self._base_url, timeout=120.0) as client:
            response = await client.post(
                _CHAT_COMPLETIONS_PATH,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            return response.json()

    async def chat_text(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        response = await self.chat_completion(messages, **kwargs)
        return str(response["choices"][0]["message"]["content"])

    async def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        kwargs["json_mode"] = True
        text = await self.chat_text(messages, **kwargs)
        return json.loads(text)
