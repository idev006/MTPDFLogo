"""TOML save/load support for reusable overlay settings."""

from __future__ import annotations

import json
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from mtpdflogo.domain.models import OverlayType, Position, PositionMode

PRESET_SCHEMA_VERSION = 2


def _quote(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def save_overlay_preset(
    path: Path,
    overlays: list[dict[str, Any]],
    page_filter: dict[str, Any] | None = None,
) -> None:
    """Persist the current text/logo overlay settings as TOML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"schema_version = {PRESET_SCHEMA_VERSION}",
        'application = "MTPDFLogo"',
        "",
    ]
    if page_filter is not None:
        lines.extend(
            [
                "[page_filter]",
                f"enabled = {_bool_value(page_filter.get('enabled', False))}",
                f"keyword = {_quote(page_filter.get('keyword', ''))}",
                f"use_regex = {_bool_value(page_filter.get('use_regex', False))}",
                f"min_occurrences = {int(page_filter.get('min_occurrences', 1))}",
                f"max_occurrences = {int(page_filter.get('max_occurrences', 10))}",
                f"page_ranges = {_quote(page_filter.get('page_ranges', ''))}",
                "",
            ]
        )
    for index, item in enumerate(overlays, 1):
        lines.extend(
            [
                "[[overlays]]",
                f"id = {_quote(item.get('id') or f'overlay-{index}')}",
                f"type = {_quote(_enum_value(item.get('type'), OverlayType.TEXT))}",
                "position_mode = "
                f"{_quote(_enum_value(item.get('position_mode'), PositionMode.PRESET))}",
                f"position = {_quote(_enum_value(item.get('position'), Position.MIDDLE_CENTER))}",
                f"x_percent = {_float_or_default(item.get('x_percent'), 50.0):.4f}",
                f"y_percent = {_float_or_default(item.get('y_percent'), 50.0):.4f}",
                f"text = {_quote(item.get('text', ''))}",
                f"asset_path = {_quote(item.get('asset_path', ''))}",
                f"font = {_quote(item.get('font', ''))}",
                f"font_size = {int(item.get('font_size', 32))}",
                f"logo_size = {int(item.get('logo_size', 12))}",
                f"opacity = {int(item.get('opacity', 100))}",
                f"rotation = {int(item.get('rotation', 0))}",
                f"color = {_quote(item.get('color', '#000000'))}",
                "",
            ]
        )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write("\n".join(lines))
    temporary_path.replace(path)


def load_overlay_preset(path: Path) -> list[dict[str, Any]]:
    """Load text/logo overlay settings from a TOML preset file."""
    data = _load_preset_data(path)
    overlays: list[dict[str, Any]] = []
    for index, raw_item in enumerate(data.get("overlays", []), 1):
        overlay_type = OverlayType(str(raw_item.get("type", OverlayType.TEXT.value)))
        default_position = (
            Position.TOP_RIGHT
            if overlay_type is OverlayType.IMAGE
            else Position.MIDDLE_CENTER
        )
        position_mode = PositionMode(
            str(raw_item.get("position_mode", PositionMode.PRESET.value))
        )
        overlays.append(
            {
                "id": str(raw_item.get("id") or f"overlay-{index}"),
                "type": overlay_type,
                "position_mode": position_mode,
                "position": Position(str(raw_item.get("position", default_position.value))),
                "x_percent": _bounded_float(raw_item.get("x_percent", 50.0), 0.0, 100.0),
                "y_percent": _bounded_float(raw_item.get("y_percent", 50.0), 0.0, 100.0),
                "opacity": _bounded_int(raw_item.get("opacity", 100), 0, 100),
                "rotation": _bounded_int(raw_item.get("rotation", 0), -360, 360),
                "font_size": _bounded_int(raw_item.get("font_size", 32), 6, 240),
                "font": str(raw_item.get("font", "")),
                "logo_size": _bounded_int(raw_item.get("logo_size", 12), 1, 100),
                "text": str(raw_item.get("text", "")),
                "asset_path": str(raw_item.get("asset_path", "")),
                "color": str(raw_item.get("color", "#000000")),
            }
        )
    return overlays


def load_page_filter_options(path: Path) -> dict[str, Any]:
    """Load optional page filter settings from a TOML preset file."""
    data = _load_preset_data(path)
    raw_filter = data.get("page_filter", {})
    if not isinstance(raw_filter, dict):
        raw_filter = {}
    return {
        "enabled": bool(raw_filter.get("enabled", False)),
        "keyword": str(raw_filter.get("keyword", "")),
        "use_regex": bool(raw_filter.get("use_regex", False)),
        "min_occurrences": _bounded_int(raw_filter.get("min_occurrences", 1), 1, 999),
        "max_occurrences": _bounded_int(raw_filter.get("max_occurrences", 10), 0, 999),
        "page_ranges": str(raw_filter.get("page_ranges", "")),
    }


def _load_preset_data(path: Path) -> dict[str, Any]:
    with path.open("rb") as preset_file:
        data = tomllib.load(preset_file)
    schema_version = int(data.get("schema_version", 0))
    if schema_version not in {1, PRESET_SCHEMA_VERSION}:
        raise ValueError("unsupported overlay preset schema version")
    return data


def _bool_value(value: object) -> str:
    return "true" if bool(value) else "false"


def _enum_value(value: object, default: OverlayType | Position | PositionMode) -> str:
    if isinstance(value, OverlayType | Position | PositionMode):
        return value.value
    return str(value or default.value)


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _bounded_float(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
