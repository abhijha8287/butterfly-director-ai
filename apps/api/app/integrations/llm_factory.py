from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config.settings import Settings, get_settings
from app.core.exceptions import ProviderUnavailableError

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def get_llm(settings: Settings | None = None, *, temperature: float = 0.7) -> ChatOpenAI:
    settings = settings or get_settings()
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ProviderUnavailableError("GEMINI_API_KEY is not configured")
        return ChatOpenAI(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
            base_url=_GEMINI_BASE_URL,
            temperature=temperature,
        )
    if not settings.dashscope_api_key:
        raise ProviderUnavailableError("DASHSCOPE_API_KEY is not configured")
    return ChatOpenAI(
        model=settings.qwen_model,
        api_key=settings.dashscope_api_key,
        base_url=f"{settings.dashscope_base_url}/compatible-mode/v1",
        temperature=temperature,
    )


def active_model_name(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return settings.gemini_model if settings.llm_provider == "gemini" else settings.qwen_model
