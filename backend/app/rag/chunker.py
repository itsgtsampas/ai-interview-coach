"""Stages 2-3 of indexing: section detection, then parent-child contextual chunking.

Children (~350 chars) are embedded for retrieval precision; parents (whole
sections) are what the LLM actually reads, so a matched bullet arrives with the
role it belongs to.  Each child is prefixed with its breadcrumb before embedding
— without it, "Reduced p99 latency by 60%" is unattributable to a job or a person.
"""

import re
from dataclasses import dataclass, field

from app.rag.loader import LoadedDocument

CHILD_CHARS = 350
CHILD_OVERLAP = 60
PARENT_MAX_CHARS = 2000

_KNOWN_HEADINGS = re.compile(
    r"^\s*(professional\s+)?(work\s+)?"
    r"(experience|employment|education|skills?|technical\s+skills?|projects?|"
    r"summary|profile|about|certifications?|publications?|languages?|interests?|"
    r"requirements?|responsibilities|qualifications?|what\s+you.{0,3}ll\s+do|"
    r"what\s+you.{0,3}ll\s+need|about\s+(the\s+)?(role|us|you)|benefits?|"
    r"nice\s+to\s+have|must\s+have|the\s+role|who\s+you\s+are)"
    r"\s*:?\s*$",
    re.I,
)


@dataclass
class Parent:
    id: str
    section: str
    page: int
    text: str


@dataclass
class Child:
    id: str
    parent_id: str
    section: str
    page: int
    text: str            # raw slice
    embed_text: str      # breadcrumb + raw slice; this is what gets embedded


@dataclass
class ChunkedDocument:
    parents: list[Parent] = field(default_factory=list)
    children: list[Child] = field(default_factory=list)


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not (2 < len(stripped) < 60):
        return False
    if _KNOWN_HEADINGS.match(stripped):
        return True
    letters = [c for c in stripped if c.isalpha()]
    # Short, fully upper-case, unpunctuated lines are headings in most CVs.
    return (
        bool(letters)
        and all(c.isupper() for c in letters)
        and not stripped.endswith((".", ","))
        and len(stripped.split()) <= 5
    )


def split_sections(doc: LoadedDocument) -> list[tuple[str, int, str]]:
    """-> [(section_name, first_page, body_text)]"""
    sections: list[tuple[str, int, list[str]]] = []
    current_name, current_page, buffer = "Header", 1, []

    for page in doc.pages:
        for line in page.text.splitlines():
            if _looks_like_heading(line):
                if buffer:
                    sections.append((current_name, current_page, buffer))
                current_name, current_page, buffer = line.strip().rstrip(":"), page.number, []
            else:
                buffer.append(line)
    if buffer:
        sections.append((current_name, current_page, buffer))

    out = [(n, p, "\n".join(b).strip()) for n, p, b in sections if "\n".join(b).strip()]
    # Fall back to whole-page sections when heading detection finds nothing usable.
    if len(out) < 2:
        out = [(f"Page {p.number}", p.number, p.text) for p in doc.pages if p.text.strip()]
    return out


def _split_parent(text: str) -> list[str]:
    if len(text) <= PARENT_MAX_CHARS:
        return [text]
    parts, buf = [], ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) > PARENT_MAX_CHARS and buf:
            parts.append(buf.strip())
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _split_children(text: str) -> list[str]:
    if len(text) <= CHILD_CHARS:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHILD_CHARS)
        if end < len(text):
            window = text.rfind(" ", start + CHILD_CHARS // 2, end)
            if window != -1:
                end = window
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - CHILD_OVERLAP)
    return out


def chunk_document(
    doc: LoadedDocument,
    *,
    doc_key: str,
    doc_label: str,
    strategy: str = "parent_child",
) -> ChunkedDocument:
    """strategy="parent_child" is the production path (section-aware, contextual
    breadcrumbs, small-to-big). strategy="fixed" is the naive baseline the eval
    harness ablates against: fixed-size slices, no sections, no breadcrumb."""
    if strategy == "fixed":
        return _chunk_fixed(doc, doc_key=doc_key)

    result = ChunkedDocument()
    for s_idx, (section, page, body) in enumerate(split_sections(doc)):
        for p_idx, parent_text in enumerate(_split_parent(body)):
            parent_id = f"{doc_key}-s{s_idx}-p{p_idx}"
            result.parents.append(
                Parent(id=parent_id, section=section, page=page, text=parent_text)
            )
            for c_idx, child_text in enumerate(_split_children(parent_text)):
                breadcrumb = f"[{doc_label} › {section}]"
                result.children.append(
                    Child(
                        id=f"{parent_id}-c{c_idx}",
                        parent_id=parent_id,
                        section=section,
                        page=page,
                        text=child_text,
                        embed_text=f"{breadcrumb}\n{child_text}",
                    )
                )
    return result


def _chunk_fixed(doc: LoadedDocument, *, doc_key: str) -> ChunkedDocument:
    """Ablation baseline: slice the whole document every CHILD_CHARS characters,
    ignoring structure. Each chunk is its own parent, so there is no extra
    context to hand the model."""
    result = ChunkedDocument()
    page_for_offset: list[tuple[int, int]] = []
    cursor = 0
    for page in doc.pages:
        page_for_offset.append((cursor, page.number))
        cursor += len(page.text) + 1
    full = "\n".join(p.text for p in doc.pages)

    offset = 0
    for i, piece in enumerate(_split_children(full)):
        start = full.find(piece, offset)
        offset = start + 1 if start >= 0 else offset
        page = 1
        for pos, number in page_for_offset:
            if pos <= max(start, 0):
                page = number
        cid = f"{doc_key}-f{i}"
        result.parents.append(Parent(id=cid, section="", page=page, text=piece))
        result.children.append(
            Child(id=f"{cid}-c0", parent_id=cid, section="", page=page,
                  text=piece, embed_text=piece)
        )
    return result
