from pathlib import Path

import fitz
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.pdf.overlay_service import (
    PageTextRule,
    PdfOverlaySpec,
    apply_overlays,
)
from PIL import Image


def test_text_and_logo_settings_create_valid_output(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    logo = tmp_path / "logo.png"
    output = tmp_path / "output.pdf"

    document = fitz.open()
    document.new_page(width=600, height=800)
    document.save(source)
    document.close()
    Image.new("RGBA", (100, 50), (255, 0, 0, 180)).save(logo)

    apply_overlays(
        source,
        output,
        [
            PdfOverlaySpec(
                overlay_type=OverlayType.TEXT,
                position=Position.MIDDLE_CENTER,
                text="CONFIDENTIAL",
                font_size=28,
                font_path=Path("app/assets/fonts/TH-SarabunNew/THSarabunNew.ttf").resolve(),
                color=(1.0, 0.0, 0.0),
                opacity=0.25,
                rotation=45,
            ),
            PdfOverlaySpec(
                overlay_type=OverlayType.IMAGE,
                position=Position.TOP_RIGHT,
                asset_path=logo,
                width_percent=20,
                opacity=0.5,
                rotation=15,
            ),
        ],
    )

    result = fitz.open(output)
    assert result.page_count == 1
    assert len(result[0].get_images(full=True)) == 2
    result.close()


def test_mixed_portrait_and_landscape_pages_keep_page_geometry(tmp_path: Path) -> None:
    source = tmp_path / "mixed.pdf"
    output = tmp_path / "mixed_marked.pdf"
    document = fitz.open()
    document.new_page(width=600, height=800)
    document.new_page(width=800, height=600)
    document.save(source)
    document.close()

    apply_overlays(
        source,
        output,
        [PdfOverlaySpec(OverlayType.TEXT, Position.TOP_RIGHT, text="MIXED", font_size=18)],
    )

    result = fitz.open(output)
    assert result.page_count == 2
    assert (result[0].rect.width, result[0].rect.height) == (600, 800)
    assert (result[1].rect.width, result[1].rect.height) == (800, 600)
    result.close()


def test_rotated_logo_cache_is_reused_without_double_rotation(tmp_path: Path) -> None:
    source = tmp_path / "rotated-logo.pdf"
    logo = tmp_path / "logo.png"
    output = tmp_path / "rotated-logo-output.pdf"
    document = fitz.open()
    document.new_page(width=400, height=240)
    document.new_page(width=400, height=240)
    document.save(source)
    document.close()
    Image.new("RGBA", (80, 40), (255, 0, 0, 180)).save(logo)

    apply_overlays(
        source,
        output,
        [
            PdfOverlaySpec(
                overlay_type=OverlayType.IMAGE,
                position=Position.MIDDLE_CENTER,
                asset_path=logo,
                width_percent=20,
                rotation=15,
            )
        ],
    )

    with fitz.open(output) as result:
        assert result.page_count == 2
        assert [len(page.get_images(full=True)) for page in result] == [1, 1]


def test_overlay_service_reports_real_page_progress(tmp_path: Path) -> None:
    source = tmp_path / "progress.pdf"
    output = tmp_path / "progress_marked.pdf"
    document = fitz.open()
    for _ in range(3):
        document.new_page()
    document.save(source)
    document.close()
    progress: list[tuple[int, int]] = []

    apply_overlays(
        source,
        output,
        [PdfOverlaySpec(OverlayType.TEXT, Position.TOP_LEFT, text="P")],
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_page_text_rule_applies_overlays_only_to_matching_pages(tmp_path: Path) -> None:
    source = tmp_path / "conditional.pdf"
    output = tmp_path / "conditional_marked.pdf"
    document = fitz.open()
    first = document.new_page(width=400, height=240)
    first.insert_text((72, 72), "total amount")
    second = document.new_page(width=400, height=240)
    second.insert_text((72, 72), "amount amount amount")
    third = document.new_page(width=400, height=240)
    third.insert_text((72, 72), "no match")
    document.save(source)
    document.close()

    apply_overlays(
        source,
        output,
        [PdfOverlaySpec(OverlayType.TEXT, Position.TOP_LEFT, text="MATCH")],
        page_text_rule=PageTextRule("amount", min_occurrences=1, max_occurrences=2),
    )

    with fitz.open(output) as result:
        assert [len(page.get_images(full=True)) for page in result] == [1, 0, 0]


def test_page_text_rule_counts_keyword_anywhere_on_page() -> None:
    rule = PageTextRule("จำนวนเงิน", min_occurrences=1, max_occurrences=3)

    text = "ข้าพเจ้าขอยืนยันจํานวนเงิน\nหุ้นปกติ\nจํานวนเงิน\nบาท\nจํานวนเงิน"

    assert rule.count_occurrences(text) == 3
    assert rule.matches(text)


def test_page_text_rule_supports_regex() -> None:
    rule = PageTextRule(
        r"จํานวนเงิน\s*บาท\s*\d{1,3}(?:,\d{3})*\.\d{2}",
        use_regex=True,
    )

    assert rule.count_occurrences("จํานวนเงิน\nบาท\n7,500.00") == 1
    assert rule.matches("จํานวนเงิน\nบาท\n7,500.00")
    assert not rule.matches("จํานวนเงิน\nบาท\nเจ็ดพันห้าร้อย")


def test_page_text_rule_reuses_compiled_regex_for_large_searches() -> None:
    rule = PageTextRule(r"\d{3}-\d{3}", use_regex=True)

    first = rule.compiled_regex()
    second = rule.compiled_regex()

    assert first is second
    assert rule.count_occurrences("ref 123-456 ref 999-000") == 2


def test_page_text_rule_reuses_normalized_plain_keyword() -> None:
    rule = PageTextRule("จำนวน เงิน")

    first = rule.searchable_keyword()
    second = rule.searchable_keyword()

    assert first is second
    assert first == "จํานวนเงิน"
    assert rule.matches("จํานวน\nเงิน")


def test_page_text_rule_stops_regex_counting_after_max_occurrences() -> None:
    rule = PageTextRule(r"\d+", max_occurrences=2, use_regex=True)

    assert rule.count_occurrences("1 2 3 4 5") == 3
    assert not rule.matches("1 2 3 4 5")


def test_page_text_rule_stops_plain_counting_after_max_occurrences() -> None:
    rule = PageTextRule("amount", max_occurrences=2)

    assert rule.count_occurrences("amount amount amount amount") == 3
    assert not rule.matches("amount amount amount amount")


def test_thai_text_exports_as_visible_pdf_overlay_without_question_marks_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "thai-source.pdf"
    output = tmp_path / "thai-output.pdf"
    document = fitz.open()
    document.new_page(width=400, height=240)
    document.save(source)
    document.close()

    apply_overlays(
        source,
        output,
        [
            PdfOverlaySpec(
                overlay_type=OverlayType.TEXT,
                position=Position.TOP_CENTER,
                position_mode=PositionMode.ABSOLUTE,
                x_percent=50,
                y_percent=25,
                text="ข้อความภาษาไทย",
                font_size=36,
                font_path=Path("app/assets/fonts/TH-SarabunNew/THSarabunNew.ttf").resolve(),
                color=(1.0, 0.0, 0.0),
                opacity=1.0,
                rotation=0,
            )
        ],
    )

    with fitz.open(output) as result:
        assert result.page_count == 1
        assert len(result[0].get_images(full=True)) == 1
        pixmap = result[0].get_pixmap(alpha=False)
        assert any(
            pixmap.samples[index] > 180
            and pixmap.samples[index + 1] < 120
            and pixmap.samples[index + 2] < 120
            for index in range(0, len(pixmap.samples), pixmap.n)
        )
