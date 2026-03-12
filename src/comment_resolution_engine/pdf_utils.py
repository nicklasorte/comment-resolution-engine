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


def extract_report_context(line_reference: str, pdf_text: str, window: int = 5) -> tuple[str, str]:
    targets = parse_line_reference(line_reference)
    if not targets or not pdf_text:
        return "", "NO_CONTEXT_FOUND"

    lines = [ln for ln in (pdf_text or "").splitlines() if ln.strip()]
    indexed: dict[int, str] = {}
    for line in lines:
        match = LEADING_LINE_RE.match(line)
        if match:
            indexed[int(match.group(1))] = match.group(2).strip()

    if indexed:
        snippets: list[str] = []
        for target in targets:
            for ln in range(max(1, target - window), target + window + 1):
                text = indexed.get(ln)
                if text:
                    snippets.append(f"L{ln}: {text}")
        if snippets:
            deduped = list(dict.fromkeys(snippets))
            return " | ".join(deduped), "EXACT_LINE_MATCH"

    approximate: list[str] = []
    if lines:
        for target in targets:
            idx = max(0, min(len(lines) - 1, target - 1))
            start = max(0, idx - window)
            end = min(len(lines), idx + window + 1)
            approximate.extend([f"~L{start + i + 1}: {lines[start + i]}" for i in range(end - start)])
        if approximate:
            deduped = list(dict.fromkeys(approximate))
            return " | ".join(deduped), "PAGE_APPROXIMATION"

    return "", "NO_CONTEXT_FOUND"
