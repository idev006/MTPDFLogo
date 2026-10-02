import fitz
import pytest
from mtpdflogo.config.overlay_preset import load_overlay_preset, save_overlay_preset
from mtpdflogo.domain.models import OverlayType, PositionMode
from mtpdflogo.presentation.main_window import DraggablePixmapItem, MainWindow
from PIL import Image


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "settings"))
    source = tmp_path / "mixed.pdf"
    with fitz.open() as doc:
        doc.new_page(width=612, height=1008)
        doc.new_page(width=595.32, height=841.92)
        doc.save(source)
    logo = tmp_path / "logo.png"
    Image.new("RGB", (120, 60), "red").save(logo)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_pdf(source)
    window._append_overlay(OverlayType.IMAGE, str(logo))
    return window


def graphic(window):
    return next(g for g in window._scene.items() if isinstance(g, DraggablePixmapItem))


def test_mm_conversion_drag_resize_roundtrip(window, qtbot, tmp_path):
    original = graphic(window).sceneBoundingRect().center()
    window.position_mode.setCurrentIndex(window.position_mode.findData(PositionMode.FIXED_MM))
    center = graphic(window).sceneBoundingRect().center()
    assert center.x() == pytest.approx(original.x(), abs=1)
    assert center.y() == pytest.approx(original.y(), abs=1)
    window.logo_size_mode.setCurrentIndex(window.logo_size_mode.findData("mm"))
    item = window._overlays[0]
    old_width = item["logo_width_mm"]
    window.x_mm.setValue(100)
    window.y_mm.setValue(70)
    g = graphic(window)
    g.moveBy(10, 20)
    window._preview_item_dropped(item["id"], g)
    qtbot.wait(10)
    assert item["position_mode"] is PositionMode.FIXED_MM
    assert item["x_mm"] > 100 and item["y_mm"] > 70
    window._commit_overlay_resize(item["id"], 1.5)
    assert item["logo_width_mm"] == pytest.approx(old_width * 1.5, abs=.001)
    assert window.logo_width_mm.value() == item["logo_width_mm"]
    stored = (item["x_mm"], item["y_mm"], item["logo_width_mm"])
    window._preview_page_index = 1
    window._refresh_preview()
    assert (item["x_mm"], item["y_mm"], item["logo_width_mm"]) == stored
    path = tmp_path / "preset.toml"
    save_overlay_preset(path, window._overlays)
    loaded = load_overlay_preset(path)[0]
    assert (loaded["x_mm"], loaded["y_mm"], loaded["logo_width_mm"]) == stored
    spec = window._to_specs()[0]
    assert (spec.x_mm, spec.y_mm, spec.width_mm) == stored
    window.y_mm.setValue(1000)
    assert window.bounds_warning.text()


def test_text_and_logo_settings_remain_independent(window):
    before = dict(window._overlays[0])
    window._append_overlay(OverlayType.TEXT)
    window.position_mode.setCurrentIndex(window.position_mode.findData(PositionMode.FIXED_MM))
    window.x_mm.setValue(70)
    window.y_mm.setValue(100)
    window.font_size.setValue(48)
    assert window._overlays[0] == before
    assert window._to_specs()[1].x_mm == 70
    assert len([g for g in window._scene.items() if isinstance(g, DraggablePixmapItem)]) == 2
