from pathlib import Path

from mtpdflogo.config.overlay_preset import (
    load_overlay_preset,
    load_page_filter_options,
    save_overlay_preset,
)
from mtpdflogo.domain.models import OverlayType, Position, PositionMode


def test_overlay_preset_round_trip_as_toml(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    overlays = [
        {
            "id": "text-1",
            "type": OverlayType.TEXT,
            "position_mode": PositionMode.ABSOLUTE,
            "position": Position.MIDDLE_CENTER,
            "x_percent": 44.25,
            "y_percent": 18.5,
            "opacity": 54,
            "rotation": -30,
            "font_size": 32,
            "font": "Mali-Bold",
            "logo_size": 12,
            "text": "ข้อความตัวอย่าง",
            "asset_path": "",
            "color": "#112233",
        },
        {
            "id": "logo-1",
            "type": OverlayType.IMAGE,
            "position_mode": PositionMode.PRESET,
            "position": Position.TOP_RIGHT,
            "x_percent": 50.0,
            "y_percent": 50.0,
            "opacity": 75,
            "rotation": 15,
            "font_size": 20,
            "font": "THSarabunNew",
            "logo_size": 25,
            "text": "",
            "asset_path": str(tmp_path / "logo.png"),
            "color": "#000000",
        },
    ]

    save_overlay_preset(
        path,
        overlays,
        {
            "enabled": True,
            "keyword": "จำนวนเงิน",
            "use_regex": False,
            "min_occurrences": 2,
            "max_occurrences": 9,
            "page_ranges": "1-3,5",
        },
    )

    assert load_overlay_preset(path) == overlays
    assert load_page_filter_options(path) == {
        "enabled": True,
        "keyword": "จำนวนเงิน",
        "use_regex": False,
        "min_occurrences": 2,
        "max_occurrences": 9,
        "page_ranges": "1-3,5",
    }


def test_overlay_preset_defaults_page_filter_for_older_files(tmp_path: Path) -> None:
    path = tmp_path / "old-settings.toml"
    save_overlay_preset(path, [])

    assert load_page_filter_options(path) == {
        "enabled": False,
        "keyword": "",
        "use_regex": False,
        "min_occurrences": 1,
        "max_occurrences": 10,
        "page_ranges": "",
    }
