# Evaluation

> Reproduce with `cd backend && .venv/bin/python -m evals.run`.
> Provider: `stub` · Embeddings: `stub` · Judge: `heuristic` · 35 unit tests passing.

Every design decision in the retrieval and grounding layers was stated as a hypothesis in
`DESIGN.md` and is tested here. Where a technique did not earn its place, that is recorded
as a negative result rather than quietly dropped.

---

## 1. Golden set

Synthetic, authored by hand, committed to the repository — no real personal data.

| Pair | CV | Job description | Why it exists |
|---|---|---|---|
| `backend-mixed` | Senior backend engineer | Senior backend role | A genuine mix: some requirements evidenced, some absent. |
| `backend-poor-fit` | Junior frontend developer | Senior backend role | Almost everything should be **missing**. Exists to catch invented evidence. |
| `frontend-good-fit` | Junior frontend developer | Senior frontend role | Most requirements evidenced. Exists to catch the opposite error. |

**31 labelled requirements**, **13 retrieval probes**, **12 hand-scored interview answers**
with **10 ordering judgements**. Expected statuses and scores were written before running
the system against them.

---

## 2. Headline results

### Retrieval

| Metric | Value | Meaning |
|---|---|---|
| hit_rate@1 | **0.769** | correct chunk ranked first |
| hit_rate@3 | **1.000** | correct chunk always in the top 3 |
| MRR | **0.885** | mean reciprocal rank |
| mean first rank | 1.23 | |

### Grounding

| Metric | Value | Meaning |
|---|---|---|
| citation_validity | **1.000** | every quote appears verbatim in the source CV |
| citation_in_context | **1.000** | every quote came from the passages actually retrieved |
| unsupported_verdict_rate | **0.000** | no claim is made without a quote |
| summary_numeric_consistency | **1.000** | counts stated in prose match the structured verdicts |
| status_accuracy | **0.839** | verdicts matching human labels exactly |
| status_within_one | **0.935** | verdicts within one step |
| false_evidence_rate | 0.125 | evidence claimed for a skill the CV lacks |
| missed_evidence_rate | **0.000** | real evidence reported as missing |

The grounding contract holds absolutely: **no hallucinated citation was produced in any
configuration tested.** That is the property the whole design is built around.

### Answer scoring

| Metric | Value | Meaning |
|---|---|---|
| spearman | **0.867** | rank correlation with human scores |
| pairwise_accuracy | **0.900** | the better answer scores higher |
| score_mae | 0.867 | mean absolute error |
| within_one | 0.667 | within 1.0 of the human label |
| score_bias | **−0.667** | the system scores *lower* than a human |
| self_consistency_stdev | 0.000 | deterministic by construction (see §5) |

**The rubric ranks well but is calibrated low.** It never awards a 5: the two answers a
human scored 5 came back at 3.2 and 2.8. This is the *opposite* of the usual failure —
models normally inflate — and it is a property of the stub's heuristic scale, which a real
model replaces entirely.

---

## 3. Ablations

Each row disables one technique and re-runs both suites.

| Configuration | hit@1 | MRR | status acc | cite ok |
|---|---|---|---|---|
| **Full pipeline** | **0.769** | **0.885** | **0.839** | 1.000 |
| No re-ranking | 0.692 | 0.846 | 0.806 | 1.000 |
| No BM25 (dense only) | 0.769 | 0.872 | 0.839 | 1.000 |
| No multi-query | 0.769 | 0.885 | 0.839 | 1.000 |
| Dense only, no fusion or re-rank | 0.462 | 0.718 | 0.806 | 1.000 |
| Fixed-size chunking | 0.769 | 0.859 | 0.806 | 1.000 |

### What this says

1. **The retrieval ensemble is the single biggest win.** Stripping fusion and re-ranking
   drops hit@1 from 0.769 to 0.462 — a **30-point** fall. Ranking the right chunk first
   is what the combination buys.
2. **Re-ranking earns its place on its own:** +7.7pp hit@1, +0.039 MRR, +3.3pp status
   accuracy.
3. **Parent-child + contextual chunking is worth +3.3pp status accuracy** over naive
   fixed-size slicing, and +0.026 MRR. Note hit@1 is unchanged — the benefit is in what
   the model *reads*, not in what is found.
