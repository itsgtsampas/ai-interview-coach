"""ChromaDB vector store.

One collection holds every chunk from every user.  Isolation is enforced by a
metadata filter carrying user_id and session_id on EVERY query — the RBAC
pattern for RAG: the retriever can only ever see chunks the caller owns, so a
document cannot leak into another user's LLM context.
"""

import os
import threading

# Must be set before chromadb is imported.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "none")

import logging

# chromadb 0.5.x calls its telemetry client with the wrong signature and
# logs an error per collection access. Nothing is sent; silence the noise.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.rag.chunker import ChunkedDocument
from app.rag.embedder import get_embedder

COLLECTION = "documents"

# Chroma's PersistentClient is not safe for concurrent writes: its internal
# subscription set is mutated while being iterated, which raises
# "Set changed size during iteration" when two writes overlap. Our two
# documents are indexed in separate background tasks, so they do overlap.
# Serialising writes here costs nothing at this scale and removes the race.
# Note this never reproduced under TestClient, which runs background tasks
# sequentially — it needs a real ASGI server to surface.
_WRITE_LOCK = threading.Lock()


@dataclass
class Retrieved:
    chunk_id: str
    parent_id: str
    text: str
    section: str
    page: int
    doc_kind: str
    score: float
    parent_text: str = ""


class _EmbeddingFunctionAdapter:
    """Adapts our Embedder to Chroma's interface.

    Supplying one stops Chroma instantiating its default ONNX model, so no model
    download ever happens.
    """

    def __init__(self) -> None:
        self._embedder = get_embedder()

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma's arg name
        return self._embedder.embed(list(input))

    def name(self) -> str:
        return self._embedder.name


_CLIENT: chromadb.ClientAPI | None = None
_CLIENT_LOCK = threading.Lock()


def get_client() -> chromadb.ClientAPI:
    """Build the Chroma client once, under a lock.

    functools.lru_cache does not serialise the call it memoises: concurrent
    first callers each construct a client, and Chroma's tenant setup races with
    itself ("Could not connect to tenant default_tenant"). Double-checked
    locking keeps the fast path lock-free after the first call.
    """
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                settings = get_settings()
                settings.ensure_dirs()
                _CLIENT = chromadb.PersistentClient(
                    path=str(settings.chroma_dir),
                    settings=ChromaSettings(
                        anonymized_telemetry=False, allow_reset=True
                    ),
                )
    return _CLIENT


def get_collection():
    return get_client().get_or_create_collection(
        name=COLLECTION,
        embedding_function=_EmbeddingFunctionAdapter(),
        metadata={"hnsw:space": "cosine"},
    )


def index_document(
    chunked: ChunkedDocument, *, user_id: int, session_id: int, document_id: int, doc_kind: str
) -> int:
    """Upsert every child chunk. Parent text rides along in metadata so that
    small-to-big retrieval needs no second store."""
    collection = get_collection()
    parents = {p.id: p for p in chunked.parents}

    ids, docs, metas = [], [], []
    for child in chunked.children:
        parent = parents.get(child.parent_id)
        ids.append(f"u{user_id}-s{session_id}-{child.id}")
        docs.append(child.embed_text)
        metas.append({
            "user_id": user_id,
            "session_id": session_id,
            "document_id": document_id,
            "doc_kind": doc_kind,
            "chunk_id": child.id,
            "parent_id": child.parent_id,
            "section": child.section or "",
            "page": int(child.page),
            "child_text": child.text,
            "parent_text": parent.text if parent else child.text,
        })

    if ids:
        with _WRITE_LOCK:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def query(
    text: str, *, user_id: int, session_id: int, doc_kind: str, top_k: int = 8
) -> list[Retrieved]:
    collection = get_collection()
    where: dict[str, Any] = {
        "$and": [
            {"user_id": {"$eq": user_id}},
            {"session_id": {"$eq": session_id}},
            {"doc_kind": {"$eq": doc_kind}},
        ]
    }
    try:
        res = collection.query(query_texts=[text], n_results=top_k, where=where)
    except Exception:
        return []

    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out: list[Retrieved] = []
    for meta, dist in zip(metas, dists):
        out.append(Retrieved(
            chunk_id=str(meta.get("chunk_id", "")),
            parent_id=str(meta.get("parent_id", "")),
            text=str(meta.get("child_text", "")),
            section=str(meta.get("section", "")),
            page=int(meta.get("page", 0) or 0),
            doc_kind=str(meta.get("doc_kind", "")),
            score=1.0 - float(dist),  # cosine distance -> similarity
            parent_text=str(meta.get("parent_text", "")),
        ))
    return out


def all_chunks(*, user_id: int, session_id: int, doc_kind: str) -> list[Retrieved]:
    """Every chunk for one document kind — the corpus BM25 scores against."""
    collection = get_collection()
    where: dict[str, Any] = {
        "$and": [
            {"user_id": {"$eq": user_id}},
            {"session_id": {"$eq": session_id}},
            {"doc_kind": {"$eq": doc_kind}},
        ]
    }
    try:
        res = collection.get(where=where)
    except Exception:
        return []
    out = []
    for meta in res.get("metadatas") or []:
        out.append(Retrieved(
            chunk_id=str(meta.get("chunk_id", "")),
            parent_id=str(meta.get("parent_id", "")),
            text=str(meta.get("child_text", "")),
            section=str(meta.get("section", "")),
            page=int(meta.get("page", 0) or 0),
            doc_kind=str(meta.get("doc_kind", "")),
            score=0.0,
            parent_text=str(meta.get("parent_text", "")),
        ))
    return out


def parent_text(parent_id: str, *, user_id: int, session_id: int) -> str | None:
    collection = get_collection()
    try:
        res = collection.get(where={"$and": [
            {"user_id": {"$eq": user_id}},
            {"session_id": {"$eq": session_id}},
            {"parent_id": {"$eq": parent_id}},
        ]})
    except Exception:
        return None
    metas = res.get("metadatas") or []
    return str(metas[0].get("parent_text")) if metas else None


def delete_session(*, user_id: int, session_id: int) -> None:
    """Purge every vector for a session. Called when the user deletes it."""
    try:
        with _WRITE_LOCK:
            get_collection().delete(where={"$and": [
                {"user_id": {"$eq": user_id}},
                {"session_id": {"$eq": session_id}},
            ]})
    except Exception:
        pass
