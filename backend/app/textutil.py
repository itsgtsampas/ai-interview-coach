"""Small, dependency-free text helpers shared by the RAG and stub-LLM layers.

Handles Greek as well as Latin script. Greek needs three things Latin does not:
accents folded away (Άριστη / αριστη), final sigma normalised, and a light
suffix stripper, because the language inflects far more than English and a
requirement saying "γνώση" must match a CV saying "γνώσεις".
"""

import math
import re
import unicodedata

# Greek (0370-03FF) and Greek Extended (1F00-1FFF) alongside Latin, so a Greek
# CV is not invisible to every lexical stage in the pipeline.
_L = r"A-Za-z\u0370-\u03FF\u1F00-\u1FFF"
_WORD = re.compile(
    rf"[{_L}][{_L}0-9+#.\-]*(?:/[{_L}0-9+#.\-]+)+|[{_L}][{_L}0-9+#.\-]{{1,}}"
)
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+")
_ENDS_SENTENCE = re.compile(r"[.!?:;]$")
# A line ending on any of these continues onto the next, even if that line
# starts with a capital.
_DANGLING_END = re.compile(
    r"(?:[,;:\-\u2013\u2014]|\b(?:and|or|with|of|the|a|an|in|to|for|on|at|by|from"
    r"|that|which|including|using|such as))\s*$",
    re.I,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "its", "of", "on", "or", "our", "that", "the", "their", "to",
    "with", "you", "your", "we", "will", "should", "must", "can", "able", "using",
    "use", "used", "experience", "strong", "good", "excellent", "years", "year",
    "plus", "including", "etc", "work", "working", "ability", "knowledge", "skills",
    "team", "teams", "role", "job", "candidate", "this", "they", "who", "what",
    # Job-description boilerplate: it phrases a requirement, it never evidences one.
    "demonstrated", "proven", "practical", "solid", "commercial", "hands", "exposure",
    "familiarity", "comfortable", "attention", "understanding", "expertise", "deep",
    "extensive", "relevant", "ideally", "preferably", "such", "well", "very",
    "fluency", "proficiency", "familiarity", "competence", "mastery", "command",
    "degree", "framework", "frameworks", "api", "apis", "tool", "tools",
    "technology", "technologies", "systems", "platform", "platforms", "stack",
    "library", "libraries", "solutions", "applications", "environment",
    "production", "commercial", "professional", "previous", "prior", "recent",
    "on", "off", "up", "side",
}


# Greek, folded to match `tokens()` output. Two groups, mirroring the English
# list above: grammar (articles, prepositions, conjunctions, auxiliaries), and
# job-description boilerplate - words that phrase a requirement but never
# evidence one, so they must not become the term a verdict hinges on.
STOPWORDS |= {
    # grammar
    "ο", "η", "το", "οι", "τα", "του", "τησ", "των", "τον", "την", "στο", "στη",
    "στην", "στον", "στα", "στουσ", "στισ", "σε", "με", "και", "ή", "για", "απο",
    "που", "ενα", "ενασ", "μια", "μιασ", "ειναι", "εχει", "εχουν", "θα", "να",
    "ωσ", "κατα", "προσ", "ανα", "επι", "υπο", "δια", "μετα", "χωρισ", "αλλα",
    "οπωσ", "οταν", "οπου", "καθε", "ολα", "ολων", "αυτο", "αυτη", "αυτων",
    "τουλαχιστον", "περιπου", "επισησ", "ετων", "ετη", "χρονια", "χρονων",
    # job-description boilerplate
    "εμπειρια", "εμπειριασ", "εμπειριεσ", "γνωση", "γνωσησ", "γνωσεισ",
    "ικανοτητα", "ικανοτητεσ", "δεξιοτητεσ", "προσοντα", "απαραιτητα",
    "επιθυμητα", "απαιτησεισ", "αρμοδιοτητεσ", "καθηκοντα", "προυποθεσεισ",
    "αριστη", "πολυ", "καλη", "καλησ", "ισχυρη", "βαθια", "αποδεδειγμενη",
    "εξοικειωση", "κατανοηση", "συναφουσ", "αντικειμενου", "τομεα", "θεση",
    "ρολο", "ομαδα", "ομαδασ", "εταιρεια", "υποψηφιοσ", "υποψηφιου",
    "κατοχη", "επαγγελματικησ", "επαγγελματικη", "σχετικη", "σχετικησ",
}

