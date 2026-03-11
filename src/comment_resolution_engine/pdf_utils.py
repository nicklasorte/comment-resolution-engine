from __future__ import annotations

from pathlib import Path


def extract_pdf_text(pdf_path: str | Path, max_pages: int = 5) -> str:
    """Best-effort PDF text extraction.

    Returns an empty string if extraction fails, dependency is unavailable,
    or no text is available.
    """

    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        return ""

    try:
        reader = PdfReader(str(pdf_path))
        chunks: list[str] = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks).strip()
    except Exception:
        return ""
