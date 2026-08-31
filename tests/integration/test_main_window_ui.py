from pathlib import Path

from mtpdflogo.config.overlay_preset import save_overlay_preset
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.presentation.main_window import MainWindow
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsTextItem,
    QGroupBox,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolBar,
)


def test_main_window_has_single_pdf_picker_and_pipeline(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    toolbar = window.findChild(QToolBar, "mainToolbar")
    action_labels = [action.text() for action in toolbar.actions()]

    assert action_labels.count("เลือก File(s)") == 1
    assert action_labels.count("เลือก Folder") == 1
    assert "เพิ่ม Text+Logo" in action_labels
    assert "เลือก PDF File(s)" not in action_labels
    assert "Batch PDF (หลายไฟล์)" not in action_labels
    assert [label.text() for label in window.pipeline_labels] == [
        "1  เลือกไฟล์/โฟลเดอร์",
        "2  ตั้ง Text/Logo",
        "3  ตั้ง Output",
        "4  Start Batch",
        "5  ตรวจ Output",
    ]
    assert window.pipeline_summary.text() == "รอเลือกไฟล์"


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


def test_batch_workspace_groups_controls_and_summary(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    groups = {group.title() for group in window.findChildren(QGroupBox)}
    workspace = window.findChild(QSplitter, "workspaceSplitter")

    assert {"Input", "Output", "Options"}.issubset(groups)
    assert workspace is not None
    assert not workspace.childrenCollapsible()
    assert window.queue_table.minimumHeight() >= 170
    assert window.queue_summary.text() == "ยังไม่มีไฟล์ใน queue"
    assert window.worker_count.value() >= 1
    assert window.queue_table.horizontalHeaderItem(1).text() == "Input File"
    assert window.queue_table.horizontalHeaderItem(2).text() == "Pages/Items"
    assert window.queue_table.horizontalHeaderItem(3).text() == "Output File"


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


def test_preview_drop_updates_only_dragged_item_to_absolute(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._append_overlay(OverlayType.TEXT)
    window._append_overlay(OverlayType.IMAGE, "")
    dragged = QGraphicsTextItem("dragged")
    dragged.setPos(90, 190)
    window._scene.setSceneRect(0, 0, 200, 400)

    window._preview_item_dropped("overlay-1", dragged)

    assert window._overlays[0]["position_mode"] is PositionMode.ABSOLUTE
    assert 40 <= window._overlays[0]["x_percent"] <= 60
    assert 45 <= window._overlays[0]["y_percent"] <= 55
    assert window._overlays[1]["position_mode"] is PositionMode.PRESET
    assert window.position_mode.currentData() == PositionMode.ABSOLUTE


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
    window._populate_queue([(source, Path())])

    window.batch_output_folder.setText(str(output))
    qtbot.keyClick(window.batch_output_folder, Qt.Key.Key_Enter)

    assert window.start_batch_action.isEnabled()
    assert window.queue_table.item(0, 3).text() == str(output / "input-watermask.pdf")
    assert "1 ไฟล์ใน queue" in window.queue_summary.text()
    assert f"Workers: {window.worker_count.value()}" in window.queue_summary.text()
    assert "พร้อมเริ่ม" in window.queue_summary.text()

    window.worker_count.setValue(min(window.worker_count.maximum(), 3))

    assert f"Workers: {window.worker_count.value()}" in window.queue_summary.text()


def test_batch_controls_are_ready_after_export_finished_without_clearing(
    qtbot, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.touch()
    destination.parent.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
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
    assert window.start_batch_action.isEnabled()


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
