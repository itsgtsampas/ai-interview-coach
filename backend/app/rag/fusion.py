"""Reciprocal Rank Fusion.

Merges rankings that use incompatible score scales — dense cosine similarity and
BM25 term weights — by using rank position alone.  A chunk that places well in
several rankings rises above one that wins a single ranking outright.

    RRF(d) = sum over rankings of 1 / (k + rank(d))
"""

from app.rag.store import Retrieved

K = 60


def reciprocal_rank_fusion(rankings: list[list[Retrieved]], *, k: int = K) -> list[Retrieved]:
    scores: dict[str, float] = {}
    seen: dict[str, Retrieved] = {}

    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            if not item.chunk_id:
                continue
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
            seen.setdefault(item.chunk_id, item)

    fused = []
    for chunk_id, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        item = seen[chunk_id]
        fused.append(Retrieved(
            chunk_id=item.chunk_id,
            parent_id=item.parent_id,
            text=item.text,
            section=item.section,
            page=item.page,
            doc_kind=item.doc_kind,
            score=score,
            parent_text=item.parent_text,
        ))
    return fused
