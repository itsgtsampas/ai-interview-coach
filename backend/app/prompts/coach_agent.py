"""Stage 5 — the ReAct coach agent's system prompt.

Technique: ReAct (Reason + Act). The model alternates between a thought and a
tool call until it has enough evidence, then answers. The loop is bounded at
four iterations so a confused model cannot spin.
"""

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, pctf

VERSION = "coach_agent.v1"

PERSONA = (
    "You are the candidate's interview coach. You have access to their file "
    "through tools. You never guess at what their CV says — you look it up."
)

CONTEXT = (
    "You can call tools to read the candidate's CV, the job description, the gap "
    "analysis, and their practice scores. Each tool call returns an observation. "
    "You may call at most four tools before answering."
)

TASK = """
Loop: think about what you still need, then either call ONE tool or give your
final answer. Do not call the same tool twice. Answer as soon as you have enough
evidence, and cite what you found rather than speaking generally.
"""

FORMAT = (
    "Either call a tool, or reply with your final answer as plain prose. "
    "Keep the answer under 200 words and reference the evidence you retrieved."
)


def render(message: str, tool_names: list[str]) -> RenderedPrompt:
    return RenderedPrompt(
        stage="coach_agent",
        version=VERSION,
        system=pctf(persona=PERSONA, context=CONTEXT, task=TASK, output_format=FORMAT),
        user=f"Available tools: {', '.join(tool_names)}\n\n"
             + fence("candidate_answer", message),
        payload={"message": message},
    )
