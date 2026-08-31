"""Apply independent text and logo overlays to image files."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from mtpdflogo.application.positioning import resolve_overlay_top_left
from mtpdflogo.domain.models import OverlayType
from mtpdflogo.infrastructure.pdf.overlay_service import PdfOverlaySpec


def apply_image_overlays(
    source: Path,
    destination: Path,
    overlays: list[PdfOverlaySpec],
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Create one watermarked image from one source image."""
    if source.resolve() == destination.resolve():
        raise ValueError("destination must not overwrite the source image")
    if cancel_check and cancel_check():
        raise RuntimeError("batch cancelled")
    destination.parent.mkdir(parents=True, exist_ok=True)
    active = sorted((item for item in overlays if item.enabled), key=lambda item: item.z_index)
    with Image.open(source) as source_image:
        base = ImageOps.exif_transpose(source_image).convert("RGBA")
        for spec in active:
            if spec.overlay_type is OverlayType.TEXT:
                _apply_text(base, spec)
            else:
                _apply_logo(base, spec)
        _save_atomically(base, destination)
    if progress_callback:
        progress_callback(1, 1)


def _apply_text(base: Image.Image, spec: PdfOverlaySpec) -> None:
    if not spec.text:
        return
    scale = 3
    font_size = max(1, round(spec.font_size * scale))
    font = (
        ImageFont.truetype(str(spec.font_path), font_size)
        if spec.font_path and spec.font_path.exists()
        else ImageFont.load_default(size=font_size)
    )
    padding = max(12, round(spec.font_size * 0.4)) * scale
    probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    bbox = draw.multiline_textbbox((padding, padding), spec.text, font=font)
    text_layer = Image.new(
        "RGBA",
        (max(1, bbox[2] + padding), max(1, bbox[3] + padding)),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(text_layer)
    color = tuple(round(channel * 255) for channel in spec.color)
    draw.multiline_text(
        (padding, padding),
        spec.text,
        font=font,
        fill=(*color, round(255 * spec.opacity)),
    )
    if spec.rotation % 360:
        text_layer = text_layer.rotate(
            -spec.rotation,
            expand=True,
            resample=Image.Resampling.BICUBIC,
        )
    text_layer = text_layer.resize(
        (max(1, text_layer.width // scale), max(1, text_layer.height // scale)),
        Image.Resampling.LANCZOS,
    )
    base.alpha_composite(text_layer, _anchor_xy(base.size, text_layer.size, spec))


def _apply_logo(base: Image.Image, spec: PdfOverlaySpec) -> None:
    if spec.asset_path is None or not spec.asset_path.exists():
        raise FileNotFoundError(f"Logo asset not found: {spec.asset_path}")
    with Image.open(spec.asset_path) as source_logo:
        logo = ImageOps.exif_transpose(source_logo).convert("RGBA")
    target_width = max(1, round(base.width * spec.width_percent / 100))
    target_height = max(1, round(target_width * logo.height / logo.width))
    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if spec.opacity < 1.0:
        alpha = logo.getchannel("A").point(lambda value: round(value * spec.opacity))
        logo.putalpha(alpha)
    if spec.rotation % 360:
        logo = logo.rotate(-spec.rotation, expand=True, resample=Image.Resampling.BICUBIC)
    base.alpha_composite(logo, _anchor_xy(base.size, logo.size, spec))


def _anchor_xy(
    base_size: tuple[int, int],
    overlay_size: tuple[int, int],
    spec: PdfOverlaySpec,
    margin: int = 24,
) -> tuple[int, int]:
    base_width, base_height = base_size
    width, height = overlay_size
    x, y = resolve_overlay_top_left(
        page_width=base_width,
        page_height=base_height,
        overlay_width=width,
        overlay_height=height,
        position=spec.position,
        position_mode=spec.position_mode,
        x_percent=spec.x_percent,
        y_percent=spec.y_percent,
        margin=margin,
    )
    return round(x), round(y)


def _save_atomically(image: Image.Image, destination: Path) -> None:
    suffix = destination.suffix.lower()
    output = image.convert("RGB") if suffix in {".jpg", ".jpeg"} else image
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.stem}-",
        suffix=f".tmp{destination.suffix}",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        output.save(temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
