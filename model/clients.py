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


llm_router = ChatOpenAI(
    model=ROUTER_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=ROUTER_TEMPERATURE,
    timeout=MODEL_REQUEST_TIMEOUT_SEC,
    max_retries=MODEL_MAX_RETRIES,
)

llm_synthesizer = ChatOpenAI(
    model=SYNTHESIZER_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=SYNTHESIZER_TEMPERATURE,
    max_tokens=SYNTHESIZER_MAX_TOKENS,
    timeout=MODEL_REQUEST_TIMEOUT_SEC,
    max_retries=MODEL_MAX_RETRIES,
)
