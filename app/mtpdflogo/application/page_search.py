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


@dataclass(frozen=True, slots=True)
class BatchSearchResult:
    documents: list[DocumentSearchResult]
    skipped_non_pdf: int
    file_count: int
    pdf_count: int
    matched_files: int
    page_count: int
    matched_pages: int
    total_occurrences: int
    elapsed_seconds: float


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


def search_pdf_batch(
    sources: list[Path],
    rule: PageTextRule,
    *,
    max_hits_per_file: int | None = 5,
) -> BatchSearchResult:
    """Search many input files and summarize PDF-only page matches.

    Non-PDF inputs are skipped because page text filters only apply to PDF text
    layers; image watermark exports do not have searchable page text.
    """
    started = time.perf_counter()
    documents: list[DocumentSearchResult] = []
    skipped_non_pdf = 0
    for source in sources:
        if source.suffix.lower() != ".pdf":
            skipped_non_pdf += 1
            continue
        documents.append(search_pdf_pages(source, rule, max_hits=max_hits_per_file))
    matched_files = sum(1 for result in documents if result.matched_pages > 0)
    return BatchSearchResult(
        documents=documents,
        skipped_non_pdf=skipped_non_pdf,
        file_count=len(sources),
        pdf_count=len(documents),
        matched_files=matched_files,
        page_count=sum(result.page_count for result in documents),
        matched_pages=sum(result.matched_pages for result in documents),
        total_occurrences=sum(result.total_occurrences for result in documents),
        elapsed_seconds=time.perf_counter() - started,
    )


def _excerpt(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"
