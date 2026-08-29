from mtpdflogo.domain.models import OverlayItem, OverlayType, Position


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
    try:
        OverlayItem("logo", OverlayType.IMAGE, Position.TOP_RIGHT, opacity=1.1)
    except ValueError as error:
        assert "opacity" in str(error)
    else:
        raise AssertionError("invalid opacity should be rejected")
