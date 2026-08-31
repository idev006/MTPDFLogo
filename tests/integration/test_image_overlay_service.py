from pathlib import Path

from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.image_overlay_service import apply_image_overlays
from mtpdflogo.infrastructure.pdf.overlay_service import PdfOverlaySpec
from PIL import Image, ImageChops


def test_text_and_logo_settings_create_watermarked_image(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    logo = tmp_path / "logo.png"
    output = tmp_path / "source-watermask.png"
    Image.new("RGBA", (400, 300), (255, 255, 255, 255)).save(source)
    Image.new("RGBA", (80, 40), (255, 0, 0, 220)).save(logo)
    progress: list[tuple[int, int]] = []

    apply_image_overlays(
        source,
        output,
        [
            PdfOverlaySpec(
                overlay_type=OverlayType.TEXT,
                position=Position.MIDDLE_CENTER,
                text="WATERMARK",
                font_size=32,
                color=(0.0, 0.0, 0.0),
                opacity=0.6,
                rotation=-20,
            ),
            PdfOverlaySpec(
                overlay_type=OverlayType.IMAGE,
                position=Position.BOTTOM_RIGHT,
                asset_path=logo,
                width_percent=20,
                opacity=0.5,
                rotation=10,
            ),
        ],
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert output.exists()
    with Image.open(source) as original, Image.open(output) as result:
        assert result.size == original.size
        assert ImageChops.difference(original.convert("RGB"), result.convert("RGB")).getbbox()
    assert progress == [(1, 1)]


def test_absolute_logo_position_is_applied_to_image_output(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    logo = tmp_path / "logo.png"
    output = tmp_path / "absolute-watermask.png"
    Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(source)
    Image.new("RGBA", (20, 20), (255, 0, 0, 255)).save(logo)

    apply_image_overlays(
        source,
        output,
        [
            PdfOverlaySpec(
                overlay_type=OverlayType.IMAGE,
                position=Position.TOP_LEFT,
                position_mode=PositionMode.ABSOLUTE,
                x_percent=50,
                y_percent=50,
                asset_path=logo,
                width_percent=20,
                opacity=1,
            ),
        ],
    )

    with Image.open(output) as result:
        assert result.convert("RGB").getpixel((50, 50)) == (255, 0, 0)
