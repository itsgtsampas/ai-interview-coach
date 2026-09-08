"""Stage 3 — score a candidate's answer against an explicit rubric.

Techniques:
  - FEW-SHOT CALIBRATION: two anchor answers pin what a 2 and a 4 look like.
    Without anchors, models drift upward and score almost everything 4.
  - CHAIN-OF-THOUGHT: the reasoning field is produced BEFORE the scores, so the
    verdict follows the analysis instead of the analysis rationalising a guess.
  - RUBRIC: STAR for behavioural answers, a five-part technical rubric otherwise.
    (Note: PCTF builds this prompt; PCTF is not itself the scoring rubric.)
"""

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf

VERSION = "evaluate_answer.v4"

PERSONA = (
    "You are an interview coach who has debriefed hundreds of real interview "
    "loops. You are constructive but you do not inflate scores: a 3 means "
    "adequate, and most first attempts are a 3."
)

CONTEXT = (
    "You are given one interview question, the requirement it was asked against, "
    "and the candidate's answer. Score only what the answer actually contains. "
    "Do not credit the candidate for things you assume they know."
)

ANCHORS = """
Calibration anchors — match these standards exactly.

An answer scoring 2 on Result:
"We improved the performance quite a lot and everyone was happy with the outcome."
Why 2: asserts an outcome, gives no measurement, no baseline, no timeframe.

An answer scoring 4 on Result:
"p99 went from 840ms to 210ms over three weeks, measured on the same dashboard
we had before the change; the on-call pages for that service stopped entirely."
Why 4: baseline, target, instrument and a second-order consequence. It is a 4
rather than a 5 because it does not say whether the gain held after launch.
"""

TASK = """
1. Write your analysis FIRST, in the reasoning field, as numbered observations:
   shape and length, then each rubric dimension in turn, citing what is present
   or absent in the answer. Quote short fragments of the answer as you go.
2. THEN score each rubric dimension 1-5, consistent with what you just wrote.
   - Behavioural answers use: Situation, Task, Action, Result, Impact.
   - Technical answers use: Correctness, Depth, Trade-offs, Communication, Relevance.
3. Compute overall_score as the mean of the dimensions, to one decimal place.
4. List up to three strengths and up to three improvements. Improvements must be
   actionable rewrites, not restatements of the score.
5. Write a model_answer describing the shape a top answer would take here.
6. Write one follow_up_question targeting the LOWEST-scoring dimension - the
   question a real interviewer would ask next to probe that weakness.
"""

FORMAT = json_only(
    '{"rubric": "star"|"technical", "reasoning": "<numbered observations>", '
    '"criteria": [{"name": "...", "score": 1-5, "comment": "..."}], '
    '"overall_score": 1.0-5.0, "strengths": [...], "improvements": [...], '
    '"model_answer": "...", "follow_up_question": "..."}'
)


def render(question: str, answer_text: str, rubric: str, linked_requirement: str) -> RenderedPrompt:
    return RenderedPrompt(
        stage="evaluate_answer",
        version=VERSION,
        system=pctf(
            persona=PERSONA,
            context=CONTEXT + "\n" + ANCHORS,
            task=TASK,
            output_format=FORMAT,
        ),
        user=(
            f"Rubric to apply: {rubric}\n"
            f"Requirement this was asked against: {linked_requirement or 'general competency'}\n"
            f"Question: {question}\n\n" + fence("candidate_answer", answer_text)
        ),
        payload={
            "question": question,
            "answer_text": answer_text,
            "rubric": rubric,
            "linked_requirement": linked_requirement,
        },
    )