4. **Multi-query expansion contributes nothing measurable — a negative result.** Identical
   numbers with it on and off. The likely reason is that the stub embedder is lexical, so
   paraphrases retrieve the same chunks. It stays in the codebase because it should pay
   off against real semantic embeddings, but on this evidence it is *not* currently
   earning the extra LLM call it would cost in the `openai` configuration. It should be
   re-measured, and disabled by default if it still shows nothing.
5. **BM25 alone is marginal** (MRR 0.885 → 0.872) but it supplies the second ranking that
   fusion needs; removing fusion entirely is what hurts.

---

## 4. What the harness found — and changed

The harness was not a rubber stamp. Building it surfaced four defects that the passing
test suite and good-looking demo output had both missed:

| # | Found | Fix | Effect |
|---|---|---|---|
| 1 | Thresholds hand-tuned against a single CV/JD pair did not generalise | Swept on the full golden set; a flat optimum sits at 0.20–0.25, so 0.22 was chosen (the mid-plateau, not the edge) | status accuracy **0.710 → 0.806** |
| 2 | The relevance floor (0.10) discarded genuinely relevant passages whenever CV and job description shared little vocabulary — one cross-domain requirement retrieved a single irrelevant passage | Lowered to 0.02 and always keep the top passage; deciding what counts as evidence is the verdict stage's job, not the retriever's | contributed to the gains below |
| 3 | The best sentence was chosen by coverage *first*, then the decisive-term gate applied to it — so a wordy sentence lacking the term blocked a shorter one containing it. A CV reading *"Built the customer dashboard in React and TypeScript"* was reported as **no evidence of React** | Made selection gate-aware (`textutil.best_evidence`) | status accuracy **0.806 → 0.839**, missed_evidence **0.167 → 0.000** |
| 4 | Splitting on `"."` to find sentence openers broke `Next.js` into `Next` + `js`, so it never matched | Requirements are one sentence; skip only the first word | correct handling of dotted technology names |

### A change the numbers talked me out of

Two remaining errors come from a lexical trap: *"Demonstrated experience mentoring
engineers and raising the standard of code review"* matches a CV containing "code review"
even when it contains no mentoring. The obvious fix — extend the decisive-term gate to
requirements that name no technology — was implemented and measured:

| | exact | within one | false evidence | missed evidence |
|---|---|---|---|---|
| Current rule | **0.839** | **0.935** | 0.125 | **0.000** |
| With fallback gate | 0.774 | 0.871 | **0.062** | 0.250 |

It halves invented evidence but **a quarter of genuinely evidenced requirements would be
reported as missing**. Telling a candidate they lack a skill they have is the worse error
and would be four times more frequent, so the change was rejected. Without the harness I
would have shipped it on intuition.

---

## 5. Honest limits of these numbers

- **The stub provider is lexical, not semantic.** Retrieval, chunking, fusion, re-ranking
  and grounding numbers are real — that code is not stubbed. Absolute answer scores are a
  property of a heuristic rubric and will change completely under a real model.
- **`self_consistency_stdev` is 0.000 by construction**, because the provider is
  deterministic. The metric is implemented and clears the completion cache between
  repeats; it only becomes informative with `LLM_PROVIDER=openai`.
- **Prompt-wording ablations cannot run offline.** The stub reads `prompt.payload`, not the
  rendered text, so few-shot vs zero-shot shows nothing. The prompt registry supports the
  comparison the moment a real provider is configured.
- **The judge is the heuristic one.** It shares the stub's lexical world view, so it cannot
  catch an error both would make; it is reported as indicative only. `--judge llm` runs the
  real LLM-as-judge.
- **31 labels is a small set.** Two thresholds were tuned on it. The 0.20–0.25 plateau is
  reassuring — a spike would have suggested overfitting — but this is calibration on a
  small sample, not a benchmark result.

## 6. Re-running

```bash
cd backend
.venv/bin/python -m evals.run                    # everything, writes evals/results/<ts>.json
.venv/bin/python -m evals.run --suite ablations  # the comparison table
.venv/bin/python -m evals.run --judge llm        # LLM-as-judge (needs LLM_PROVIDER=openai)
.venv/bin/python -m pytest tests/test_metrics.py # the metrics' own unit tests
```
