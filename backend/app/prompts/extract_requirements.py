"""Stage 1a — pull discrete requirements out of a job description.

Version history
---------------
v4  The `kind` field was in the contract and in the model layer from the start,
    but this prompt never asked for it: neither the task nor the format block
    mentioned it, so the model never emitted one and the contract default made
    every requirement "evidenceable". The distinction worked only under the
    deterministic provider, which classifies by rule, and stopped silently when
    a real model took over. A real posting was scored 55/100 with "keen to
    constantly learn and improve your own skills" counted as a missing
    requirement — exactly the penalty this field exists to prevent.

Technique: ZERO-SHOT. Extraction against a fixed schema is well specified in
words; exemplars would add tokens without adding accuracy. This is also the
baseline the eval harness compares few-shot variants against.
"""

import json

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf
from app.textutil import detect_language

VERSION = "extract_requirements.v4"

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
6. Label each as evidenceable or behavioural, by asking one question: COULD A CV
   SHOW THIS AT ALL?
   - evidenceable: a CV can demonstrate it. Technologies, years of experience,
     degrees, named systems, measurable outcomes, ways of working a CV can state
     ("worked in a Scrum team", "mentored juniors").
   - behavioural: no CV can demonstrate it, only an interview can. Character and
     disposition — "self-motivated", "keen to learn", "excellent eye for detail",
     "passionate", "team player", "thrives under pressure".
   This is not about whether THIS candidate has it. It is about whether the
   document type can carry the evidence. Marking a disposition as evidenceable
   penalises the candidate for a limitation of the medium, so when a requirement
   mixes both — "strong communication skills (English is a must)" — split it if
   each half stands alone, and otherwise label it behavioural.
Return at most 12 requirements, most important first.
"""

FORMAT = json_only(
    '{"requirements": [{"text": "<one sentence>", '
    '"category": "must_have" | "nice_to_have", '
    '"kind": "evidenceable" | "behavioural"}]}'
)


def render(jd_text: str) -> RenderedPrompt:
    return RenderedPrompt(
        stage="extract_requirements",
        version=VERSION,
        system=pctf(persona=PERSONA, context=CONTEXT, task=TASK,
                    output_format=FORMAT,
                    language=detect_language(jd_text)),
        user=fence("job_description", jd_text),
        payload={"jd_text": jd_text},
    )
