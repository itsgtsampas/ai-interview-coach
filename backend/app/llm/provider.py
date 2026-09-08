"""Provider selection. One place decides which implementation the app uses."""

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.stub import StubLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    name = get_settings().llm_provider.lower()
    if name == "stub":
        return StubLLMProvider()
    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER {name!r}. Use 'stub' or 'openai'.")
