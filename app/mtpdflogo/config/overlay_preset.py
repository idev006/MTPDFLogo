"""TOML save/load support for reusable overlay settings."""

from __future__ import annotations

import json
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from mtpdflogo.domain.models import OverlayType, Position

PRESET_SCHEMA_VERSION = 1


def _quote(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def save_overlay_preset(path: Path, overlays: list[dict[str, Any]]) -> None:
    """Persist the current text/logo overlay settings as TOML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"schema_version = {PRESET_SCHEMA_VERSION}",
        'application = "MTPDFLogo"',
        "",
    ]
    for index, item in enumerate(overlays, 1):
        lines.extend(
            [
                "[[overlays]]",
                f"id = {_quote(item.get('id') or f'overlay-{index}')}",
                f"type = {_quote(_enum_value(item.get('type'), OverlayType.TEXT))}",
                f"position = {_quote(_enum_value(item.get('position'), Position.MIDDLE_CENTER))}",
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
    with path.open("rb") as preset_file:
        data = tomllib.load(preset_file)
    if int(data.get("schema_version", 0)) != PRESET_SCHEMA_VERSION:
        raise ValueError("unsupported overlay preset schema version")
    overlays: list[dict[str, Any]] = []
    for index, raw_item in enumerate(data.get("overlays", []), 1):
        overlay_type = OverlayType(str(raw_item.get("type", OverlayType.TEXT.value)))
        default_position = (
            Position.TOP_RIGHT
            if overlay_type is OverlayType.IMAGE
            else Position.MIDDLE_CENTER
        )
        overlays.append(
            {
                "id": str(raw_item.get("id") or f"overlay-{index}"),
                "type": overlay_type,
                "position": Position(str(raw_item.get("position", default_position.value))),
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


def _enum_value(value: object, default: OverlayType | Position) -> str:
    if isinstance(value, OverlayType | Position):
        return value.value
    return str(value or default.value)


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
