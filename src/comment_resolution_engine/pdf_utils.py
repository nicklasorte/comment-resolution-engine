from __future__ import annotations

import re
from pathlib import Path


LINE_REF_TOKEN_RE = re.compile(r"\d+\s*(?:-\s*\d+)?")
LEADING_LINE_RE = re.compile(r"^\s*(\d+)\s*[:.)\-]?\s*(.*)$")


def parse_line_reference(line_reference: str) -> list[int]:
    """Parse line references like '12', '12-14', or '12, 15-16' into sorted line numbers."""
    if not line_reference:
        return []

    line_numbers: set[int] = set()
    for token in LINE_REF_TOKEN_RE.findall(str(line_reference)):
        token = token.replace(" ", "")
        if "-" in token:
            start_s, end_s = token.split("-", maxsplit=1)
            start, end = int(start_s), int(end_s)
            low, high = sorted((start, end))
            line_numbers.update(range(low, high + 1))
        else:
            line_numbers.add(int(token))

    return sorted(line_numbers)


def extract_pdf_text(pdf_path: str | Path, max_pages: int = 20) -> str:
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


def extract_report_context(line_reference: str, pdf_text: str, window: int = 1) -> str:
    """Extract nearby report lines from text using numeric line references.

    Falls back to an empty string when parsing or extraction is not possible.
    """
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
