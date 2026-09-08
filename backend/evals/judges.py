"""Relevance judging — is a citation actually evidence for the requirement it is attached to?

citation_validity only proves a quote is real. It cannot tell whether a real
sentence was attached to the wrong requirement, which is a distinct and more
subtle failure. That judgement needs a judge.

Two implementations behind one interface: a deterministic heuristic that works
offline, and an LLM-as-judge that uses a stronger model to grade the pipeline's
output. The runner reports which one produced the numbers, because they are not
interchangeable.
"""

from dataclasses import dataclass
from typing import Protocol

from app.textutil import build_idf, pivot_gate, weighted_coverage


@dataclass
class Judgement:
    supported: bool
    score: float
    rationale: str


class Judge(Protocol):
    name: str
    trustworthy: bool  # False when the judge is weaker than what it is grading

    def supports(self, requirement: str, quote: str, context: list[str]) -> Judgement: ...


class HeuristicJudge:
    """Offline judge: does the quote carry the requirement's decisive term?

    Deterministic and free, but it shares the stub provider's lexical world view,
    so it cannot catch an error that both of them would make. Reported as
    untrustworthy for that reason.
    """

    name = "heuristic"
    trustworthy = False

    def supports(self, requirement: str, quote: str, context: list[str]) -> Judgement:
        if not quote:
            return Judgement(False, 0.0, "No quote to judge.")
        idf = build_idf(context or [quote])
        cov = weighted_coverage(requirement, quote, idf)
        pivot = pivot_gate(requirement, quote, idf)
        supported = pivot and cov >= 0.15
        return Judgement(
            supported=supported,
            score=round(cov, 3),
            rationale=(
                f"decisive term {'present' if pivot else 'absent'}, "
                f"weighted coverage {cov:.2f}"
            ),
        )


class LLMJudge:
    """LLM-as-judge, per deck 5.4. Requires a real provider.

    Grades with a stronger model than the one being graded, which is the whole
    point; running it against the stub would be a model marking its own work.
    """

    name = "llm"
    trustworthy = True

    def __init__(self) -> None:
        from app.config import get_settings
        from app.exceptions import ProviderUnavailable

        if get_settings().llm_provider == "stub":
            raise ProviderUnavailable(
                "LLM-as-judge needs a real provider. Set LLM_PROVIDER=openai, or run "
                "with --judge heuristic."
            )

    def supports(self, requirement: str, quote: str, context: list[str]) -> Judgement:
        from typing import Literal

        from pydantic import BaseModel, Field
        from sqlmodel import Session

        from app.config import get_settings
        from app.db import engine
        from app.llm.base import RenderedPrompt
        from app.llm.structured import complete_structured
        from app.prompts.blocks import fence, json_only, pctf

        class JudgeOut(BaseModel):
            verdict: Literal["supported", "unsupported"]
            confidence: float = Field(ge=0.0, le=1.0)
            rationale: str = ""

        prompt = RenderedPrompt(
            stage="judge_citation",
            version="judge_citation.v1",
            system=pctf(
                persona="You are a strict evaluator of retrieval-augmented systems. "
                        "You judge only what the text says, never what it implies.",
                context="You are given a job requirement and one sentence quoted from a "
                        "candidate's CV as evidence for it.",
                task="Decide whether that sentence is genuine evidence for that specific "
                     "requirement. A sentence about a related but different technology is "
                     "NOT evidence. Answer 'supported' only if a hiring manager would "
                     "accept the sentence as proof of the requirement.",
                output_format=json_only(
                    '{"verdict": "supported"|"unsupported", "confidence": 0.0-1.0, '
                    '"rationale": "one sentence"}'
                ),
            ),
            user=f"Requirement: {requirement}\n\n" + fence("retrieved_evidence", quote),
            payload={"requirement": requirement, "quote": quote},
        )
        with Session(engine) as db:
            out = complete_structured(
                prompt, JudgeOut, db=db, session_id=None,
                model=get_settings().openai_chat_model_large, temperature=0.0,
            )
        return Judgement(out.verdict == "supported", out.confidence, out.rationale)


def get_judge(name: str) -> Judge:
    if name == "llm":
        return LLMJudge()
    return HeuristicJudge()
