"""Metric implementations.

Everything here is a pure function over already-collected results, so the
metrics can be unit-tested without running the pipeline.
"""

import math
import re
import statistics
from dataclasses import dataclass, field

# Statuses are ordinal, which lets us distinguish a near-miss (strong vs partial)
# from a dangerous one (strong vs missing).
STATUS_ORDER = {"missing": 0, "partial": 1, "strong": 2}


def normalise(text: str) -> str:
    return " ".join((text or "").split()).lower()


# --- retrieval -------------------------------------------------------------

@dataclass
class RetrievalOutcome:
    query: str
    ranks: list[int] = field(default_factory=list)  # 1-based ranks of relevant hits
    retrieved: int = 0


def hit_rate_at(outcomes: list[RetrievalOutcome], k: int) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if any(r <= k for r in o.ranks)) / len(outcomes)


def mrr(outcomes: list[RetrievalOutcome]) -> float:
    """Mean reciprocal rank of the first relevant chunk. 1.0 = always ranked first."""
    if not outcomes:
        return 0.0
    return sum(1.0 / min(o.ranks) if o.ranks else 0.0 for o in outcomes) / len(outcomes)


def mean_first_rank(outcomes: list[RetrievalOutcome]) -> float | None:
    found = [min(o.ranks) for o in outcomes if o.ranks]
    return statistics.mean(found) if found else None


# --- grounding -------------------------------------------------------------

@dataclass
class ItemOutcome:
    requirement: str
    predicted: str
    expected: str | None
    category: str
    quote: str | None
    quote_in_context: bool
    quote_in_source: bool


def citation_validity(items: list[ItemOutcome]) -> float | None:
    """Of the citations produced, how many appear verbatim in the source CV.

    The cheapest possible hallucination check, and the one that matters most:
    a confident verdict attached to a sentence the CV never contained.
    """
    cited = [i for i in items if i.quote]
    if not cited:
        return None
    return sum(1 for i in cited if i.quote_in_source) / len(cited)


def citation_in_context_rate(items: list[ItemOutcome]) -> float | None:
    """Citations that came from the passages actually retrieved for that
    requirement, rather than from elsewhere in the document."""
    cited = [i for i in items if i.quote]
    if not cited:
        return None
    return sum(1 for i in cited if i.quote_in_context) / len(cited)


def unsupported_verdict_rate(items: list[ItemOutcome]) -> float:
    """Non-missing verdicts asserted with no supporting quote at all."""
    if not items:
        return 0.0
    claimed = [i for i in items if i.predicted != "missing"]
    if not claimed:
        return 0.0
    return sum(1 for i in claimed if not i.quote) / len(claimed)


def status_accuracy(items: list[ItemOutcome]) -> float | None:
    labelled = [i for i in items if i.expected]
    if not labelled:
        return None
    return sum(1 for i in labelled if i.predicted == i.expected) / len(labelled)


def status_within_one(items: list[ItemOutcome]) -> float | None:
    """Tolerates strong/partial confusion, which is often genuinely arguable,
    while still counting strong/missing as a failure."""
    labelled = [i for i in items if i.expected]
    if not labelled:
        return None
    return sum(
        1 for i in labelled
        if abs(STATUS_ORDER[i.predicted] - STATUS_ORDER[i.expected]) <= 1
    ) / len(labelled)


def false_evidence_rate(items: list[ItemOutcome]) -> float | None:
    """The dangerous error: the CV has nothing, and the system says it does.

    This is what would send a candidate into an interview unprepared, so it is
    tracked separately from overall accuracy.
    """
    truly_missing = [i for i in items if i.expected == "missing"]
    if not truly_missing:
        return None
    return sum(1 for i in truly_missing if i.predicted != "missing") / len(truly_missing)


def missed_evidence_rate(items: list[ItemOutcome]) -> float | None:
    """The opposite error: the CV evidences it, and the system says it does not."""
    truly_strong = [i for i in items if i.expected == "strong"]
    if not truly_strong:
        return None
    return sum(1 for i in truly_strong if i.predicted == "missing") / len(truly_strong)


_COUNT_CLAIM = re.compile(r"(\d+)\s+of\s+(\d+)\s+requirements", re.I)


def summary_numeric_consistency(summary: str, items: list[ItemOutcome]) -> float | None:
    """Do the numbers the model states in prose match the structured verdicts?

    A faithfulness check that needs no judge: if the summary says "6 of 11
    requirements are backed by evidence", exactly 6 items must be strong.
    """
    match = _COUNT_CLAIM.search(summary or "")
    if not match:
        return None
    claimed_strong, claimed_total = int(match.group(1)), int(match.group(2))
    actual_strong = sum(1 for i in items if i.predicted == "strong")
    return float(claimed_strong == actual_strong and claimed_total == len(items))


# --- answer scoring --------------------------------------------------------

@dataclass
class ScoreOutcome:
    answer_id: str
    expected: float
    predicted: float
    repeats: list[float] = field(default_factory=list)


def score_mae(outcomes: list[ScoreOutcome]) -> float | None:
    if not outcomes:
        return None
    return sum(abs(o.predicted - o.expected) for o in outcomes) / len(outcomes)


def score_bias(outcomes: list[ScoreOutcome]) -> float | None:
    """Positive means the system scores higher than a human would — the failure
    mode calibration anchors exist to prevent."""
    if not outcomes:
        return None
    return sum(o.predicted - o.expected for o in outcomes) / len(outcomes)


def within_one(outcomes: list[ScoreOutcome]) -> float | None:
    if not outcomes:
        return None
    return sum(1 for o in outcomes if abs(o.predicted - o.expected) <= 1.0) / len(outcomes)


def pairwise_accuracy(
    outcomes: list[ScoreOutcome], pairs: list[tuple[str, str]]
) -> tuple[float | None, list[tuple[str, str]]]:
    """Does the answer a human ranked higher actually score higher?

    More robust than absolute agreement: it survives any global miscalibration
    and still catches a rubric that cannot tell good from bad.
    """
    by_id = {o.answer_id: o for o in outcomes}
    checked = 0
    correct = 0
    violations: list[tuple[str, str]] = []
    for better, worse in pairs:
        if better not in by_id or worse not in by_id:
            continue
        checked += 1
        if by_id[better].predicted > by_id[worse].predicted:
            correct += 1
        else:
            violations.append((better, worse))
    return (correct / checked if checked else None), violations


def self_consistency(outcomes: list[ScoreOutcome]) -> float | None:
    """Standard deviation across repeated scorings of the same answer.

    0.0 with a deterministic provider by construction; it becomes informative
    once a real model is scoring, where an unstable rubric shows up here first.
    """
    devs = [statistics.pstdev(o.repeats) for o in outcomes if len(o.repeats) > 1]
    return statistics.mean(devs) if devs else None


def spearman(outcomes: list[ScoreOutcome]) -> float | None:
    """Rank correlation between human and system scores."""
    if len(outcomes) < 3:
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = shared
            i = j + 1
        return out

    a, b = ranks([o.expected for o in outcomes]), ranks([o.predicted for o in outcomes])
    n = len(a)
    mean_a, mean_b = sum(a) / n, sum(b) / n
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den = math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
    return num / den if den else None
