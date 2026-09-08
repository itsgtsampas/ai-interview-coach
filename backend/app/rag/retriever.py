"""The online query pipeline, assembled.

    requirement
      -> multi-query expansion
      -> dense search per variant  (metadata-filtered to this user + session)
      -> BM25 over the same corpus
      -> reciprocal rank fusion
      -> re-rank
      -> resolve children to parents (small-to-big)
      -> relevance floor

Every stage is switchable so the eval harness can measure each one's
contribution independently rather than asserting it helps.
"""

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.rag import store
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.query_analysis import expand
from app.rag.rerank import get_reranker
from app.rag.store import Retrieved
from app.textutil import tokens

# Only true noise is dropped here. The floor used to be 0.10, which discarded
# relevant passages whenever the CV and the job description shared little
# vocabulary — the eval harness caught this on a cross-domain pair, where a
# requirement about bundle size retrieved one irrelevant passage instead of four
# relevant ones. Deciding what counts as evidence is the verdict stage's job,
# not the retriever's.
SCORE_FLOOR = 0.02


@dataclass
class RetrievalConfig:
    """Ablation switches. Defaults are the full pipeline."""

    multi_query: bool = True
    bm25: bool = True
    rerank: bool = True
    candidate_k: int = 15
    top_k: int = 5
    max_variants: int = 3


@dataclass
class Passage:
    chunk_id: str
    text: str          # parent text: what the LLM reads
    section: str
    page: int
    score: float

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "section": self.section,
            "page": self.page,
            "score": round(self.score, 4),
        }


def _bm25_ranking(query: str, corpus: list[Retrieved], limit: int) -> list[Retrieved]:
    if not corpus:
        return []
    tokenised = [tokens(c.text) or ["_"] for c in corpus]
    bm25 = BM25Okapi(tokenised)
    scores = bm25.get_scores(tokens(query) or ["_"])
    ranked = sorted(zip(corpus, scores), key=lambda pair: -pair[1])
    return [c for c, s in ranked[:limit] if s > 0]


def rank_chunks(
    query: str,
    *,
    user_id: int,
    session_id: int,
    doc_kind: str = "cv",
    config: RetrievalConfig | None = None,
) -> list[Retrieved]:
    """The ranked CHILD chunks, before they are resolved to parents.

    Retrieval quality has to be measured here: children are what the index
    actually ranks, and a parent section is coarse enough that several distinct
    queries resolve to the same one.
    """
    cfg = config or RetrievalConfig()
    variants = expand(query, max_variants=cfg.max_variants) if cfg.multi_query else [query]

    rankings: list[list[Retrieved]] = []
    for variant in variants:
        hits = store.query(
            variant,
            user_id=user_id,
            session_id=session_id,
            doc_kind=doc_kind,
            top_k=cfg.candidate_k,
        )
        if hits:
            rankings.append(hits)

    if cfg.bm25:
        corpus = store.all_chunks(user_id=user_id, session_id=session_id, doc_kind=doc_kind)
        lexical = _bm25_ranking(query, corpus, cfg.candidate_k)
        if lexical:
            rankings.append(lexical)

    if not rankings:
        return []

    fused = reciprocal_rank_fusion(rankings) if len(rankings) > 1 else rankings[0]
    return get_reranker(cfg.rerank).rerank(query, fused, top_k=cfg.candidate_k)


def retrieve(
    query: str,
    *,
    user_id: int,
    session_id: int,
    doc_kind: str = "cv",
    config: RetrievalConfig | None = None,
) -> list[Passage]:
    cfg = config or RetrievalConfig()
    reranked = rank_chunks(
        query, user_id=user_id, session_id=session_id, doc_kind=doc_kind, config=cfg
    )

    # Small-to-big: matched on the child, hand the LLM the whole parent section,
    # one passage per parent.
    seen: set[str] = set()
    passages: list[Passage] = []
    for hit in reranked:
        if hit.parent_id in seen:
            continue
        seen.add(hit.parent_id)
        passages.append(Passage(
            chunk_id=hit.chunk_id,
            text=hit.parent_text or hit.text,
            section=hit.section,
            page=hit.page,
            score=hit.score,
        ))
        if len(passages) >= cfg.top_k:
            break

    # Below the floor a passage is noise. Always keep the best one regardless, so
    # the verdict stage sees the strongest candidate and can reject it on the
    # record rather than never seeing it.
    kept = [p for p in passages if p.score >= SCORE_FLOOR]
    return kept or passages[:1]
