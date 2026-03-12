from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

LINE_REF_TOKEN_RE = re.compile(r"\d+\s*(?:-\s*\d+)?")
LEADING_LINE_RE = re.compile(r"^\s*(\d+)\s*[:.)\-]?\s*(.*)$")


def parse_line_reference(line_reference: str) -> list[int]:
    if not line_reference:
        return []
    numbers: set[int] = set()
    for token in LINE_REF_TOKEN_RE.findall(str(line_reference)):
        token = token.replace(" ", "")
        if "-" in token:
            start, end = token.split("-", maxsplit=1)
            low, high = sorted((int(start), int(end)))
            numbers.update(range(low, high + 1))
        else:
            numbers.add(int(token))
    return sorted(numbers)


@dataclass(slots=True)
class PdfContext:
    pages: Dict[int, List[Tuple[int, str]]]
    raw_pages: Dict[int, List[str]] = field(default_factory=dict)

    def extract_window(self, page: int | None, line_reference: str | int | None, window: int = 5) -> Tuple[str, str]:
        if not (self.pages or self.raw_pages) or line_reference in (None, ""):
            return "", "NO_CONTEXT_FOUND"

        lines = parse_line_reference(line_reference) if not isinstance(line_reference, int) else [line_reference]
        page_key = int(page) if page is not None else next(iter(self.pages.keys() or self.raw_pages.keys()), None)
        if page_key is None:
            return "", "NO_CONTEXT_FOUND"

        page_lines = self.pages.get(page_key, [])
        if page_lines:
            indexed = {ln: text for ln, text in page_lines}
            snippets: list[str] = []
            for target in lines:
                for ln in range(max(1, target - window), target + window + 1):
                    if ln in indexed:
                        snippets.append(f"L{ln}: {indexed[ln]}")
            if snippets:
                deduped = list(dict.fromkeys(snippets))
                return " | ".join(deduped), "EXACT_LINE_MATCH"

        raw_lines = self.raw_pages.get(page_key, [])
        if raw_lines and lines:
            approx_snippets: list[str] = []
            for target in lines:
                idx = max(0, min(len(raw_lines) - 1, target - 1))
                start = max(0, idx - window)
                end = min(len(raw_lines), idx + window + 1)
                approx_snippets.extend([f"~L{start + i + 1}: {raw_lines[start + i]}" for i in range(end - start)])
            if approx_snippets:
                deduped = list(dict.fromkeys(approx_snippets))
                return " | ".join(deduped), "PAGE_APPROXIMATION"

        return "", "NO_CONTEXT_FOUND"


def _safe_extract_text(pdf_path: str | Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        return []

    try:
        reader = PdfReader(str(pdf_path))
        return [(reader.pages[i].extract_text() or "") for i in range(len(reader.pages))]
    except Exception:
        return []


def _index_lines(pages_text: List[str]) -> Tuple[Dict[int, List[Tuple[int, str]]], Dict[int, List[str]]]:
    indexed: Dict[int, List[Tuple[int, str]]] = {}
    raw_lookup: Dict[int, List[str]] = {}
    for page_idx, text in enumerate(pages_text, start=1):
        page_lines: list[Tuple[int, str]] = []
        raw_lines: list[str] = []
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            raw_lines.append(raw_line)
            match = LEADING_LINE_RE.match(raw_line)
            if match:
                line_no = int(match.group(1))
                page_lines.append((line_no, match.group(2).strip()))
        if raw_lines:
            raw_lookup[page_idx] = raw_lines
        if page_lines:
            indexed[page_idx] = page_lines
    return indexed, raw_lookup


def load_pdf_context(pdf_path: str | Path | None) -> PdfContext:
    if not pdf_path:
        return PdfContext(pages={}, raw_pages={})
    pdf_path = Path(pdf_path)
    if pdf_path.suffix.lower() == ".txt":
        content = pdf_path.read_text()
        pages_text = content.split("\f") if "\f" in content else [content]
    else:
        pages_text = _safe_extract_text(pdf_path)
    indexed, raw_lookup = _index_lines(pages_text)
    return PdfContext(pages=indexed, raw_pages=raw_lookup)
