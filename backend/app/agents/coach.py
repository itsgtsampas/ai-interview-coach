"""The ReAct loop.

    think -> act (call a tool) -> observe -> think ... -> answer

Bounded at MAX_ITERATIONS so a confused model cannot spin, and the full step
trace is returned to the UI: the user can see which tools were consulted and
what came back, rather than trusting an opaque answer.
"""

import time
from dataclasses import dataclass

from sqlmodel import Session

from app.agents.tools import build_tools
from app.llm.base import AgentStep
from app.config import get_settings
from app.llm.provider import get_llm_provider
from app.llm.structured import check_budget
from app.llm.tokens import estimate_cost, estimate_tokens
from app.models import LLMCall
from app.prompts import coach_agent

MAX_ITERATIONS = 4


@dataclass
class CoachResult:
    answer: str
    steps: list[AgentStep]


def ask(message: str, *, user_id: int, session_id: int, db: Session) -> CoachResult:
    provider = get_llm_provider()
    tools = build_tools(user_id=user_id, session_id=session_id, db=db)
    prompt = coach_agent.render(message, list(tools))

    history: list[AgentStep] = []
    answer = "I could not gather enough information to answer that."
    started = time.perf_counter()
    prompt_tokens = completion_tokens = 0

    for _ in range(MAX_ITERATIONS):
        # The only provider call that bypasses complete_structured, so the
        # ceiling is enforced here — every iteration, not just on entry.
        check_budget(db)
        step = provider.plan_step(prompt, [t.spec for t in tools.values()], history)
        prompt_tokens += step.prompt_tokens
        completion_tokens += step.completion_tokens
        if step.final_answer:
            answer = step.final_answer
            history.append(step)
            break
        if step.tool and step.tool in tools:
            try:
                step.observation = tools[step.tool].run(step.tool_input or {})
            except Exception as exc:  # noqa: BLE001 - a failing tool must not kill the loop
                step.observation = f"That lookup failed: {exc}"
            history.append(step)
        else:
            history.append(AgentStep(
                thought=step.thought,
                observation=f"No such tool: {step.tool}",
            ))

    # Bill the model that actually served the loop, summing every iteration.
    model = (
        f"stub:{coach_agent.VERSION}" if provider.name == "stub"
        else get_settings().openai_chat_model_large
    )
    if not prompt_tokens:  # the stub reports no usage
        prompt_tokens = estimate_tokens(prompt.system + prompt.user)
        completion_tokens = estimate_tokens(answer)

    db.add(LLMCall(
        session_id=session_id,
        stage="coach_agent",
        provider=provider.name,
        model=model,
        prompt_version=coach_agent.VERSION,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        status="ok",
    ))
    db.commit()
    return CoachResult(answer=answer, steps=history)
