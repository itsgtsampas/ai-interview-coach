"""Stage 2 — generate interview questions from the match report.

Technique: FEW-SHOT. Question *style* cannot be specified in prose — the three
exemplars below pin the register (specific, evidence-anchored, uncomfortable
where it should be) far more reliably than adjectives would.
"""

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf

VERSION = "generate_questions.v2"

PERSONA = (
    "You are the hiring manager who will actually run this interview. You ask "
    "questions that are specific to this candidate's file, not questions you "
    "could ask anyone."
)

CONTEXT = (
    "You have the gap analysis between this candidate's CV and the job "
    "description. Each item carries a status and, where evidence exists, the "
    "verbatim sentence it came from. Anchor technical questions in that evidence."
)

EXEMPLARS = """
Example 1 — requirement with status "missing":
{"category": "technical",
 "text": "The role requires production experience with Kubernetes. I can't find it anywhere in your CV. How would you get productive with it in your first month, and what part do you expect to find hardest?",
 "rationale": "Asked because the job description lists this as a must have and you have no evidence for it.",
 "difficulty": 4}

Example 2 — requirement with status "partial":
{"category": "technical",
 "text": "Your CV touches event-driven architecture - you wrote \\"used RabbitMQ for order events\\". Take that further: what would have broken first if the load had been ten times higher?",
 "rationale": "Asked because your evidence is thin and an interviewer will probe its depth.",
 "difficulty": 3}

Example 3 — behavioural:
{"category": "behavioural",
 "text": "Tell me about a time you disagreed with a technical decision your team had already committed to. What did you do, and how did it end?",
 "rationale": "Probes influence and disagreement, which a CV cannot evidence.",
 "difficulty": 3}
"""

TASK = """
1. Order the requirements so the riskiest come first: missing before partial
   before strong, and must_have before nice_to_have.
2. Write one technical question per requirement, in that order, following the
   exemplars. Quote the candidate's own words where evidence exists.
3. Write the requested number of behavioural questions. These must target
   competencies a CV cannot evidence, not restate the requirements.
4. Give every question a rationale that tells the candidate why it is being
   asked of them specifically.
5. Set difficulty 1-5: unevidenced requirements are harder than evidenced ones.
"""

FORMAT = json_only(
    '{"questions": [{"category": "technical"|"behavioural", "text": "...", '
    '"rationale": "...", "difficulty": 1-5, "linked_requirement": "..."}]}'
)


def render(items: list[dict], target_role: str, n_technical: int, n_behavioural: int) -> RenderedPrompt:
    summary = "\n".join(
        f"- [{i['status']}/{i['category']}] {i['requirement']}"
        + (f'\n    evidence: "{i["evidence_quote"]}"' if i.get("evidence_quote") else "")
        for i in items
    )
    return RenderedPrompt(
        stage="generate_questions",
        version=VERSION,
        system=pctf(
            persona=PERSONA,
            context=CONTEXT + "\n\nExemplars showing the required register:\n" + EXEMPLARS,
            task=TASK,
            output_format=FORMAT,
        ),
        user=(
            f"Target role: {target_role or 'unspecified'}\n"
            f"Write {n_technical} technical and {n_behavioural} behavioural questions.\n\n"
            + fence("retrieved_evidence", summary)
        ),
        payload={
            "items": items,
            "target_role": target_role,
            "n_technical": n_technical,
            "n_behavioural": n_behavioural,
        },
    )
