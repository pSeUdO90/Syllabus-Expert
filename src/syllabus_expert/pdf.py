from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    char_count: int


def load_pdf(path: str | Path) -> pymupdf.Document:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path}")
    return pymupdf.open(pdf_path)


def extract_pages(path: str | Path) -> list[PageText]:
    """Extract reading-order text from each page."""
    document = load_pdf(path)
    try:
        pages: list[PageText] = []
        for index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            normalized = _normalize_text(text)
            pages.append(
                PageText(page=index, text=normalized, char_count=len(normalized.strip()))
            )
        return pages
    finally:
        document.close()


def render_page_png(path: str | Path, page_number: int, *, dpi: int = 144) -> bytes:
    """Render a 1-indexed page to PNG bytes (for vision models / scanned PDFs)."""
    document = load_pdf(path)
    try:
        if page_number < 1 or page_number > document.page_count:
            raise IndexError(
                f"Page {page_number} is out of range (1-{document.page_count})."
            )
        page = document[page_number - 1]
        zoom = dpi / 72
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


def join_pages(pages: list[PageText]) -> str:
    """Join pages with markers so parsers can recover page numbers."""
    blocks: list[str] = []
    for page in pages:
        blocks.append(f"<<<PAGE {page.page}>>>\n{page.text}".rstrip())
    return "\n\n".join(blocks)


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\ufb01", "fi").replace("\ufb02", "fl")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()