SYNONYMS: dict[str, set[str]] = {
    "kubernetes": {"k8s", "eks", "gke", "openshift"},
    "orchestration": {"kubernetes", "k8s", "swarm"},
    "container": {"docker", "containerised", "containerized", "podman"},
    "containerisation": {"docker", "kubernetes", "container"},
    "broker": {"rabbitmq", "kafka", "sqs", "pubsub", "nats"},
    "brokers": {"rabbitmq", "kafka", "sqs", "pubsub", "nats"},
    "messaging": {"rabbitmq", "kafka", "sqs", "queue"},
    "queue": {"rabbitmq", "kafka", "sqs"},
    "observability": {"cloudwatch", "prometheus", "grafana", "monitoring", "logging"},
    "monitoring": {"cloudwatch", "prometheus", "grafana", "alerts", "dashboards"},
    "metrics": {"cloudwatch", "prometheus", "grafana", "dashboards"},
    "tracing": {"jaeger", "opentelemetry", "datadog"},
    "cloud": {"aws", "azure", "gcp", "ec2", "s3", "rds"},
    "ci/cd": {"ci", "cd", "pipeline", "pipelines", "actions", "jenkins", "deploys"},
    # The 5-character prefix rule in _matches cannot bridge these: "restful"[:5]
    # is "restf", which no form of "REST" starts with.
    "restful": {"rest", "rest/soap", "soap/rest"},
    "rest": {"restful", "rest/soap", "soap/rest"},
    "ci": {"jenkins", "actions", "circleci", "pipeline", "pipelines"},
    "cd": {"deploys", "deployment", "pipeline", "pipelines"},
    "pipelines": {"actions", "jenkins", "circleci", "deploys"},
    "database": {"postgresql", "postgres", "mysql", "rds"},
    "databases": {"postgresql", "postgres", "mysql", "rds"},
    "sql": {"postgresql", "postgres", "mysql"},
    "async": {"asyncio", "fastapi", "await"},
    "mentoring": {"mentored", "pairing", "coaching"},
    "graphql": set(),        # deliberately empty: no CV term implies GraphQL
    "terraform": {"pulumi", "cloudformation"},
}


# Naming the language outright beats asking the model to infer it. An English
# system prompt anchors the reply to English hard enough that "answer in the
# same language as the CV" is simply ignored, which is what happened here.
_GREEK_CHARS = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")
_GREEK_SHARE = 0.15


def detect_language(text: str) -> str:
    """"Greek" or "English", from the script the text is mostly written in.

    A Greek CV is full of Latin technology names, so the test is a share rather
    than a presence: well below half, because "Java, Spring Boot, PostgreSQL,
    Docker" in a skills section can easily outweigh a short Greek summary.
    """
    greek = len(_GREEK_CHARS.findall(text))
    latin = len(_LATIN_CHARS.findall(text))
    if greek + latin == 0:
        return "English"
    return "Greek" if greek / (greek + latin) >= _GREEK_SHARE else "English"


def fold(text: str) -> str:
    """Lowercase, strip diacritics, and normalise final sigma.

    Greek marks stress on almost every word and moves it under inflection, so
    "Άριστη" and "άριστης" share no exact prefix until the accents are gone.
    Folding Latin too is harmless and quietly fixes "Café" / "cafe".
    """
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in lowered if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped).replace("\u03c2", "\u03c3")


def tokens(text: str) -> list[str]:
    return [fold(m.group(0)) for m in _WORD.finditer(text)]


def keywords(text: str, *, limit: int = 24) -> list[str]:
    """Content words, de-duplicated, order preserved."""
    seen: dict[str, None] = {}
    for t in tokens(text):
        if len(t) >= 2 and t not in STOPWORDS:
            seen.setdefault(t, None)
    return list(seen)[:limit]


def _is_heading_line(line: str) -> bool:
    if len(line) > 70:
        return False
    if line.endswith(":"):
        return True
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(line.split()) <= 6


def _is_continuation(buffer: str, nxt: str) -> bool:
    """Is `nxt` the rest of a wrapped line, or a new item in its own right?

    Getting this wrong in either direction is costly. Merging everything — the
    original rule, "join unless the line ends in punctuation" — destroys bullet
    lists, and real job postings are bullet lists whose items carry no full
    stop. Merging nothing leaves PDF-wrapped sentences broken mid-clause.

    A wrapped line almost always resumes mid-sentence, so it starts lowercase;
    a new bullet starts with a capital or a digit. The dangling-word check
    catches the remaining case, where a wrap lands just before a proper noun.
    """
    if not buffer:
        return False
    if nxt[:1].islower():
        return True
    return bool(_DANGLING_END.search(buffer))


def reflow(text: str) -> str:
    """Undo the hard line wrapping that PDF extraction produces, without
    flattening lists.

    Sentence splitting depends on this: without it a citation is cut mid-clause
    and reads as truncated in the UI. With too much of it, every requirement in
    a job posting merges into one paragraph and the section headings disappear.
    """
    out: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if buffer:
                out.append(buffer)
                buffer = ""
            continue
        # A heading is a line in its own right: joining it to the paragraph below
        # would destroy the section structure the extractor depends on.
        if _is_heading_line(line):
            if buffer:
                out.append(buffer)
                buffer = ""
            out.append(line)
            continue
        if _is_continuation(buffer, line):
            buffer = f"{buffer} {line}"
        else:
            if buffer:
                out.append(buffer)
            buffer = line
        if _ENDS_SENTENCE.search(line):
            out.append(buffer)
            buffer = ""
    if buffer:
        out.append(buffer)
    return "\n".join(out)


