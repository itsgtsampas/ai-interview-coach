"""Money: what gets billed, and what stops it.

Switching LLM_PROVIDER to a real provider puts a credit card behind every one of
these calls, so the accounting has to be right before the key goes in.
"""

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.exceptions import BudgetExceeded
from app.llm.structured import check_budget, spent_usd
from app.models import LLMCall
from tests.test_pipeline import STRONG_ANSWER, ready_session  # noqa: F401


def test_the_stub_is_never_billed(auth_client, ready_session):  # noqa: F811
    """A free provider must not be recorded as a paid model.

    complete_stream has no response object to learn the model from, so it used
    the one it was asked for — recording the stub as gpt-4o and pricing it at
    gpt-4o rates. That is a false telemetry row, and it was phantom spend
    counting against a real ceiling.
    """
    sid = ready_session
    auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    with auth_client.stream(
        "POST", f"/api/v1/sessions/{sid}/cover-letter/stream", json={"tone": "plain"},
    ) as r:
        assert r.status_code == 200
        "".join(r.iter_text())

    with Session(engine) as db:
        rows = db.exec(select(LLMCall).where(LLMCall.provider == "stub")).all()
        assert rows, "the run should have written telemetry"
        for row in rows:
            assert row.cost_usd == 0.0, f"{row.stage} billed {row.cost_usd} for a free call"
            assert row.model.startswith("stub:"), (
                f"{row.stage} recorded model={row.model!r}, which did not serve it"
            )


def test_every_priced_model_has_a_rate():
    """A model missing from the table is silently free, which hides real spend."""
    from app.llm.tokens import PRICING_USD_PER_1M

    settings = get_settings()
    for model in (settings.openai_chat_model_large, settings.openai_chat_model_small,
                  settings.openai_embedding_model):
        assert model in PRICING_USD_PER_1M, f"{model} has no price, so it bills as 0"


def test_the_ceiling_refuses_once_it_is_reached(monkeypatch):
    """The guard reads real telemetry, so the test writes some."""
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "max_spend_usd", 0.01)

    with Session(engine) as db:
        before = spent_usd(db)
        db.add(LLMCall(stage="test", provider="openai", model="gpt-4o-mini",
                       cost_usd=0.02, status="ok"))
        db.commit()
        try:
            with pytest.raises(BudgetExceeded) as caught:
                check_budget(db)
            assert "ceiling" in caught.value.message
            assert caught.value.status_code == 402
            assert caught.value.details["spent_usd"] >= 0.02
        finally:
            row = db.exec(
                select(LLMCall).where(LLMCall.stage == "test").order_by(LLMCall.id.desc())
            ).first()
            db.delete(row)
            db.commit()
            assert abs(spent_usd(db) - before) < 1e-9


def test_the_stub_is_never_gated_by_the_ceiling():
    """The stub costs nothing, so a ceiling must not block an offline run."""
    settings = get_settings()
    assert settings.llm_provider == "stub"
    with Session(engine) as db:
        check_budget(db)  # must not raise whatever the ceiling is
