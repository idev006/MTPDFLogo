"""TOML persistence for multi-rule overlay projects (schema version 6)."""

from __future__ import annotations

import json
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from mtpdflogo.config.overlay_preset import normalize_mm_settings
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.domain.rules import ConditionLogic, RuleScope

RULE_PRESET_SCHEMA_VERSION = 6


def is_rule_preset(path: Path) -> bool:
    with path.open("rb") as preset_file:
        return int(tomllib.load(preset_file).get("schema_version", 0)) in {5, 6}


def save_rule_preset(path: Path, groups: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"schema_version = {RULE_PRESET_SCHEMA_VERSION}",
        'application = "MTPDFLogo"',
        'mode = "multi_rule"',
        "",
    ]
    for group in groups:
        lines.extend(
            [
                "[[rule_groups]]",
                f"id = {_quote(group.get('id', ''))}",
                f"name = {_quote(group.get('name', ''))}",
                f"enabled = {_bool(group.get('enabled', True))}",
                f"keyword = {_quote(group.get('keyword', ''))}",
                f"use_regex = {_bool(group.get('use_regex', False))}",
                f"case_sensitive = {_bool(group.get('case_sensitive', False))}",
                f"page_ranges = {_quote(group.get('page_ranges', ''))}",
                f"scope = {_quote(group.get('scope', RuleScope.PAGE.value))}",
                "",
            ]
        )
        for branch in group.get("branches", []):
            maximum = branch.get("max_occurrences", 0)
            persisted_maximum = -1 if maximum is None else max(0, int(maximum))
            lines.extend(
                [
                    "[[rule_groups.branches]]",
                    f"id = {_quote(branch.get('id', ''))}",
                    f"name = {_quote(branch.get('name', ''))}",
                    f"enabled = {_bool(branch.get('enabled', True))}",
                    f"is_else = {_bool(branch.get('is_else', False))}",
                    "condition_logic = "
                    f"{_quote(branch.get('condition_logic', ConditionLogic.ALL.value))}",
                    f"min_occurrences = {max(0, int(branch.get('min_occurrences', 0)))}",
                    f"max_occurrences = {persisted_maximum}",
                    "",
                ]
            )
            for condition in branch.get("conditions", []):
                lines.extend(_condition_lines(condition))
            for index, overlay in enumerate(branch.get("overlays", []), 1):
                lines.extend(_overlay_lines(overlay, index))
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write("\n".join(lines))
    temporary_path.replace(path)


