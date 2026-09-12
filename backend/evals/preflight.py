"""One cheap call against the real provider, to prove the path works.

Run this immediately after putting a key in .env and before anything else. It
exercises the whole chain — settings, provider construction, the HTTP call, the
JSON mode, Pydantic validation and the telemetry row — for roughly a tenth of a
cent, so a misconfiguration costs that instead of a full eval sweep.

    .venv/bin/python -m evals.preflight
"""

import sys
import time

from sqlmodel import Session

from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.llm.contracts import RequirementsOut
from app.llm.structured import complete_structured, spent_usd
from app.prompts import extract_requirements

# Deliberately tiny, and deliberately a real posting shape rather than "say hi":
# it exercises the same prompt and the same contract the application uses.
SAMPLE = """Backend Engineer

Requirements:
- Strong experience with Python and FastAPI
- Production experience with PostgreSQL
- Familiarity with Docker
"""


def main() -> int:
    settings = get_settings()
    print("Preflight\n" + "-" * 58)
    print(f"  llm_provider        {settings.llm_provider}")
    print(f"  chat model (large)  {settings.openai_chat_model_large}")
    print(f"  chat model (small)  {settings.openai_chat_model_small}")
    print(f"  api key             {'present' if settings.openai_api_key else 'MISSING'}")
    print(f"  spend ceiling       ${settings.max_spend_usd:.2f}")

    if settings.llm_provider == "stub":
        print("\n  LLM_PROVIDER is still 'stub'. Set it to 'openai' in .env first.")
        return 1
    if not settings.openai_api_key:
        print("\n  OPENAI_API_KEY is not set. Add it to backend/.env.")
        return 1

    create_db_and_tables()
    with Session(engine) as db:
        before = spent_usd(db)
        print(f"  spent so far        ${before:.4f}\n")

        started = time.perf_counter()
        try:
            out = complete_structured(
                extract_requirements.render(SAMPLE),
                RequirementsOut,
                db=db,
                session_id=None,
                model=settings.openai_chat_model_small,
            )
        except Exception as exc:  # noqa: BLE001 - this is the diagnostic
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            print("\n  Nothing else will work until this does. Common causes:")
            print("   · key rejected      -> check it at platform.openai.com")
            print("   · insufficient_quota -> the account has no credit on it")
            print("   · model not found    -> the key's project cannot see that model")
            return 1

        elapsed = (time.perf_counter() - started) * 1000
        after = spent_usd(db)

        print(f"  OK — {len(out.requirements)} requirements parsed and validated "
              f"in {elapsed:.0f} ms")
        for r in out.requirements:
            print(f"     [{r.category:12}] [{r.kind:12}] {r.text}")
        print(f"\n  this call cost      ${after - before:.5f}")
        print(f"  remaining budget    ${max(0.0, settings.max_spend_usd - after):.4f}")
        print("\n  The real provider is wired up correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
