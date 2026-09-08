"""Stage 1 of indexing: PDF -> per-page text, with a scan guard."""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import get_settings
from app.exceptions import UnparseablePDF


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
        LoadedPage(number=i + 1, text=(p.extract_text() or "").strip())
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
