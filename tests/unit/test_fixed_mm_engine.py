from dataclasses import replace

import fitz
import pytest
from mtpdflogo.application.export_policy import settings_fingerprint
from mtpdflogo.application.physical_preflight import validate_physical_source
from mtpdflogo.application.positioning import resolve_overlay_top_left
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.image_overlay_service import apply_image_overlays
from mtpdflogo.infrastructure.pdf.overlay_service import (
    PageTextRule,
    PdfOverlaySpec,
    apply_overlays,
)
from PIL import Image, ImageChops


@pytest.fixture
def logo_spec(tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGB", (120, 60), "red").save(logo)
    return PdfOverlaySpec(
        OverlayType.IMAGE, Position.MIDDLE_CENTER, position_mode=PositionMode.FIXED_MM,
        x_mm=100, y_mm=70, width_mm=25, asset_path=logo,
    )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_mixed_sizes_keep_physical_top_left_and_width(tmp_path, logo_spec, rotation):
    source, output = tmp_path / "input.pdf", tmp_path / "output.pdf"
    with fitz.open() as doc:
        for width, height in [(612, 1008), (595.32, 841.92)]:
            page = doc.new_page(width=width, height=height)
            page.set_rotation(rotation)
        doc.save(source)
    validate_physical_source(source, [logo_spec], None)
    apply_overlays(source, output, [logo_spec])
    with fitz.open(output) as doc:
        for page in doc:
            pix = page.get_pixmap(alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            bounds = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
            x0, y0, x1, y1 = bounds
            assert x0 == pytest.approx(100 * 72 / 25.4, abs=1)
            assert y0 == pytest.approx(70 * 72 / 25.4, abs=1)
            assert x1 - x0 == pytest.approx(25 * 72 / 25.4, abs=2)
            assert y1 - y0 == pytest.approx(12.5 * 72 / 25.4, abs=2)


def test_bounds_filter_and_atomic_output(tmp_path, logo_spec):
    source, output = tmp_path / "input.pdf", tmp_path / "output.pdf"
    with fitz.open() as doc:
        doc.new_page(width=612, height=1008).insert_text((30, 30), "target target target")
        doc.new_page(width=595, height=842)
        doc.save(source)
    spec = replace(logo_spec, y_mm=320)
    rule = PageTextRule("target", min_occurrences=3, max_occurrences=3)
    validate_physical_source(source, [spec], rule)
    apply_overlays(source, output, [spec], rule)
    before = output.read_bytes()
    with pytest.raises(ValueError, match="page 2"):
        validate_physical_source(source, [spec], None)
    with pytest.raises(ValueError, match="bounds"):
        apply_overlays(source, output, [spec])
    assert output.read_bytes() == before


def test_image_physical_units_use_96_dpi(tmp_path, logo_spec):
    source, output = tmp_path / "input.png", tmp_path / "output.png"
    Image.new("RGB", (1000, 1000), "white").save(source)
    apply_image_overlays(source, output, [logo_spec])
    with Image.open(output) as result:
        image = result.convert("RGB")
        x0, y0, x1, y1 = ImageChops.difference(
            image, Image.new("RGB", image.size, "white")
        ).getbbox()
        assert x0 == pytest.approx(100 * 96 / 25.4, abs=1)
        assert y0 == pytest.approx(70 * 96 / 25.4, abs=1)


def test_fingerprint_changes_for_each_physical_setting(logo_spec):
    initial = settings_fingerprint([logo_spec], None)
    for change in [
        dict(x_mm=101), dict(y_mm=71), dict(width_mm=26), dict(anchor_mode="center")
    ]:
        assert settings_fingerprint([replace(logo_spec, **change)], None) != initial


def test_legacy_percent_still_relative():
    def position(height):
        return resolve_overlay_top_left(
            page_width=612, page_height=height, overlay_width=20, overlay_height=20,
            position=Position.TOP_LEFT, position_mode=PositionMode.ABSOLUTE,
            x_percent=50, y_percent=50,
        )
    assert position(1008)[1] - position(842)[1] == 83


def test_cropped_pdf_uses_visible_top_left(tmp_path, logo_spec):
    source, output = tmp_path / "crop.pdf", tmp_path / "output.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=700, height=1000)
        page.set_cropbox(fitz.Rect(40, 50, 640, 950))
        doc.save(source)
    apply_overlays(source, output, [logo_spec])
    with fitz.open(output) as doc:
        info = doc[0].get_image_info()[0]
        rect = fitz.Rect(info["bbox"])
        assert rect.x0 == pytest.approx(100 * 72 / 25.4, abs=.01)
        assert rect.y0 == pytest.approx(70 * 72 / 25.4, abs=.01)


def test_center_anchor_remains_available_for_schema_3_settings(logo_spec):
    spec = replace(logo_spec, anchor_mode="center")
    x, y = resolve_overlay_top_left(
        page_width=612, page_height=1008, overlay_width=60, overlay_height=30,
        position=spec.position, position_mode=spec.position_mode,
        x_mm=spec.x_mm, y_mm=spec.y_mm, anchor_mode=spec.anchor_mode,
    )
    assert x == pytest.approx(100 * 72 / 25.4 - 30)
    assert y == pytest.approx(70 * 72 / 25.4 - 15)


def test_physical_text_cache_preserves_dimensions(tmp_path, logo_spec, monkeypatch):
    from mtpdflogo.infrastructure.pdf import overlay_service

    source, output = tmp_path / "text.pdf", tmp_path / "output.pdf"
    with fitz.open() as doc:
        for height in [1008, 842, 1008]:
            doc.new_page(width=612, height=height)
        doc.save(source)
    spec = replace(logo_spec, overlay_type=OverlayType.TEXT, text="APPROVED", rotation=30)
    calls = []
    render = overlay_service.render_physical_layer

    def counted(*args):
        calls.append(1)
        return render(*args)

    monkeypatch.setattr(overlay_service, "render_physical_layer", counted)
    apply_overlays(source, output, [spec])
    assert len(calls) == 1
    with fitz.open(output) as doc:
        boxes = [p.get_image_info()[0]["bbox"] for p in doc]
        assert boxes[0] == boxes[1] == boxes[2]
