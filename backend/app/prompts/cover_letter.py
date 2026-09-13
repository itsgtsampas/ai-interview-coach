"""Stage 7 - a cover letter assembled only from evidenced claims.

Technique: PROMPT CHAINING with a grounding constraint. The letter is built from
the gap analysis, not from the CV directly, which means every sentence about the
candidate traces to a requirement that was marked `strong` and to the quote that
earned that mark. A requirement the CV did not evidence cannot appear as a
strength, by construction: it is never put in the prompt.

This is the same promise the rest of the product makes. A cover letter generator
that writes "I am deeply passionate about distributed systems" for someone whose
CV says nothing of the sort is the exact thing this application exists not to do.
"""

import json

from app.llm.base import RenderedPrompt
from app.prompts.blocks import json_only, pctf
from app.textutil import detect_language

VERSION = "cover_letter.v2"

TONES = {
    "plain": "Direct and unadorned. Short sentences. No adjectives about yourself.",
    "warm": "Human and specific, still concise. One sentence may say why the work interests you.",
    "formal": "Conventional business register, suitable for a bank or the public sector.",
}

PERSONA = (
    "You are the candidate, writing to a hiring manager who has thirty seconds. "
    "You write in first person, in plain British English, and you never claim "
    "anything you cannot point at."
)

CONTEXT = """
You are given the requirements the candidate's CV DOES evidence, each with the
exact sentence from the CV that evidenced it. You are also given the
requirements the CV does not evidence.

You may write about the evidenced list. You may not write about the unevidenced
list — not as a strength, not as an aspiration, not as "a keen interest in". If
the evidenced list is thin, the letter is short. A short honest letter is the
correct output; padding it is a failure.
"""

TASK = """
1. Opening: one sentence naming the role and the single strongest evidenced match.
2. Body: two short paragraphs. Each takes ONE evidenced requirement and states
   what the candidate did, drawn from the quoted sentence. Do not quote the CV
   verbatim - rewrite it as a claim in first person. Numbers already in the CV
   may be used; no new numbers.
3. If a must-have is unevidenced, write ONE honest sentence acknowledging the
   nearest adjacent experience. Do not apologise and do not dwell.
4. Close: one sentence proposing a conversation.
5. 180-250 words total. No "I am writing to apply for". No "passionate".
   No "dynamic". No "team player".
"""

# The streaming path asks for prose, not JSON. Streaming a stage whose FORMAT
# block demands "return ONLY a single JSON object" means streaming the JSON: the
# reader watches `{"subject": "...", "body": "...` appear character by character,
# and the whole object lands in the stored letter body.
FORMAT_PROSE = (
    "Return ONLY the letter itself, as plain paragraphs separated by blank "
    "lines. No JSON, no markdown, no subject line, no preamble and no sign-off "
    "block - just the body of the letter."
)

FORMAT = json_only(
    '{"subject": "...", "body": "the letter as plain paragraphs separated by '
    'blank lines", "claims_used": ["requirement text", ...]}'
)


def render(
    role: str,
    company: str,
    evidenced: list[dict],
    unevidenced: list[str],
    tone: str = "plain",
    *,
    streaming: bool = False,
) -> RenderedPrompt:
    return RenderedPrompt(
        stage="cover_letter",
        version=VERSION,
        system=pctf(
            persona=PERSONA,
            context=CONTEXT + f"\n\nTone for this letter: {TONES.get(tone, TONES['plain'])}",
            task=TASK,
            output_format=FORMAT_PROSE if streaming else FORMAT,
            language=detect_language(json.dumps(evidenced, ensure_ascii=False)),
        ),
        user=(
            f"Role: {role or 'the advertised role'}\n"
            f"Company: {company or 'the company'}\n\n"
            "Requirements your CV evidences, with the sentence that earned each:\n"
            + json.dumps(evidenced, ensure_ascii=False, indent=2)[:5000]
            + "\n\nRequirements your CV does NOT evidence (never present these as "
              "strengths):\n"
            + json.dumps(unevidenced, ensure_ascii=False)[:1500]
        ),
        payload={
            "role": role,
            "company": company,
            "evidenced": evidenced,
            "unevidenced": unevidenced,
            "tone": tone,
        },
    )
