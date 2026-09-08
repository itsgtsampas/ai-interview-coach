"""The suites: retrieval, grounding, scoring, and the ablations over them."""

from dataclasses import dataclass, field
from typing import Any

from app.llm.cache import completion_cache
from app.rag.retriever import RetrievalConfig

from evals import metrics
from evals.harness import (
    IndexedPair,
    analyse,
    evidence_for,
    index_pair,
    load_answers,
    load_labels,
    ranked_chunk_texts,
    score_answer,
)
from evals.judges import Judge
from evals.metrics import ItemOutcome, RetrievalOutcome, ScoreOutcome, normalise

# Indexing is the slow step; reuse it across suites and configurations.
_INDEX_CACHE: dict[tuple[str, str], IndexedPair] = {}


def get_indexed(pair: dict, strategy: str) -> IndexedPair:
    key = (pair["id"], strategy)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = index_pair(pair, strategy=strategy)
    return _INDEX_CACHE[key]


@dataclass
class SuiteResult:
    name: str
    metrics: dict[str, Any] = field(default_factory=dict)
    detail: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --- retrieval -------------------------------------------------------------

def retrieval_suite(
    *, config: RetrievalConfig, strategy: str = "parent_child", k: int = 5
) -> SuiteResult:
    labels = load_labels()
    outcomes: list[RetrievalOutcome] = []
    detail: list[dict] = []

    for pair in labels["pairs"]:
        probes = pair.get("retrieval") or []
        if not probes:
            continue
        indexed = get_indexed(pair, strategy)
        for probe in probes:
            texts = ranked_chunk_texts(indexed, probe["query"], config)
            wanted = [normalise(w) for w in probe["relevant_contains"]]
            ranks = [
                rank
                for rank, text in enumerate(texts, start=1)
                if any(w in normalise(text) for w in wanted)
            ]
            outcomes.append(
                RetrievalOutcome(query=probe["query"], ranks=ranks, retrieved=len(texts))
            )
            detail.append({
                "pair": pair["id"],
                "query": probe["query"],
                "first_rank": min(ranks) if ranks else None,
                "retrieved": len(texts),
            })

    return SuiteResult(
        name="retrieval",
        metrics={
            "probes": len(outcomes),
            "hit_rate@1": metrics.hit_rate_at(outcomes, 1),
            "hit_rate@3": metrics.hit_rate_at(outcomes, 3),
            f"hit_rate@{k}": metrics.hit_rate_at(outcomes, k),
            "mrr": metrics.mrr(outcomes),
            "mean_first_rank": metrics.mean_first_rank(outcomes),
        },
        detail=detail,
    )


# --- grounding -------------------------------------------------------------

def _match_label(requirement: str, labels: list[dict]) -> dict | None:
    low = requirement.lower()
    for label in labels:
        if label["match"].lower() in low:
            return label
    return None