def sentences(text: str) -> list[str]:
    """Split into citable units.

    The length floor keeps fragments out of citations, but a skills list is
    made of entries far shorter than it — "React.js", "Docker" — and those are
    the lines that name a technology. A short line is kept when it names
    something, which is why a CV listing React.js was reported as having no
    evidence of React.
    """
    out = []
    for block in reflow(text).splitlines():
        for raw in _SENT_SPLIT.split(block):
            candidate = raw.strip(" \t•-–—*·›»‣▪")
            if len(candidate) >= 15 or (candidate and salient_terms(candidate)):
                out.append(candidate)
    return out


_GREEK = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")

# Longest first, so "-ματων" is tried before "-ων". Deliberately short: an
# aggressive stemmer conflates unrelated words, and a false match here becomes a
# false citation, which is the expensive error.
_GR_SUFFIXES = (
    "ματων", "ματα", "οντασ", "ωντασ", "μενοσ", "μενη", "μενο",
    "ιδεσ", "εωσ", "εων", "ουσ", "εισ", "ησ", "οσ", "ασ", "εσ", "οι",
    "ων", "ου", "α", "ε", "η", "ι", "ο", "υ",
)
_MIN_GREEK_STEM = 4


def greek_stem(token: str) -> str:
    """Strip one inflectional ending, when what remains is still a real stem.

    Greek inflects heavily: a posting asking for "σχεδιασμό" against a CV saying
    "σχεδίασα" shares no useful prefix. This is not a full stemmer and is not
    meant to be - it removes the endings that separate the same word from
    itself, and leaves everything else alone.
    """
    if not _GREEK.search(token):
        return token
    for suffix in _GR_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_GREEK_STEM:
            return token[: -len(suffix)]
    return token


def _matches(keyword: str, haystack_tokens: set[str]) -> bool:
    if keyword in haystack_tokens:
        return True
    if SYNONYMS.get(keyword, set()) & haystack_tokens:
        return True
    # _WORD keeps slash-compounds whole, so "java" must still match the token
    # "java/spring". Done here, not at tokenisation, to leave IDF weights alone.
    if any("/" in h and keyword in h.split("/") for h in haystack_tokens):
        return True
    # Partial credit for morphological variants: containerise / containerisation.
    if len(keyword) >= 5 and any(h.startswith(keyword[:5]) for h in haystack_tokens):
        return True
    # Greek inflection, which the prefix rule above misses more often than not.
    stem = greek_stem(keyword)
    return stem != keyword and any(greek_stem(h) == stem for h in haystack_tokens)


def salient_terms(text: str) -> list[str]:
    """Capitalised words that are not sentence-initial.

    In a job description these are the technology names — Kubernetes, PostgreSQL,
    FastAPI, AWS, GraphQL — as opposed to the sentence-opening filler ("Strong",
    "Proven", "Hands-on"). Rarity alone is a poor guide to importance: in
    "preferably AWS", "preferably" is the rarer word and the meaningless one.
    """
    out: list[str] = []
    # Every word counts, including the first: a requirement is often just the
    # technology's name. Sentence openers are handled by STOPWORDS.
    for word in text.split():
        cleaned = word.strip("(),;:/\"'").rstrip(".")
        if len(cleaned) >= 2 and any(c.isupper() for c in cleaned):
            for tok in tokens(cleaned):
                if len(tok) < 2 or tok in STOPWORDS:
                    continue
                # "Hands-on", "Full-stack": phrasing, not technologies.
                if any(part in STOPWORDS for part in tok.split("-")):
                    continue
                out.append(tok)
    return list(dict.fromkeys(out))


# Splits one requirement into the separate things it names. Spaced slash only:
# a bare one is inside a token ("CI/CD"), which _WORD keeps whole.
_COORDINATOR = re.compile(
    r"[,;()\[\]]|\s+/\s+|\b(?:or|and|in|of|with|for|to|using|from|across)\b",
    re.I,
)


def _coordinate_groups(text: str) -> list[str]:
    """Split a requirement into the separate things it names."""
    return [part.strip() for part in _COORDINATOR.split(text) if part and part.strip()]


def decisive_hit(needle: str, haystack: str, idf: dict[str, float]) -> bool:
    """Whether a decisive term was actually matched.

    Narrower than `pivot_gate`, which also returns True when the requirement
    named nothing distinctive and there was no gate to apply.
    """
    groups = [g for g in (_coordinate_groups(needle) or [needle]) if salient_terms(g)]
    if not groups:
        return False
    max_idf = max(idf.values(), default=2.0)
    hay = set(tokens(haystack))
    return any(
        _matches(max(salient_terms(g), key=lambda k: idf.get(k, max_idf)), hay)
        for g in groups
    )


