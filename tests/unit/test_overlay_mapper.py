from __future__ import annotations

from pathlib import Path

from mtpdflogo.application.overlay_mapper import (
    color_to_rgb_float,
    has_effective_overlay,
    missing_logo_paths,
    overlays_to_specs,
    page_filter_error,
    page_text_rule_from_options,
    safe_regex_error,
)
from mtpdflogo.domain.models import OverlayType, Position, PositionMode


def test_overlays_to_specs_maps_text_and_logo_independently(tmp_path: Path) -> None:
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"fake")
    font = tmp_path / "Mali-Bold.ttf"
    font.write_bytes(b"font")
    overlays = [
        {
            "id": "text-1",
            "type": OverlayType.TEXT,
            "position": Position.TOP_CENTER,
            "position_mode": PositionMode.ABSOLUTE,
            "x_percent": 33.5,
            "y_percent": 20.25,
            "text": "ข้อความ",
            "asset_path": "",
            "font": "Mali-Bold",
            "font_size": 44,
            "color": "#336699",
            "opacity": 55,
            "rotation": -15,
            "logo_size": 12,
            "z_index": 4,
        },
        {
            "id": "logo-1",
            "type": OverlayType.IMAGE,
            "position": Position.BOTTOM_RIGHT,
            "position_mode": PositionMode.PRESET,
            "text": "",
            "asset_path": str(logo),
            "font": "",
            "font_size": 32,
            "color": "#000000",
            "opacity": 80,
            "rotation": 30,
            "logo_size": 25,
            "z_index": 5,
        },
    ]

    specs = overlays_to_specs(
        overlays,
        lambda name: font if name == "Mali-Bold" else None,
    )

    assert specs[0].overlay_type is OverlayType.TEXT
    assert specs[0].position_mode is PositionMode.ABSOLUTE
    assert specs[0].x_percent == 33.5
    assert specs[0].font_path == font
    assert specs[0].color == (0x33 / 255, 0x66 / 255, 0x99 / 255)
    assert specs[0].opacity == 0.55
    assert specs[0].rotation == -15
    assert specs[1].overlay_type is OverlayType.IMAGE
    assert specs[1].asset_path == logo
    assert specs[1].width_percent == 25


def test_missing_logo_paths_and_effective_overlay_are_headless(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    assert missing_logo_paths(
        [
            {"id": "empty", "type": OverlayType.IMAGE, "asset_path": ""},
            {"id": "bad", "type": OverlayType.IMAGE, "asset_path": str(missing)},
        ]
    ) == ["empty: ยังไม่ได้เลือกไฟล์ Logo", str(missing)]
    assert has_effective_overlay([{"type": OverlayType.TEXT, "text": "  hello "}])
    assert has_effective_overlay([{"type": OverlayType.IMAGE, "asset_path": str(missing)}])
    assert not has_effective_overlay([{"type": OverlayType.TEXT, "text": "  "}])


def test_page_filter_validation_and_rule_options() -> None:
    assert page_filter_error(enabled=False, keyword="", use_regex=True) is None
    assert page_filter_error(enabled=True, keyword="", use_regex=False)
    assert page_filter_error(enabled=True, keyword="[", use_regex=True).startswith(
        "Regex ไม่ถูกต้อง"
    )
    assert page_filter_error(enabled=True, keyword=r"\d+", use_regex=True) is None
    assert page_filter_error(
        enabled=True,
        keyword="",
        use_regex=False,
        page_ranges="1-3,5,10-",
    ) is None
    assert page_filter_error(
        enabled=True,
        keyword="",
        use_regex=False,
        page_ranges="3-1",
    ).startswith("ช่วงหน้าไม่ถูกต้อง")
    assert page_filter_error(enabled=True, keyword="(a+)+$", use_regex=True).startswith(
        "Regex เสี่ยง"
    )

    assert page_text_rule_from_options(
        enabled=False,
        keyword="amount",
        min_occurrences=1,
        max_occurrences=0,
        use_regex=False,
    ) is None
    rule = page_text_rule_from_options(
        enabled=True,
        keyword=" amount ",
        min_occurrences=2,
        max_occurrences=0,
        use_regex=False,
    )
    assert rule is not None
    assert rule.keyword == "amount"
    assert rule.min_occurrences == 2
    assert rule.max_occurrences is None
    ranged_rule = page_text_rule_from_options(
        enabled=True,
        keyword="",
        min_occurrences=1,
        max_occurrences=0,
        use_regex=False,
        page_ranges="2-4",
    )
    assert ranged_rule is not None
    assert ranged_rule.keyword == ""
    assert ranged_rule.page_ranges == "2-4"


def test_color_to_rgb_float_falls_back_to_black() -> None:
    assert color_to_rgb_float("not-a-color") == (0.0, 0.0, 0.0)


def test_safe_regex_error_blocks_high_risk_patterns() -> None:
    assert safe_regex_error(r"(.*)+") is not None
    assert safe_regex_error("a" * 501) == "Regex ยาวเกินไป: จำกัด 500 ตัวอักษร"
    assert safe_regex_error(r"invoice\s+\d+") is None
