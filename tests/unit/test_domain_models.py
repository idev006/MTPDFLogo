import pytest
from mtpdflogo.domain.models import OverlayItem, OverlayType, Position, PositionMode


def test_overlay_item_is_independently_configurable() -> None:
    item = OverlayItem(
        id="confidential",
        overlay_type=OverlayType.TEXT,
        position=Position.MIDDLE_CENTER,
        opacity=0.25,
        rotation=45,
    )

    assert item.overlay_type is OverlayType.TEXT
    assert item.position is Position.MIDDLE_CENTER
    assert item.opacity == 0.25
    assert item.rotation == 45


def test_overlay_item_rejects_invalid_opacity() -> None:
    with pytest.raises(ValueError, match="opacity"):
        OverlayItem("logo", OverlayType.IMAGE, Position.TOP_RIGHT, opacity=1.1)


def test_overlay_item_rejects_negative_margin() -> None:
    with pytest.raises(ValueError, match="margin_pt"):
        OverlayItem("logo", OverlayType.IMAGE, Position.TOP_RIGHT, margin_pt=-1)


def test_absolute_position_requires_coordinates() -> None:
    with pytest.raises(ValueError, match="absolute position"):
        OverlayItem(
            "logo",
            OverlayType.IMAGE,
            Position.TOP_RIGHT,
            position_mode=PositionMode.ABSOLUTE,
        )


def test_absolute_position_rejects_out_of_range_coordinates() -> None:
    with pytest.raises(ValueError, match="x_percent"):
        OverlayItem(
            "logo",
            OverlayType.IMAGE,
            Position.TOP_RIGHT,
            position_mode=PositionMode.ABSOLUTE,
            x_percent=101,
            y_percent=50,
        )

    with pytest.raises(ValueError, match="y_percent"):
        OverlayItem(
            "logo",
            OverlayType.IMAGE,
            Position.TOP_RIGHT,
            position_mode=PositionMode.ABSOLUTE,
            x_percent=50,
            y_percent=-1,
        )
