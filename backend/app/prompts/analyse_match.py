"""Stage 1b — judge each requirement against evidence retrieved from the CV.

Techniques: CHAIN-OF-THOUGHT (reason before verdict), RAG CONTEXT INJECTION,
and a hard GROUNDING rule — no verbatim quote means the verdict is "missing".
That rule is enforced again in code by the citation verifier.
"""

import json

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf
from app.textutil import detect_language

VERSION = "analyse_match.v4"

PERSONA = (
    "You are a senior hiring manager with twelve years of experience screening "
    "engineering candidates. You are rigorous and specific. You never inflate a "
    "verdict to be encouraging, and you never claim the CV says something it "
    "does not."
)

CONTEXT = (
    "For each job requirement you are given the passages retrieved from the "
    "candidate's CV that are most similar to it. These passages are the ONLY "
    "evidence you may use. You have not seen the rest of the CV."
)

TASK = """
For each requirement, in order:
1. Read the retrieved passages and decide what the candidate has actually done,
   as opposed to what they have merely named.
2. Write your reasoning first, in one or two sentences.
3. Only then assign a status:
   - "strong"  : a passage shows concrete work on this requirement.
   - "partial" : related material exists but does not show depth or scale.
   - "missing" : no passage supports it.
4. If the status is "strong" or "partial", copy ONE sentence from the passages
   VERBATIM as evidence_quote, and carry over its page and chunk id unchanged.
   If you cannot find such a sentence, the status is "missing".
5. Give a confidence between 0 and 1.
Finally, produce an overall score from 0 to 100, weighting must_have
requirements twice as heavily as nice_to_have, and a two-sentence summary that
names the gaps that will cost the candidate most.
"""

FORMAT = json_only(
    '{"overall_score": 0-100, "verdict": "<short phrase>", "summary": "<2 sentences>", '
    '"items": [{"requirement": "...", "category": "must_have"|"nice_to_have", '
    '"status": "strong"|"partial"|"missing", "confidence": 0.0-1.0, '
    '"reasoning": "...", "evidence_quote": "<verbatim or null>", '
    '"evidence_page": <int or null>, "evidence_chunk_id": "<id or null>", '
    '"evidence_section": "<section or null>"}]}'
)


def render(requirements: list[dict], evidence: dict[str, list[dict]]) -> RenderedPrompt:
    blocks = []
    for idx, req in enumerate(requirements):
        passages = evidence.get(str(idx), [])
        rendered = "\n".join(
            f"  [chunk {p['chunk_id']} | section: {p.get('section') or 'unknown'} "
            f"| page {p.get('page')}]\n  {p['text']}"
            for p in passages
        ) or "  (no passage passed the relevance floor)"
        blocks.append(
            f"REQUIREMENT {idx} ({req.get('category', 'must_have')}): {req['text']}\n{rendered}"
        )
    return RenderedPrompt(
        stage="analyse_match",
        version=VERSION,
        system=pctf(persona=PERSONA, context=CONTEXT, task=TASK,
                    output_format=FORMAT,
                    language=detect_language(json.dumps(evidence, ensure_ascii=False))),
        user=fence("retrieved_evidence", "\n\n".join(blocks)),
        payload={"requirements": requirements, "evidence": evidence},
    )
