"""Domain model for independent text/logo overlays."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OverlayType(StrEnum):
    TEXT = "text"
    IMAGE = "image"


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
