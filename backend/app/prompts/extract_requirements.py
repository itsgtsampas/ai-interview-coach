"""Stage 1a — pull discrete requirements out of a job description.

Technique: ZERO-SHOT. Extraction against a fixed schema is well specified in
words; exemplars would add tokens without adding accuracy. This is also the
baseline the eval harness compares few-shot variants against.
"""

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf

VERSION = "extract_requirements.v2"

PERSONA = (
    "You are a technical recruiter who has screened several thousand engineering "
    "job descriptions. You separate what a role actually requires from the "
    "boilerplate that appears in every posting."
)

CONTEXT = (
    "You are given the full text of one job description. It may contain company "
    "marketing, benefits and legal text that are not requirements."
)

TASK = """
Work through these steps:
1. Locate the sections that state what the candidate must be or have.
2. Extract each distinct requirement as one self-contained sentence.
3. Discard benefits, salary, company description and equal-opportunity text.
4. Merge duplicates that differ only in wording.
5. Label each as must_have or nice_to_have. Wording such as "required",
   "strong", "proven", "must" indicates must_have; "nice to have", "bonus",
   "a plus", "preferred" indicates nice_to_have.
Return at most 12 requirements, most important first.
"""

FORMAT = json_only(
    '{"requirements": [{"text": "<one sentence>", '
    '"category": "must_have" | "nice_to_have"}]}'
)


def render(jd_text: str) -> RenderedPrompt:
    return RenderedPrompt(
        stage="extract_requirements",
        version=VERSION,
        system=pctf(persona=PERSONA, context=CONTEXT, task=TASK, output_format=FORMAT),
        user=fence("job_description", jd_text),
        payload={"jd_text": jd_text},
    )
