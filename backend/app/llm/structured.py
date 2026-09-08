"""The single entry point for every model call.

Pipeline: cache lookup -> provider call -> Pydantic validation -> one repair
retry on failure -> telemetry row written either way.  Nothing else in the
application talks to a provider directly.
"""

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.exceptions import LLMOutputError
from app.llm.base import RenderedPrompt
from app.llm.cache import completion_cache, content_hash
from app.llm.provider import get_llm_provider
from app.llm.tokens import estimate_cost
from app.models import LLMCall

logger = logging.getLogger("cvcoach.llm")

T = TypeVar("T", bound=BaseModel)


def complete_structured(
    prompt: RenderedPrompt,
    schema: type[T],
    *,
    db: Session,
    session_id: int | None,
    model: str,
    temperature: float = 0.0,
) -> T:
    provider = get_llm_provider()
    cacheable = temperature == 0.0
    key = content_hash(provider.name, model, prompt.cache_key_material(),
                       json.dumps(prompt.payload, sort_keys=True, default=str))

    started = time.perf_counter()
    cache_hit = False
    raw: str | None = None

    if cacheable:
        raw = completion_cache.get(key)
        cache_hit = raw is not None

    prompt_tokens = completion_tokens = 0
    error: str | None = None

    try:
        if raw is None:
            response = provider.complete_json(
                prompt, schema, model=model, temperature=temperature
            )
            raw, prompt_tokens, completion_tokens = (
                response.text, response.prompt_tokens, response.completion_tokens
            )
            model = response.model or model

        try:
            result = schema.model_validate_json(raw)
        except ValidationError as first_error:
            # One repair attempt: hand the validation error back to the provider.
            logger.warning("Stage %s failed validation, retrying once: %s",
                           prompt.stage, first_error)
            repair = RenderedPrompt(
                stage=prompt.stage,
                version=prompt.version,
                system=prompt.system,
                user=(f"{prompt.user}\n\nYour previous output failed schema validation "
                      f"with:\n{first_error}\nReturn corrected JSON only."),
                payload=prompt.payload,
            )
            retry = provider.complete_json(repair, schema, model=model, temperature=temperature)
            prompt_tokens += retry.prompt_tokens
            completion_tokens += retry.completion_tokens
            try:
                result = schema.model_validate_json(retry.text)
            except ValidationError as second_error:
                raise LLMOutputError(
                    "The model returned data that does not match the expected schema.",
                    {"stage": prompt.stage, "problem": str(second_error)[:500]},
                ) from second_error
            raw = retry.text

        if cacheable and not cache_hit:
            completion_cache.set(key, raw)
        return result

    except LLMOutputError as exc:
        error = exc.message
        raise
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        db.add(LLMCall(
            session_id=session_id,
            stage=prompt.stage,
            provider=provider.name,
            model=model,
            prompt_version=prompt.version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
            latency_ms=round(elapsed, 2),
            cache_hit=cache_hit,
            status="error" if error else "ok",
            error=error,
        ))
        db.commit()
