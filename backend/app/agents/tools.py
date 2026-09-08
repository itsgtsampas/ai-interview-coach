"""Tools the coach agent can call.

Every tool is bound to one user and one session at construction time, so the
agent physically cannot reach another user's documents — the model chooses which
tool to call, never whose data to read.
"""

from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session

from app.llm.base import ToolSpec
from app.rag.retriever import retrieve
from app.services.analysis import get_report
from app.services.evaluation import evaluations_for_session

_QUERY_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "What to look for."}},
    "required": ["query"],
}


@dataclass
class Tool:
    spec: ToolSpec
    run: Callable[[dict[str, Any]], str]


def build_tools(*, user_id: int, session_id: int, db: Session) -> dict[str, Tool]:
    def search_cv(args: dict[str, Any]) -> str:
        passages = retrieve(
            args.get("query", ""), user_id=user_id, session_id=session_id, doc_kind="cv"
        )
        if not passages:
            return "Nothing in the CV matched that."
        return "\n".join(
            f"From your CV ({p.section or 'unlabelled section'}, p.{p.page}): "
            f"{' '.join(p.text.split())[:280]}"
            for p in passages[:3]
        )

    def search_job_description(args: dict[str, Any]) -> str:
        passages = retrieve(
            args.get("query", ""), user_id=user_id, session_id=session_id, doc_kind="jd"
        )
        if not passages:
            return "Nothing in the job description matched that."
        return "\n".join(
            f"From the job description ({p.section or 'unlabelled section'}): "
            f"{' '.join(p.text.split())[:280]}"
            for p in passages[:3]
        )

    def get_match_report(_args: dict[str, Any]) -> str:
        report, items = get_report(session_id, db)
        if report is None:
            return "No gap analysis has been run for this session yet."
        missing = [i.requirement for i in items if str(i.status).endswith("missing")]
        strong = [i.requirement for i in items if str(i.status).endswith("strong")]
        parts = [f"Overall CV match: {report.overall_score}/100 ({report.verdict})."]
        if strong:
            parts.append("Evidenced: " + "; ".join(strong[:4]) + ".")
        if missing:
            parts.append("No evidence for: " + "; ".join(missing[:4]) + ".")
        return " ".join(parts)

    def get_score_history(_args: dict[str, Any]) -> str:
        rows = evaluations_for_session(session_id, db)
        if not rows:
            return "You have not answered any practice questions yet."
        lines = [
            f"{q.category.value} question scored {e.overall_score}/5 "
            f"(weakest: {min(e.criterion_scores, key=e.criterion_scores.get)})"
            for q, _a, e in rows[:5]
        ]
        mean = sum(e.overall_score for _q, _a, e in rows) / len(rows)
        return f"Average {mean:.1f}/5 across {len(rows)} answers. " + " ".join(lines)

    definitions = [
        (search_cv, "search_cv", "Search the candidate's CV for relevant passages.", _QUERY_SCHEMA),
        (search_job_description, "search_job_description",
         "Search the job description for what the role requires.", _QUERY_SCHEMA),
        (get_match_report, "get_match_report",
         "Get the CV-to-role gap analysis: overall score, evidenced and missing requirements.",
         {"type": "object", "properties": {}}),
        (get_score_history, "get_score_history",
         "Get the candidate's scores across the practice answers they have given.",
         {"type": "object", "properties": {}}),
    ]
    return {
        name: Tool(spec=ToolSpec(name=name, description=desc, parameters=schema), run=fn)
        for fn, name, desc, schema in definitions
    }
