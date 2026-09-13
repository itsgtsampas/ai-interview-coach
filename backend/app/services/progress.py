"""Cross-session progress.

Aggregates every application at once, which is the only place a *recurring* gap
is visible: missing one posting's requirement is a mismatch, missing the same
one in four is worth learning.

Pure aggregation over stored rows — no model is called.
"""

from collections import defaultdict
from statistics import fmean

from sqlmodel import Session, select

from app.models import (
    Answer,
    Evaluation,
    EvidenceStatus,
    InterviewSession,
    MatchItem,
    MatchReport,
    Question,
    Scorecard,
)
from app.textutil import STOPWORDS, salient_terms, tokens

# Below this, a "trend" is one or two dots and a line through them would be a
# claim the data does not support. The UI shows figures instead.
MIN_POINTS_FOR_TREND = 3


def _gap_key(requirement: str) -> str:
    """Group the same gap across postings that phrase it differently.

    Keys on the first salient term, since postings append qualifiers in no
    consistent order. Over-merges rather than under-merges: "AWS Lambda" and
    "AWS S3" both key on "aws", which is the better error for a list whose
    purpose is "go and learn this".
    """
    terms = salient_terms(requirement)
    if not terms:
        terms = [t for t in tokens(requirement) if t not in STOPWORDS]
    return terms[0] if terms else ""


def build(user_id: int, db: Session) -> dict:
    sessions = list(
        db.exec(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at)
        ).all()
    )

    points: list[dict] = []
    gap_sessions: dict[str, dict] = defaultdict(
        lambda: {"label": "", "sessions": [], "count": 0}
    )
    competency_series: dict[str, list[float]] = defaultdict(list)
    all_answer_scores: list[float] = []

    for s in sessions:
        report = db.exec(
            select(MatchReport).where(MatchReport.session_id == s.id)
        ).first()
        card = db.exec(select(Scorecard).where(Scorecard.session_id == s.id)).first()

        scores = [
            e.overall_score
            for e in db.exec(
                select(Evaluation)
                .join(Answer, Answer.id == Evaluation.answer_id)
                .join(Question, Question.id == Answer.question_id)
                .where(Question.session_id == s.id)
            ).all()
        ]
        all_answer_scores.extend(scores)

        if report is not None:
            for item in db.exec(
                select(MatchItem).where(MatchItem.report_id == report.id)
            ).all():
                # Behavioural requirements are excluded from the match score, so
                # counting them as recurring gaps would contradict that decision.
                if item.status != EvidenceStatus.missing or item.kind.value != "evidenceable":
                    continue
                key = _gap_key(item.requirement)
                if not key:
                    continue
                bucket = gap_sessions[key]
                bucket["label"] = bucket["label"] or item.requirement
                if s.title not in bucket["sessions"]:
                    bucket["sessions"].append(s.title)
                    bucket["count"] += 1

        if card is not None:
            for name, value in card.competencies.items():
                competency_series[name].append(value)

        points.append({
            "session_id": s.id,
            "title": s.title,
            "target_role": s.target_role,
            "created_at": s.created_at,
            "match_score": report.overall_score if report else None,
            "readiness_score": card.readiness_score if card else None,
            "answers": len(scores),
            "mean_answer_score": round(fmean(scores), 2) if scores else None,
        })

    readiness = [p["readiness_score"] for p in points if p["readiness_score"] is not None]
    matches = [p["match_score"] for p in points if p["match_score"] is not None]

    recurring = sorted(
        (
            {
                "requirement": v["label"],
                "missing_in": v["count"],
                "sessions": v["sessions"],
            }
            for v in gap_sessions.values()
            if v["count"] >= 2
        ),
        key=lambda g: (-g["missing_in"], g["requirement"]),
    )[:8]

    competencies = sorted(
        (
            {
                "name": name,
                "first": round(series[0], 2),
                "latest": round(series[-1], 2),
                "delta": round(series[-1] - series[0], 2),
                "points": [round(v, 2) for v in series],
            }
            for name, series in competency_series.items()
            if len(series) >= 2
        ),
        key=lambda c: c["delta"],
    )

    return {
        "sessions_total": len(sessions),
        "sessions_scored": len(readiness),
        "answers_total": len(all_answer_scores),
        "mean_answer_score": (
            round(fmean(all_answer_scores), 2) if all_answer_scores else None
        ),
        "best_readiness": max(readiness) if readiness else None,
        "latest_readiness": readiness[-1] if readiness else None,
        "readiness_delta": (
            readiness[-1] - readiness[0] if len(readiness) >= 2 else None
        ),
        "mean_match": round(fmean(matches), 1) if matches else None,
        "has_trend": len(readiness) >= MIN_POINTS_FOR_TREND,
        "points": points,
        "recurring_gaps": recurring,
        "competencies": competencies,
    }
