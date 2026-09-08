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
from app.llm.provider import get_llm_provider
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

    for _ in range(MAX_ITERATIONS):
        step = provider.plan_step(prompt, [t.spec for t in tools.values()], history)
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

    db.add(LLMCall(
        session_id=session_id,
        stage="coach_agent",
        provider=provider.name,
        model=f"{provider.name}:agent",
        prompt_version=coach_agent.VERSION,
        prompt_tokens=estimate_tokens(prompt.system + prompt.user),
        completion_tokens=estimate_tokens(answer),
        cost_usd=estimate_cost("stub", 0, 0),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        status="ok",
    ))
    db.commit()
    return CoachResult(answer=answer, steps=history)
