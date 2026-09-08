"""Eval harness CLI.

    python -m evals.run                     # everything
    python -m evals.run --suite retrieval   # one suite
    python -m evals.run --suite ablations   # the comparison tables
    python -m evals.run --judge llm         # LLM-as-judge (needs LLM_PROVIDER=openai)

Results are printed and written to evals/results/<timestamp>.json.

The environment is redirected to a scratch directory BEFORE any application
module is imported, so a run never touches the developer's database, uploads or
vector store.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_SCRATCH = Path(tempfile.mkdtemp(prefix="cvcoach-evals-"))
os.environ.setdefault("SECRET_KEY", "eval-harness-secret")
os.environ["DATABASE_URL"] = f"sqlite:///{_SCRATCH / 'evals.db'}"
os.environ["STORAGE_DIR"] = str(_SCRATCH / "storage")
os.environ["CHROMA_DIR"] = str(_SCRATCH / "chroma")

from evals import suites  # noqa: E402
from evals.judges import get_judge  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"

DESCRIPTIONS = {
    "hit_rate@1": "correct chunk ranked first",
    "hit_rate@3": "correct chunk in top 3",
    "hit_rate@5": "correct chunk in top 5",
    "mrr": "mean reciprocal rank (1.0 = always first)",
    "mean_first_rank": "average position of the correct chunk",
    "citation_validity": "quotes that appear verbatim in the CV",
    "citation_in_context": "quotes drawn from the retrieved passages",
    "unsupported_verdict_rate": "claims made with no quote (lower is better)",
    "status_accuracy": "verdicts matching human labels exactly",
    "status_within_one": "verdicts within one step of the label",
    "false_evidence_rate": "invented evidence for absent skills (lower is better)",
    "missed_evidence_rate": "real evidence reported missing (lower is better)",
    "summary_numeric_consistency": "prose counts matching the structured verdicts",
    "judge_support_rate": "citations a judge accepts as real evidence",
    "score_mae": "mean absolute error vs human scores",
    "score_bias": "positive = scores higher than a human",
    "within_one": "scores within 1.0 of the human label",
    "spearman": "rank correlation with human scores",
    "pairwise_accuracy": "better answer scores higher",
    "self_consistency_stdev": "variation across repeated scorings (lower is better)",
}


def fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def print_suite(result) -> None:
    print(f"\n\033[1m{result.name.upper()}\033[0m")
    print("-" * 74)
    for key, value in result.metrics.items():
        note = DESCRIPTIONS.get(key, "")
        print(f"  {key:<30} {fmt(value):>8}   {note}")
    for note in result.notes:
        print(f"  · {note}")
    if result.detail and result.name == "grounding":
        print(f"\n  Disagreements with the labels ({len(result.detail)}):")
        for d in result.detail[:12]:
            print(f"    [{d['pair']}] expected {d['expected']:<8} got {d['predicted']:<8} "
                  f"{d['requirement']}")
    if result.detail and result.name == "scoring":
        print("\n  Per answer:")
        for d in result.detail:
            flag = "  " if abs(d["delta"]) <= 1 else " !"
            print(f"   {flag} {d['answer']:<22} human {d['expected']:<4} "
                  f"system {d['predicted']:<5} delta {d['delta']:+.1f}")


def print_ablations(rows) -> None:
    print("\n\033[1mABLATIONS\033[0m")
    print("-" * 96)
    header = (f"  {'configuration':<28} {'hit@1':>6} {'hit@3':>6} {'mrr':>6} "
              f"{'status acc':>11} {'false ev':>9} {'cite ok':>8}")
    print(header)
    print("  " + "-" * 92)
    for name, retrieval, grounding in rows:
        print(f"  {name:<28} "
              f"{fmt(retrieval.metrics['hit_rate@1']):>6} "
              f"{fmt(retrieval.metrics['hit_rate@3']):>6} "
              f"{fmt(retrieval.metrics['mrr']):>6} "
              f"{fmt(grounding.metrics['status_accuracy']):>11} "
              f"{fmt(grounding.metrics['false_evidence_rate']):>9} "
              f"{fmt(grounding.metrics['citation_validity']):>8}")
    print("\n  hit@1/hit@3/mrr: retrieval. status acc: verdicts matching human labels.")
    print("  false ev: invented evidence (lower is better). cite ok: quotes that are verbatim.")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Interview Coach evaluation harness")
    parser.add_argument(
        "--suite",
        choices=["all", "retrieval", "grounding", "scoring", "ablations"],
        default="all",
    )
    parser.add_argument("--judge", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--repeats", type=int, default=3,
                        help="Repeated scorings per answer, for self-consistency.")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    from app.config import get_settings

    settings = get_settings()
    print("\033[1mAI Interview Coach — evaluation harness\033[0m")
    print(f"provider: {settings.llm_provider}   embeddings: {settings.embedding_provider}")
    if settings.llm_provider == "stub":
        print("\033[33mNote: the stub provider is deterministic and lexical. Retrieval,")
        print("chunking and grounding numbers are real; prompt-wording ablations and")
        print("self-consistency only become meaningful with LLM_PROVIDER=openai.\033[0m")

    judge = get_judge(args.judge)
    payload: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "judge": judge.name,
        "suites": {},
    }

    if args.suite in ("all", "retrieval"):
        result = suites.retrieval_suite(config=suites.RetrievalConfig())
        print_suite(result)
        payload["suites"]["retrieval"] = result.metrics

    if args.suite in ("all", "grounding"):
        result = suites.grounding_suite(config=suites.RetrievalConfig(), judge=judge)
        print_suite(result)
        payload["suites"]["grounding"] = result.metrics
        payload["grounding_disagreements"] = result.detail

    if args.suite in ("all", "scoring"):
        result = suites.scoring_suite(repeats=args.repeats)
        print_suite(result)
        payload["suites"]["scoring"] = result.metrics
        payload["scoring_detail"] = result.detail

    if args.suite in ("all", "ablations"):
        rows = suites.ablation_suite()
        print_ablations(rows)
        payload["ablations"] = {
            name: {"retrieval": r.metrics, "grounding": g.metrics}
            for name, r, g in rows
        }

    if not args.no_save:
        RESULTS.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = RESULTS / f"{stamp}.json"
        path.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nWritten to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
