from pathlib import Path

import pymupdf
from pydantic import BaseModel

from app.core.exceptions import ParsingError


class PageText(BaseModel):
    page_number: int
    text: str


def extract_pdf_pages(file_path: str | Path) -> list[PageText]:
    """Extract 1-indexed page text from a PDF using PyMuPDF."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ParsingError(f"PDF file not found: {path}")

    try:
        pages: list[PageText] = []
        with pymupdf.open(path) as doc:
            if doc.page_count == 0:
                raise ParsingError(f"PDF has no pages: {path.name}")
            for idx, page in enumerate(doc, start=1):
                raw_text = page.get_text("text") or ""
                pages.append(PageText(page_number=idx, text=raw_text.strip()))
        return pages
    except ParsingError:
        raise
    except Exception as exc:
        raise ParsingError(f"Failed to parse PDF '{path.name}': {exc}") from exc