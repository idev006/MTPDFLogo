"""Apply independent text and image overlays to PDF files."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from mtpdflogo.application.positioning import resolve_overlay_top_left
from mtpdflogo.domain.models import OverlayType, Position, PositionMode


@dataclass(frozen=True, slots=True)
class PdfOverlaySpec:
    overlay_type: OverlayType
    position: Position
    position_mode: PositionMode = PositionMode.PRESET
    x_percent: float | None = None
    y_percent: float | None = None
    text: str = ""
    asset_path: Path | None = None
    font_size: float = 32.0
    font_path: Path | None = None
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    opacity: float = 1.0
    rotation: int = 0
    width_percent: float = 12.0
    margin_pt: float = 18.0
    enabled: bool = True
    z_index: int = 0


def _anchor_rect(
    page_rect: fitz.Rect,
    spec: PdfOverlaySpec,
    position: Position,
    width: float,
    height: float,
    margin: float,
) -> fitz.Rect:
    x, y = resolve_overlay_top_left(
        page_width=page_rect.width,
        page_height=page_rect.height,
        overlay_width=width,
        overlay_height=height,
        position=position,
        position_mode=spec.position_mode,
        x_percent=spec.x_percent,
        y_percent=spec.y_percent,
        margin=margin,
    )
    horizontal = page_rect.x0 + x
    vertical = page_rect.y0 + y
    return fitz.Rect(horizontal, vertical, horizontal + width, vertical + height)


def _apply_text(page: fitz.Page, page_rect: fitz.Rect, spec: PdfOverlaySpec) -> None:
    if spec.rotation % 90:
        _apply_rotated_text_as_image(page, page_rect, spec)
        return
    width = page_rect.width * 0.45
    height = max(spec.font_size * 2.5, 40)
    rect = _anchor_rect(page_rect, spec, spec.position, width, height, spec.margin_pt)
    kwargs = {
        "fontsize": spec.font_size,
        "fontname": "helv",
        "color": spec.color,
        "rotate": spec.rotation,
        "overlay": True,
        "fill_opacity": spec.opacity,
    }
    if spec.font_path and spec.font_path.exists():
        kwargs["fontfile"] = str(spec.font_path)
    page.insert_textbox(rect, spec.text, **kwargs)


def _apply_rotated_text_as_image(
    page: fitz.Page,
    page_rect: fitz.Rect,
    spec: PdfOverlaySpec,
) -> None:
    """Render arbitrary-angle text to a transparent image."""
    scale = 3
    font = (
        ImageFont.truetype(str(spec.font_path), max(1, round(spec.font_size * scale)))
        if spec.font_path and spec.font_path.exists()
        else ImageFont.load_default()
    )
    padding = 12 * scale
    probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    bbox = draw.multiline_textbbox((padding, padding), spec.text, font=font, spacing=4 * scale)
    image = Image.new(
        "RGBA", (max(1, bbox[2] + padding), max(1, bbox[3] + padding)), (0, 0, 0, 0)
    )
    draw = ImageDraw.Draw(image)
    color = tuple(round(channel * 255) for channel in spec.color)
    draw.multiline_text(
        (padding, padding), spec.text, font=font,
        fill=(*color, round(255 * spec.opacity)), spacing=4 * scale,
    )
    image = image.rotate(-spec.rotation, expand=True, resample=Image.Resampling.BICUBIC)
    stream = BytesIO()
    image.save(stream, format="PNG")
    width = image.width / scale
    height = image.height / scale
    rect = _anchor_rect(page_rect, spec, spec.position, width, height, spec.margin_pt)
    page.insert_image(rect, stream=stream.getvalue(), overlay=True)


def _apply_image(
    page: fitz.Page,
    page_rect: fitz.Rect,
    spec: PdfOverlaySpec,
    image_xrefs: dict[tuple[Path, float, int], int],
) -> None:
    if spec.asset_path is None or not spec.asset_path.exists():
        raise FileNotFoundError(f"Logo asset not found: {spec.asset_path}")
    with Image.open(spec.asset_path) as source_image:
        image = source_image.convert("RGBA")
        if spec.opacity < 1.0:
            alpha = image.getchannel("A").point(lambda value: round(value * spec.opacity))
            image.putalpha(alpha)
        if spec.rotation % 360:
            image = image.rotate(-spec.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        aspect = image.height / image.width
    width = page_rect.width * spec.width_percent / 100
    height = width * aspect
    rect = _anchor_rect(page_rect, spec, spec.position, width, height, spec.margin_pt)
    cache_key = (spec.asset_path, round(spec.opacity, 4), spec.rotation)
    xref = image_xrefs.get(cache_key)
    if xref is None:
        stream = BytesIO()
        image.save(stream, format="PNG")
        xref = page.insert_image(rect, stream=stream.getvalue())
        image_xrefs[cache_key] = xref
    else:
        page.insert_image(rect, xref=xref, rotate=spec.rotation)


def apply_overlays(
    source: Path,
    destination: Path,
    overlays: list[PdfOverlaySpec],
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Create one marked PDF from one source PDF without combining files."""
    if source.resolve() == destination.resolve():
        raise ValueError("destination must not overwrite the source PDF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    active = sorted((item for item in overlays if item.enabled), key=lambda item: item.z_index)
    with fitz.open(source) as document:
        image_xrefs: dict[tuple[Path, float, int], int] = {}
        total_pages = document.page_count
        for page_number, page in enumerate(document, 1):
            if cancel_check and cancel_check():
                raise RuntimeError("batch cancelled")
            page_rect = page.rect
            for spec in active:
                if spec.overlay_type is OverlayType.TEXT:
                    _apply_text(page, page_rect, spec)
                else:
                    _apply_image(page, page_rect, spec, image_xrefs)
            if progress_callback:
                progress_callback(page_number, total_pages)
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.stem}-",
            suffix=".tmp.pdf",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            document.save(temporary_path, deflate=True, garbage=0)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