def grounding_suite(
    *, config: RetrievalConfig, strategy: str = "parent_child", judge: Judge | None = None
) -> SuiteResult:
    labels = load_labels()
    all_items: list[ItemOutcome] = []
    detail: list[dict] = []
    consistency: list[float] = []
    judged_supported = 0
    judged_total = 0

    for pair in labels["pairs"]:
        indexed = get_indexed(pair, strategy)
        report, items = analyse(indexed, config)
        cv_text = normalise(indexed.cv_text)

        outcomes: list[ItemOutcome] = []
        for item in items:
            label = _match_label(item.requirement, pair["requirements"])
            quote = item.evidence_quote
            context = evidence_for(indexed, item.requirement, config) if quote else []
            outcome = ItemOutcome(
                requirement=item.requirement,
                predicted=str(getattr(item.status, "value", item.status)),
                expected=label["expected_status"] if label else None,
                category=str(getattr(item.category, "value", item.category)),
                quote=quote,
                quote_in_source=bool(quote) and normalise(quote) in cv_text,
                quote_in_context=bool(quote)
                and any(normalise(quote) in normalise(c) for c in context),
            )
            outcomes.append(outcome)

            if judge and quote:
                judgement = judge.supports(item.requirement, quote, context)
                judged_total += 1
                judged_supported += int(judgement.supported)

            if label and outcome.predicted != outcome.expected:
                detail.append({
                    "pair": pair["id"],
                    "requirement": item.requirement[:70],
                    "expected": outcome.expected,
                    "predicted": outcome.predicted,
                    "quote": (quote or "")[:70],
                })

        numeric = metrics.summary_numeric_consistency(report.summary, outcomes)
        if numeric is not None:
            consistency.append(numeric)
        all_items.extend(outcomes)

    result = SuiteResult(
        name="grounding",
        metrics={
            "requirements": len(all_items),
            "labelled": sum(1 for i in all_items if i.expected),
            "citation_validity": metrics.citation_validity(all_items),
            "citation_in_context": metrics.citation_in_context_rate(all_items),
            "unsupported_verdict_rate": metrics.unsupported_verdict_rate(all_items),
            "status_accuracy": metrics.status_accuracy(all_items),
            "status_within_one": metrics.status_within_one(all_items),
            "false_evidence_rate": metrics.false_evidence_rate(all_items),
            "missed_evidence_rate": metrics.missed_evidence_rate(all_items),
            "summary_numeric_consistency": (
                sum(consistency) / len(consistency) if consistency else None
            ),
        },
        detail=detail,
    )
    if judge and judged_total:
        result.metrics["judge_support_rate"] = judged_supported / judged_total
        result.notes.append(
            f"Citations judged by the {judge.name} judge"
            + ("" if judge.trustworthy else " (weaker than what it grades — indicative only)")
        )
    return result


# --- answer scoring --------------------------------------------------------

def scoring_suite(*, repeats: int = 3) -> SuiteResult:
    labels = load_labels()
    data = load_answers()
    # Any indexed session will do: scoring does not read the documents.
    indexed = get_indexed(labels["pairs"][0], "parent_child")

    outcomes: list[ScoreOutcome] = []
    for spec in data["answers"]:
        runs: list[float] = []
        for _ in range(max(1, repeats)):
            # Clear the cache, otherwise repeats measure the cache rather than
            # the model and self-consistency is 0 by construction.
            completion_cache.clear()
            runs.append(score_answer(indexed, spec))
        outcomes.append(ScoreOutcome(
            answer_id=spec["id"],
            expected=float(spec["expected_score"]),
            predicted=runs[0],
            repeats=runs,
        ))

    pairs = [tuple(p) for p in data["pairs"]]
    accuracy, violations = metrics.pairwise_accuracy(outcomes, pairs)

    return SuiteResult(
        name="scoring",
        metrics={
            "answers": len(outcomes),
            "score_mae": metrics.score_mae(outcomes),
            "score_bias": metrics.score_bias(outcomes),
            "within_one": metrics.within_one(outcomes),
            "spearman": metrics.spearman(outcomes),
            "pairwise_accuracy": accuracy,
            "self_consistency_stdev": metrics.self_consistency(outcomes),
        },
        detail=[
            {"answer": o.answer_id, "expected": o.expected, "predicted": o.predicted,
             "delta": round(o.predicted - o.expected, 2)}
            for o in outcomes
        ],
        notes=(
            [f"Ordering violated: {b} should outscore {w}" for b, w in violations]
            if violations else []
        ),
    )


# --- ablations -------------------------------------------------------------

ABLATIONS: dict[str, tuple[RetrievalConfig, str]] = {
    "full pipeline": (RetrievalConfig(), "parent_child"),
    "no re-ranking": (RetrievalConfig(rerank=False), "parent_child"),
    "no BM25 (dense only)": (RetrievalConfig(bm25=False), "parent_child"),
    "no multi-query": (RetrievalConfig(multi_query=False), "parent_child"),
    "dense, no fusion or rerank": (
        RetrievalConfig(multi_query=False, bm25=False, rerank=False), "parent_child",
    ),
    "fixed-size chunking": (RetrievalConfig(), "fixed"),
}


def ablation_suite(*, judge: Judge | None = None) -> list[tuple[str, SuiteResult, SuiteResult]]:
    rows = []
    for name, (config, strategy) in ABLATIONS.items():
        rows.append((
            name,
            retrieval_suite(config=config, strategy=strategy),
            grounding_suite(config=config, strategy=strategy, judge=judge),
        ))
    return rows
