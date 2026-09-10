"""Stage 1 of indexing: a source document -> per-page text.

Two sources produce the same LoadedDocument, so everything downstream —
chunking, embedding, retrieval — is identical for both.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import get_settings
from app.exceptions import InvalidUpload, UnparseablePDF


# Designer CV templates set letter-spacing on headings, which PDF extraction
# renders as "C O N T A C T" or "S o f t w a r e". Every downstream stage —
# tokenising, section detection, citation quoting — is damaged by it, so it is
# repaired at the point of extraction. Four letters minimum, so ordinary
# single-letter words ("I a m") are left alone.
_LETTER_SPACED = re.compile(r"\b(?:[A-Za-z]\u0020){3,}[A-Za-z]\b")


def unspace(text: str) -> str:
    return _LETTER_SPACED.sub(lambda m: m.group(0).replace(" ", ""), text)


@dataclass
class LoadedPage:
    number: int  # 1-based, so it can be shown to the user as a citation
    text: str


@dataclass
class LoadedDocument:
    pages: list[LoadedPage]

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def char_count(self) -> int:
        return sum(len(p.text) for p in self.pages)


def load_pdf(path: Path) -> LoadedDocument:
    settings = get_settings()
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise UnparseablePDF(f"This file could not be opened as a PDF: {exc}") from exc

    if len(reader.pages) > settings.max_pdf_pages:
        raise UnparseablePDF(
            f"This PDF has {len(reader.pages)} pages; the limit is {settings.max_pdf_pages}.",
            {"pages": len(reader.pages), "limit": settings.max_pdf_pages},
        )

    pages = [
        LoadedPage(number=i + 1, text=unspace((p.extract_text() or "").strip()))
        for i, p in enumerate(reader.pages)
    ]
    doc = LoadedDocument(pages=pages)

    # A text-based PDF yields far more than this per page. Below the floor it is
    # almost certainly a scan, and every downstream stage would silently produce
    # nonsense. Fail loudly instead; OCR is out of scope.
    if not pages or doc.char_count / len(pages) < settings.min_chars_per_page:
        raise UnparseablePDF(
            "This PDF appears to be a scan or an image. Upload a text-based PDF — "
            "one where you can select the text in a PDF reader.",
            {"extracted_chars": doc.char_count, "pages": len(pages)},
        )
    return doc


# A job description shorter than this is almost certainly a partial paste — a
# heading without the body, or a stray line. Better to say so than to build an
# analysis on it.
MIN_TEXT_CHARS = 200


def load_text(path: Path) -> LoadedDocument:
    """Pasted text needs no extraction, so there is nothing to fail at.

    It arrives cleaner than PDF output: no hard line wrapping to undo and no
    possibility of being a scan.
    """
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(raw) < MIN_TEXT_CHARS:
        raise InvalidUpload(
            f"That is only {len(raw)} characters. Paste the full job description — "
            "requirements, responsibilities and all.",
            {"chars": len(raw), "minimum": MIN_TEXT_CHARS},
        )
    return LoadedDocument(pages=[LoadedPage(number=1, text=raw)])