def load_rule_preset(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as preset_file:
        data = tomllib.load(preset_file)
    schema_version = int(data.get("schema_version", 0))
    if schema_version not in {5, RULE_PRESET_SCHEMA_VERSION}:
        raise ValueError("not a multi-rule preset")
    groups: list[dict[str, Any]] = []
    for group_index, raw_group in enumerate(data.get("rule_groups", []), 1):
        branches: list[dict[str, Any]] = []
        for branch_index, raw_branch in enumerate(raw_group.get("branches", []), 1):
            is_else = bool(raw_branch.get("is_else", False))
            conditions = [
                _load_condition(condition, condition_index)
                for condition_index, condition in enumerate(
                    raw_branch.get("conditions", []), 1
                )
            ]
            if schema_version == 5 and not is_else:
                conditions = [
                    {
                        "id": f"condition-{group_index}-{branch_index}-1",
                        "name": "เงื่อนไข 1",
                        "enabled": True,
                        "keyword": str(raw_group.get("keyword", "")),
                        "use_regex": bool(raw_group.get("use_regex", False)),
                        "case_sensitive": bool(raw_group.get("case_sensitive", False)),
                        "negate": False,
                        "scope": str(raw_group.get("scope", RuleScope.PAGE.value)),
                        "min_occurrences": _int(
                            raw_branch.get("min_occurrences", 0), 0, 1_000_000
                        ),
                        "max_occurrences": (
                            None
                            if int(raw_branch.get("max_occurrences", 0)) < 0
                            else _int(
                                raw_branch.get("max_occurrences", 0), 0, 1_000_000
                            )
                        ),
                    }
                ]
            branches.append(
                {
                    "id": str(raw_branch.get("id") or f"branch-{group_index}-{branch_index}"),
                    "name": str(raw_branch.get("name") or f"เงื่อนไข {branch_index}"),
                    "enabled": bool(raw_branch.get("enabled", True)),
                    "is_else": is_else,
                    "condition_logic": str(
                        raw_branch.get("condition_logic", ConditionLogic.ALL.value)
                    ),
                    "conditions": conditions,
                    "min_occurrences": _int(raw_branch.get("min_occurrences", 0), 0, 1_000_000),
                    "max_occurrences": (
                        None
                        if int(raw_branch.get("max_occurrences", 0)) < 0
                        else _int(raw_branch.get("max_occurrences", 0), 0, 1_000_000)
                    ),
                    "overlays": [
                        _load_overlay(item, overlay_index)
                        for overlay_index, item in enumerate(raw_branch.get("overlays", []), 1)
                    ],
                }
            )
        groups.append(
            {
                "id": str(raw_group.get("id") or f"rule-{group_index}"),
                "name": str(raw_group.get("name") or f"Rule Group {group_index}"),
                "enabled": bool(raw_group.get("enabled", True)),
                "keyword": str(raw_group.get("keyword", "")),
                "use_regex": bool(raw_group.get("use_regex", False)),
                "case_sensitive": bool(raw_group.get("case_sensitive", False)),
                "page_ranges": str(raw_group.get("page_ranges", "")),
                "scope": str(raw_group.get("scope", RuleScope.PAGE.value)),
                "branches": branches,
            }
        )
    return groups


def _condition_lines(condition: dict[str, Any]) -> list[str]:
    maximum = condition.get("max_occurrences")
    persisted_maximum = -1 if maximum is None else max(0, int(maximum))
    return [
        "[[rule_groups.branches.conditions]]",
        f"id = {_quote(condition.get('id', ''))}",
        f"name = {_quote(condition.get('name', ''))}",
        f"enabled = {_bool(condition.get('enabled', True))}",
        f"keyword = {_quote(condition.get('keyword', ''))}",
        f"use_regex = {_bool(condition.get('use_regex', False))}",
        f"case_sensitive = {_bool(condition.get('case_sensitive', False))}",
        f"negate = {_bool(condition.get('negate', False))}",
        f"scope = {_quote(condition.get('scope', RuleScope.PAGE.value))}",
        f"min_occurrences = {max(0, int(condition.get('min_occurrences', 0)))}",
        f"max_occurrences = {persisted_maximum}",
        "",
    ]


def _load_condition(raw: dict[str, Any], index: int) -> dict[str, Any]:
    maximum = int(raw.get("max_occurrences", 0))
    return {
        "id": str(raw.get("id") or f"condition-{index}"),
        "name": str(raw.get("name") or f"เงื่อนไข {index}"),
        "enabled": bool(raw.get("enabled", True)),
        "keyword": str(raw.get("keyword", "")),
        "use_regex": bool(raw.get("use_regex", False)),
        "case_sensitive": bool(raw.get("case_sensitive", False)),
        "negate": bool(raw.get("negate", False)),
        "scope": str(raw.get("scope", RuleScope.PAGE.value)),
        "min_occurrences": _int(raw.get("min_occurrences", 0), 0, 1_000_000),
        "max_occurrences": (
            None if maximum < 0 else _int(maximum, 0, 1_000_000)
        ),
    }


def _overlay_lines(item: dict[str, Any], index: int) -> list[str]:
    mm = normalize_mm_settings(item)
    overlay_type = _value(item.get("type"), OverlayType.TEXT.value)
    default_position = (
        Position.TOP_RIGHT.value
        if overlay_type == "image"
        else Position.MIDDLE_CENTER.value
    )
    return [
        "[[rule_groups.branches.overlays]]",
        f"id = {_quote(item.get('id') or f'overlay-{index}')}",
        f"name = {_quote(item.get('name', ''))}",
        f"enabled = {_bool(item.get('enabled', True))}",
        f"locked = {_bool(item.get('locked', False))}",
        f"type = {_quote(overlay_type)}",
        f"position_mode = {_quote(_value(item.get('position_mode'), PositionMode.PRESET.value))}",
        f"position = {_quote(_value(item.get('position'), default_position))}",
        f"x_percent = {_float(item.get('x_percent'), 50.0)}",
        f"y_percent = {_float(item.get('y_percent'), 50.0)}",
        f"x_mm = {mm['x_mm']}",
        f"y_mm = {mm['y_mm']}",
        f"size_mode = {_quote(mm['size_mode'])}",
        f"logo_width_mm = {mm['logo_width_mm']}",
        f"anchor_mode = {_quote(mm['anchor_mode'])}",
        f"text = {_quote(item.get('text', ''))}",
        f"asset_path = {_quote(item.get('asset_path', ''))}",
        f"font = {_quote(item.get('font', ''))}",
        f"font_size = {_int(item.get('font_size', 32), 6, 240)}",
        f"logo_size = {_int(item.get('logo_size', 12), 1, 100)}",
        f"opacity = {_int(item.get('opacity', 100), 0, 100)}",
        f"rotation = {_int(item.get('rotation', 0), -360, 360)}",
        f"color = {_quote(item.get('color', '#000000'))}",
        f"z_index = {_int(item.get('z_index', index - 1), -10000, 10000)}",
        "",
    ]


def _load_overlay(raw: dict[str, Any], index: int) -> dict[str, Any]:
    overlay_type = OverlayType(str(raw.get("type", OverlayType.TEXT.value)))
    default_position = (
        Position.TOP_RIGHT
        if overlay_type is OverlayType.IMAGE
        else Position.MIDDLE_CENTER
    )
    return {
        "id": str(raw.get("id") or f"overlay-{index}"),
        "name": str(raw.get("name", "")),
        "enabled": bool(raw.get("enabled", True)),
        "locked": bool(raw.get("locked", False)),
        "type": overlay_type,
        "position_mode": PositionMode(str(raw.get("position_mode", PositionMode.PRESET.value))),
        "position": Position(str(raw.get("position", default_position.value))),
        "x_percent": _float(raw.get("x_percent"), 50.0),
        "y_percent": _float(raw.get("y_percent"), 50.0),
        **normalize_mm_settings(raw),
        "text": str(raw.get("text", "")),
        "asset_path": str(raw.get("asset_path", "")),
        "font": str(raw.get("font", "")),
        "font_size": _int(raw.get("font_size", 32), 6, 240),
        "logo_size": _int(raw.get("logo_size", 12), 1, 100),
        "opacity": _int(raw.get("opacity", 100), 0, 100),
        "rotation": _int(raw.get("rotation", 0), -360, 360),
        "color": str(raw.get("color", "#000000")),
        "z_index": _int(raw.get("z_index", index - 1), -10000, 10000),
    }


def _quote(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _bool(value: object) -> str:
    return "true" if bool(value) else "false"


def _value(value: object, default: str) -> str:
    return str(getattr(value, "value", value) or default)


def _int(value: object, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
