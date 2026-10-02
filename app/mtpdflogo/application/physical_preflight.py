"""Check physical overlay bounds on applicable pages without writing output."""

from pathlib import Path

import fitz
from PIL import Image, ImageOps

from mtpdflogo.application.positioning import resolve_overlay_top_left
from mtpdflogo.domain.models import OverlayType, PositionMode
from mtpdflogo.infrastructure.pdf.overlay_service import (
    PageTextRule,
    PdfOverlaySpec,
    render_physical_layer,
)


def validate_physical_source(
    source: Path, specs: list[PdfOverlaySpec], rule: PageTextRule | None,
) -> None:
    active = [s for s in specs if s.enabled and s.position_mode is PositionMode.FIXED_MM
              and (s.overlay_type is not OverlayType.TEXT or s.text)]
    if not active:
        return
    cache = {}

    def check(width: float, height: float, units: float, page: int) -> None:
        for spec in active:
            key = (spec, width, units)
            if key not in cache:
                _, w, h = render_physical_layer(spec, width, units)
                cache[key] = (w, h)
            w, h = cache[key]
            try:
                resolve_overlay_top_left(
                    page_width=width, page_height=height, overlay_width=w, overlay_height=h,
                    position=spec.position, position_mode=spec.position_mode,
                    x_mm=spec.x_mm, y_mm=spec.y_mm, units_per_mm=units,
                )
            except ValueError as error:
                raise ValueError(f"{source.name}, page {page}: {error}") from error

    if source.suffix.lower() == ".pdf":
        with fitz.open(source) as document:
            for number, page in enumerate(document, 1):
                if rule and (not rule.matches_page(number) or not rule.matches(page.get_text())):
                    continue
                check(page.rect.width, page.rect.height, 72 / 25.4, number)
    else:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            check(image.width, image.height, 96 / 25.4, 1)
