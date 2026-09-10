from app.rag.chunker import chunk_document, split_sections
from app.rag.embedder import StubEmbedder
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.loader import LoadedDocument, LoadedPage
from app.rag.query_analysis import expand
from app.rag.store import Retrieved
from app.textutil import best_sentence, coverage


def _doc() -> LoadedDocument:
    return LoadedDocument(pages=[LoadedPage(number=1, text=(
        "EXPERIENCE\n"
        "Senior Backend Engineer, Nexora (2021-2024)\n"
        "Rebuilt the checkout API in Python and FastAPI, cutting p99 from 840ms to 210ms.\n"
        "Designed the PostgreSQL schema and partitioned the orders table.\n"
        "SKILLS\n"
        "Python, FastAPI, PostgreSQL, Docker, AWS\n"
    ))])


def test_sections_are_detected_from_headings():
    names = [s[0] for s in split_sections(_doc())]
    assert "EXPERIENCE" in names and "SKILLS" in names


def test_children_carry_a_breadcrumb_and_map_to_a_parent():
    chunked = chunk_document(_doc(), doc_key="cv1", doc_label="CV")
    assert chunked.parents and chunked.children
    child = chunked.children[0]
    assert child.embed_text.startswith("[CV")           # contextual prefix
    assert child.parent_id in {p.id for p in chunked.parents}  # parent-child link


def test_embeddings_are_deterministic_and_normalised():
    e = StubEmbedder(dim=64)
    a, b = e.embed(["python fastapi"])[0], e.embed(["python fastapi"])[0]
    assert a == b
    assert abs(sum(x * x for x in a) ** 0.5 - 1.0) < 1e-6


def test_similar_text_scores_higher_than_unrelated_text():
    e = StubEmbedder(dim=256)
    q, close, far = e.embed([
        "PostgreSQL schema design",
        "Designed the PostgreSQL schema for the orders domain",
        "Baked a chocolate cake for the office party",
    ])
    dot = lambda x, y: sum(a * b for a, b in zip(x, y))  # noqa: E731
    assert dot(q, close) > dot(q, far)


def test_multi_query_expansion_adds_synonyms():
    variants = expand("Production experience with Kubernetes")
    assert len(variants) > 1
    assert any("k8s" in v or "container" in v for v in variants)


def test_rrf_rewards_agreement_across_rankings():
    def r(cid): return Retrieved(cid, f"p-{cid}", cid, "s", 1, "cv", 0.0)
    # 'b' is second in both rankings; 'a' and 'c' each win one.
    fused = reciprocal_rank_fusion([[r("a"), r("b")], [r("c"), r("b")]])
    assert fused[0].chunk_id == "b"


def test_best_sentence_is_returned_verbatim():
    passage = ("Designed the PostgreSQL schema for the orders domain. "
               "Mentored two junior engineers through their first year.")
    quote = best_sentence("PostgreSQL schema", passage)
    assert quote in passage           # verbatim: the citation contract
    assert "PostgreSQL" in quote


def test_coverage_is_bounded_and_ordered():
    assert coverage("python fastapi", "I use Python and FastAPI daily") == 1.0
    assert coverage("kubernetes terraform", "I use Python and FastAPI daily") == 0.0


def test_concurrent_indexing_does_not_race(tmp_path):
    """Two documents are indexed in separate background tasks, so their writes
    to the vector store overlap.

    Chroma's PersistentClient mutates an internal subscription set while
    iterating it, which raises "Set changed size during iteration" when two
    writes land at once. TestClient runs background tasks sequentially, so this
    only ever appeared against a real ASGI server — hence an explicit test.
    """
    from concurrent.futures import ThreadPoolExecutor

    from app.rag import store
    from app.rag.chunker import chunk_document
    from app.rag.loader import LoadedDocument, LoadedPage

    def index(n: int) -> int:
        doc = LoadedDocument(pages=[LoadedPage(number=1, text=(
            f"EXPERIENCE\nEngineer {n} built services in Python and FastAPI.\n"
            f"SKILLS\nPython, PostgreSQL, Docker, AWS, pytest, RabbitMQ\n"
        ))])
        chunked = chunk_document(doc, doc_key=f"race{n}", doc_label="CV")
        return store.index_document(
            chunked, user_id=9000 + n, session_id=9000 + n,
            document_id=n, doc_kind="cv",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(index, range(8)))

    assert all(c > 0 for c in counts), "every concurrent write must succeed"
    # And each writer's chunks must be retrievable under its own filter.
    for n in range(8):
        assert store.all_chunks(user_id=9000 + n, session_id=9000 + n, doc_kind="cv")
