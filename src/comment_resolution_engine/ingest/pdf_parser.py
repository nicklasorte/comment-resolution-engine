from __future__ import annotations

import re
from dataclasses import dataclass
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

    def extract_window(self, page: int | None, line_reference: str | int | None, window: int = 5) -> str:
        if not self.pages or line_reference in (None, ""):
            return ""

        lines = parse_line_reference(line_reference) if not isinstance(line_reference, int) else [line_reference]
        page_key = int(page) if page is not None else next(iter(self.pages.keys()))
        page_lines = self.pages.get(page_key, [])
        if not page_lines:
            return ""

        indexed = {ln: text for ln, text in page_lines}
        snippets: list[str] = []
        for target in lines:
            for ln in range(max(1, target - window), target + window + 1):
                if ln in indexed:
                    snippets.append(f"L{ln}: {indexed[ln]}")

        if not snippets:
            return ""

        deduped = list(dict.fromkeys(snippets))
        return " | ".join(deduped)


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


def _index_lines(pages_text: List[str]) -> Dict[int, List[Tuple[int, str]]]:
    indexed: Dict[int, List[Tuple[int, str]]] = {}
    for page_idx, text in enumerate(pages_text, start=1):
        page_lines: list[Tuple[int, str]] = []
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            match = LEADING_LINE_RE.match(raw_line)
            if match:
                line_no = int(match.group(1))
                page_lines.append((line_no, match.group(2).strip()))
        if page_lines:
            indexed[page_idx] = page_lines
    return indexed


def load_pdf_context(pdf_path: str | Path | None) -> PdfContext:
    if not pdf_path:
        return PdfContext(pages={})
    pages_text = _safe_extract_text(pdf_path)
    return PdfContext(pages=_index_lines(pages_text))
