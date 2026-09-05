"""Map user-facing overlay settings into export-ready specifications.

This module is intentionally Qt-free so the settings-to-output contract can be
tested without opening the desktop UI.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec

_HEX_COLOR_PATTERN = re.compile(r"^#?([0-9a-fA-F]{6})$")


def missing_logo_paths(overlays: list[dict[str, Any]]) -> list[str]:
    """Return missing logo asset issues for preflight display."""
    missing: list[str] = []
    for item in overlays:
        if item.get("type") is not OverlayType.IMAGE:
            continue
        asset_path = str(item.get("asset_path", "")).strip()
        if not asset_path:
            missing.append(f"{item.get('id', 'logo')}: ยังไม่ได้เลือกไฟล์ Logo")
        elif not Path(asset_path).exists():
            missing.append(asset_path)
    return missing


def has_effective_overlay(overlays: list[dict[str, Any]]) -> bool:
    """Return True when at least one item can visibly change output bytes."""
    for item in overlays:
        if item.get("type") is OverlayType.TEXT and str(item.get("text", "")).strip():
            return True
        if item.get("type") is OverlayType.IMAGE and str(item.get("asset_path", "")).strip():
            return True
    return False


def color_to_rgb_float(color_name: str) -> tuple[float, float, float]:
    """Convert a #RRGGBB color string to PyMuPDF-compatible float RGB."""
    match = _HEX_COLOR_PATTERN.match(color_name.strip())
    if not match:
        return (0.0, 0.0, 0.0)
    value = match.group(1)
    red = int(value[0:2], 16) / 255
    green = int(value[2:4], 16) / 255
    blue = int(value[4:6], 16) / 255
    return (red, green, blue)


def overlays_to_specs(
    overlays: list[dict[str, Any]],
    font_path_resolver: Callable[[str], Path | None],
) -> list[PdfOverlaySpec]:
    """Create export specs from persisted/UI overlay dictionaries."""
    specs: list[PdfOverlaySpec] = []
    for item in overlays:
        asset_path = str(item.get("asset_path", "")).strip()
        font_name = str(item.get("font", "")).strip()
        specs.append(
            PdfOverlaySpec(
                overlay_type=OverlayType(item["type"]),
                position=Position(item["position"]),
                text=str(item.get("text", "")),
                position_mode=PositionMode(item.get("position_mode", PositionMode.PRESET)),
                x_percent=float(item.get("x_percent", 50.0)),
                y_percent=float(item.get("y_percent", 50.0)),
                asset_path=Path(asset_path) if asset_path else None,
                font_size=float(item.get("font_size", 32)),
                font_path=font_path_resolver(font_name) if font_name else None,
                color=color_to_rgb_float(str(item.get("color", "#000000"))),
                opacity=float(item.get("opacity", 100)) / 100,
                rotation=int(item.get("rotation", 0)),
                width_percent=float(item.get("logo_size", 12)),
                z_index=int(item.get("z_index", 0)),
            )
        )
    return specs


def page_filter_error(
    *,
    enabled: bool,
    keyword: str,
    use_regex: bool,
) -> str | None:
    """Validate page text filter options the same way export will use them."""
    if not enabled:
        return None
    keyword = keyword.strip()
    if not keyword:
        return "ใส่คำหรือ regex ที่จะใช้กรองหน้าก่อนเริ่ม Batch"
    if use_regex:
        try:
            re.compile(PageTextRule(keyword, use_regex=True).normalized_pattern())
        except re.error as error:
            return f"Regex ไม่ถูกต้อง: {error}"
    return None


def page_text_rule_from_options(
    *,
    enabled: bool,
    keyword: str,
    min_occurrences: int,
    max_occurrences: int,
    use_regex: bool,
) -> PageTextRule | None:
    """Build a PageTextRule from UI-like options."""
    keyword = keyword.strip()
    if not enabled or not keyword:
        return None
    return PageTextRule(
        keyword=keyword,
        min_occurrences=min_occurrences,
        max_occurrences=max_occurrences if max_occurrences > 0 else None,
        use_regex=use_regex,
    )
