"""Stage 4 of indexing: text -> vector.

The stub embedder is a signed hashing vectorizer over word tokens plus character
4-grams, L2-normalised.  It is deterministic, needs no network or model download,
and gives genuine lexical-similarity retrieval — enough for the pipeline to work
end to end.  It is not semantic: synonyms do not converge.  The multi-query
expansion in query_analysis.py exists partly to compensate.

Set EMBEDDING_PROVIDER=openai to swap in text-embedding-3-small (1536-dim).
"""

import hashlib
import math
from typing import Protocol

from app.config import get_settings
from app.llm.cache import content_hash, embedding_cache
from app.textutil import tokens


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    index = int.from_bytes(digest[:4], "big") % dim
    sign = 1.0 if digest[4] & 1 else -1.0
    return index, sign


class StubEmbedder:
    name = "stub-hashing"

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or get_settings().embedding_dim

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = tokens(text)
        for tok in toks:
            i, s = _bucket(f"w:{tok}", self.dim)
            vec[i] += s * 1.0
            # Character 4-grams give partial credit for morphological variants
            # ("containerise" / "containerisation").
            if len(tok) >= 5:
                for k in range(len(tok) - 3):
                    j, s2 = _bucket(f"g:{tok[k:k + 4]}", self.dim)
                    vec[j] += s2 * 0.35
        for a, b in zip(toks, toks[1:]):
            i, s = _bucket(f"b:{a}_{b}", self.dim)
            vec[i] += s * 0.6
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            key = content_hash(self.name, str(self.dim), t)
            cached = embedding_cache.get(key)
            if cached:
                out.append([float(x) for x in cached.split(",")])
                continue
            vec = self._one(t)
            # repr() round-trips a float exactly; formatting to fixed decimals
            # would make a cached vector differ from a freshly computed one.
            embedding_cache.set(key, ",".join(repr(v) for v in vec))
            out.append(vec)
        return out


class OpenAIEmbedder:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            from app.exceptions import ProviderUnavailable

            raise ProviderUnavailable(
                "EMBEDDING_PROVIDER is 'openai' but OPENAI_API_KEY is not set."
            )
        self._key = settings.openai_api_key
        self._model = settings.openai_embedding_model
        self.dim = 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        from app.exceptions import ProviderUnavailable

        out: list[list[float]] = []
        for start in range(0, len(texts), 100):  # batch, per provider limits
            batch = texts[start:start + 100]
            try:
                r = httpx.post(
                    "https://api.openai.com/v1/embeddings",
                    json={"model": self._model, "input": batch},
                    headers={"Authorization": f"Bearer {self._key}"},
                    timeout=60.0,
                )
                r.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"Embedding request failed: {exc}") from exc
            out.extend(d["embedding"] for d in r.json()["data"])
        return out


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        provider = get_settings().embedding_provider.lower()
        _embedder = OpenAIEmbedder() if provider == "openai" else StubEmbedder()
    return _embedder
