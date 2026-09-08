"""Drives the real pipeline against the fixture corpus.

Nothing here re-implements application logic: the suites exercise the same
services the API calls, so a measurement is a statement about the shipped
system rather than about a copy of it.

The environment must already point at a scratch database and vector store —
`run.py` does that before importing anything from `app`.
"""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session

from app.db import create_db_and_tables, engine
from app.models import (
    DocumentKind,
    InterviewSession,
    Question,
    QuestionCategory,
    User,
)
from app.rag.retriever import RetrievalConfig, rank_chunks, retrieve
from app.services.analysis import run_analysis
from app.services.ingestion import ingest_document, save_upload
from app.services.evaluation import evaluate

DATA = Path(__file__).resolve().parent / "data"


def load_labels() -> dict:
    return json.loads((DATA / "labels.json").read_text())


def load_answers() -> dict:
    return json.loads((DATA / "answers.json").read_text())


@dataclass
class IndexedPair:
    """One CV + job description, ingested and ready to query."""

    pair_id: str
    user_id: int
    session_id: int
    cv_text: str
    labels: dict = field(default_factory=dict)


def _new_user(db: Session) -> User:
    user = User(
        email=f"eval-{uuid.uuid4().hex[:10]}@example.invalid",
        full_name="Eval Harness",
        hashed_password="not-a-real-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def index_pair(pair: dict, *, strategy: str = "parent_child") -> IndexedPair:
    """Create an isolated user and session, then ingest both documents."""
    create_db_and_tables()
    with Session(engine) as db:
        user = _new_user(db)
        sess = InterviewSession(
            user_id=user.id or 0, title=pair["id"], target_role="Eval"
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)

        for kind, filename in (
            (DocumentKind.cv, pair["cv"]),
            (DocumentKind.jd, pair["jd"]),
        ):
            doc = save_upload(
                content=(DATA / filename).read_bytes(),
                filename=filename,
                session_id=sess.id or 0,
                user_id=user.id or 0,
                kind=kind,
                db=db,
            )
            ingest_document(doc.id or 0, user.id or 0, db, strategy=strategy)

        return IndexedPair(
            pair_id=pair["id"],
            user_id=user.id or 0,
            session_id=sess.id or 0,
            cv_text=(DATA / pair["cv"].replace(".pdf", ".txt")).read_text(),
            labels=pair,
        )


def analyse(indexed: IndexedPair, config: RetrievalConfig) -> tuple[object, list]:
    with Session(engine) as db:
        sess = db.get(InterviewSession, indexed.session_id)
        report = run_analysis(sess, db, config)
        from app.services.analysis import get_report

        _, items = get_report(indexed.session_id, db)
        # Detach so the rows survive the session closing.
        return report.model_copy(), [i.model_copy() for i in items]


def evidence_for(indexed: IndexedPair, requirement: str, config: RetrievalConfig) -> list[str]:
    """The passages the analysis stage would have seen for this requirement."""
    passages = retrieve(
        requirement,
        user_id=indexed.user_id,
        session_id=indexed.session_id,
        doc_kind="cv",
        config=config,
    )
    return [p.text for p in passages]


def ranked_chunk_texts(
    indexed: IndexedPair, query: str, config: RetrievalConfig
) -> list[str]:
    return [
        c.text
        for c in rank_chunks(
            query,
            user_id=indexed.user_id,
            session_id=indexed.session_id,
            doc_kind="cv",
            config=config,
        )
    ]


def score_answer(indexed: IndexedPair, spec: dict) -> float:
    """Run one labelled answer through the real evaluation service."""
    from app.models import Answer

    with Session(engine) as db:
        question = Question(
            session_id=indexed.session_id,
            category=(
                QuestionCategory.behavioural
                if spec["rubric"] == "star"
                else QuestionCategory.technical
            ),
            text=spec["question"],
            linked_requirement=spec.get("requirement", ""),
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        answer = Answer(question_id=question.id or 0, text=spec["text"])
        db.add(answer)
        db.commit()
        db.refresh(answer)

        evaluation = evaluate(answer, question, db, indexed.session_id)
        return evaluation.overall_score
