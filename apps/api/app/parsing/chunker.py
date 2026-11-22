from pydantic import BaseModel

from app.parsing.pdf_parser import PageText


class DocumentChunk(BaseModel):
    deal_id: str
    tenant_name: str
    file_name: str
    page_number: int
    chunk_index: int
    text: str


def chunk_pages(
    pages: list[PageText],
    *,
    deal_id: str,
    tenant_name: str,
    file_name: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[DocumentChunk]:
    """Split each page into overlapping chunks without crossing page boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks: list[DocumentChunk] = []
    step = chunk_size - overlap

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        start = 0
        chunk_idx = 0
        while start < len(text):
            piece = text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    DocumentChunk(
                        deal_id=deal_id,
                        tenant_name=tenant_name,
                        file_name=file_name,
                        page_number=page.page_number,
                        chunk_index=chunk_idx,
                        text=piece,
                    )
                )
                chunk_idx += 1
            if start + chunk_size >= len(text):
                break
            start += step

    return chunks