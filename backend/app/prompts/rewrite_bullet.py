"""Stage 6 - turn one unmet requirement into a CV bullet the candidate can adapt.

Technique: FEW-SHOT with a negative example. The failure mode here is not a
badly written bullet, it is a *fabricated* one: a model asked to "fix the gap"
will happily write "Led migration of 40 microservices to Kubernetes" for someone
who has never touched Kubernetes. That output looks excellent and would get the
candidate caught in the first ten minutes of a technical screen.

So the contract is inverted. The model does not write a claim; it writes a
SHAPE, with the candidate's own facts left as explicit [placeholders]. The
few-shot examples teach the placeholder discipline, and the third example is a
negative one showing the invented version being rejected.
"""

import json

from app.llm.base import RenderedPrompt
from app.prompts.blocks import fence, json_only, pctf

VERSION = "rewrite_bullet.v1"

PERSONA = (
    "You are a CV editor who has screened thousands of engineering CVs. You know "
    "that the bullets which survive a recruiter's six-second scan lead with the "
    "outcome, name the technology, and carry a number. You never write a claim "
    "the candidate has not made."
)

CONTEXT = """
One requirement from a job description is unmet or thinly evidenced by this
candidate's CV. You are given the requirement, the verdict, and whatever the CV
does say nearby.

You are NOT being asked whether the candidate has this skill. You are writing
the bullet they would use IF they have it, so they can either fill it in or
recognise that they cannot — which is itself useful information.
"""

TASK = """
1. Decide the honest premise. If the CV shows adjacent evidence, the bullet
   should build on that evidence and reference it. If the CV shows nothing at
   all, say so in `premise` and write a bullet that only works if the candidate
   supplies real experience.
2. Write ONE bullet, at most 30 words, in this shape:
   <action verb> <what> using <technology> — <measurable outcome>.
3. Every fact you do not have must appear as a [square-bracket placeholder]
   naming what the candidate must supply, e.g. [number of services],
   [latency before -> after]. Never guess a number. Never invent a project.
4. If `CV evidence` is "none", the WORK ITSELF is a fact you do not have, so it
   must be a placeholder too — not only the outcome. "Designed and implemented a
   document storage solution using Couchbase, achieving [number]% faster reads"
   is a REJECTED answer: it states as done a thing this candidate has never
   done, and the placeholder on the outcome does not rescue it. Write
   "Built [what you built] on Couchbase, [outcome]" instead. A bullet with a
   placeholder only in its outcome is the failure this rule exists to stop.
5. In `why`, state in one sentence what this bullet proves to the screener.
6. In `if_you_cannot`, give the honest alternative for a candidate who has no
   such experience: the smallest real thing that would earn this bullet.
"""

EXAMPLES = """
Requirement: "Experience with Kubernetes in production"
CV evidence: "Deployed services with Docker Compose on a single VM"
GOOD -> bullet: "Migrated [number] Dockerised services to Kubernetes, cutting
deploy time from [before] to [after]."
  premise: "Your CV shows Docker but not orchestration, so this builds on it."
  if_you_cannot: "Run your existing Compose stack on k3s locally and write that up."

Requirement: "Experience with Kubernetes in production"
CV evidence: none
BAD -> bullet: "Led the migration of 40 microservices to a multi-region
Kubernetes cluster, reducing p99 latency by 45%."
  Why this is rejected: the candidate never said any of this. The numbers, the
  scale and the outcome are all invented, and the first follow-up question in
  the interview exposes it.
"""

FORMAT = json_only(
    '{"bullet": "...", "premise": "...", "why": "...", "if_you_cannot": "...", '
    '"placeholders": ["[number of services]", ...]}'
)


def render(requirement: str, status: str, evidence: str | None, cv_context: str) -> RenderedPrompt:
    return RenderedPrompt(
        stage="rewrite_bullet",
        version=VERSION,
        system=pctf(
            persona=PERSONA,
            context=CONTEXT + "\n\nWorked examples:\n" + EXAMPLES,
            task=TASK,
            output_format=FORMAT,
        ),
        user=(
            f"Requirement: {requirement}\n"
            f"Current verdict: {status}\n"
            f"Sentence the CV offered: {evidence or 'none'}\n\n"
            + fence("cv_context", cv_context[:3000])
        ),
        payload={
            "requirement": requirement,
            "status": status,
            "evidence": evidence,
            "cv_context": cv_context,
        },
    )
