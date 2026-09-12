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


# --- real-world document shapes -------------------------------------------

def test_reflow_keeps_bullets_apart_but_joins_wrapped_sentences():
    """The two jobs pull in opposite directions and both must hold.

    Job postings are bullet lists whose items carry no full stop; PDF text is
    prose broken mid-clause. An earlier rule joined any line not ending in
    punctuation, which merged a whole requirements section into one paragraph
    and made its heading unfindable.
    """
    from app.textutil import reflow

    bullets = reflow("What you'll need\nFluency with Java\n4+ years of experience")
    assert bullets.splitlines() == [
        "What you'll need", "Fluency with Java", "4+ years of experience",
    ]

    wrapped = reflow("Rebuilt the checkout API in Python and FastAPI, replacing a\n"
                     "legacy Flask service.")
    assert wrapped == "Rebuilt the checkout API in Python and FastAPI, replacing a legacy Flask service."

    # A wrap landing just before a proper noun still joins, because the previous
    # line ends on a word that cannot end a sentence.
    assert reflow("Strong commercial experience with\nPython and FastAPI") == (
        "Strong commercial experience with Python and FastAPI")


def test_letter_spaced_headings_are_repaired():
    """Designer CV templates set letter-spacing, which extracts as 'C O N T A C T'."""
    from app.rag.loader import unspace

    assert unspace("C O N T A C T") == "CONTACT"
    assert unspace("S o f t w a r e  E n g i n e e r") == "Software  Engineer"
    # Ordinary prose, including real single-letter words, is left alone.
    assert unspace("I am a backend engineer") == "I am a backend engineer"
    assert unspace("Python, SQL and Go") == "Python, SQL and Go"


# --- the pivot gate, and the ways it went wrong ----------------------------
#
# A real Java CV scored 19/100 against a real Java posting. Every failure below
# is one of the reasons, reduced to the smallest case that reproduces it.

CV = (
    "CORE SKILLS\n"
    "Java EE / Java 21\nSpring Boot\nMicroservices\nREST APIs / SOAP\n"
    "Hibernate\nOracle SQL / MySQL / PG\nMaven . Git\nCI/CD Pipelines\n"
    "PROFILE\n"
    "Software Engineer with 3+ years of experience. Specialises in Java/Spring Boot "
    "backend development, microservices architecture, and enterprise application "
    "engineering.\n"
    "EXPERIENCE\n"
    "Migrated legacy Java 8 enterprise applications to Java 17, covering dependency "
    "upgrades, API compatibility, and runtime validation across multiple modules.\n"
    "EDUCATION\nBSc in Computer Science\n"
)


def _verdict(requirement: str, cv: str = CV):
    from app.textutil import best_evidence, build_idf

    idf = build_idf([cv])
    return best_evidence(requirement, cv, idf)


def test_a_requirement_naming_several_things_is_not_gated_on_the_one_absent_term():
    """IDF is built from the CV, so a term the CV lacks carries the most weight.

    Choosing one decisive term across the whole requirement therefore picked the
    term the CV did NOT have, every time. "Solid knowledge of Java (17+), the JVM
    ecosystem and object-oriented design" hinged on JVM and reported a Java CV as
    having no Java.
    """
    _, _, gate, decisive = _verdict(
        "Solid knowledge of Java (17+), the JVM ecosystem and object-oriented design"
    )
    assert gate and decisive, "the CV plainly evidences Java"


def test_a_compound_noun_still_requires_its_distinctive_modifier():
    """The protection the gate exists for must survive the fix above.

    "Familiarity with GraphQL APIs" is not evidenced by a CV that only has REST
    APIs — within a compound, the modifier is mandatory and the head is not.
    """
    _, _, _, decisive = _verdict("Familiarity with GraphQL APIs")
    assert not decisive


def test_a_slash_compound_in_the_cv_does_not_hide_its_parts():
    """_WORD keeps "CI/CD" whole, which also buries Java inside "Java/Spring"."""
    from app.textutil import _matches, tokens

    hay = set(tokens("Specialises in Java/Spring Boot backend development"))
    assert _matches("java", hay), "the CV says Java, in a slash compound"
    assert _matches("spring", hay)
    assert not _matches("python", hay), "matching parts must not match anything"


def test_rest_and_restful_are_the_same_requirement():
    """The 5-character prefix rule cannot bridge these: "restf" vs "rest"."""
    _, _, _, decisive = _verdict("Experience designing and consuming RESTful APIs")
    assert decisive


def test_an_alternative_the_cv_satisfies_counts():
    """"Quarkus (or Spring Boot ...)" is met by a CV with Spring Boot."""
    _, _, _, decisive = _verdict(
        "Experience with the Quarkus framework (or Spring Boot with willingness "
        "to move to Quarkus)"
    )
    assert decisive


def test_a_degree_requirement_is_not_gated_on_the_word_bachelor():
    _, _, _, decisive = _verdict(
        "Bachelor's degree in Computer Science or a related field"
    )
    assert decisive, "the CV says BSc in Computer Science"


def test_a_genuinely_absent_skill_is_still_absent():
    """The whole point: none of the above may turn a gap into evidence."""
    for absent in (
        "Experience with Couchbase or another NoSQL document database",
        "Familiarity with containers and orchestration (Docker, Kubernetes)",
        "Experience with messaging / event-driven architectures (e.g. Kafka)",
    ):
        _, _, _, decisive = _verdict(absent)
        assert not decisive, f"{absent!r} is not in this CV"
