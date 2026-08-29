from pathlib import Path

from mtpdflogo.config.overlay_preset import load_overlay_preset, save_overlay_preset
from mtpdflogo.domain.models import OverlayType, Position


def test_overlay_preset_round_trip_as_toml(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    overlays = [
        {
            "id": "text-1",
            "type": OverlayType.TEXT,
            "position": Position.MIDDLE_CENTER,
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
            "position": Position.TOP_RIGHT,
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

    save_overlay_preset(path, overlays)

    assert load_overlay_preset(path) == overlays
