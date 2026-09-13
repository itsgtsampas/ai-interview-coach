"""Provider selection. One place decides which implementation the app uses.

The product runs on the OpenAI API. The deterministic provider is a test double:
it keeps the suite free and reproducible, and the eval harness uses it to
measure retrieval and prompt changes without a model in the loop. Selecting it
outside those two contexts is a configuration mistake, and is logged as one.
"""

import logging
from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.stub import StubLLMProvider


logger = logging.getLogger("cvcoach.llm")


@lru_cache
def get_llm_provider() -> LLMProvider:
    name = get_settings().llm_provider.lower()
    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "stub":
        # Loud, because a deployment that quietly answers from rules instead of
        # a model looks like it is working right up until someone checks a
        # citation. Earlier this was the default; now it has to be asked for.
        logger.warning(
            "LLM_PROVIDER=stub — using the deterministic test double, NOT the "
            "OpenAI API. Correct for tests and evals; wrong for running the app."
        )
        return StubLLMProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER {name!r}. Use 'openai' to run the application, "
        f"or 'stub' for the offline test double."
    )
