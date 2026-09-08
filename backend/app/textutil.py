"""Small, dependency-free text helpers shared by the RAG and stub-LLM layers."""

import math
import re

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*(?:/[A-Za-z0-9+#.\-]+)+|[A-Za-z][A-Za-z0-9+#.\-]{1,}")
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+")
_ENDS_SENTENCE = re.compile(r"[.!?:;]$")

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


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text)]


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


def reflow(text: str) -> str:
    """Undo the hard line wrapping that PDF extraction produces.

    A line that does not end in sentence punctuation is a continuation of the
    next one. Without this, sentence splitting cuts citations mid-clause and the
    quote shown in the UI reads as truncated.
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
        buffer = f"{buffer} {line}".strip() if buffer else line
        if _ENDS_SENTENCE.search(line):
            out.append(buffer)
            buffer = ""
    if buffer:
        out.append(buffer)
    return "\n".join(out)


def sentences(text: str) -> list[str]:
    out = []
    for block in reflow(text).splitlines():
        for raw in _SENT_SPLIT.split(block):
            s = raw.strip(" \t•-–—*·")
            if len(s) >= 15:
                out.append(s)
    return out


def _matches(keyword: str, haystack_tokens: set[str]) -> bool:
    if keyword in haystack_tokens:
        return True
    if SYNONYMS.get(keyword, set()) & haystack_tokens:
        return True
    # Partial credit for morphological variants: containerise / containerisation.
    return len(keyword) >= 5 and any(h.startswith(keyword[:5]) for h in haystack_tokens)


def salient_terms(text: str) -> list[str]:
    """Capitalised words that are not sentence-initial.

    In a job description these are the technology names — Kubernetes, PostgreSQL,
    FastAPI, AWS, GraphQL — as opposed to the sentence-opening filler ("Strong",
    "Proven", "Hands-on"). Rarity alone is a poor guide to importance: in
    "preferably AWS", "preferably" is the rarer word and the meaningless one.
    """
    out: list[str] = []
    # A requirement is one sentence, so only its first word is a sentence opener.
    # Splitting on "." to find openers would break "Next.js" into "Next" and "js".
    for word in text.split()[1:]:
        cleaned = word.strip("(),;:/\"'").rstrip(".")
        if len(cleaned) >= 2 and any(c.isupper() for c in cleaned):
            for tok in tokens(cleaned):
                if tok not in STOPWORDS and len(tok) >= 2:
                    out.append(tok)
    return list(dict.fromkeys(out))


def pivot_gate(needle: str, haystack: str, idf: dict[str, float]) -> bool:
    """Does the haystack contain the requirement's decisive term?

    When a requirement names technologies, the most distinctive of them must be
    present: "Familiarity with GraphQL APIs" is not evidenced by a CV that only
    mentions APIs. When a requirement names no technology at all ("mentoring
    engineers"), there is no decisive term and coverage alone decides.
    """
    salient = salient_terms(needle)
    if not salient:
        return True  # no gate to apply
    max_idf = max(idf.values(), default=2.0)
    decisive = max(salient, key=lambda k: idf.get(k, max_idf))
    return _matches(decisive, set(tokens(haystack)))


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
) -> tuple[str, float, bool]:
    """Pick the sentence that best evidences `query`, preferring one that carries
    the requirement's decisive term.

    Selecting purely on coverage and checking the decisive term afterwards lets a
    high-coverage sentence that lacks the term block a lower-coverage sentence
    that has it — which is how a CV reading "Built the customer dashboard in React
    and TypeScript" was reported as no evidence of React.

    Returns (quote, weighted coverage, whether the decisive term is present).
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
    return quote[:400], cov, has_pivot
