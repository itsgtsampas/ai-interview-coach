"""Query rewriting and multi-query expansion.

A job description says "containerisation"; a CV says "Docker". One query string
will miss that. Generating several phrasings and fusing the result sets is the
cheapest recall win available, and it matters more with the stub embedder, which
is lexical rather than semantic.
"""

import re

from app.textutil import keywords

_SYNONYMS = {
    "kubernetes": ["k8s", "container orchestration", "eks", "gke"],
    "containerisation": ["docker", "containers", "kubernetes"],
    "containerization": ["docker", "containers", "kubernetes"],
    "docker": ["containers", "containerisation"],
    "ci/cd": ["continuous integration", "pipeline", "github actions", "jenkins"],
    "cloud": ["aws", "azure", "gcp"],
    "aws": ["cloud", "amazon web services", "s3", "lambda"],
    "microservices": ["distributed systems", "service oriented", "apis"],
    "rest": ["api", "http", "endpoints"],
    "sql": ["postgres", "postgresql", "mysql", "database", "queries"],
    "nosql": ["mongodb", "dynamodb", "redis"],
    "testing": ["pytest", "unit tests", "test coverage", "tdd"],
    "python": ["fastapi", "django", "flask", "pandas"],
    "javascript": ["typescript", "node", "react"],
    "leadership": ["mentoring", "led", "ownership", "line management"],
    "communication": ["stakeholders", "presented", "documentation"],
    "machine learning": ["ml", "model", "training", "scikit"],
    "observability": ["monitoring", "logging", "metrics", "prometheus", "tracing"],
    "agile": ["scrum", "kanban", "sprints"],
    "security": ["authentication", "authorisation", "oauth", "encryption"],
    "performance": ["latency", "throughput", "optimisation", "profiling"],
}


def expand(requirement: str, *, max_variants: int = 3) -> list[str]:
    """Return the original query plus up to max_variants-1 rewrites."""
    base = " ".join(requirement.split())
    variants = [base]

    # Variant 1: content words only — drops boilerplate like "strong experience with".
    kws = keywords(base, limit=10)
    if kws and len(kws) >= 2:
        stripped = " ".join(kws)
        if stripped.lower() != base.lower():
            variants.append(stripped)

    # Variant 2: swap in domain synonyms so vocabulary mismatch does not cost recall.
    low = base.lower()
    extra: list[str] = []
    for term, alts in _SYNONYMS.items():
        if re.search(rf"\b{re.escape(term)}\b", low):
            extra.extend(alts[:2])
    if extra:
        variants.append(" ".join(dict.fromkeys(kws[:6] + extra)))

    deduped = list(dict.fromkeys(v for v in variants if v.strip()))
    return deduped[:max_variants]
