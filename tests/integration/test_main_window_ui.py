from pathlib import Path

import fitz
import pytest
from mtpdflogo.application.export_policy import output_conflict_issues
from mtpdflogo.application.positioning import point_to_percent
from mtpdflogo.config.overlay_preset import load_page_filter_options, save_overlay_preset
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.presentation.main_window import DraggableTextItem, MainWindow
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGraphicsTextItem,
    QGroupBox,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolBar,
)


@pytest.fixture(autouse=True)
def isolate_user_preferences(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


def test_main_window_has_single_pdf_picker_and_pipeline(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    toolbar = window.findChild(QToolBar, "mainToolbar")
    action_labels = [action.text() for action in toolbar.actions()]

    assert action_labels.count("เลือกไฟล์") == 1
    menu_labels = [action.text() for menu in window.menuBar().actions()
                   for action in menu.menu().actions()]
    assert "เลือกโฟลเดอร์ต้นทาง" in menu_labels
    assert "เพิ่ม Text+Logo" in menu_labels
    assert "บันทึก Default" in menu_labels
    assert "โหลด Default" in menu_labels
    assert "About Dev" in action_labels
    assert "เลือก PDF File(s)" not in action_labels
    assert "Batch PDF (หลายไฟล์)" not in action_labels
    assert [label.text() for label in window.pipeline_labels] == [
        "1  เลือกไฟล์/โฟลเดอร์",
        "2  ตั้ง Text/Logo",
        "3  ตั้ง Output",
        "4  เริ่ม Batch",
        "5  ตรวจ Output",
    ]
    assert window.pipeline_summary.text() == "รอเลือกไฟล์"


def test_preview_canvas_is_large_and_resizable(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1800, 1000)
    window.show()
    qtbot.waitExposed(window)

    canvas_splitter = window.findChild(QSplitter, "canvasSplitter")
    workspace_splitter = window.findChild(QSplitter, "batchSplitter")

    assert canvas_splitter is not None
    assert workspace_splitter is not None
    assert canvas_splitter.orientation() == Qt.Orientation.Horizontal
    assert workspace_splitter.orientation() == Qt.Orientation.Horizontal
    assert 6 <= canvas_splitter.handleWidth() <= 10
    assert 6 <= workspace_splitter.handleWidth() <= 10
    assert canvas_splitter.opaqueResize()
    assert workspace_splitter.opaqueResize()
    assert not canvas_splitter.childrenCollapsible()
    assert not workspace_splitter.childrenCollapsible()
    assert canvas_splitter.handle(1).toolTip() == "ลากเพื่อปรับขนาด panel"
    assert workspace_splitter.handle(1).toolTip() == "ลากเพื่อปรับขนาด panel"
    assert canvas_splitter.widget(0).maximumWidth() > 1000
    assert canvas_splitter.widget(2).maximumWidth() > 1000
    assert window.preview.height() > 600
    assert window.preview.minimumHeight() >= 240
    assert "ลากเส้นแบ่งเพื่อปรับขนาด panel" in window.statusBar().currentMessage()
    assert canvas_splitter.sizes()[1] > canvas_splitter.sizes()[0]
    assert canvas_splitter.sizes()[1] > canvas_splitter.sizes()[2]
    window.main_tabs.setCurrentIndex(1)
    qtbot.wait(0)
    assert window.queue_table.height() > 500


def test_about_dev_content_is_present_and_privacy_safe(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    about = window._about_dev_text()

    assert "Developer: Masteriii (MT)" in about
    assert "MTPDFLogo" in about
    assert "Privacy note" in about
    assert "@" not in about


def test_properties_panel_uses_scrollable_tabs(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    tabs = window.findChild(QTabWidget, "propertiesTabs")

    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Content",
        "Layout",
        "Style",
    ]


def test_preview_zoom_persists_without_and_with_overlay(qtbot, tmp_path) -> None:
    image = tmp_path / "source.png"
    Image.new("RGB", (200, 100), "white").save(image)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_image(image)

    window.zoom_in_button.click()
    zoomed_transform = window.preview.transform()

    assert window._preview_zoom == 1.25
    assert window.zoom_label.text() == "125%"

    window._refresh_preview()

    assert window._preview_zoom == 1.25
    assert window.preview.transform().m11() == pytest.approx(zoomed_transform.m11())

    window._append_overlay(OverlayType.TEXT)

    assert window._preview_zoom == 1.25
    assert window.preview.transform().m11() == pytest.approx(zoomed_transform.m11())

    window.zoom_fit_button.click()

    assert window._preview_zoom == 1.0
    assert window.zoom_label.text() == "Fit"


def test_pdf_preview_can_switch_pages_before_positioning(qtbot, tmp_path) -> None:
    source = tmp_path / "mixed-pages.pdf"
    document = fitz.open()
    document.new_page(width=400, height=200)
    document.new_page(width=200, height=400)
    document.save(source)
    document.close()
    window = MainWindow()
    qtbot.addWidget(window)

    window._load_pdf(source)

    assert window.page_label.text() == "หน้า 1 / 2"
    assert window.preview_page_number.isEnabled()
    assert window._scene.sceneRect().width() == pytest.approx(500)
    assert window._scene.sceneRect().height() == pytest.approx(250)

    window.next_page_button.click()

    assert window._preview_page_index == 1
    assert window.preview_page_number.value() == 2
    assert window.page_label.text() == "หน้า 2 / 2"
    assert window._scene.sceneRect().width() == pytest.approx(250)
    assert window._scene.sceneRect().height() == pytest.approx(500)
    assert not window.next_page_button.isEnabled()


def test_dragging_overlay_uses_current_preview_page_geometry(qtbot, tmp_path) -> None:
    source = tmp_path / "position-page.pdf"
    document = fitz.open()
    document.new_page(width=400, height=200)
    document.new_page(width=200, height=400)
    document.save(source)
    document.close()
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_pdf(source)
    window._append_overlay(OverlayType.TEXT)
    window.next_page_button.click()
    dragged = QGraphicsTextItem("dragged")
    dragged.setPos(115, 240)

    window._preview_item_dropped("overlay-1", dragged)

    assert window._overlays[0]["position_mode"] is PositionMode.ABSOLUTE
    assert window._overlays[0]["x_percent"] == pytest.approx(50, abs=10)
    assert window._overlays[0]["y_percent"] == pytest.approx(50, abs=10)


def test_batch_workspace_groups_controls_and_summary(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    groups = {group.title() for group in window.findChildren(QGroupBox)}
    workspace = window.findChild(QSplitter, "batchSplitter")
    batch_workspace = window.findChild(QTabWidget, "mainWorkspaceTabs")

    assert {"Input — ไฟล์ต้นทาง", "Output — โฟลเดอร์ปลายทาง", "Options — การประมวลผล"}.issubset(groups)
    assert workspace is not None
    assert not workspace.childrenCollapsible()
    assert batch_workspace is not None
    assert batch_workspace.count() == 3
    assert batch_workspace.tabText(0) == "ออกแบบลายน้ำ"
    assert batch_workspace.tabText(2) == "ผลลัพธ์"
    assert window.batch_tabs.count() == 3
    assert window.batch_tabs.tabText(0) == "ไฟล์และปลายทาง"
    assert window.batch_tabs.tabText(1) == "Search / ช่วงหน้า"
    assert window.batch_tabs.tabText(2) == "Processing"
    settings_scrolls = [
        window.findChild(QScrollArea, "fileOutputSettingsScroll"),
        window.findChild(QScrollArea, "searchSettingsScroll"),
        window.findChild(QScrollArea, "processingSettingsScroll"),
    ]
    assert all(scroll is not None for scroll in settings_scrolls)
    assert all(
        scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        for scroll in settings_scrolls
        if scroll is not None
    )
    assert all(
        scroll.widget().minimumHeight() >= scroll.widget().sizeHint().height()
        for scroll in settings_scrolls
        if scroll is not None and scroll.widget() is not None
    )
    assert window.queue_table.minimumHeight() >= 200
    assert window.queue_table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.queue_table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.queue_table.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
    assert window.queue_table.horizontalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
    assert window.batch_input_folder.minimumWidth() >= 280
    assert window.batch_output_folder.minimumWidth() >= 280
    assert window.queue_summary.text() == "ยังไม่มีไฟล์ใน queue"
    assert window.batch_progress.value() == 0
    assert window.batch_progress.format() == "พร้อมเริ่มเมื่อข้อมูลครบ"
    assert window.worker_count.value() >= 1
    assert window.open_output_folder_on_finish.text() == "เปิด Output เมื่อเสร็จ"
    assert window.page_filter_enabled.text() == "วางเฉพาะหน้าที่พบคำนี้"
    assert window.page_filter_ranges.placeholderText() == "ช่วงหน้า เช่น 1-3,5,10-"
    assert window.page_filter_min.minimum() == 0
    assert window.page_filter_min.maximum() == 100
    assert window.page_filter_max.minimum() == 0
    assert window.page_filter_max.maximum() == 100
    assert window.max_depth_slider.value() == window.max_depth.value()
    assert window.worker_count_slider.value() == window.worker_count.value()
    assert window.page_filter_range_slider.lowerValue() == window.page_filter_min.value()
    assert window.page_filter_range_slider.upperValue() == window.page_filter_max.value()
    assert window.queue_table.horizontalHeaderItem(1).text() == "Input File"
    assert window.queue_table.horizontalHeaderItem(2).text() == "Pages/Items"
    assert window.queue_table.horizontalHeaderItem(3).text() == "Output File"
    assert window.queue_table.columnWidth(6) >= 200


def test_settings_scroll_area_prevents_bottom_clipping(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1800, 560)
    window.main_tabs.setCurrentIndex(1)
    window.show()
    qtbot.waitExposed(window)

    settings_scroll = window.findChild(QScrollArea, "fileOutputSettingsScroll")

    assert settings_scroll is not None
    assert settings_scroll.widget() is not None
    assert settings_scroll.widget().minimumHeight() >= settings_scroll.widget().sizeHint().height()
    settings_scroll.resize(settings_scroll.width(), 120)
    qtbot.wait(0)
    assert settings_scroll.verticalScrollBar().maximum() > 0


def test_queue_monitor_tab_shows_file_count(qtbot, tmp_path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.7\n")
    second.write_bytes(b"%PDF-1.7\n")
    window = MainWindow()
    qtbot.addWidget(window)

    window._populate_queue(
        [
            (first, tmp_path / "out" / "first-watermask.pdf"),
            (second, tmp_path / "out" / "second-watermask.pdf"),
        ]
    )

    batch_workspace = window.findChild(QTabWidget, "mainWorkspaceTabs")
    assert batch_workspace is not None
    assert batch_workspace.tabText(1) == "ไฟล์และการประมวลผล (2)"


def test_results_survive_queue_clear_and_retry_only_failed(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    jobs = [(tmp_path / f"{name}.pdf", tmp_path / "out" / f"{name}-watermask.pdf")
            for name in ("good", "bad")]
    window._populate_queue(jobs)
    window._last_export_jobs = jobs
    window._update_queue_file(str(jobs[0][0]), "Completed", 100)
    window._show_file_error(str(jobs[1][0]), "Unreadable PDF")
    window._capture_results("สำเร็จ 1 ล้มเหลว 1")
    window._clear_queue()
    assert window.results_table.rowCount() == 2
    assert window.results_table.item(1, 2).text() == "Unreadable PDF"
    started = []
    monkeypatch.setattr(window, "_start_export", lambda jobs: started.extend(jobs))
    window._retry_failed_results()
    assert started == [jobs[1]]
    assert window.queue_table.rowCount() == 1
    assert window.main_tabs.currentIndex() == 1


def test_preview_file_switch_and_tabs_keep_overlay_settings(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    jobs = []
    for name, pages in (("one", 1), ("two", 2)):
        source = tmp_path / f"{name}.pdf"
        with fitz.open() as document:
            for _ in range(pages):
                document.new_page()
            document.save(source)
        jobs.append((source, tmp_path / "out" / source.name))
    window._populate_queue(jobs)
    window._append_overlay(OverlayType.TEXT)
    window.text_input.setText("Independent text")
    window._select_preview_file(1)
    for index in (1, 2, 0):
        window.main_tabs.setCurrentIndex(index)
    assert window._preview_page_count() == 2
    assert window._source_path == jobs[1][0]
    assert window.text_input.text() == "Independent text"
    window._duplicate_overlay()
    window.text_input.setText("Copy")
    assert window._overlays[0]["text"] == "Independent text"
    assert window._overlays[1]["text"] == "Copy"
    assert window._overlays[0]["id"] != window._overlays[1]["id"]


def test_layout_round_trip_uses_toml(qtbot):
    from mtpdflogo.config.preferences import load_preferences

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.canvas_splitter.setSizes([250, 600, 330])
    state = bytes(window.canvas_splitter.saveState().toHex()).decode("ascii")
    window.close()
    preferences = load_preferences()
    assert preferences.layout["canvas"] == state
    restored = MainWindow()
    qtbot.addWidget(restored)
    assert bytes(restored.canvas_splitter.saveState().toHex()).decode("ascii") == state


def test_numeric_sliders_stay_synced_with_spin_boxes(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.max_depth_slider.setValue(7)
    assert window.max_depth.value() == 7
    window.max_depth.setValue(3)
    assert window.max_depth_slider.value() == 3

    worker_target = min(window.worker_count.maximum(), 4)
    window.worker_count_slider.setValue(worker_target)
    assert window.worker_count.value() == worker_target
    window.worker_count.setValue(1)
    assert window.worker_count_slider.value() == 1

    window.page_filter_enabled.setChecked(True)
    window.page_filter_range_slider.setValues(5, 20)
    assert window.page_filter_min.value() == 5
    assert window.page_filter_max.value() == 20
    window.page_filter_max.setValue(30)
    assert window.page_filter_range_slider.upperValue() == 30


def test_occurrence_range_controls_keep_min_less_than_or_equal_max(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.page_filter_enabled.setChecked(True)

    window.page_filter_max.setValue(10)
    window.page_filter_min.setValue(78)

    assert window.page_filter_max.value() == 78
    assert window.page_filter_range_slider.lowerValue() == 78
    assert window.page_filter_range_slider.upperValue() == 78

    window.page_filter_max.setValue(40)

    assert window.page_filter_min.value() == 40
    assert window.page_filter_range_slider.lowerValue() == 40
    assert window.page_filter_range_slider.upperValue() == 40

    window.page_filter_max.setValue(100)
    window.page_filter_min.setValue(250)

    assert window.page_filter_min.value() == 100
    assert window.page_filter_max.value() == 100
    assert window.page_filter_range_slider.lowerValue() == 100
    assert window.page_filter_range_slider.upperValue() == 100


def test_empty_state_guides_first_time_user(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    scene_text = "\n".join(
        item.toPlainText()
        for item in window._scene.items()
        if isinstance(item, QGraphicsTextItem)
    )

    assert "เลือก PDF/รูปภาพ เพื่อเริ่ม" in scene_text
    assert "+ Text หรือ + Logo" in window.selected_item_label.text()
    assert "ยังไม่มี overlay" in window.overlay_list.toolTip()


def test_layout_tab_supports_absolute_position_controls(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window._append_overlay(OverlayType.TEXT)

    assert window.position_mode.currentData() == PositionMode.PRESET
    assert not window.x_percent.isEnabled()
    assert not window.y_percent.isEnabled()

    window.position_mode.setCurrentIndex(window.position_mode.findData(PositionMode.ABSOLUTE))

    assert window._overlays[0]["position_mode"] is PositionMode.ABSOLUTE
    assert window.x_percent.isEnabled()
    assert window.y_percent.isEnabled()

    window.x_percent.setValue(42.5)
    window.y_percent.setValue(12.25)

    assert window._overlays[0]["x_percent"] == 42.5
    assert window._overlays[0]["y_percent"] == 12.25

    window.reset_to_preset.click()

    assert window._overlays[0]["position_mode"] is PositionMode.PRESET


def test_properties_tab_is_preserved_when_switching_overlay_items(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window._append_overlay(OverlayType.IMAGE, "")
    layout_index = 1
    window.properties_tabs.setCurrentIndex(layout_index)

    window.overlay_list.setCurrentRow(0)

    assert window.properties_tabs.currentIndex() == layout_index


def test_preview_drop_updates_only_dragged_item_to_absolute(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window._append_overlay(OverlayType.IMAGE, "")
    dragged = QGraphicsTextItem("dragged")
    dragged.setPos(90, 190)
    window._scene.setSceneRect(0, 0, 200, 400)
    center_x = dragged.pos().x() + dragged.boundingRect().width() / 2
    center_y = dragged.pos().y() + dragged.boundingRect().height() / 2
    expected_x, expected_y = point_to_percent(
        x=center_x,
        y=center_y,
        page_width=200,
        page_height=400,
    )

    window._preview_item_dropped("overlay-1", dragged)

    assert window._overlays[0]["position_mode"] is PositionMode.ABSOLUTE
    assert window._overlays[0]["x_percent"] == round(expected_x, 2)
    assert window._overlays[0]["y_percent"] == round(expected_y, 2)
    assert window._overlays[1]["position_mode"] is PositionMode.PRESET
    assert window.position_mode.currentData() == PositionMode.ABSOLUTE


def test_clicking_preview_item_without_moving_keeps_preset_position(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    graphic = DraggableTextItem("dragged", "overlay-1", window)
    graphic.setPos(40, 40)

    assert window._overlays[0]["position_mode"] is PositionMode.PRESET

    graphic._press_pos = graphic.pos()
    if (graphic.pos() - graphic._press_pos).manhattanLength() >= 2:
        window._preview_item_dropped("overlay-1", graphic)

    assert window._overlays[0]["position_mode"] is PositionMode.PRESET


def test_save_settings_remembers_last_settings_folder(qtbot, tmp_path, monkeypatch) -> None:
    remembered = tmp_path / "remembered"
    pdf_folder = tmp_path / "pdfs"
    output_folder = tmp_path / "outputs"
    remembered.mkdir()
    pdf_folder.mkdir()
    output_folder.mkdir()
    target = remembered / "team-preset.toml"
    captured: dict[str, str] = {}
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.pdf_folder = pdf_folder
    window._preferences.output_folder = output_folder
    window._preferences.settings_folder = remembered
    window._append_overlay(OverlayType.TEXT)
    window.page_filter_enabled.setChecked(True)
    window.page_filter_keyword.setText("จำนวนเงิน")
    window.page_filter_regex.setChecked(False)
    window.page_filter_min.setValue(2)
    window.page_filter_max.setValue(100)
    window.page_filter_ranges.setText("1-3,5")

    def fake_save_dialog(*args) -> tuple[str, str]:
        captured["initial"] = args[2]
        return str(target), "MTPDFLogo settings (*.toml)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_save_dialog)

    window._save_overlay_settings()

    assert captured["initial"] == str(remembered / "mtpdflogo-settings.toml")
    assert window._preferences.settings_folder == remembered
    assert window._preferences.pdf_folder == pdf_folder
    assert window._preferences.output_folder == output_folder
    assert target.exists()
    assert window.recent_settings.itemText(1) == target.name
    assert window.recent_settings.itemData(1) == str(target.resolve())
    assert load_page_filter_options(target) == {
        "enabled": True,
        "keyword": "จำนวนเงิน",
        "use_regex": False,
        "min_occurrences": 2,
        "max_occurrences": 100,
        "page_ranges": "1-3,5",
    }


def test_load_settings_remembers_last_settings_folder(qtbot, tmp_path, monkeypatch) -> None:
    remembered = tmp_path / "remembered"
    next_folder = tmp_path / "next"
    pdf_folder = tmp_path / "pdfs"
    output_folder = tmp_path / "outputs"
    remembered.mkdir()
    next_folder.mkdir()
    pdf_folder.mkdir()
    output_folder.mkdir()
    source = next_folder / "loaded.toml"
    save_overlay_preset(
        source,
        [
            {
                "id": "text-1",
                "type": OverlayType.TEXT,
                "position_mode": PositionMode.ABSOLUTE,
                "position": Position.MIDDLE_CENTER,
                "x_percent": 25.0,
                "y_percent": 35.0,
                "opacity": 100,
                "rotation": 0,
                "font_size": 32,
                "font": "Mali-Bold",
                "logo_size": 12,
                "text": "loaded",
                "asset_path": "",
                "color": "#000000",
            }
        ],
        {
            "enabled": True,
            "keyword": "amount",
            "use_regex": True,
            "min_occurrences": 1,
            "max_occurrences": 4,
            "page_ranges": "2-",
        },
    )
    captured: dict[str, str] = {}
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.pdf_folder = pdf_folder
    window._preferences.output_folder = output_folder
    window._preferences.settings_folder = remembered

    def fake_open_dialog(*args) -> tuple[str, str]:
        captured["initial"] = args[2]
        return str(source), "MTPDFLogo settings (*.toml)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_open_dialog)

    window._load_overlay_settings()

    assert captured["initial"] == str(remembered)
    assert window._preferences.settings_folder == next_folder
    assert window._preferences.pdf_folder == pdf_folder
    assert window._preferences.output_folder == output_folder
    assert window._overlays[0]["text"] == "loaded"
    assert window.page_filter_enabled.isChecked()
    assert window.page_filter_keyword.text() == "amount"
    assert window.page_filter_regex.isChecked()
    assert window.page_filter_min.value() == 1
    assert window.page_filter_max.value() == 4
    assert window.page_filter_ranges.text() == "2-"
    assert window.statusBar().currentMessage() == "โหลด Settings: loaded.toml (1 รายการ)"


def test_load_settings_warns_when_logo_asset_is_missing(qtbot, tmp_path, monkeypatch) -> None:
    source = tmp_path / "logo-missing.toml"
    missing_logo = tmp_path / "missing-logo.png"
    save_overlay_preset(
        source,
        [
            {
                "id": "logo-1",
                "type": OverlayType.IMAGE,
                "position_mode": PositionMode.PRESET,
                "position": Position.TOP_RIGHT,
                "x_percent": 50.0,
                "y_percent": 50.0,
                "opacity": 100,
                "rotation": 0,
                "font_size": 32,
                "font": "Mali-Bold",
                "logo_size": 12,
                "text": "",
                "asset_path": str(missing_logo),
                "color": "#000000",
            }
        ],
    )
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert window._load_overlay_settings_file(source)

    assert str(missing_logo) in warnings[0]


def test_recent_settings_missing_file_is_removed(qtbot, tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing.toml"
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.recent_settings_files = [missing]
    window._update_recent_settings_control()
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    window._load_recent_overlay_settings(1)

    assert window._preferences.recent_settings_files == []
    assert "missing.toml" in window.statusBar().currentMessage()
    assert str(missing) in warnings[0]


def test_save_and_load_default_settings(qtbot, tmp_path, monkeypatch) -> None:
    target = tmp_path / "default.toml"
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.default_settings_file = None
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), ""))

    window._save_default_overlay_settings()

    assert window._preferences.default_settings_file == target
    assert target.exists()
    window._overlays = []
    assert window._load_overlay_settings_file(target)
    assert window._overlays[0]["text"] == "ข้อความตัวอย่าง"


def test_cancelled_settings_dialog_keeps_preferences(qtbot, tmp_path, monkeypatch) -> None:
    remembered = tmp_path / "remembered"
    pdf_folder = tmp_path / "pdfs"
    output_folder = tmp_path / "outputs"
    remembered.mkdir()
    pdf_folder.mkdir()
    output_folder.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.pdf_folder = pdf_folder
    window._preferences.output_folder = output_folder
    window._preferences.settings_folder = remembered
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))

    window._save_overlay_settings()
    window._load_overlay_settings()

    assert window._preferences.settings_folder == remembered
    assert window._preferences.pdf_folder == pdf_folder
    assert window._preferences.output_folder == output_folder


def test_invalid_loaded_settings_keeps_settings_folder(qtbot, tmp_path, monkeypatch) -> None:
    remembered = tmp_path / "remembered"
    remembered.mkdir()
    bad_file = tmp_path / "bad.toml"
    bad_file.write_text("not valid toml = [", encoding="utf-8")
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.settings_folder = remembered
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(bad_file), ""))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    window._load_overlay_settings()

    assert window._preferences.settings_folder == remembered


def test_missing_settings_folder_falls_back_to_home(qtbot, tmp_path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._preferences.settings_folder = tmp_path / "missing"

    assert window._settings_initial_folder() == Path.home()


def test_pasted_output_folder_updates_queue_and_start_button(qtbot, tmp_path) -> None:
    source = tmp_path / "input.pdf"
    output = tmp_path / "out"
    source.touch()
    output.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window._populate_queue([(source, Path())])

    assert not window.start_batch_action.isEnabled()
    assert "ยังไม่มีไฟล์ใน queue" in window.start_batch_action.toolTip()

    window.batch_output_folder.setText(str(output))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)

    assert window.start_batch_action.isEnabled()
    assert window.start_batch_action.toolTip() == "พร้อมเริ่ม Batch"
    assert window.queue_table.item(0, 3).text() == str(output / "input-watermask.pdf")
    assert "1 ไฟล์ใน queue" in window.queue_summary.text()
    assert f"Workers: {window.worker_count.value()}" in window.queue_summary.text()
    assert "พร้อมเริ่ม" in window.queue_summary.text()

    window.worker_count.setValue(min(window.worker_count.maximum(), 3))

    assert f"Workers: {window.worker_count.value()}" in window.queue_summary.text()


def test_batch_overall_progress_updates_from_worker_signal(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window._update_batch_progress(42, "input.pdf")

    assert window.batch_progress.value() == 42
    assert window.batch_progress.format() == "42% — input.pdf"
    assert "42% — input.pdf" in window.statusBar().currentMessage()


def test_busy_guard_blocks_reentry_even_when_stop_button_is_disabled(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    jobs = [(tmp_path / "a.pdf", tmp_path / "out.pdf")]
    window._populate_queue(jobs)
    window._append_overlay(OverlayType.TEXT)
    window._thread = object()  # Final signal received; thread cleanup still pending.
    window.cancel_action.setEnabled(False)
    try:
        window._refresh_batch_readiness()
        assert not window.start_batch_action.isEnabled()
        assert not window.batch_tabs.isEnabled()
        assert not window._start_export(jobs)
        window._populate_queue([])
        assert window.queue_table.rowCount() == 1
    finally:
        window._export_thread_finished()
    assert window.start_batch_action.isEnabled()
    assert window.batch_tabs.isEnabled()
    assert window._overlays
    assert not window._start_export([])


def test_grid_progress_paints_real_numeric_data(qtbot, tmp_path):
    from mtpdflogo.presentation.progress_delegate import ProgressDelegate

    window = MainWindow()
    qtbot.addWidget(window)
    source = tmp_path / "a.pdf"
    window._populate_queue([(source, tmp_path / "out.pdf")])
    assert isinstance(window.queue_table.itemDelegateForColumn(4), ProgressDelegate)
    window._update_queue_progress(str(source), 3, 8)
    progress = window.queue_table.item(0, 4)
    assert progress.text() == "37% (3/8)"
    assert progress.data(Qt.ItemDataRole.UserRole) == 37
    assert window.queue_table.cellWidget(0, 4) is None
    window.main_tabs.setCurrentIndex(1)
    window.show()
    qtbot.waitExposed(window)
    window.queue_table.scrollTo(window.queue_table.model().index(0, 4))
    qtbot.wait(0)
    assert not window.queue_table.grab().isNull()  # Exercise native delegate painting.
    window._update_queue_file(str(source), "Completed", 100)
    assert progress.data(Qt.ItemDataRole.UserRole) == 100
    window._update_queue_progress(str(source), 0, 0)
    assert progress.data(Qt.ItemDataRole.UserRole) == 0


def test_two_real_export_rounds_restore_controls_without_clearing(qtbot, tmp_path, monkeypatch):
    source = tmp_path / "input.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(source)
    output = tmp_path / "output"
    output.mkdir()
    destination = output / "input-watermask.pdf"
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window._append_overlay(OverlayType.TEXT)
    window.batch_output_folder.setText(str(output))
    window.worker_count.setValue(1)
    window.overwrite_outputs.setChecked(True)
    window.open_output_folder_on_finish.setChecked(False)
    jobs = [(source, destination)]
    window._populate_queue(jobs)
    for text in ("first run", "second run"):
        window.text_input.setText(text)
        assert window._start_export(jobs)
        assert not window.start_batch_action.isEnabled()
        qtbot.waitUntil(lambda: not window._export_busy(), timeout=30000)
        assert window.start_batch_action.isEnabled()
        assert window.batch_tabs.isEnabled()
        assert not window.cancel_action.isEnabled()
        assert window.queue_table.item(0, 5).text() == "Completed"
        assert window.queue_table.item(0, 4).data(Qt.ItemDataRole.UserRole) == 100
        assert window.text_input.text() == text
        with fitz.open(destination) as pdf:
            assert pdf.page_count == 1


def test_destination_uses_configured_output_suffix(qtbot, tmp_path) -> None:
    source = tmp_path / "input.pdf"
    output = tmp_path / "out"
    output.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)

    window._config = type(
        "Config",
        (),
        {"output_suffix": "-signed", "preserve_subfolders": True},
    )()

    assert window._destination_for(source, output)[1] == output / "input-signed.pdf"


def test_start_batch_requires_effective_overlay(qtbot, tmp_path) -> None:
    source = tmp_path / "input.pdf"
    output = tmp_path / "out"
    source.touch()
    output.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window._populate_queue([(source, Path())])

    window.batch_output_folder.setText(str(output))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)

    assert not window.start_batch_action.isEnabled()


def test_manual_open_output_folder_button(qtbot, tmp_path, monkeypatch) -> None:
    output = tmp_path / "out"
    output.mkdir()
    opened: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "mtpdflogo.presentation.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )

    window.batch_output_folder.setText(str(output))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)
    window.open_output_folder_button.click()

    assert window.open_output_folder_button.isEnabled()
    assert [Path(path) for path in opened] == [output]


def test_manual_open_output_folder_rejects_missing_path(qtbot, tmp_path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.batch_output_folder.setText(str(tmp_path / "missing"))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)

    assert not window.open_output_folder_button.isEnabled()


def test_export_preflight_blocks_missing_logo_asset(qtbot, tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    missing_logo = tmp_path / "missing-logo.png"
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.IMAGE, str(missing_logo))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert not window._start_export([(source, destination)])
    assert str(missing_logo) in warnings[0]


def test_export_preflight_blocks_blank_logo_asset(qtbot, tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.IMAGE, "")
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert not window._start_export([(source, destination)])
    assert "ยังไม่ได้เลือกไฟล์ Logo" in warnings[0]


def test_export_preflight_blocks_existing_output_without_overwrite(
    qtbot, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input.pdf"
    output = tmp_path / "out"
    destination = output / "input-watermask.pdf"
    source.touch()
    output.mkdir()
    destination.touch()
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window.batch_output_folder.setText(str(output))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert not window._start_export([(source, destination)])
    assert str(destination) in warnings[0]


def test_output_folder_inside_input_is_blocked(qtbot, tmp_path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    output = input_root / "out"
    source = input_root / "input.pdf"
    destination = output / "input-watermask.pdf"
    output.mkdir(parents=True)
    source.touch()
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._input_root = input_root
    window._append_overlay(OverlayType.TEXT)
    window.batch_output_folder.setText(str(output))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert not window._start_export([(source, destination)])
    assert "Output Folder ต้องไม่อยู่ภายใน Input Folder" in warnings[0]


def test_output_conflict_is_ignored_when_overwrite_is_checked(qtbot, tmp_path) -> None:
    source = tmp_path / "input.pdf"
    output = tmp_path / "out"
    destination = output / "input-watermask.pdf"
    source.touch()
    output.mkdir()
    destination.touch()
    window = MainWindow()
    qtbot.addWidget(window)
    window.overwrite_outputs.setChecked(True)

    assert output_conflict_issues(
        [(source, destination)],
        output / ".mtpdflogo-batch-status.json",
        "fingerprint",
        overwrite=window.overwrite_outputs.isChecked(),
        resume_enabled=window._config.resume_enabled,
    ) == []


def test_page_filter_requires_keyword_before_export(qtbot, tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    warnings: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window.page_filter_enabled.setChecked(True)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    assert not window._start_export([(source, destination)])
    assert "ใส่คำ/regex หรือช่วงหน้า" in warnings[0]


def test_page_filter_builds_text_rule(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._page_text_rule() is None

    window.page_filter_enabled.setChecked(True)
    window.page_filter_keyword.setText("จำนวนเงิน")
    window.page_filter_regex.setChecked(True)
    window.page_filter_min.setValue(1)
    window.page_filter_max.setValue(10)
    window.page_filter_ranges.setText("2-5")

    rule = window._page_text_rule()

    assert rule is not None
    assert rule.keyword == "จำนวนเงิน"
    assert rule.min_occurrences == 1
    assert rule.max_occurrences == 10
    assert rule.use_regex
    assert rule.page_ranges == "2-5"


def test_page_filter_rejects_invalid_regex(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.page_filter_enabled.setChecked(True)
    window.page_filter_regex.setChecked(True)
    window.page_filter_keyword.setText("[")

    assert window._page_filter_error() is not None
    assert "Regex ไม่ถูกต้อง" in window.pipeline_summary.text()


def test_page_filter_rejects_high_risk_regex(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.page_filter_enabled.setChecked(True)
    window.page_filter_regex.setChecked(True)
    window.page_filter_keyword.setText("(a+)+$")

    assert window._page_filter_error() is not None
    assert "Regex เสี่ยง" in window.pipeline_summary.text()


def test_page_filter_allows_page_ranges_without_keyword(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.page_filter_enabled.setChecked(True)
    window.page_filter_ranges.setText("2-")

    assert window._page_filter_error() is None
    rule = window._page_text_rule()
    assert rule is not None
    assert rule.keyword == ""
    assert rule.page_ranges == "2-"


def test_page_filter_test_button_reports_matching_pages(qtbot, tmp_path) -> None:
    source = tmp_path / "search-preview.pdf"
    document = fitz.open()
    first = document.new_page(width=300, height=180)
    first.insert_text((36, 72), "invoice amount 100")
    second = document.new_page(width=300, height=180)
    second.insert_text((36, 72), "no match")
    third = document.new_page(width=300, height=180)
    third.insert_text((36, 72), "amount amount")
    document.save(source)
    document.close()
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_pdf(source)
    window.page_filter_enabled.setChecked(True)
    window.page_filter_keyword.setText("amount")
    window.page_filter_min.setValue(1)
    window.page_filter_max.setValue(0)

    window._test_page_filter_on_current_file()

    assert "พบ 2/3 หน้า" in window.page_filter_result.text()
    assert "หน้า 1, 3" in window.page_filter_result.text()


def test_page_filter_queue_button_reports_batch_search_summary(qtbot, tmp_path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    image = tmp_path / "scan.png"
    for path, texts in (
        (first, ["invoice amount 100", "amount amount"]),
        (second, ["no match", "still no match"]),
    ):
        document = fitz.open()
        for text in texts:
            page = document.new_page(width=300, height=180)
            page.insert_text((36, 72), text)
        document.save(path)
        document.close()
    image.write_bytes(b"fake")
    window = MainWindow()
    qtbot.addWidget(window)
    window._populate_queue(
        [
            (first, tmp_path / "out" / "first-watermask.pdf"),
            (image, tmp_path / "out" / "scan-watermask.png"),
            (second, tmp_path / "out" / "second-watermask.pdf"),
        ]
    )
    window.page_filter_enabled.setChecked(True)
    window.page_filter_keyword.setText("amount")
    window.page_filter_min.setValue(1)
    window.page_filter_max.setValue(0)

    window._test_page_filter_on_queue()

    summary = window.page_filter_result.text()
    assert "ทั้ง Queue พบ 1/2 PDF" in summary
    assert "2/4 หน้า" in summary
    assert "รวม 3 ครั้ง" in summary
    assert "ข้ามรูปภาพ/ไฟล์ที่ไม่ใช่ PDF 1 ไฟล์" in summary


def test_page_filter_queue_button_supports_page_ranges_without_keyword(qtbot, tmp_path) -> None:
    source = tmp_path / "pages.pdf"
    document = fitz.open()
    for text in ["cover", "body", "appendix"]:
        page = document.new_page(width=300, height=180)
        page.insert_text((36, 72), text)
    document.save(source)
    document.close()
    window = MainWindow()
    qtbot.addWidget(window)
    window._populate_queue([(source, tmp_path / "out" / "pages-watermask.pdf")])
    window.page_filter_enabled.setChecked(True)
    window.page_filter_ranges.setText("2-")

    window._test_page_filter_on_queue()

    assert "ทั้ง Queue พบ 1/1 PDF" in window.page_filter_result.text()
    assert "2/3 หน้า" in window.page_filter_result.text()


def test_selected_queue_error_dialog_uses_copyable_details(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "bad.pdf"
    destination = tmp_path / "out" / "bad-watermask.pdf"
    source.touch()
    captured: dict[str, str] = {}
    window = MainWindow()
    qtbot.addWidget(window)
    window._populate_queue([(source, destination)])
    window.queue_table.setCurrentCell(0, 1)
    window._show_file_error(str(source), "permission denied")

    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda self: captured.update(
            {
                "title": self.windowTitle(),
                "text": self.text(),
                "details": self.detailedText(),
            }
        ),
    )

    window._show_selected_queue_error()

    assert captured["title"] == "รายละเอียด Error"
    assert "bad.pdf" in captured["text"]
    assert captured["details"] == "permission denied"


def test_batch_controls_are_ready_after_export_finished_without_clearing(
    qtbot, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window._populate_queue([(source, destination)])
    window._pending_batch_jobs = [(source, destination)]
    window._last_export_jobs = [(source, destination)]
    window.start_batch_action.setEnabled(False)
    window.cancel_action.setEnabled(True)

    window._export_finished("done")

    assert not window.cancel_action.isEnabled()
    assert window.start_batch_action.isEnabled()
    assert window._pending_batch_jobs == [(source, destination)]
    assert "พร้อมเริ่ม" in window.queue_summary.text()


def test_export_finished_keeps_editable_source_preview(qtbot, tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    destination.touch()
    loaded: list[tuple[Path, bool]] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        window,
        "_load_source",
        lambda path, preview_overlays=True: loaded.append((path, preview_overlays)),
    )
    window._source_path = source
    window._last_export_jobs = [(source, destination)]

    window._export_finished("สำเร็จ 1 ไฟล์, ล้มเหลว 0 ไฟล์ | Workers: 1")

    assert loaded == []
    assert window._preview_bakes_overlays


def test_open_output_checkbox_updates_preferences(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    saved: list[bool] = []
    monkeypatch.setattr(
        "mtpdflogo.presentation.main_window.save_preferences",
        lambda preferences: saved.append(preferences.open_output_folder_on_finish),
    )

    window.open_output_folder_on_finish.setChecked(False)
    window.open_output_folder_on_finish.setChecked(True)

    assert window._preferences.open_output_folder_on_finish is True
    assert saved[-1:] == [True]


def test_successful_export_opens_output_folder_when_requested(
    qtbot, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    opened: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "mtpdflogo.presentation.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    window._populate_queue([(source, destination)])
    window._last_export_jobs = [(source, destination)]
    window.open_output_folder_on_finish.setChecked(True)

    window._export_finished("สำเร็จ 1 ไฟล์, ล้มเหลว 0 ไฟล์ | Workers: 1")

    assert [Path(path) for path in opened] == [destination.parent]


def test_output_folder_is_not_opened_when_unchecked_cancelled_or_partial_failure(
    qtbot, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    opened: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "mtpdflogo.presentation.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    window._populate_queue([(source, destination)])
    window._last_export_jobs = [(source, destination)]

    window.open_output_folder_on_finish.setChecked(False)
    window._export_finished("สำเร็จ 1 ไฟล์, ล้มเหลว 0 ไฟล์ | Workers: 1")
    window.open_output_folder_on_finish.setChecked(True)
    window._export_finished("ยกเลิกแล้ว: สำเร็จ 0 ไฟล์ | Workers: 1")
    window._export_finished("สำเร็จ 0 ไฟล์, ล้มเหลว 1 ไฟล์ | Workers: 1")

    assert opened == []


def test_cancel_button_marks_active_rows_and_restores_ready_state(
    qtbot, tmp_path, monkeypatch
) -> None:
    class FakeWorker:
        def __init__(self) -> None:
            self.cancel_called = False

        def cancel(self) -> None:
            self.cancel_called = True

    completed_source = tmp_path / "completed.pdf"
    pending_source = tmp_path / "pending.pdf"
    completed_destination = tmp_path / "out" / "completed-watermask.pdf"
    pending_destination = tmp_path / "out" / "pending-watermask.pdf"
    completed_source.touch()
    pending_source.touch()
    completed_destination.parent.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window._populate_queue([
        (completed_source, completed_destination),
        (pending_source, pending_destination),
    ])
    window.queue_table.item(0, 5).setText("Completed")
    window.queue_table.item(1, 5).setText("Processing")
    worker = FakeWorker()
    window._worker = worker
    window.cancel_action.setEnabled(True)
    window.start_batch_action.setEnabled(False)

    window._cancel_export()

    assert worker.cancel_called
    assert window.queue_table.item(0, 5).text() == "Completed"
    assert window.queue_table.item(1, 5).text() == "Stopping"

    window._export_finished("ยกเลิกแล้ว: สำเร็จ 1 ไฟล์ | Workers: 1")

    assert window.queue_table.item(0, 5).text() == "Completed"
    assert window.queue_table.item(1, 5).text() == "Cancelled"
    assert not window.cancel_action.isEnabled()
    assert not window.start_batch_action.isEnabled()
    window._export_thread_finished()
    assert window.start_batch_action.isEnabled()


def test_close_during_export_requests_cancel_and_ignores_event(
    qtbot, monkeypatch
) -> None:
    class FakeWorker:
        def __init__(self) -> None:
            self.cancel_called = False

        def cancel(self) -> None:
            self.cancel_called = True

    class FakeEvent:
        def __init__(self) -> None:
            self.ignored = False
            self.accepted = False

        def ignore(self) -> None:
            self.ignored = True

        def accept(self) -> None:
            self.accepted = True

    window = MainWindow()
    qtbot.addWidget(window)
    worker = FakeWorker()
    event = FakeEvent()
    window._worker = worker
    window.cancel_action.setEnabled(True)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.closeEvent(event)

    assert worker.cancel_called
    assert event.ignored
    assert not event.accepted
    window._export_thread_finished()


def test_properties_controls_match_selected_text_and_logo_items(qtbot, tmp_path) -> None:
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"not loaded in this test")
    window = MainWindow()
    qtbot.addWidget(window)

    window._append_overlay(OverlayType.TEXT)
    text_item = window._overlays[0]
    text_item.update(
        text="Approved",
        position=Position.BOTTOM_CENTER,
        font="Font-Not-In-Combo",
        font_size=48,
        opacity=64,
        rotation=12,
        color="#112233",
    )
    window._append_overlay(OverlayType.IMAGE, str(logo))
    logo_item = window._overlays[1]
    logo_item.update(position=Position.TOP_RIGHT, logo_size=33, opacity=71, rotation=-15)

    window.overlay_list.setCurrentRow(0)

    assert window.type_value.text() == "Text"
    assert window.text_input.text() == "Approved"
    assert window.position.currentData() == Position.BOTTOM_CENTER
    assert window.font.currentText() == "Font-Not-In-Combo"
    assert window.font_size.value() == 48
    assert window.opacity.value() == 64
    assert window.opacity_label.text() == "64%"
    assert window.rotation.value() == 12
    assert window.color_button.text() == "#112233"
    assert window.text_input.isEnabled()
    assert window.font.isEnabled()
    assert not window.logo_button.isEnabled()
    assert not window.logo_size.isEnabled()

    window.overlay_list.setCurrentRow(1)

    assert window.type_value.text() == "Logo"
    assert window.logo_value.text() == str(logo)
    assert window.position.currentData() == Position.TOP_RIGHT
    assert window.logo_size.value() == 33
    assert window.opacity.value() == 71
    assert window.opacity_label.text() == "71%"
    assert window.rotation.value() == -15
    assert not window.text_input.isEnabled()
    assert not window.font.isEnabled()
    assert window.logo_button.isEnabled()
    assert window.logo_size.isEnabled()

    window.position.setCurrentIndex(window.position.findData(Position.BOTTOM_LEFT))
    assert logo_item["position"] is Position.BOTTOM_LEFT


def test_invalid_pasted_output_folder_keeps_start_button_disabled(qtbot, tmp_path) -> None:
    source = tmp_path / "input.pdf"
    source.touch()
    window = MainWindow()
    qtbot.addWidget(window)
    window._populate_queue([(source, Path())])

    window.batch_output_folder.setText(str(tmp_path / "missing"))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)

    assert not window.start_batch_action.isEnabled()
    assert window.pipeline_summary.text() == "Output Folder ไม่ถูกต้อง"


def test_editing_selected_text_does_not_mutate_logo_item(qtbot, tmp_path) -> None:
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"not loaded in this test")
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window._append_overlay(OverlayType.IMAGE, str(logo))
    logo_before = dict(window._overlays[1])

    window.overlay_list.setCurrentRow(0)
    window.text_input.setText("Text only")
    window.font_size.setValue(72)
    window.opacity.setValue(40)
    window.rotation.setValue(30)
    window.position.setCurrentIndex(window.position.findData(Position.TOP_LEFT))

    assert window._overlays[0]["text"] == "Text only"
    assert window._overlays[0]["font_size"] == 72
    assert window._overlays[0]["opacity"] == 40
    assert window._overlays[0]["rotation"] == 30
    assert window._overlays[0]["position"] is Position.TOP_LEFT
    assert window._overlays[1] == logo_before


def test_input_folder_load_preserves_source_structure(qtbot, tmp_path) -> None:
    input_root = tmp_path / "input"
    customer = input_root / "customer"
    output = tmp_path / "output"
    customer.mkdir(parents=True)
    output.mkdir()
    Image.new("RGB", (10, 10), "white").save(input_root / "root.png")
    Image.new("RGB", (10, 10), "white").save(customer / "nested.png")
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)

    window.batch_input_folder.setText(str(input_root))
    window.batch_output_folder.setText(str(output))
    window.recursive_input.setChecked(True)
    window.max_depth.setValue(1)
    window.preserve_structure.setChecked(True)
    window._load_input_folder_files()

    outputs = {
        window.queue_table.item(row, 3).text()
        for row in range(window.queue_table.rowCount())
    }

    assert window.queue_table.rowCount() == 2
    assert str(output / "root-watermask.png") in outputs
    assert str(output / "customer" / "nested-watermask.png") in outputs
    assert window.start_batch_action.isEnabled()
