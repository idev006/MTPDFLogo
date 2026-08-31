"""Shared overlay positioning rules for preview and export."""

from __future__ import annotations

from mtpdflogo.domain.models import Position, PositionMode


def resolve_overlay_top_left(
    *,
    page_width: float,
    page_height: float,
    overlay_width: float,
    overlay_height: float,
    position: Position,
    position_mode: PositionMode = PositionMode.PRESET,
    x_percent: float | None = None,
    y_percent: float | None = None,
    margin: float = 18.0,
) -> tuple[float, float]:
    """Resolve an overlay's top-left coordinate on a page-like rectangle."""
    if position_mode is PositionMode.ABSOLUTE and x_percent is not None and y_percent is not None:
        center_x = page_width * clamp_percent(x_percent) / 100
        center_y = page_height * clamp_percent(y_percent) / 100
        return _clamp_to_page(
            center_x - overlay_width / 2,
            center_y - overlay_height / 2,
            page_width,
            page_height,
            overlay_width,
            overlay_height,
        )
    return _preset_top_left(
        page_width, page_height, overlay_width, overlay_height, position, margin
    )


def point_to_percent(
    *,
    x: float,
    y: float,
    page_width: float,
    page_height: float,
) -> tuple[float, float]:
    """Convert a point on the page into bounded page percentages."""
    if page_width <= 0 or page_height <= 0:
        return 50.0, 50.0
    return clamp_percent(x * 100 / page_width), clamp_percent(y * 100 / page_height)


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _preset_top_left(
    page_width: float,
    page_height: float,
    overlay_width: float,
    overlay_height: float,
    position: Position,
    margin: float,
) -> tuple[float, float]:
    horizontal = {
        Position.TOP_LEFT: margin,
        Position.MIDDLE_LEFT: margin,
        Position.BOTTOM_LEFT: margin,
        Position.TOP_CENTER: (page_width - overlay_width) / 2,
        Position.MIDDLE_CENTER: (page_width - overlay_width) / 2,
        Position.BOTTOM_CENTER: (page_width - overlay_width) / 2,
        Position.TOP_RIGHT: page_width - overlay_width - margin,
        Position.MIDDLE_RIGHT: page_width - overlay_width - margin,
        Position.BOTTOM_RIGHT: page_width - overlay_width - margin,
    }[position]
    vertical = {
        Position.TOP_LEFT: margin,
        Position.TOP_CENTER: margin,
        Position.TOP_RIGHT: margin,
        Position.MIDDLE_LEFT: (page_height - overlay_height) / 2,
        Position.MIDDLE_CENTER: (page_height - overlay_height) / 2,
        Position.MIDDLE_RIGHT: (page_height - overlay_height) / 2,
        Position.BOTTOM_LEFT: page_height - overlay_height - margin,
        Position.BOTTOM_CENTER: page_height - overlay_height - margin,
        Position.BOTTOM_RIGHT: page_height - overlay_height - margin,
    }[position]
    return _clamp_to_page(
        horizontal, vertical, page_width, page_height, overlay_width, overlay_height
    )


def _clamp_to_page(
    x: float,
    y: float,
    page_width: float,
    page_height: float,
    overlay_width: float,
    overlay_height: float,
) -> tuple[float, float]:
    max_x = max(0.0, page_width - overlay_width)
    max_y = max(0.0, page_height - overlay_height)
    return max(0.0, min(max_x, x)), max(0.0, min(max_y, y))
