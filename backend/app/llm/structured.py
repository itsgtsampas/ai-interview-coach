"""The single entry point for every model call.

Pipeline: cache lookup -> provider call -> Pydantic validation -> one repair
retry on failure -> telemetry row written either way.  Nothing else in the
application talks to a provider directly.
"""

import json
import logging
import time
from collections.abc import Iterator
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlmodel import Session, select

from app.exceptions import BudgetExceeded, LLMOutputError
from app.llm.base import RenderedPrompt
from app.llm.cache import completion_cache, content_hash
from app.config import get_settings
from app.llm.provider import get_llm_provider
from app.llm.tokens import estimate_cost, estimate_tokens
from app.models import LLMCall

logger = logging.getLogger("cvcoach.llm")

T = TypeVar("T", bound=BaseModel)


def spent_usd(db: Session) -> float:
    """Everything this installation has spent, from the telemetry it already writes."""
    total = db.exec(select(func.coalesce(func.sum(LLMCall.cost_usd), 0.0))).one()
    return float(total or 0.0)


def check_budget(db: Session) -> None:
    """Refuse before the call, not after.

    Checked here because this module is the only thing that reaches a provider,
    so there is exactly one place money can leave — and one place to stop it.
    The stub is free, so its calls never consult this.
    """
    settings = get_settings()
    if settings.llm_provider == "stub" or settings.max_spend_usd <= 0:
        return
    spent = spent_usd(db)
    if spent >= settings.max_spend_usd:
        raise BudgetExceeded(
            f"This project has spent ${spent:.2f}, which is at or over the "
            f"${settings.max_spend_usd:.2f} ceiling. Raise MAX_SPEND_USD in .env "
            f"if that is intended.",
            {"spent_usd": round(spent, 4), "ceiling_usd": settings.max_spend_usd},
        )


def complete_structured(
    prompt: RenderedPrompt,
    schema: type[T],
    *,
    db: Session,
    session_id: int | None,
    model: str,
    temperature: float = 0.0,
) -> T:
    check_budget(db)
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


def complete_stream(
    prompt: RenderedPrompt,
    *,
    db: Session,
    session_id: int | None,
    model: str,
    temperature: float = 0.4,
) -> Iterator[str]:
    """Streaming counterpart of `complete_structured`.

    Same contract as the rest of this module: the provider is reached through
    here and nowhere else, and a telemetry row is written whatever happens. The
    difference is that the text is handed back in pieces as it is produced, and
    the caller is expected to be inside a `StreamingResponse`.

    Not cached. A cached stream would replay instantly, which is indistinguishable
    from the non-streaming path and would make the cost of this stage invisible
    in the telemetry — the two reasons to look at it at all.
    """
    check_budget(db)
    provider = get_llm_provider()
    started = time.perf_counter()
    parts: list[str] = []
    error: str | None = None

    try:
        for piece in provider.stream_text(prompt, model=model, temperature=temperature):
            parts.append(piece)
            yield piece
    except Exception as exc:  # noqa: BLE001 - recorded, re-raised
        error = str(exc)[:500]
        raise
    finally:
        text = "".join(parts)
        elapsed = (time.perf_counter() - started) * 1000
        completion_tokens = estimate_tokens(text)
        prompt_tokens = estimate_tokens(prompt.system + prompt.user)
        # Attribute the call to whoever actually served it. complete_structured
        # learns this from the response; a stream has no response object, so
        # without this the free stub was recorded as gpt-4o and priced at gpt-4o
        # rates — a telemetry row that was simply untrue, and phantom spend
        # counting against a real budget ceiling.
        served_by = f"stub:{prompt.stage}" if provider.name == "stub" else model
        db.add(LLMCall(
            session_id=session_id,
            stage=prompt.stage,
            provider=provider.name,
            model=served_by,
            prompt_version=prompt.version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=estimate_cost(served_by, prompt_tokens, completion_tokens),
            latency_ms=round(elapsed, 2),
            cache_hit=False,
            status="error" if error else "ok",
            error=error,
        ))
        db.commit()
