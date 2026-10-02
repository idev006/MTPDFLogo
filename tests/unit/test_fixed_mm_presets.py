"""Schema 4 physical-unit anchors and legacy preset compatibility."""

import math
import tomllib
from pathlib import Path

import pytest
from mtpdflogo.application.overlay_mapper import overlays_to_specs
from mtpdflogo.config.overlay_preset import (
    load_overlay_preset,
    load_page_filter_options,
    save_overlay_preset,
)
from mtpdflogo.domain.models import OverlayType, Position, PositionMode


def test_fixed_mm_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "fixed.toml"
    overlay = {
        "type": OverlayType.IMAGE,
        "position": Position.TOP_LEFT,
        "position_mode": PositionMode.FIXED_MM,
        "x_mm": 12.3456789,
        "y_mm": 2000.0,
        "size_mode": "mm",
        "logo_width_mm": 0.1,
        "anchor_mode": "top_left",
        "asset_path": "logo.png",
    }
    page_filter = {
        "enabled": True,
        "keyword": "invoice",
        "use_regex": False,
        "min_occurrences": 1,
        "max_occurrences": 5,
        "page_ranges": "1-3",
    }
    save_overlay_preset(path, [overlay], page_filter)
    assert tomllib.loads(path.read_text(encoding="utf-8"))["schema_version"] == 4
    loaded = load_overlay_preset(path)
    for key, value in overlay.items():
        assert loaded[0][key] == value
    assert load_page_filter_options(path) == page_filter
    save_overlay_preset(path, loaded, page_filter)
    assert load_overlay_preset(path) == loaded
    spec = overlays_to_specs(loaded, lambda _: None)[0]
    assert spec.position_mode is PositionMode.FIXED_MM
    assert (spec.x_mm, spec.y_mm, spec.width_mm) == (12.3456789, 2000.0, 0.1)


@pytest.mark.parametrize("schema", [1, 2, 3, 4])
@pytest.mark.parametrize("mode", [None, "preset", "absolute"])
def test_legacy_modes_and_defaults_are_preserved(
    tmp_path: Path, schema: int, mode: str | None
) -> None:
    path = tmp_path / "legacy.toml"
    mode_line = f'position_mode = "{mode}"\n' if mode else ""
    path.write_text(
        f'schema_version = {schema}\n[[overlays]]\ntype = "image"\n'
        f'{mode_line}x_percent = 31.25\ny_percent = 68.5\nlogo_size = 18\n',
        encoding="utf-8",
    )
    loaded = load_overlay_preset(path)
    item = loaded[0]
    assert item["position_mode"] is PositionMode(mode or "preset")
    assert item["position"] is Position.TOP_RIGHT
    assert (item["x_percent"], item["y_percent"], item["logo_size"]) == (31.25, 68.5, 18)
    assert (item["x_mm"], item["y_mm"], item["logo_width_mm"]) == (0.0, 0.0, 25.0)
    assert item["size_mode"] == "percent"
    assert item["anchor_mode"] == ("center" if schema <= 3 else "top_left")
    spec = overlays_to_specs(loaded, lambda _: None)[0]
    assert spec.position_mode is PositionMode(mode or "preset")
    assert (spec.x_percent, spec.y_percent, spec.width_percent) == (31.25, 68.5, 18.0)
    assert spec.width_mm is None
    save_overlay_preset(path, loaded)
    assert load_overlay_preset(path) == loaded


@pytest.mark.parametrize(
    ("literal", "coordinate", "width"),
    [
        ("nan", 0.0, 25.0),
        ("inf", 0.0, 25.0),
        ("-inf", 0.0, 25.0),
        ('"invalid"', 0.0, 25.0),
        ('"NaN"', 0.0, 25.0),
        ("[]", 0.0, 25.0),
        ("-5.0", 0.0, 0.1),
        ("0.0", 0.0, 0.1),
        ("2500.0", 2000.0, 2000.0),
        ("0.1", 0.1, 0.1),
        ("2000.0", 2000.0, 2000.0),
    ],
)
def test_load_normalizes_invalid_and_bounded_mm_values(
    tmp_path: Path, literal: str, coordinate: float, width: float
) -> None:
    path = tmp_path / "numbers.toml"
    path.write_text(
        'schema_version = 3\n[[overlays]]\nsize_mode = "mm"\n'
        f'x_mm = {literal}\ny_mm = {literal}\nlogo_width_mm = {literal}\n',
        encoding="utf-8",
    )
    item = load_overlay_preset(path)[0]
    assert (item["x_mm"], item["y_mm"], item["logo_width_mm"]) == (
        coordinate, coordinate, width
    )
    assert all(math.isfinite(item[key]) for key in ("x_mm", "y_mm", "logo_width_mm"))


@pytest.mark.parametrize("value", [None, "bad", float("nan"), float("inf"), -float("inf"),
                                  10**400, [], {}])
def test_save_and_mapper_normalize_invalid_mm_values(tmp_path: Path, value: object) -> None:
    path = tmp_path / "invalid.toml"
    overlay = {
        "type": OverlayType.IMAGE,
        "position": Position.TOP_LEFT,
        "position_mode": PositionMode.FIXED_MM,
        "size_mode": "mm",
        "x_mm": value,
        "y_mm": value,
        "logo_width_mm": value,
    }
    save_overlay_preset(path, [overlay])
    raw = tomllib.loads(path.read_text(encoding="utf-8"))["overlays"][0]
    assert (raw["x_mm"], raw["y_mm"], raw["logo_width_mm"]) == (0.0, 0.0, 25.0)
    spec = overlays_to_specs([overlay], lambda _: None)[0]
    assert (spec.x_mm, spec.y_mm, spec.width_mm) == (0.0, 0.0, 25.0)
    assert overlay["x_mm"] is value  # Normalization must not mutate caller settings.


@pytest.mark.parametrize("mode", ["preset", "absolute", "fixed_mm"])
@pytest.mark.parametrize("size_mode", [None, "percent", "mm", "invalid"])
def test_mapper_keeps_position_and_size_modes_independent(mode: str, size_mode: str | None) -> None:
    overlay = {
        "type": OverlayType.IMAGE,
        "position": Position.TOP_LEFT,
        "position_mode": mode,
        "x_mm": 10.0,
        "y_mm": 20.0,
        "logo_width_mm": 35.0,
        "logo_size": 17,
    }
    if size_mode is not None:
        overlay["size_mode"] = size_mode
    spec = overlays_to_specs([overlay], lambda _: None)[0]
    assert spec.position_mode is PositionMode(mode)
    assert (spec.x_mm, spec.y_mm) == (10.0, 20.0)
    assert spec.width_mm == (35.0 if size_mode == "mm" else None)
    assert spec.width_percent == 17.0


def test_unknown_size_mode_defaults_to_percent(tmp_path: Path) -> None:
    path = tmp_path / "unknown-size.toml"
    path.write_text(
        'schema_version = 3\n[[overlays]]\nsize_mode = "unknown"\n', encoding="utf-8"
    )
    assert load_overlay_preset(path)[0]["size_mode"] == "percent"
    save_overlay_preset(path, [{"size_mode": "unknown"}])
    assert load_overlay_preset(path)[0]["size_mode"] == "percent"


@pytest.mark.parametrize("schema", [0, 5])
def test_unsupported_schema_is_rejected(tmp_path: Path, schema: int) -> None:
    path = tmp_path / "unsupported.toml"
    path.write_text(f"schema_version = {schema}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported overlay preset schema"):
        load_overlay_preset(path)
