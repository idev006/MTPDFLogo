from pathlib import Path

import fitz
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.pdf.overlay_service import PdfOverlaySpec, apply_overlays
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