def pivot_gate(needle: str, haystack: str, idf: dict[str, float]) -> bool:
    """Whether the CV evidences the decisive term of anything the requirement names.

    Within a compound noun the distinctive modifier is mandatory and the generic
    head is not, so "GraphQL APIs" is not evidenced by a CV with only REST APIs.
    Asked per coordinate group rather than once over the whole sentence: IDF is
    built from the CV, so an absent term carries maximum weight and a single
    decisive term would always be the one the CV lacks.

    How completely the requirement is met is weighted_coverage's job, not this.
    """
    groups = [g for g in (_coordinate_groups(needle) or [needle]) if salient_terms(g)]
    if not groups:
        return True  # nothing distinctive named; coverage alone decides

    max_idf = max(idf.values(), default=2.0)
    hay = set(tokens(haystack))
    for group in groups:
        salient = salient_terms(group)
        decisive = max(salient, key=lambda k: idf.get(k, max_idf))
        if _matches(decisive, hay):
            return True
    return False


def coverage(needle: str, haystack: str) -> float:
    """Unweighted fraction of the needle's keywords present in the haystack."""
    need = keywords(needle)
    if not need:
        return 0.0
    hay = set(tokens(haystack))
    return sum(1 for k in need if _matches(k, hay)) / len(need)


def build_idf(passages: list[str]) -> dict[str, float]:
    """Inverse document frequency over a small corpus.

    Without it, a requirement like "Familiarity with GraphQL APIs" scores 50%
    against any CV that mentions APIs at all — the generic word carries the same
    weight as the distinctive one. IDF makes the rare term the one that decides.
    """
    n = len(passages) or 1
    df: dict[str, int] = {}
    for text in passages:
        for term in set(tokens(text)):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def weighted_coverage(needle: str, haystack: str, idf: dict[str, float]) -> float:
    """Coverage with each keyword weighted by how distinctive it is in the corpus.

    A term absent from the corpus gets the maximum weight: not finding it is the
    strongest possible signal that the requirement is unmet.
    """
    need = keywords(needle)
    if not need:
        return 0.0
    hay = set(tokens(haystack))
    max_idf = max(idf.values(), default=2.0)
    total = matched = 0.0
    for k in need:
        weight = idf.get(k, max_idf)
        total += weight
        if _matches(k, hay):
            matched += weight
    return matched / total if total else 0.0


def best_sentence(query: str, passage: str) -> str:
    """The sentence in `passage` that best covers `query` — returned verbatim.

    Verbatim matters: this string becomes the citation shown in the UI, and the
    eval harness checks that every citation appears literally in its source.
    """
    cands = sentences(passage) or [" ".join(reflow(passage).split())]
    scored = [(coverage(query, s), -abs(len(s) - 140), s) for s in cands]
    scored.sort(reverse=True)
    return scored[0][2][:400]


def best_sentence_weighted(
    query: str, passage: str, idf: dict[str, float]
) -> tuple[str, float]:
    """Return the best-supporting sentence and its weighted coverage.

    The verdict and the quote must come from the same measurement, otherwise the
    evidence shown to the user does not justify the score attached to it.
    """
    cands = sentences(passage) or [" ".join(reflow(passage).split())]
    scored = [(weighted_coverage(query, s, idf), -abs(len(s) - 140), s) for s in cands]
    scored.sort(reverse=True)
    top = scored[0]
    return top[2][:400], top[0]


def best_evidence(
    query: str, passage: str, idf: dict[str, float]
) -> tuple[str, float, bool, bool]:
    """Pick the sentence that best evidences `query`, preferring one that carries
    the requirement's decisive term.

    Selecting purely on coverage and checking the decisive term afterwards lets a
    high-coverage sentence that lacks the term block a lower-coverage sentence
    that has it — which is how a CV reading "Built the customer dashboard in React
    and TypeScript" was reported as no evidence of React.

    Returns (quote, weighted coverage, whether the gate passed, whether a
    decisive term was actually found). The last two differ when the requirement
    names nothing distinctive: the gate opens, but nothing was matched.
    """
    cands = sentences(passage) or [" ".join(reflow(passage).split())]
    scored = [
        (weighted_coverage(query, c, idf), pivot_gate(query, c, idf), -abs(len(c) - 140), c)
        for c in cands
    ]
    gated = [s for s in scored if s[1]]
    pool = gated or scored
    pool.sort(key=lambda t: (t[0], t[2]), reverse=True)
    cov, has_pivot, _, quote = pool[0]
    return quote[:400], cov, has_pivot, decisive_hit(query, quote, idf)
