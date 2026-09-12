"""Active prompt version per stage.

Every llm_call row records the version that produced it, so any stored output
can be traced back to its prompt, and the eval harness can A/B two versions on
the same golden set.
"""

from app.prompts import (
    analyse_match,
    build_scorecard,
    coach_agent,
    cover_letter,
    evaluate_answer,
    extract_requirements,
    generate_questions,
    rewrite_bullet,
)

ACTIVE: dict[str, str] = {
    "extract_requirements": extract_requirements.VERSION,
    "analyse_match": analyse_match.VERSION,
    "generate_questions": generate_questions.VERSION,
    "evaluate_answer": evaluate_answer.VERSION,
    "build_scorecard": build_scorecard.VERSION,
    "coach_agent": coach_agent.VERSION,
    "rewrite_bullet": rewrite_bullet.VERSION,
    "cover_letter": cover_letter.VERSION,
}
