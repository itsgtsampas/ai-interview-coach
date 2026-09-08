"""Unit tests for the eval metrics.

A metric that is silently wrong is worse than no metric at all: it produces
confident numbers that justify the wrong decision. These pin the arithmetic.
"""

from evals.metrics import (
    ItemOutcome,
    RetrievalOutcome,
    ScoreOutcome,
    citation_validity,
    false_evidence_rate,
    hit_rate_at,
    missed_evidence_rate,
    mrr,
    pairwise_accuracy,
    score_bias,
    self_consistency,
    spearman,
    status_accuracy,
    status_within_one,
    summary_numeric_consistency,
    unsupported_verdict_rate,
)


def _item(predicted, expected, quote=None, in_source=True, in_context=True):
    return ItemOutcome(
        requirement="r", predicted=predicted, expected=expected, category="must_have",
        quote=quote, quote_in_source=in_source, quote_in_context=in_context,
    )


# --- retrieval -------------------------------------------------------------

def test_hit_rate_counts_only_within_k():
    outcomes = [RetrievalOutcome("a", [1]), RetrievalOutcome("b", [4]),
                RetrievalOutcome("c", [])]
    assert hit_rate_at(outcomes, 1) == 1 / 3
    assert hit_rate_at(outcomes, 5) == 2 / 3


def test_mrr_uses_the_first_relevant_rank():
    assert mrr([RetrievalOutcome("a", [2, 5])]) == 0.5
    assert mrr([RetrievalOutcome("a", [])]) == 0.0


def test_empty_input_does_not_divide_by_zero():
    assert hit_rate_at([], 5) == 0.0
    assert mrr([]) == 0.0


# --- grounding -------------------------------------------------------------

def test_citation_validity_ignores_items_with_no_quote():
    items = [_item("strong", "strong", "q", in_source=True),
             _item("strong", "strong", "q", in_source=False),
             _item("missing", "missing")]
    assert citation_validity(items) == 0.5


def test_citation_validity_is_none_when_nothing_was_cited():
    assert citation_validity([_item("missing", "missing")]) is None


def test_unsupported_verdict_rate_counts_claims_without_a_quote():
    items = [_item("strong", "strong", "q"), _item("partial", "partial"),
             _item("missing", "missing")]
    assert unsupported_verdict_rate(items) == 0.5  # 1 of the 2 non-missing claims


def test_status_accuracy_and_within_one_differ_on_near_misses():
    items = [_item("strong", "partial"), _item("strong", "strong")]
    assert status_accuracy(items) == 0.5
    assert status_within_one(items) == 1.0  # strong vs partial is one step


def test_within_one_still_fails_a_two_step_error():
    assert status_within_one([_item("strong", "missing")]) == 0.0


def test_false_and_missed_evidence_are_measured_separately():
    items = [_item("strong", "missing"), _item("missing", "missing"),
             _item("missing", "strong"), _item("strong", "strong")]
    assert false_evidence_rate(items) == 0.5   # 1 of 2 truly-missing over-credited
    assert missed_evidence_rate(items) == 0.5  # 1 of 2 truly-strong dropped


def test_summary_numeric_consistency_catches_a_wrong_count():
    items = [_item("strong", "strong"), _item("missing", "missing")]
    assert summary_numeric_consistency("1 of 2 requirements are backed", items) == 1.0
    assert summary_numeric_consistency("2 of 2 requirements are backed", items) == 0.0
    assert summary_numeric_consistency("no numbers here", items) is None


# --- scoring ---------------------------------------------------------------

def test_bias_is_signed_so_over_and_under_scoring_are_distinguishable():
    assert score_bias([ScoreOutcome("a", expected=3, predicted=4)]) == 1.0
    assert score_bias([ScoreOutcome("a", expected=3, predicted=2)]) == -1.0


def test_pairwise_accuracy_reports_the_violating_pairs():
    outcomes = [ScoreOutcome("good", 5, 4.0), ScoreOutcome("bad", 2, 4.5)]
    accuracy, violations = pairwise_accuracy(outcomes, [("good", "bad")])
    assert accuracy == 0.0
    assert violations == [("good", "bad")]


def test_pairwise_accuracy_skips_pairs_it_has_no_data_for():
    outcomes = [ScoreOutcome("a", 5, 4.0)]
    accuracy, _ = pairwise_accuracy(outcomes, [("a", "missing-id")])
    assert accuracy is None


def test_self_consistency_is_zero_for_a_deterministic_scorer():
    assert self_consistency([ScoreOutcome("a", 3, 3, repeats=[3.0, 3.0, 3.0])]) == 0.0


def test_self_consistency_grows_with_disagreement():
    value = self_consistency([ScoreOutcome("a", 3, 3, repeats=[1.0, 3.0, 5.0])])
    assert value is not None and value > 1.0


def test_spearman_is_one_for_a_perfectly_ordered_prediction():
    outcomes = [ScoreOutcome(str(i), expected=i, predicted=i * 0.5 + 1)
                for i in range(1, 6)]
    assert spearman(outcomes) == 1.0


def test_spearman_is_negative_when_the_order_is_reversed():
    outcomes = [ScoreOutcome(str(i), expected=i, predicted=6 - i) for i in range(1, 6)]
    assert spearman(outcomes) == -1.0
