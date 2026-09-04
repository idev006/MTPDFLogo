from mtpdflogo.application.positioning import point_to_percent, resolve_overlay_top_left
from mtpdflogo.domain.models import Position, PositionMode


def test_resolve_preset_position_keeps_existing_nine_point_behavior() -> None:
    assert resolve_overlay_top_left(
        page_width=600,
        page_height=800,
        overlay_width=100,
        overlay_height=50,
        position=Position.BOTTOM_RIGHT,
        margin=20,
    ) == (480, 730)


def test_resolve_absolute_position_uses_percent_center() -> None:
    assert resolve_overlay_top_left(
        page_width=600,
        page_height=800,
        overlay_width=100,
        overlay_height=50,
        position=Position.TOP_LEFT,
        position_mode=PositionMode.ABSOLUTE,
        x_percent=50,
        y_percent=25,
    ) == (250, 175)


def test_point_to_percent_is_bounded() -> None:
    assert point_to_percent(x=700, y=-10, page_width=600, page_height=800) == (100, 0)
