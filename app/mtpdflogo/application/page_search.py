"""Headless PDF page text search utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import fitz

from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule


@dataclass(frozen=True, slots=True)
class PageSearchHit:
    page_number: int
    occurrences: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class DocumentSearchResult:
    source: Path
    page_count: int
    matched_pages: int
    total_occurrences: int
    elapsed_seconds: float
    hits: list[PageSearchHit]


def search_pdf_pages(
    source: Path,
    rule: PageTextRule,
    *,
    max_hits: int | None = None,
    excerpt_chars: int = 160,
) -> DocumentSearchResult:
    """Search a PDF text layer and return per-page match evidence.

    The function performs one text extraction per page and never mutates the PDF,
    making it suitable for pre-export preview, CI tests, and future batch search.
    """
    started = time.perf_counter()
    hits: list[PageSearchHit] = []
    total_occurrences = 0
    matched_pages = 0
    with fitz.open(source) as document:
        page_count = document.page_count
        for page_index, page in enumerate(document):
            text = page.get_text("text")
            occurrences = rule.count_occurrences(text)
            if occurrences <= 0:
                continue
            matched_pages += 1
            total_occurrences += occurrences
            if max_hits is None or len(hits) < max_hits:
                hits.append(
                    PageSearchHit(
                        page_number=page_index + 1,
                        occurrences=occurrences,
                        excerpt=_excerpt(text, excerpt_chars),
                    )
                )
    return DocumentSearchResult(
        source=source,
        page_count=page_count,
        matched_pages=matched_pages,
        total_occurrences=total_occurrences,
        elapsed_seconds=time.perf_counter() - started,
        hits=hits,
    )


def _excerpt(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"
