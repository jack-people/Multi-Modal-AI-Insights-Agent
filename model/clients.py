from __future__ import annotations

from typing import Any, Callable

from langchain_openai import ChatOpenAI

from .settings import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    ROUTER_MODEL,
    SYNTHESIZER_MODEL,
    ROUTER_TEMPERATURE,
    SYNTHESIZER_TEMPERATURE,
    SYNTHESIZER_MAX_TOKENS,
    MODEL_REQUEST_TIMEOUT_SEC,
    MODEL_MAX_RETRIES,
)


class _LazyChatOpenAI:
    """Construct ChatOpenAI on first use so import does not require credentials."""

    def __init__(self, factory: Callable[[], ChatOpenAI]) -> None:
        self._factory = factory
        self._client: ChatOpenAI | None = None

    def _get(self) -> ChatOpenAI:
        if self._client is None:
            if not DEEPSEEK_API_KEY:
                raise RuntimeError("缺少 DEEPSEEK_API_KEY")
            self._client = self._factory()
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


llm_router = _LazyChatOpenAI(
    lambda: ChatOpenAI(
        model=ROUTER_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=ROUTER_TEMPERATURE,
        timeout=MODEL_REQUEST_TIMEOUT_SEC,
        max_retries=MODEL_MAX_RETRIES,
    )
)

llm_synthesizer = _LazyChatOpenAI(
    lambda: ChatOpenAI(
        model=SYNTHESIZER_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=SYNTHESIZER_TEMPERATURE,
        max_tokens=SYNTHESIZER_MAX_TOKENS,
        timeout=MODEL_REQUEST_TIMEOUT_SEC,
        max_retries=MODEL_MAX_RETRIES,
    )
)
