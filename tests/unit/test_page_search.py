from __future__ import annotations

from pathlib import Path

import fitz
from mtpdflogo.application.page_search import search_pdf_batch, search_pdf_pages
from mtpdflogo.config.resources import font_directory
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule


def _make_search_pdf(path: Path, page_texts: list[str], font_path: Path | None = None) -> None:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page(width=300, height=180)
        if font_path is None:
            page.insert_text((36, 72), text)
        else:
            page.insert_font(fontname="MaliRegular", fontfile=str(font_path))
            page.insert_text((36, 72), text, fontname="MaliRegular")
    document.save(path)
    document.close()


def test_search_pdf_pages_returns_per_page_hits_and_elapsed_time(tmp_path: Path) -> None:
    source = tmp_path / "search.pdf"
    _make_search_pdf(
        source,
        [
            "invoice amount 100",
            "no match here",
            "amount amount amount",
        ],
    )

    result = search_pdf_pages(source, PageTextRule("amount", min_occurrences=1))

    assert result.source == source
    assert result.page_count == 3
    assert result.matched_pages == 2
    assert result.total_occurrences == 4
    assert [hit.page_number for hit in result.hits] == [1, 3]
    assert result.elapsed_seconds >= 0


def test_search_pdf_pages_supports_regex_and_hit_limit(tmp_path: Path) -> None:
    source = tmp_path / "regex.pdf"
    _make_search_pdf(
        source,
        [
            "invoice amount 7,500.00",
            "invoice amount seven thousand",
            "invoice amount 9,900.00",
        ],
    )
    rule = PageTextRule(
        r"invoice\s*amount\s*\d{1,3}(?:,\d{3})*\.\d{2}",
        use_regex=True,
    )

    result = search_pdf_pages(source, rule, max_hits=1)

    assert result.page_count == 3
    assert result.matched_pages == 2
    assert result.total_occurrences == 2
    assert len(result.hits) == 1
    assert result.hits[0].page_number == 1


def test_search_pdf_pages_supports_thai_unicode_normalization(tmp_path: Path) -> None:
    source = tmp_path / "thai-search.pdf"
    thai_font = font_directory() / "Mali" / "Mali-Regular.ttf"
    _make_search_pdf(
        source,
        [
            "ไม่มีคำที่ต้องการ",
            "จํานวน เงิน\nบาท\n7,500.00",
            "จํานวนเงิน บาท เจ็ดพันห้าร้อย",
        ],
        thai_font,
    )
    rule = PageTextRule(
        r"จำนวน\s*เงิน\s*บาท\s*\d{1,3}(?:,\d{3})*\.\d{2}",
        use_regex=True,
    )

    result = search_pdf_pages(source, rule)

    assert result.page_count == 3
    assert result.matched_pages == 1
    assert result.total_occurrences == 1
    assert [hit.page_number for hit in result.hits] == [2]


def test_search_pdf_batch_summarizes_many_files_and_skips_images(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    image = tmp_path / "scan.png"
    _make_search_pdf(first, ["amount 100", "amount 200"])
    _make_search_pdf(second, ["no match", "still no match"])
    image.write_bytes(b"not a real image for search summary")

    result = search_pdf_batch([first, image, second], PageTextRule("amount"))

    assert result.file_count == 3
    assert result.pdf_count == 2
    assert result.skipped_non_pdf == 1
    assert result.matched_files == 1
    assert result.page_count == 4
    assert result.matched_pages == 2
    assert result.total_occurrences == 2
    assert [document.source for document in result.documents] == [first, second]


def test_search_pdf_pages_respects_page_ranges_with_keyword(tmp_path: Path) -> None:
    source = tmp_path / "ranged-search.pdf"
    _make_search_pdf(source, ["amount", "amount", "amount"])

    result = search_pdf_pages(source, PageTextRule("amount", page_ranges="2-3"))

    assert result.page_count == 3
    assert result.matched_pages == 2
    assert [hit.page_number for hit in result.hits] == [2, 3]


def test_search_pdf_pages_supports_page_ranges_without_keyword(tmp_path: Path) -> None:
    source = tmp_path / "page-only-search.pdf"
    _make_search_pdf(source, ["cover", "body", "appendix"])

    result = search_pdf_pages(source, PageTextRule("", page_ranges="2-"))

    assert result.page_count == 3
    assert result.matched_pages == 2
    assert [hit.page_number for hit in result.hits] == [2, 3]
