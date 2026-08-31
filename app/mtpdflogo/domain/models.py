"""Domain model for independent text/logo overlays."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OverlayType(StrEnum):
    TEXT = "text"
    IMAGE = "image"


class PositionMode(StrEnum):
    PRESET = "preset"
    ABSOLUTE = "absolute"


class Position(StrEnum):
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


@dataclass(frozen=True, slots=True)
class OverlayItem:
    """One independently configurable text or image item."""

    id: str
    overlay_type: OverlayType
    position: Position
    position_mode: PositionMode = PositionMode.PRESET
    x_percent: float | None = None
    y_percent: float | None = None
    opacity: float = 1.0
    rotation: float = 0.0
    margin_pt: float = 18.0
    x_offset_pt: float = 0.0
    y_offset_pt: float = 0.0
    z_index: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        if self.margin_pt < 0:
            raise ValueError("margin_pt must not be negative")
        if self.position_mode is PositionMode.ABSOLUTE:
            if self.x_percent is None or self.y_percent is None:
                raise ValueError("absolute position requires x_percent and y_percent")
            if not 0.0 <= self.x_percent <= 100.0:
                raise ValueError("x_percent must be between 0.0 and 100.0")
            if not 0.0 <= self.y_percent <= 100.0:
                raise ValueError("y_percent must be between 0.0 and 100.0")
