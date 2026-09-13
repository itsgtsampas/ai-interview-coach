"""Greek-language handling.

The pipeline's lexical stages were Latin-only: `[A-Za-z]` saw nothing in a Greek
CV, so retrieval, coverage and the pivot gate all operated on whatever Latin
technology names happened to survive. A Greek CV lost evidence it plainly had.
"""

import pytest

from app.services.analysis import locate_citation, verify_citation
from app.textutil import _matches, fold, greek_stem, keywords, salient_terms, tokens

CV = (
    "Μηχανικός Λογισμικού με 4 χρόνια εμπειρίας στην ανάπτυξη backend εφαρμογών. "
    "Ανέπτυξα μικροϋπηρεσία διαχείρισης παραγγελιών σε Java 17 και Spring Boot. "
    "Σχεδίασα το σχήμα της βάσης δεδομένων PostgreSQL για τον τομέα των πληρωμών, "
    "μειώνοντας τον χρόνο απόκρισης. "
    "Υλοποίησα δοκιμές μονάδας με JUnit. "
    "Πτυχίο Πληροφορικής, Οικονομικό Πανεπιστήμιο Αθηνών. Αγγλικά (C1)."
)


def test_greek_words_are_tokenised_at_all():
    """The original regex returned only the Latin fragments."""
    got = tokens("Ανέπτυξα μικροϋπηρεσία σε Java")
    assert "java" in got
    assert any(t.startswith("ανεπτυξ") for t in got), got
    assert len(got) >= 3, "Greek words must not vanish"


def test_accents_and_final_sigma_are_folded():
    assert fold("Άριστη") == fold("αριστη")
    assert fold("ΓΝΩΣΗΣ") == fold("γνώσης")
    assert fold("πληροφορικής")[-1] == fold("πληροφορικης")[-1]
    # final sigma and medial sigma must not be different characters
    assert fold("Λογισμικός") == "λογισμικοσ"


def test_latin_is_unaffected_by_folding():
    assert tokens("Built a CI/CD pipeline with Docker") == [
        "built", "ci/cd", "pipeline", "with", "docker"
    ]


@pytest.mark.parametrize("a,b", [
    ("πτυχίο", "πτυχίου"),
    ("δοκιμές", "δοκιμών"),
    ("σχεδιασμό", "σχεδίασα"),
    ("εμπειρία", "εμπειρίας"),
])
def test_inflected_forms_match_each_other(a, b):
    """Greek inflects far more than English; a requirement and a CV rarely agree
    on the case ending of the same word."""
    assert _matches(fold(a), set(tokens(b))), f"{a} should match {b}"


def test_greek_boilerplate_does_not_become_a_decisive_term():
    """"Εμπειρία" and "γνώση" phrase a requirement; they never evidence one."""
    got = salient_terms("Άριστη γνώση Java 17 και εμπειρία σε RESTful APIs")
    assert "java" in got
    for boilerplate in ("γνωση", "εμπειρια", "αριστη"):
        assert boilerplate not in got, f"{boilerplate} must be a stopword"


def test_a_real_greek_requirement_finds_its_evidence():
    hay = set(tokens(CV))
    for term in ("πτυχίου", "δοκιμών", "postgresql", "σχεδιασμό"):
        assert _matches(fold(term), hay), f"{term} is evidenced in this CV"
    for absent in ("kubernetes", "kafka"):
        assert not _matches(absent, hay), f"{absent} is not in this CV"


def test_greek_stem_leaves_latin_alone():
    for word in ("kubernetes", "postgresql", "ci/cd", "fastapi"):
        assert greek_stem(word) == word


# --- citation verification -------------------------------------------------

PASSAGES = [{"text": "Σχεδίασα το σχήμα της βάσης δεδομένων PostgreSQL για τον "
                     "τομέα των πληρωμών, μειώνοντας τον χρόνο απόκρισης."}]


def test_a_clause_closed_with_a_full_stop_still_verifies():
    """Models quote a clause and terminate it. The source has a comma there.

    Rejecting that cost four correct verdicts in one Greek run, because the
    dropped citation takes its verdict down to "missing".
    """
    quoted = "Σχεδίασα το σχήμα της βάσης δεδομένων PostgreSQL για τον τομέα των πληρωμών."
    assert verify_citation(quoted, PASSAGES)


def test_the_stored_quote_is_the_sources_own_text():
    """What the interface shows must be the document's characters, not a retyping."""
    quoted = "σχεδίασα το σχήμα της βάσης δεδομένων postgresql."
    found = locate_citation(quoted, PASSAGES)
    assert found is not None
    assert found in PASSAGES[0]["text"], "must be a literal span of the source"
    assert found.startswith("Σχεδίασα"), "original capitalisation is preserved"


def test_an_invented_quote_is_still_rejected():
    """The tolerance must not let a fabrication through."""
    assert not verify_citation("Σχεδίασα ένα σύστημα Kubernetes για τη διαχείριση.", PASSAGES)
    assert locate_citation("Designed a Kubernetes cluster.", PASSAGES) is None


# --- the exported PDF ------------------------------------------------------

def test_the_pdf_labels_follow_the_documents_language():
    """A Greek quote under an English heading reads as a mistake.

    The export renders the CV's own sentences, so its fixed furniture -
    COMPETENCIES, EVIDENCED, the footer - has to follow the content rather than
    stay in whatever language the code was written in.
    """
    from app.services.pdf_export import BANDS_EL, CRITERIA_EL, LABELS

    assert set(LABELS) == {"English", "Greek"}
    assert set(LABELS["English"]) == set(LABELS["Greek"]), "label sets must match"
    for key, value in LABELS["Greek"].items():
        if key == "wordmark":
            continue  # the product name is not translated
        assert value != LABELS["English"][key], f"{key} was left in English"

    # The model hands back bands and rubric dimensions in English, because the
    # prompts name them literally. They behave as enums, like in the interface.
    assert BANDS_EL["Interview ready"].startswith("Έτοιμος")
    assert CRITERIA_EL["Trade-offs"] == "Συμβιβασμοί"


def test_an_unknown_band_falls_through_untranslated():
    """A model that invents a band must not produce a blank on the page."""
    from app.services.pdf_export import BANDS_EL

    assert BANDS_EL.get("Something new", "Something new") == "Something new"
