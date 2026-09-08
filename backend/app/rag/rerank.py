"""Re-ranking: recall -> precision.

Retrieval casts a wide net so nothing relevant is lost; re-ranking scores each
candidate against the query directly and keeps only the best.  Behind an
interface with a no-op implementation so the eval harness can measure exactly
what re-ranking contributes.
"""

from typing import Protocol

from app.rag.store import Retrieved
from app.textutil import coverage


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, candidates: list[Retrieved], *, top_k: int) -> list[Retrieved]: ...


class NoopReranker:
    """Ablation baseline: keep retrieval order untouched."""

    name = "noop"

    def rerank(self, query: str, candidates: list[Retrieved], *, top_k: int) -> list[Retrieved]:
        return candidates[:top_k]


class LexicalCoverageReranker:
    """Scores each candidate on how completely it covers the query's content words.

    A cross-encoder is the production answer; this is its offline stand-in and
    slots into the same interface.
    """

    name = "lexical-coverage"

    def rerank(self, query: str, candidates: list[Retrieved], *, top_k: int) -> list[Retrieved]:
        scored = []
        for c in candidates:
            cov = coverage(query, c.text)
            # Retrieval rank still carries signal; blend rather than replace.
            blended = 0.75 * cov + 0.25 * min(1.0, max(0.0, c.score))
            scored.append(Retrieved(
                chunk_id=c.chunk_id, parent_id=c.parent_id, text=c.text,
                section=c.section, page=c.page, doc_kind=c.doc_kind, score=blended,
                parent_text=c.parent_text,
            ))
        scored.sort(key=lambda r: -r.score)
        return scored[:top_k]


def get_reranker(enabled: bool = True) -> Reranker:
    return LexicalCoverageReranker() if enabled else NoopReranker()
