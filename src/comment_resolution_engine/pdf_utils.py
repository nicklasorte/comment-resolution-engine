from __future__ import annotations

from pathlib import Path

from .ingest.pdf_parser import LEADING_LINE_RE, PdfContext, parse_line_reference


def extract_pdf_text(pdf_path: str | Path, max_pages: int = 20) -> str:
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


def extract_report_context(line_reference: str, pdf_text: str, window: int = 5) -> str:
    targets = parse_line_reference(line_reference)
    if not targets or not pdf_text:
        return ""

    lines = [ln for ln in (pdf_text or "").splitlines() if ln.strip()]
    indexed: dict[int, str] = {}
    for line in lines:
        match = LEADING_LINE_RE.match(line)
        if match:
            indexed[int(match.group(1))] = match.group(2).strip()

    if not indexed:
        return ""

    snippets: list[str] = []
    for target in targets:
        for ln in range(max(1, target - window), target + window + 1):
            text = indexed.get(ln)
            if text:
                snippets.append(f"L{ln}: {text}")

    if not snippets:
        return ""

    deduped = list(dict.fromkeys(snippets))
    return " | ".join(deduped)
