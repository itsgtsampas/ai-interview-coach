"""Stage 4 — aggregate the whole session into a readiness scorecard.

Technique: PROMPT CHAINING. This stage consumes only the structured outputs of
stages 1-3; it never re-reads the CV. That keeps the chain auditable — every
number here traces to a stored row.
"""

import json

from app.llm.base import RenderedPrompt
from app.prompts.blocks import json_only, pctf

VERSION = "build_scorecard.v1"

PERSONA = (
    "You are the interviewer writing the debrief note after a loop. You are "
    "direct about what would stop this candidate getting an offer."
)

CONTEXT = (
    "You have the CV-to-role gap analysis and the scored evaluation of every "
    "practice answer. You are not re-reading the CV; work only from these."
)

TASK = """
1. Compute readiness_score 0-100: weight the CV match 40% and the mean answer
   score 60%. If there are no answers yet, use the CV match alone.
2. Assign a band: 75+ "Interview ready", 55-74 "Nearly ready",
   35-54 "Needs work", below 35 "Not ready yet".
3. Average each rubric dimension across all answers into competencies.
4. List strengths and gaps, drawing on both the CV analysis and the answer scores.
5. Write action items, highest priority first. A missing must_have requirement is
   always high priority. Each needs a why (what it costs them) and a how (the
   concrete next action).
6. Write a summary of three sentences that a candidate could act on tonight.
"""

FORMAT = json_only(
    '{"readiness_score": 0-100, "readiness_band": "...", "summary": "...", '
    '"competencies": {"<dimension>": <mean 1-5>}, "strengths": [...], "gaps": [...], '
    '"action_items": [{"priority": "high"|"medium"|"low", "title": "...", '
    '"why": "...", "how": "..."}]}'
)


def render(report: dict, evaluations: list[dict]) -> RenderedPrompt:
    return RenderedPrompt(
        stage="build_scorecard",
        version=VERSION,
        system=pctf(persona=PERSONA, context=CONTEXT, task=TASK, output_format=FORMAT),
        user=(
            "Gap analysis:\n"
            + json.dumps(report, ensure_ascii=False, indent=2)[:6000]
            + "\n\nScored answers:\n"
            + json.dumps(evaluations, ensure_ascii=False, indent=2)[:6000]
        ),
        payload={"report": report, "evaluations": evaluations},
    )
