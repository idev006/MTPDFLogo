"""Usable PDF overlay workspace and batch export UI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import fitz
from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from mtpdflogo.application.batch import (
    SUPPORTED_IMAGE_SUFFIXES,
    SUPPORTED_INPUT_SUFFIXES,
    build_jobs,
    discover_supported_files,
    output_is_inside_input,
)
from mtpdflogo.application.export_policy import (
    evaluate_batch_readiness,
    preflight_batch_export,
)
from mtpdflogo.application.overlay_mapper import (
    has_effective_overlay,
    missing_logo_paths,
    overlays_to_specs,
    page_filter_error,
    page_text_rule_from_options,
)
from mtpdflogo.application.page_search import search_pdf_batch, search_pdf_pages
from mtpdflogo.application.positioning import point_to_percent, resolve_overlay_top_left
from mtpdflogo.application.queue_state import blocked_start_message, queue_summary_text
from mtpdflogo.config import (
    font_directory,
    load_config,
    load_overlay_preset,
    load_page_filter_options,
    load_preferences,
    save_overlay_preset,
    save_preferences,
)
from mtpdflogo.domain.models import OverlayType, Position, PositionMode
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec
from mtpdflogo.presentation.qt_export_worker import ExportWorker


class DraggableTextItem(QGraphicsTextItem):
    """Preview text item that reports its final dropped position."""

    def __init__(self, text: str, overlay_id: str, owner: MainWindow) -> None:
        super().__init__(text)
        self.overlay_id = overlay_id
        self.owner = owner
        self._press_pos = self.pos()
        self._configure_drag_flags()

    def _configure_drag_flags(self) -> None:
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: Any) -> None:
        self._press_pos = self.pos()
        self.owner._select_overlay_by_id(self.overlay_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        super().mouseReleaseEvent(event)
        if (self.pos() - self._press_pos).manhattanLength() >= 2:
            self.owner._preview_item_dropped(self.overlay_id, self)


class DraggablePixmapItem(QGraphicsPixmapItem):
    """Preview logo item that reports its final dropped position."""

    def __init__(self, pixmap: QPixmap, overlay_id: str, owner: MainWindow) -> None:
        super().__init__(pixmap)
        self.overlay_id = overlay_id
        self.owner = owner
        self._press_pos = self.pos()
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: Any) -> None:
        self._press_pos = self.pos()
        self.owner._select_overlay_by_id(self.overlay_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        super().mouseReleaseEvent(event)
        if (self.pos() - self._press_pos).manhattanLength() >= 2:
            self.owner._preview_item_dropped(self.overlay_id, self)


class PreviewGraphicsView(QGraphicsView):
    """Preview view with Ctrl+wheel zoom while keeping normal scroll behavior."""

    def __init__(self, scene: QGraphicsScene, owner: MainWindow) -> None:
        super().__init__(scene)
        self.owner = owner

    def wheelEvent(self, event: Any) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.owner._zoom_preview_in()
            else:
                self.owner._zoom_preview_out()
            event.accept()
            return
        super().wheelEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._document: fitz.Document | None = None
        self._config = load_config()
        self._preferences = load_preferences()
        self._preview_font_families: dict[str, str] = {}
        self._source_path: Path | None = None
        self._pdf_path: Path | None = None
        self._image_path: Path | None = None
        self._input_root: Path | None = None
        self._scene = QGraphicsScene(self)
        self._overlays: list[dict[str, Any]] = []
        self._pending_batch_jobs: list[tuple[Path, Path]] = []
        self._last_export_jobs: list[tuple[Path, Path]] = []
        self._batch_readiness_reason = "missing_jobs"
        self._preview_bakes_overlays = True
        self._preview_zoom = 1.0
        self._preview_page_index = 0
        self._updating_properties = False
        self._thread: QThread | None = None
        self._worker: ExportWorker | None = None
        self.setWindowTitle("MTPDFLogo — PDF Overlay Studio")
        self.resize(1500, 900)
        self._build_ui()
        shortcut = QShortcut(QKeySequence("Delete"), self)
        shortcut.activated.connect(self._delete_selected)
        self._refresh_preview()
        self._update_pipeline()

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main toolbar", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        action = toolbar.addAction("เลือกไฟล์")
        action.setToolTip("เลือก PDF/รูปภาพ หนึ่งไฟล์หรือหลายไฟล์")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        action.triggered.connect(self._select_input_files)
        action = toolbar.addAction("เลือกโฟลเดอร์ต้นทาง")
        action.setToolTip("โหลด PDF/รูปภาพ จากโฟลเดอร์ต้นทาง")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        action.triggered.connect(self._choose_batch_input_folder)
        action = toolbar.addAction("เพิ่ม Text")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        action.triggered.connect(lambda: self._add_overlay(OverlayType.TEXT))
        action = toolbar.addAction("เพิ่ม Logo")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        action.triggered.connect(lambda: self._add_overlay(OverlayType.IMAGE))
        action = toolbar.addAction("เพิ่ม Text+Logo")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        action.triggered.connect(self._add_text_and_logo)
        toolbar.addSeparator()
        action = toolbar.addAction("บันทึก Settings")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        action.triggered.connect(self._save_overlay_settings)
        action = toolbar.addAction("โหลด Settings")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        action.triggered.connect(self._load_overlay_settings)
        action = toolbar.addAction("บันทึก Default")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        action.triggered.connect(self._save_default_overlay_settings)
        action = toolbar.addAction("โหลด Default")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        action.triggered.connect(self._load_default_overlay_settings)
        self.recent_settings = QComboBox()
        self.recent_settings.setMinimumWidth(180)
        self.recent_settings.activated.connect(self._load_recent_overlay_settings)
        toolbar.addWidget(self.recent_settings)
        self._update_recent_settings_control()
        toolbar.addSeparator()
        action = toolbar.addAction("Export ไฟล์ปัจจุบัน")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        action.triggered.connect(self._export_single)
        self.start_batch_action = toolbar.addAction("▶ เริ่ม Batch")
        self.start_batch_action.setEnabled(False)
        self.start_batch_action.setToolTip("เริ่มไม่ได้: ยังไม่มีไฟล์ใน queue")
        self.start_batch_action.setStatusTip("เริ่มไม่ได้: ยังไม่มีไฟล์ใน queue")
        self.start_batch_action.triggered.connect(self._start_pending_batch)
        self.cancel_action = toolbar.addAction("หยุด Batch")
        self.cancel_action.setToolTip("หยุดรับงานใหม่ และรอไฟล์ที่กำลังทำอยู่จบอย่างปลอดภัย")
        self.cancel_action.setEnabled(False)
        self.cancel_action.triggered.connect(self._cancel_export)
        toolbar.addSeparator()
        action = toolbar.addAction("About Dev")
        action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        action.triggered.connect(self._show_about_dev)

        root = QSplitter(Qt.Orientation.Horizontal)
        root.setChildrenCollapsible(False)
        root.addWidget(self._build_overlay_panel())
        root.addWidget(self._build_preview_panel())
        root.addWidget(self._build_properties_panel())
        root.setSizes([290, 850, 360])
        workspace = QSplitter(Qt.Orientation.Vertical)
        workspace.setObjectName("workspaceSplitter")
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(root)
        workspace.addWidget(self._build_queue_panel())
        workspace.setStretchFactor(0, 4)
        workspace.setStretchFactor(1, 3)
        workspace.setSizes([620, 330])
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(10, 8, 10, 10)
        central_layout.setSpacing(8)
        central_layout.addWidget(self._build_pipeline_panel())
        central_layout.addWidget(workspace, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("พร้อมใช้งาน — เลือก PDF/Image File(s) เพื่อเริ่ม")

    def _build_pipeline_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("pipelinePanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        self.pipeline_labels: list[QLabel] = []
        steps = [
            ("1", "เลือกไฟล์/โฟลเดอร์"),
            ("2", "ตั้ง Text/Logo"),
            ("3", "ตั้ง Output"),
            ("4", "เริ่ม Batch"),
            ("5", "ตรวจ Output"),
        ]
        for number, text in steps:
            label = QLabel(f"{number}  {text}")
            label.setObjectName("pipelineStep")
            layout.addWidget(label)
            self.pipeline_labels.append(label)
        layout.addStretch()
        self.pipeline_summary = QLabel("รอเลือกไฟล์")
        self.pipeline_summary.setObjectName("pipelineSummary")
        layout.addWidget(self.pipeline_summary)
        return panel

    def _update_pipeline(self, summary: str | None = None) -> None:
        if not hasattr(self, "pipeline_labels"):
            return
        has_pdf = self.queue_table.rowCount() > 0 or self._source_path is not None
        has_overlay = bool(self._overlays)
        has_output = bool(self.batch_output_folder.text().strip())
        is_running = self.cancel_action.isEnabled()
        has_output_preview = self._source_path is not None and not self._preview_bakes_overlays
        done_states = [
            has_pdf,
            has_overlay,
            has_output,
            is_running or has_output_preview,
            has_output_preview,
        ]
        if is_running:
            active_index = 3
        elif has_output_preview:
            active_index = 4
        elif not has_pdf:
            active_index = 0
        elif not has_overlay:
            active_index = 1
        elif not has_output:
            active_index = 2
        else:
            active_index = 3
        for index, label in enumerate(self.pipeline_labels):
            is_active = index == active_index
            font = label.font()
            font.setBold(is_active)
            label.setFont(font)
            label.setEnabled(is_active or done_states[index])
            if done_states[index] and not is_active:
                label.setToolTip("ขั้นตอนนี้พร้อมแล้ว")
            elif is_active:
                label.setToolTip("ขั้นตอนปัจจุบัน")
            else:
                label.setToolTip("ยังรอข้อมูลก่อนหน้า")
        if summary is None:
            if is_running:
                summary = "กำลังประมวลผล"
            elif has_output_preview:
                summary = "เสร็จแล้ว พร้อมตรวจ Output"
            elif has_pdf and has_overlay and has_output:
                summary = "พร้อมเริ่ม Batch"
            elif has_pdf and has_overlay:
                summary = "รอ Output Folder"
            elif has_pdf:
                summary = "รอตั้ง Text/Logo"
            else:
                summary = "รอเลือกไฟล์"
        self.pipeline_summary.setText(summary)

    def _update_queue_summary(self) -> None:
        if not hasattr(self, "queue_summary"):
            return
        total = self.queue_table.rowCount()
        if total == 0:
            self.queue_summary.setText("ยังไม่มีไฟล์ใน queue")
            return
        statuses: dict[str, int] = {}
        for row in range(total):
            status_item = self.queue_table.item(row, 5)
            status = status_item.text() if status_item else "Pending"
            statuses[status] = statuses.get(status, 0) + 1
        workers = self.worker_count.value() if hasattr(self, "worker_count") else 1
        self.queue_summary.setText(
            queue_summary_text(
                total=total,
                statuses=statuses,
                output_ready=bool(self._pending_batch_jobs)
                and self.start_batch_action.isEnabled(),
                workers=workers,
                readiness_reason=self._batch_readiness_reason,
            )
        )

    @staticmethod
    def _max_worker_limit() -> int:
        return max(1, min(os.cpu_count() or 2, 16))

    def _build_queue_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumHeight(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel("Batch Workspace — เลือกไฟล์ ตั้งค่า แล้วเริ่มประมวลผล")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.batch_workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.batch_workspace_splitter.setObjectName("batchWorkspaceSplitter")
        self.batch_workspace_splitter.setChildrenCollapsible(False)

        settings_panel = QWidget()
        settings_panel.setMinimumWidth(420)
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 8, 0)
        settings_layout.setSpacing(6)
        settings_title = QLabel("ตั้งค่างาน")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)
        self.batch_tabs = QTabWidget()
        self.batch_tabs.setObjectName("batchWorkspaceTabs")
        self.batch_tabs.addTab(self._build_file_output_tab(), "ไฟล์และปลายทาง")
        self.batch_tabs.addTab(self._build_search_tab(), "Search / ช่วงหน้า")
        self.batch_tabs.addTab(self._build_processing_tab(), "Processing")
        settings_layout.addWidget(self.batch_tabs, 1)
        self.batch_workspace_splitter.addWidget(settings_panel)

        queue_panel = QWidget()
        queue_panel.setMinimumWidth(680)
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setContentsMargins(8, 0, 0, 0)
        queue_layout.setSpacing(6)
        queue_header = QHBoxLayout()
        queue_title = QLabel("Queue Monitor")
        queue_title.setObjectName("sectionTitle")
        queue_header.addWidget(queue_title)
        queue_header.addStretch()
        remove = QPushButton("ลบรายการที่เลือก")
        remove.clicked.connect(self._remove_queue_rows)
        clear = QPushButton("ล้าง Queue")
        clear.clicked.connect(self._clear_queue)
        show_error = QPushButton("ดู Error")
        show_error.setToolTip("เปิดรายละเอียด Error ของรายการที่เลือก")
        show_error.clicked.connect(self._show_selected_queue_error)
        queue_header.addWidget(show_error)
        queue_header.addWidget(remove)
        queue_header.addWidget(clear)
        queue_layout.addLayout(queue_header)

        self.queue_summary = QLabel("ยังไม่มีไฟล์ใน queue")
        queue_layout.addWidget(self.queue_summary)
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("พร้อมเริ่มเมื่อข้อมูลครบ")
        self.batch_progress.setToolTip("Progress รวมของ Batch")
        queue_layout.addWidget(self.batch_progress)
        self.queue_table = QTableWidget(0, 7)
        self.queue_table.setHorizontalHeaderLabels(
            ["#", "Input File", "Pages/Items", "Output File", "Progress", "Status", "Error"]
        )
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setMinimumHeight(260)
        self.queue_table.doubleClicked.connect(lambda _index: self._show_selected_queue_error())
        header_view = self.queue_table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        self.queue_table.setColumnWidth(0, 52)
        self.queue_table.setColumnWidth(2, 96)
        self.queue_table.setColumnWidth(4, 110)
        self.queue_table.setColumnWidth(5, 125)
        self.queue_table.setColumnWidth(6, 220)
        queue_layout.addWidget(self.queue_table, 1)
        self.batch_workspace_splitter.addWidget(queue_panel)
        self.batch_workspace_splitter.setStretchFactor(0, 2)
        self.batch_workspace_splitter.setStretchFactor(1, 3)
        self.batch_workspace_splitter.setSizes([520, 880])
        layout.addWidget(self.batch_workspace_splitter, 1)
        return panel

    def _build_file_output_tab(self) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(8)
        input_group = QGroupBox("Input — ไฟล์ต้นทาง")
        input_row = QHBoxLayout(input_group)
        input_row.addWidget(QLabel("Folder:"))
        self.batch_input_folder = QLineEdit()
        self.batch_input_folder.setMinimumWidth(280)
        self.batch_input_folder.setPlaceholderText("เลือกหรือวาง Folder ต้นทาง")
        browse_input = QPushButton("เลือก Folder...")
        browse_input.clicked.connect(self._choose_batch_input_folder)
        load_folder = QPushButton("โหลดจาก Folder")
        load_folder.clicked.connect(self._load_input_folder_files)
        input_row.addWidget(self.batch_input_folder, 1)
        input_row.addWidget(browse_input)
        input_row.addWidget(load_folder)
        container_layout.addWidget(input_group)
        output_group = QGroupBox("Output — โฟลเดอร์ปลายทาง")
        output_row = QHBoxLayout(output_group)
        output_row.addWidget(QLabel("Folder:"))
        self.batch_output_folder = QLineEdit(
            str(self._preferences.output_folder) if self._preferences.output_folder else ""
        )
        self.batch_output_folder.setMinimumWidth(280)
        self.batch_output_folder.setPlaceholderText("เลือกหรือวาง Folder ปลายทาง")
        self.batch_output_folder.editingFinished.connect(self._batch_output_text_changed)
        browse_output = QPushButton("เลือก Folder...")
        browse_output.clicked.connect(self._choose_batch_output)
        self.open_output_folder_button = QPushButton("เปิด Folder")
        self.open_output_folder_button.clicked.connect(self._open_output_folder_manual)
        output_row.addWidget(self.batch_output_folder, 1)
        output_row.addWidget(browse_output)
        output_row.addWidget(self.open_output_folder_button)
        self._update_output_folder_button()
        container_layout.addWidget(output_group)

        folder_options = QGroupBox("Folder Options — เมื่อโหลดจากโฟลเดอร์")
        folder_row = QHBoxLayout(folder_options)
        self.recursive_input = QCheckBox("Recursive")
        self.recursive_input.setChecked(True)
        self.recursive_input.toggled.connect(self._recursive_toggled)
        self.max_depth = QSpinBox()
        self.max_depth.setRange(0, 50)
        self.max_depth.setValue(10)
        self.max_depth.setToolTip("0 = เฉพาะ folder นี้, 1 = ลงไป 1 ชั้น")
        self.max_depth.setEnabled(self.recursive_input.isChecked())
        self.max_depth_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_depth_slider.setRange(0, 50)
        self.max_depth_slider.setValue(self.max_depth.value())
        self.max_depth_slider.setToolTip(self.max_depth.toolTip())
        self.max_depth_slider.setEnabled(self.recursive_input.isChecked())
        self.max_depth.valueChanged.connect(self.max_depth_slider.setValue)
        self.max_depth_slider.valueChanged.connect(self.max_depth.setValue)
        self.preserve_structure = QCheckBox("รักษาโครงสร้าง")
        self.preserve_structure.setChecked(self._config.preserve_subfolders)
        self.preserve_structure.toggled.connect(self._batch_output_text_changed)
        folder_row.addWidget(self.recursive_input)
        folder_row.addWidget(QLabel("ลึกไม่เกิน"))
        folder_row.addWidget(self.max_depth_slider, 1)
        folder_row.addWidget(self.max_depth)
        folder_row.addWidget(QLabel("ชั้น"))
        folder_row.addWidget(self.preserve_structure)
        folder_row.addStretch()
        container_layout.addWidget(folder_options)
        return self._scrollable_tab(container)

    def _build_search_tab(self) -> QWidget:
        container = QWidget()
        options_layout = QVBoxLayout(container)
        options_layout.setContentsMargins(8, 8, 8, 8)
        options_layout.setSpacing(8)
        search_group = QGroupBox("Search / Page Filter — เลือกหน้าเป้าหมาย")
        search_layout = QVBoxLayout(search_group)
        first_row = QHBoxLayout()
        self.page_filter_enabled = QCheckBox("วางเฉพาะหน้าที่พบคำนี้")
        self.page_filter_enabled.setToolTip(
            "ใช้ text layer ของ PDF ไม่ใช่ OCR; ถ้า PDF เป็นสแกนล้วนอาจค้นไม่พบ"
        )
        self.page_filter_enabled.toggled.connect(self._page_filter_changed)
        self.page_filter_keyword = QLineEdit()
        self.page_filter_keyword.setPlaceholderText("เช่น จำนวนเงิน หรือ regex")
        self.page_filter_keyword.textChanged.connect(self._page_filter_changed)
        self.page_filter_regex = QCheckBox("Regex")
        self.page_filter_regex.toggled.connect(self._page_filter_changed)
        first_row.addWidget(self.page_filter_enabled)
        first_row.addWidget(self.page_filter_keyword, 1)
        first_row.addWidget(self.page_filter_regex)
        search_layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self.page_filter_ranges = QLineEdit()
        self.page_filter_ranges.setPlaceholderText("ช่วงหน้า เช่น 1-3,5,10-")
        self.page_filter_ranges.setToolTip(
            "เว้นว่าง = ทุกหน้า; ใช้ 10- เพื่อหมายถึงตั้งแต่หน้า 10 เป็นต้นไป"
        )
        self.page_filter_ranges.textChanged.connect(self._page_filter_changed)
        self.page_filter_min = QSpinBox()
        self.page_filter_min.setRange(1, 999)
        self.page_filter_min.setValue(1)
        self.page_filter_min.valueChanged.connect(self._page_filter_changed)
        self.page_filter_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.page_filter_min_slider.setRange(1, 999)
        self.page_filter_min_slider.setValue(self.page_filter_min.value())
        self.page_filter_min_slider.setToolTip("ปรับจำนวนครั้งขั้นต่ำที่ต้องพบต่อหน้า")
        self.page_filter_min.valueChanged.connect(self.page_filter_min_slider.setValue)
        self.page_filter_min_slider.valueChanged.connect(self.page_filter_min.setValue)
        self.page_filter_max = QSpinBox()
        self.page_filter_max.setRange(0, 999)
        self.page_filter_max.setValue(10)
        self.page_filter_max.setSpecialValueText("ไม่จำกัด")
        self.page_filter_max.valueChanged.connect(self._page_filter_changed)
        self.page_filter_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.page_filter_max_slider.setRange(0, 999)
        self.page_filter_max_slider.setValue(self.page_filter_max.value())
        self.page_filter_max_slider.setToolTip("0 = ไม่จำกัดจำนวนครั้งสูงสุด")
        self.page_filter_max.valueChanged.connect(self.page_filter_max_slider.setValue)
        self.page_filter_max_slider.valueChanged.connect(self.page_filter_max.setValue)
        second_row.addWidget(QLabel("ช่วงหน้า"))
        second_row.addWidget(self.page_filter_ranges, 1)
        search_layout.addLayout(second_row)

        occurrence_row = QHBoxLayout()
        occurrence_row.addWidget(QLabel("อย่างน้อย"))
        occurrence_row.addWidget(self.page_filter_min_slider, 1)
        occurrence_row.addWidget(self.page_filter_min)
        occurrence_row.addWidget(QLabel("ไม่เกิน"))
        occurrence_row.addWidget(self.page_filter_max_slider, 1)
        occurrence_row.addWidget(self.page_filter_max)
        occurrence_row.addWidget(QLabel("ครั้งต่อหน้า"))
        search_layout.addLayout(occurrence_row)

        action_row = QHBoxLayout()
        self.test_page_filter_button = QPushButton("ทดสอบ Search")
        self.test_page_filter_button.setToolTip(
            "ทดสอบกับไฟล์ที่กำลัง preview อยู่ เพื่อดูว่าจะวาง overlay หน้าใด"
        )
        self.test_page_filter_button.clicked.connect(self._test_page_filter_on_current_file)
        self.test_queue_filter_button = QPushButton("ทดสอบทั้ง Queue")
        self.test_queue_filter_button.setToolTip(
            "ค้นหาใน PDF ทุกไฟล์ใน queue ก่อน export จริง; รูปภาพจะถูกข้าม"
        )
        self.test_queue_filter_button.clicked.connect(self._test_page_filter_on_queue)
        action_row.addWidget(self.test_page_filter_button)
        action_row.addWidget(self.test_queue_filter_button)
        action_row.addStretch()
        search_layout.addLayout(action_row)

        self.page_filter_result = QLabel("Search ยังไม่ได้ทดสอบ")
        self.page_filter_result.setWordWrap(True)
        search_layout.addWidget(self.page_filter_result)
        options_layout.addWidget(search_group)
        self._page_filter_changed()
        return self._scrollable_tab(container)

    def _build_processing_tab(self) -> QWidget:
        container = QWidget()
        setup_row = QHBoxLayout(container)
        setup_row.setContentsMargins(8, 8, 8, 8)
        setup_row.setSpacing(10)
        options_group = QGroupBox("Options — การประมวลผล")
        options_layout = QVBoxLayout(options_group)
        options_row = QHBoxLayout()
        self.worker_count = QSpinBox()
        self.worker_count.setRange(1, self._max_worker_limit())
        self.worker_count.setValue(min(self._config.max_workers, self._max_worker_limit()))
        self.worker_count.setToolTip("จำนวนไฟล์ที่ประมวลผลพร้อมกัน")
        self.worker_count.valueChanged.connect(lambda _value: self._update_queue_summary())
        self.worker_count_slider = QSlider(Qt.Orientation.Horizontal)
        self.worker_count_slider.setRange(1, self._max_worker_limit())
        self.worker_count_slider.setValue(self.worker_count.value())
        self.worker_count_slider.setToolTip("ปรับจำนวนไฟล์ที่ประมวลผลพร้อมกัน")
        self.worker_count.valueChanged.connect(self.worker_count_slider.setValue)
        self.worker_count_slider.valueChanged.connect(self.worker_count.setValue)
        options_row.addWidget(QLabel("Workers"))
        options_row.addWidget(self.worker_count_slider, 1)
        options_row.addWidget(self.worker_count)
        self.overwrite_outputs = QCheckBox("เขียนทับ output เดิม")
        self.overwrite_outputs.setChecked(self._config.overwrite)
        self.overwrite_outputs.toggled.connect(self._refresh_batch_readiness)
        options_row.addWidget(self.overwrite_outputs)
        self.open_output_folder_on_finish = QCheckBox("เปิด Output เมื่อเสร็จ")
        self.open_output_folder_on_finish.setChecked(
            self._preferences.open_output_folder_on_finish
        )
        self.open_output_folder_on_finish.setToolTip(
            "เปิดโฟลเดอร์ปลายทางอัตโนมัติเมื่อ Batch สำเร็จ"
        )
        self.open_output_folder_on_finish.toggled.connect(
            self._open_output_folder_preference_changed
        )
        options_row.addWidget(self.open_output_folder_on_finish)
        options_layout.addLayout(options_row)
        setup_row.addWidget(options_group, 1)
        setup_row.addStretch()
        return self._scrollable_tab(container)

    @staticmethod
    def _scrollable_tab(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def _build_overlay_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel("OVERLAY ITEMS")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        delete = QPushButton("ลบรายการที่เลือก  (Delete)")
        delete.clicked.connect(self._delete_selected)
        layout.addWidget(delete)
        self.overlay_list = QListWidget()
        self.overlay_list.setToolTip("ยังไม่มี overlay — กด + Text หรือ + Logo เพื่อเริ่ม")
        self.overlay_list.currentRowChanged.connect(self._select_overlay)
        layout.addWidget(self.overlay_list, 1)
        buttons = QHBoxLayout()
        text_button = QPushButton("+ Text")
        text_button.clicked.connect(lambda: self._add_overlay(OverlayType.TEXT))
        logo_button = QPushButton("+ Logo")
        logo_button.clicked.connect(lambda: self._add_overlay(OverlayType.IMAGE))
        both_button = QPushButton("+ Text+Logo")
        both_button.clicked.connect(self._add_text_and_logo)
        buttons.addWidget(text_button)
        buttons.addWidget(logo_button)
        buttons.addWidget(both_button)
        layout.addLayout(buttons)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        header = QHBoxLayout()
        self.preview_title = QLabel("PDF Preview")
        self.page_label = QLabel("หน้า 0 / 0")
        header.addWidget(self.preview_title)
        header.addStretch()
        self.previous_page_button = QPushButton("<")
        self.previous_page_button.setToolTip("Previous page")
        self.previous_page_button.clicked.connect(self._previous_preview_page)
        self.preview_page_number = QSpinBox()
        self.preview_page_number.setRange(1, 1)
        self.preview_page_number.setToolTip("Preview page")
        self.preview_page_number.valueChanged.connect(self._preview_page_number_changed)
        self.next_page_button = QPushButton(">")
        self.next_page_button.setToolTip("Next page")
        self.next_page_button.clicked.connect(self._next_preview_page)
        header.addWidget(self.previous_page_button)
        header.addWidget(self.preview_page_number)
        header.addWidget(self.next_page_button)
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.clicked.connect(self._zoom_preview_out)
        self.zoom_fit_button = QPushButton("Fit")
        self.zoom_fit_button.setToolTip("Fit page to preview")
        self.zoom_fit_button.clicked.connect(self._fit_preview)
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.clicked.connect(self._zoom_preview_in)
        self.zoom_label = QLabel("Fit")
        header.addWidget(self.zoom_out_button)
        header.addWidget(self.zoom_fit_button)
        header.addWidget(self.zoom_in_button)
        header.addWidget(self.zoom_label)
        header.addWidget(self.page_label)
        layout.addLayout(header)
        self.preview = PreviewGraphicsView(self._scene, self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setBackgroundBrush(QColor("#252a33"))
        self.preview.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.preview, 1)
        self._update_page_controls()
        return panel

    def _build_properties_panel(self) -> QWidget:
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        title = QLabel("PROPERTIES — รายการที่เลือก")
        title.setObjectName("sectionTitle")
        outer_layout.addWidget(title)
        self.selected_item_label = QLabel("ยังไม่มีรายการที่เลือก — กด + Text หรือ + Logo")
        outer_layout.addWidget(self.selected_item_label)
        self.type_value = QLabel("—")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("พิมพ์ข้อความที่ต้องการวางบนไฟล์")
        self.logo_button = QPushButton("เลือกไฟล์ Logo...")
        self.logo_button.clicked.connect(self._choose_logo)
        self.logo_value = QLabel("ยังไม่ได้เลือกไฟล์")
        self.logo_value.setWordWrap(True)
        self.position = QComboBox()
        positions = [
            ("บนซ้าย", Position.TOP_LEFT), ("บนกลาง", Position.TOP_CENTER),
            ("บนขวา", Position.TOP_RIGHT), ("กลางซ้าย", Position.MIDDLE_LEFT),
            ("กลาง", Position.MIDDLE_CENTER), ("กลางขวา", Position.MIDDLE_RIGHT),
            ("ล่างซ้าย", Position.BOTTOM_LEFT), ("ล่างกลาง", Position.BOTTOM_CENTER),
            ("ล่างขวา", Position.BOTTOM_RIGHT),
        ]
        for label, value in positions:
            self.position.addItem(label, value)
        self.position_mode = QComboBox()
        self.position_mode.addItem("ตำแหน่งมาตรฐาน", PositionMode.PRESET)
        self.position_mode.addItem("วางอิสระ", PositionMode.ABSOLUTE)
        self.x_percent = QDoubleSpinBox()
        self.x_percent.setRange(0.0, 100.0)
        self.x_percent.setDecimals(2)
        self.x_percent.setSuffix("%")
        self.x_percent.setSingleStep(0.25)
        self.y_percent = QDoubleSpinBox()
        self.y_percent.setRange(0.0, 100.0)
        self.y_percent.setDecimals(2)
        self.y_percent.setSuffix("%")
        self.y_percent.setSingleStep(0.25)
        self.reset_to_preset = QPushButton("กลับไปใช้ตำแหน่งมาตรฐาน")
        self.reset_to_preset.clicked.connect(self._reset_selected_to_preset)
        self.font = QComboBox()
        self.font.addItems(self._discover_fonts())
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 240)
        self.font_size.setValue(32)
        self.logo_size = QSpinBox()
        self.logo_size.setRange(1, 100)
        self.logo_size.setValue(12)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity_label = QLabel("100%")
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity)
        opacity_row.addWidget(self.opacity_label)
        self.rotation = QSpinBox()
        self.rotation.setRange(-360, 360)
        self.rotation.setSuffix("°")
        self.color_button = QPushButton("เลือกสี")
        self.color_button.clicked.connect(self._choose_color)
        self.properties_tabs = QTabWidget()
        self.properties_tabs.setObjectName("propertiesTabs")
        self.properties_tabs.addTab(
            self._scrollable_form(
                [
                    ("ชนิด", self.type_value),
                    ("ข้อความ", self.text_input),
                    ("Logo", self.logo_button),
                    ("ไฟล์", self.logo_value),
                ]
            ),
            "Content",
        )
        self.properties_tabs.addTab(
            self._scrollable_form(
                [
                    ("ตำแหน่งของรายการนี้", self.position),
                    ("โหมดตำแหน่ง", self.position_mode),
                    ("X ของรายการนี้", self.x_percent),
                    ("Y ของรายการนี้", self.y_percent),
                    ("", self.reset_to_preset),
                    ("ขนาด Text ของรายการนี้", self.font_size),
                    ("ขนาด Logo ของรายการนี้ (%)", self.logo_size),
                    ("หมุนรายการนี้", self.rotation),
                ]
            ),
            "Layout",
        )
        self.properties_tabs.addTab(
            self._scrollable_form(
                [
                    ("Font", self.font),
                    ("สีข้อความ", self.color_button),
                    ("ความโปร่งใสของรายการนี้", opacity_row),
                ]
            ),
            "Style",
        )
        outer_layout.addWidget(self.properties_tabs, 1)
        self.text_input.textChanged.connect(self._property_changed)
        self.position.currentIndexChanged.connect(self._preset_position_changed)
        self.position_mode.currentIndexChanged.connect(self._position_mode_changed)
        self.x_percent.valueChanged.connect(self._absolute_position_changed)
        self.y_percent.valueChanged.connect(self._absolute_position_changed)
        self.font.currentIndexChanged.connect(self._property_changed)
        self.font_size.valueChanged.connect(self._property_changed)
        self.logo_size.valueChanged.connect(self._property_changed)
        self.opacity.valueChanged.connect(self._property_changed)
        self.rotation.valueChanged.connect(self._property_changed)
        self._sync_property_controls(None)
        return outer

    def _scrollable_form(self, rows: list[tuple[str, QWidget | QHBoxLayout]]) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("propertiesScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setContentsMargins(12, 12, 12, 12)
        form.setVerticalSpacing(10)
        for label, field in rows:
            form.addRow(label, field)
        scroll.setWidget(content)
        return scroll

    def _discover_fonts(self) -> list[str]:
        directory = font_directory()
        return sorted(path.stem for path in directory.rglob("*.ttf")) or ["Arial"]

    def _populate_queue(self, jobs: list[tuple[Path, Path]]) -> None:
        self.queue_table.setRowCount(0)
        for row, (source, destination) in enumerate(jobs):
            self.queue_table.insertRow(row)
            page_count = self._source_units(source)
            values = [
                str(row + 1),
                source.name,
                page_count,
                str(destination) if str(destination) != "." else "—",
                "0%",
                "Pending",
                "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 3):
                    item.setToolTip(value)
                if column == 3 and str(destination) != ".":
                    item.setData(Qt.ItemDataRole.UserRole, str(destination))
                self.queue_table.setItem(row, column, item)
            self.queue_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, str(source))
        self._update_queue_summary()
        self._reset_batch_progress()
        self._update_pipeline()

    def _batch_output_text_changed(self) -> None:
        output_text = self.batch_output_folder.text().strip()
        if not output_text:
            self._pending_batch_jobs = []
            self._batch_readiness_reason = "missing_output"
            self.start_batch_action.setEnabled(False)
            self._update_output_folder_button()
            self._update_pipeline("เลือก Output Folder ก่อนเริ่มงาน")
            return
        output = Path(output_text)
        if not self._is_valid_output_folder(output):
            self._pending_batch_jobs = []
            self._batch_readiness_reason = "missing_output"
            self.start_batch_action.setEnabled(False)
            self._update_output_folder_button()
            self.statusBar().showMessage(f"Output Folder ไม่ถูกต้อง: {output}")
            self._update_pipeline("Output Folder ไม่ถูกต้อง")
            return
        self._update_output_folder_button()
        sources = self._queue_sources()
        if not sources:
            self._preferences.output_folder = output
            save_preferences(self._preferences)
            self._update_pipeline("จำ Output Folder แล้ว")
            return
        self._apply_output_folder(output, "พร้อมเริ่ม Batch")

    def _choose_batch_output(self) -> None:
        initial = self.batch_output_folder.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "เลือก Output Folder", initial)
        if not folder:
            return
        self._apply_output_folder(Path(folder), "Output Folder พร้อมแล้ว")

    def _apply_output_folder(self, output: Path, summary: str) -> None:
        if output_is_inside_input(self._input_root, output):
            self._pending_batch_jobs = []
            self._batch_readiness_reason = "missing_output"
            self.start_batch_action.setEnabled(False)
            self._update_output_folder_button()
            self.statusBar().showMessage("Output Folder ต้องไม่อยู่ภายใน Input Folder")
            self._update_pipeline("Output Folder ซ้อนอยู่ใน Input Folder")
            return
        self.batch_output_folder.setText(str(output))
        self._update_output_folder_button()
        self._preferences.output_folder = output
        save_preferences(self._preferences)
        sources = self._queue_sources()
        if sources:
            self._pending_batch_jobs = [
                self._destination_for(source, output, self._input_root) for source in sources
            ]
            self._populate_queue(self._pending_batch_jobs)
            self._refresh_batch_readiness()
        self._update_pipeline(summary)

    def _recursive_toggled(self, checked: bool) -> None:
        self.max_depth.setEnabled(checked)
        self.max_depth_slider.setEnabled(checked)

    def _page_filter_changed(self, _value: Any = None) -> None:
        if not hasattr(self, "page_filter_keyword"):
            return
        enabled = self.page_filter_enabled.isChecked()
        self.page_filter_keyword.setEnabled(enabled)
        self.page_filter_ranges.setEnabled(enabled)
        self.page_filter_regex.setEnabled(enabled)
        self.page_filter_min.setEnabled(enabled)
        self.page_filter_min_slider.setEnabled(enabled)
        self.page_filter_max.setEnabled(enabled)
        self.page_filter_max_slider.setEnabled(enabled)
        self.test_page_filter_button.setEnabled(enabled)
        self.test_queue_filter_button.setEnabled(enabled)
        if not enabled:
            self.page_filter_result.setText("Search ปิดอยู่ — จะวาง overlay ทุกหน้า")
        error = self._page_filter_error()
        if error:
            self.start_batch_action.setEnabled(False)
            self._update_queue_summary()
            self._update_pipeline(error)
            return
        if hasattr(self, "queue_table"):
            self._refresh_batch_readiness()

    def _test_page_filter_on_current_file(self) -> None:
        if not self.page_filter_enabled.isChecked():
            self.page_filter_result.setText("Search ปิดอยู่ — จะวาง overlay ทุกหน้า")
            return
        error = self._page_filter_error()
        if error:
            self.page_filter_result.setText(error)
            self._update_pipeline(error)
            return
        if self._pdf_path is None:
            self.page_filter_result.setText("เปิด PDF ก่อนทดสอบ Search")
            return
        rule = self._page_text_rule()
        if rule is None:
            self.page_filter_result.setText("ใส่คำหรือ regex ก่อนทดสอบ Search")
            return
        try:
            result = search_pdf_pages(self._pdf_path, rule, max_hits=20)
        except Exception as error:
            self.page_filter_result.setText(f"Search ล้มเหลว: {error}")
            return
        pages = ", ".join(str(hit.page_number) for hit in result.hits)
        hidden = result.matched_pages - len(result.hits)
        suffix = f" และอีก {hidden} หน้า" if hidden > 0 else ""
        if result.matched_pages:
            self.page_filter_result.setText(
                f"พบ {result.matched_pages}/{result.page_count} หน้า "
                f"รวม {result.total_occurrences} ครั้ง: หน้า {pages}{suffix} "
                f"({result.elapsed_seconds:.2f}s)"
            )
        else:
            self.page_filter_result.setText(
                f"ไม่พบหน้าที่ตรงเงื่อนไขใน {result.page_count} หน้า "
                f"({result.elapsed_seconds:.2f}s)"
            )

    def _test_page_filter_on_queue(self) -> None:
        if not self.page_filter_enabled.isChecked():
            self.page_filter_result.setText("Search ปิดอยู่ — จะวาง overlay ทุกหน้า")
            return
        error = self._page_filter_error()
        if error:
            self.page_filter_result.setText(error)
            self._update_pipeline(error)
            return
        sources = self._queue_sources()
        if not sources:
            self.page_filter_result.setText("เพิ่ม PDF เข้า Queue ก่อนทดสอบทั้ง Queue")
            return
        rule = self._page_text_rule()
        if rule is None:
            self.page_filter_result.setText("ใส่คำหรือ regex ก่อนทดสอบ Search")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = search_pdf_batch(sources, rule, max_hits_per_file=3)
        except Exception as error:
            self.page_filter_result.setText(f"Search ทั้ง Queue ล้มเหลว: {error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        skipped = (
            f" | ข้ามรูปภาพ/ไฟล์ที่ไม่ใช่ PDF {result.skipped_non_pdf} ไฟล์"
            if result.skipped_non_pdf
            else ""
        )
        if result.pdf_count == 0:
            self.page_filter_result.setText("Queue นี้ไม่มี PDF ให้ค้นหา")
            return
        if result.matched_pages:
            self.page_filter_result.setText(
                f"ทั้ง Queue พบ {result.matched_files}/{result.pdf_count} PDF, "
                f"{result.matched_pages}/{result.page_count} หน้า, "
                f"รวม {result.total_occurrences} ครั้ง "
                f"({result.elapsed_seconds:.2f}s){skipped}"
            )
        else:
            self.page_filter_result.setText(
                f"ทั้ง Queue ไม่พบหน้าที่ตรงเงื่อนไขใน {result.pdf_count} PDF "
                f"รวม {result.page_count} หน้า ({result.elapsed_seconds:.2f}s){skipped}"
            )

    def _page_filter_error(self) -> str | None:
        return page_filter_error(
            enabled=self.page_filter_enabled.isChecked(),
            keyword=self.page_filter_keyword.text(),
            use_regex=self.page_filter_regex.isChecked(),
            page_ranges=self.page_filter_ranges.text(),
        )

    def _page_text_rule(self) -> PageTextRule | None:
        return page_text_rule_from_options(
            enabled=self.page_filter_enabled.isChecked(),
            keyword=self.page_filter_keyword.text(),
            min_occurrences=self.page_filter_min.value(),
            max_occurrences=self.page_filter_max.value(),
            use_regex=self.page_filter_regex.isChecked(),
            page_ranges=self.page_filter_ranges.text(),
        )

    def _open_output_folder_preference_changed(self, checked: bool) -> None:
        self._preferences.open_output_folder_on_finish = checked
        save_preferences(self._preferences)

    def _update_output_folder_button(self) -> None:
        if not hasattr(self, "open_output_folder_button"):
            return
        output_text = self.batch_output_folder.text().strip()
        self.open_output_folder_button.setEnabled(
            bool(output_text) and self._is_valid_output_folder(Path(output_text))
        )

    def _open_output_folder_manual(self) -> None:
        output_text = self.batch_output_folder.text().strip()
        if output_text and self._is_valid_output_folder(Path(output_text)):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output_text))))
            return
        self.statusBar().showMessage("Output Folder ไม่ถูกต้องหรือยังไม่ได้เลือก")

    def _preview_page_count(self) -> int:
        if self._document is not None:
            return self._document.page_count
        if self._image_path is not None:
            return 1
        return 0

    def _update_page_controls(self) -> None:
        if not hasattr(self, "preview_page_number"):
            return
        page_count = self._preview_page_count()
        has_pages = page_count > 0
        if has_pages:
            self._preview_page_index = min(max(0, self._preview_page_index), page_count - 1)
            current_page = self._preview_page_index + 1
            self.preview_page_number.blockSignals(True)
            self.preview_page_number.setRange(1, page_count)
            self.preview_page_number.setValue(current_page)
            self.preview_page_number.blockSignals(False)
            prefix = "รูปภาพ" if self._image_path is not None else "หน้า"
            self.page_label.setText(f"{prefix} {current_page} / {page_count}")
        else:
            self._preview_page_index = 0
            self.preview_page_number.blockSignals(True)
            self.preview_page_number.setRange(1, 1)
            self.preview_page_number.setValue(1)
            self.preview_page_number.blockSignals(False)
            self.page_label.setText("หน้า 0 / 0")
        can_change_pages = self._document is not None and page_count > 1
        self.preview_page_number.setEnabled(can_change_pages)
        self.previous_page_button.setEnabled(can_change_pages and self._preview_page_index > 0)
        self.next_page_button.setEnabled(
            can_change_pages and self._preview_page_index < page_count - 1
        )

    def _preview_page_number_changed(self, page_number: int) -> None:
        page_count = self._preview_page_count()
        if page_count <= 0:
            return
        next_index = min(max(0, page_number - 1), page_count - 1)
        if next_index == self._preview_page_index:
            return
        self._preview_page_index = next_index
        self._update_page_controls()
        self._refresh_preview()

    def _previous_preview_page(self) -> None:
        self.preview_page_number.setValue(self._preview_page_index)

    def _next_preview_page(self) -> None:
        self.preview_page_number.setValue(self._preview_page_index + 2)

    def _choose_batch_input_folder(self) -> None:
        initial = self.batch_input_folder.text().strip() or str(
            self._preferences.pdf_folder or Path.home()
        )
        folder = QFileDialog.getExistingDirectory(self, "เลือก Input Folder", initial)
        if not folder:
            return
        self.batch_input_folder.setText(folder)
        self._load_input_folder_files()

    def _load_input_folder_files(self) -> None:
        input_text = self.batch_input_folder.text().strip()
        if not input_text:
            self.statusBar().showMessage("กรุณาเลือกหรือวาง Input Folder")
            return
        input_root = Path(input_text)
        if not input_root.exists() or not input_root.is_dir():
            self._pending_batch_jobs = []
            self.start_batch_action.setEnabled(False)
            self.statusBar().showMessage(f"Input Folder ไม่ถูกต้อง: {input_root}")
            self._update_pipeline("Input Folder ไม่ถูกต้อง")
            return
        max_depth = self.max_depth.value() if self.recursive_input.isChecked() else 0
        sources = discover_supported_files(
            input_root,
            recursive=self.recursive_input.isChecked(),
            max_depth=max_depth,
        )
        if not sources:
            self._pending_batch_jobs = []
            self._populate_queue([])
            self.start_batch_action.setEnabled(False)
            self.statusBar().showMessage("ไม่พบ PDF/Image ใน Input Folder")
            self._update_pipeline("ไม่พบไฟล์ที่รองรับ")
            return
        self._input_root = input_root
        self._preferences.pdf_folder = input_root
        save_preferences(self._preferences)
        self._load_source(sources[0])
        output_text = self.batch_output_folder.text().strip()
        if not output_text or not self._is_valid_output_folder(Path(output_text)):
            self._pending_batch_jobs = []
            self._populate_queue([(source, Path()) for source in sources])
            self.start_batch_action.setEnabled(False)
            self._update_pipeline("โหลดไฟล์แล้ว — รอ Output Folder")
            return
        output = Path(output_text)
        self._pending_batch_jobs = [
            self._destination_for(source, output, input_root) for source in sources
        ]
        self._populate_queue(self._pending_batch_jobs)
        self._refresh_batch_readiness()
        self.statusBar().showMessage(
            f"โหลดจาก Folder แล้ว {len(sources)} ไฟล์ — พร้อมเริ่ม Batch"
        )
        self._update_pipeline("พร้อมเริ่ม Batch")

    def _queue_sources(self) -> list[Path]:
        return [
            Path(self.queue_table.item(row, 1).data(Qt.ItemDataRole.UserRole))
            for row in range(self.queue_table.rowCount())
        ]

    def _queue_jobs_from_table(self) -> list[tuple[Path, Path]]:
        jobs: list[tuple[Path, Path]] = []
        for row in range(self.queue_table.rowCount()):
            source_item = self.queue_table.item(row, 1)
            destination_item = self.queue_table.item(row, 3)
            if source_item is None or destination_item is None:
                continue
            source_data = source_item.data(Qt.ItemDataRole.UserRole)
            destination_data = destination_item.data(Qt.ItemDataRole.UserRole)
            if not source_data or not destination_data:
                continue
            jobs.append((Path(source_data), Path(destination_data)))
        return jobs

    def _refresh_batch_readiness(self) -> None:
        self._pending_batch_jobs = self._queue_jobs_from_table()
        readiness = evaluate_batch_readiness(
            has_jobs=bool(self._pending_batch_jobs),
            is_running=self._worker is not None and self.cancel_action.isEnabled(),
            page_filter_error=self._page_filter_error(),
            has_effective_overlay=self._has_effective_overlay(),
        )
        self._batch_readiness_reason = readiness.reason
        self.start_batch_action.setEnabled(readiness.can_start)
        start_message = blocked_start_message(readiness.reason)
        self.start_batch_action.setToolTip(start_message)
        self.start_batch_action.setStatusTip(start_message)
        self._update_queue_summary()

    def _destination_for(
        self,
        source: Path,
        output_folder: Path,
        input_root: Path | None = None,
    ) -> tuple[Path, Path]:
        job = build_jobs(
            [source],
            output_folder,
            suffix=self._config.output_suffix,
            preserve_subfolders=self.preserve_structure.isChecked(),
            input_root=input_root,
        )[0]
        return job.source, job.destination

    @staticmethod
    def _is_valid_output_folder(output: Path) -> bool:
        return output.exists() and output.is_dir()

    @staticmethod
    def _source_units(source: Path) -> str:
        if source.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            return "1"
        try:
            with fitz.open(source) as document:
                return str(document.page_count)
        except Exception:
            return "?"

    def _queue_row_for_source(self, source_key: str) -> int | None:
        for row in range(self.queue_table.rowCount()):
            if self.queue_table.item(row, 1).data(Qt.ItemDataRole.UserRole) == source_key:
                return row
        return None

    def _update_queue_file(self, source_key: str, status: str, progress: int) -> None:
        row = self._queue_row_for_source(source_key)
        if row is not None:
            self.queue_table.item(row, 4).setText(f"{progress}%")
            self.queue_table.item(row, 5).setText(status)
            self._update_queue_summary()

    def _update_queue_progress(self, source_key: str, current: int, total: int) -> None:
        row = self._queue_row_for_source(source_key)
        if row is None:
            return
        percent = int(current * 100 / total) if total else 0
        self.queue_table.item(row, 4).setText(f"{percent}% ({current}/{total})")
        if percent < 100:
            self.queue_table.item(row, 5).setText("Processing")
        self._update_queue_summary()

    def _reset_batch_progress(self) -> None:
        if not hasattr(self, "batch_progress"):
            return
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("พร้อมเริ่มเมื่อข้อมูลครบ")

    def _update_batch_progress(self, percent: int, name: str) -> None:
        bounded = max(0, min(100, percent))
        self.batch_progress.setValue(bounded)
        self.batch_progress.setFormat(f"{bounded}% — {name}")
        self.statusBar().showMessage(f"กำลังประมวลผล {bounded}% — {name}")

    def _mark_active_rows_stopping(self) -> None:
        for row in range(self.queue_table.rowCount()):
            status_item = self.queue_table.item(row, 5)
            if status_item is None or status_item.text() in {"Completed", "Failed"}:
                continue
            status_item.setText("Stopping")
        self._update_queue_summary()

    def _mark_unfinished_rows_cancelled(self) -> None:
        for row in range(self.queue_table.rowCount()):
            status_item = self.queue_table.item(row, 5)
            if status_item is None or status_item.text() in {"Completed", "Failed"}:
                continue
            status_item.setText("Cancelled")
        self._update_queue_summary()

    def _remove_queue_rows(self) -> None:
        if self._worker is not None and self.cancel_action.isEnabled():
            QMessageBox.information(self, "กำลังประมวลผล", "หยุด Batch ก่อนลบรายการ")
            return
        rows = sorted({index.row() for index in self.queue_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        removed_sources = {
            Path(self.queue_table.item(row, 1).data(Qt.ItemDataRole.UserRole)) for row in rows
        }
        for row in rows:
            self.queue_table.removeRow(row)
        self._pending_batch_jobs = [
            job for job in self._pending_batch_jobs if job[0] not in removed_sources
        ]
        self._refresh_batch_readiness()
        self._update_pipeline()

    def _clear_queue(self) -> None:
        if self._worker is not None and self.cancel_action.isEnabled():
            QMessageBox.information(self, "กำลังประมวลผล", "หยุด Batch ก่อนล้าง Queue")
            return
        self.queue_table.setRowCount(0)
        self._pending_batch_jobs.clear()
        self._input_root = None
        self.start_batch_action.setEnabled(False)
        self._update_queue_summary()
        self._update_pipeline("ล้าง Queue แล้ว")

    def _font_path(self, name: str) -> Path | None:
        directory = font_directory()
        return next(directory.rglob(f"{name}.ttf"), None)

    def _preview_font(self, name: str, point_size: int) -> QFont:
        family = self._preview_font_families.get(name)
        if family is None:
            font_path = self._font_path(name)
            if font_path and font_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                families = QFontDatabase.applicationFontFamilies(font_id)
                family = families[0] if families else name
            else:
                family = name
            self._preview_font_families[name] = family
        return QFont(family, point_size)

    def _select_input_files(self) -> None:
        initial_folder = str(self._preferences.pdf_folder or Path.home())
        dialog = QFileDialog(self, "เลือก PDF/Image File(s)", initial_folder)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Supported files (*.pdf *.png *.jpg *.jpeg)")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        sources = [
            Path(path)
            for path in dialog.selectedFiles()
            if Path(path).suffix.lower() in SUPPORTED_INPUT_SUFFIXES
        ]
        if not sources:
            return
        self._input_root = None
        self._preferences.pdf_folder = sources[0].parent
        save_preferences(self._preferences)
        if len(sources) == 1:
            self._load_source(sources[0])
            output_text = self.batch_output_folder.text().strip()
            destination = (
                self._destination_for(sources[0], Path(output_text))[1]
                if output_text
                else Path()
            )
            if output_text and self._is_valid_output_folder(Path(output_text)):
                self._pending_batch_jobs = [(sources[0], destination)]
                self.statusBar().showMessage(
                    "พร้อมเริ่ม 1 ไฟล์ — กด Start Batch เพื่อเริ่ม"
                )
            else:
                self._pending_batch_jobs = []
                self.start_batch_action.setEnabled(False)
            self._populate_queue([(sources[0], destination)])
            self._refresh_batch_readiness()
            self._update_pipeline()
            return
        self._load_source(sources[0])
        output_text = self.batch_output_folder.text().strip()
        if not output_text or not self._is_valid_output_folder(Path(output_text)):
            self._pending_batch_jobs = []
            self._populate_queue([(source, Path()) for source in sources])
            self.start_batch_action.setEnabled(False)
            self.statusBar().showMessage(
                f"เลือกแล้ว {len(sources)} ไฟล์ — กรุณาตั้ง Output Folder ที่ถูกต้อง"
            )
            self._update_pipeline("เลือกไฟล์แล้ว — รอ Output Folder")
            return
        output_path = Path(output_text)
        self._pending_batch_jobs = [
            self._destination_for(source, output_path) for source in sources
        ]
        self._populate_queue(self._pending_batch_jobs)
        self._refresh_batch_readiness()
        self.statusBar().showMessage(
            f"พร้อมเริ่ม Batch: {len(sources)} ไฟล์ → {output_path} | กด Start Batch"
        )
        self._update_pipeline("พร้อมเริ่ม Batch")

    def _load_source(self, source_path: Path, preview_overlays: bool = True) -> None:
        if source_path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            self._load_image(source_path, preview_overlays)
        else:
            self._load_pdf(source_path, preview_overlays)

    def _load_pdf(self, pdf_path: Path, preview_overlays: bool = True) -> None:
        try:
            if self._document:
                self._document.close()
            self._document = fitz.open(pdf_path)
            self._source_path = pdf_path
            self._pdf_path = pdf_path
            self._image_path = None
            self._preview_bakes_overlays = preview_overlays
            self._preview_page_index = 0
            self.preview_title.setText(self._pdf_path.name)
            self._update_page_controls()
            self.statusBar().showMessage(f"เปิดไฟล์แล้ว: {self._pdf_path}")
            self._refresh_preview()
        except Exception as error:
            QMessageBox.critical(self, "เปิด PDF ไม่สำเร็จ", str(error))

    def _load_image(self, image_path: Path, preview_overlays: bool = True) -> None:
        if self._document:
            self._document.close()
            self._document = None
        self._source_path = image_path
        self._pdf_path = None
        self._image_path = image_path
        self._preview_bakes_overlays = preview_overlays
        self._preview_page_index = 0
        self.preview_title.setText(image_path.name)
        self._update_page_controls()
        self.statusBar().showMessage(f"เปิดไฟล์แล้ว: {image_path}")
        self._refresh_preview()

    def _add_overlay(self, overlay_type: OverlayType) -> None:
        asset_path = ""
        if overlay_type is OverlayType.IMAGE:
            asset_path, _ = QFileDialog.getOpenFileName(
                self, "เลือก Logo", "", "Images (*.png *.jpg *.jpeg)"
            )
            if not asset_path:
                return
        self._append_overlay(overlay_type, asset_path)

    def _add_text_and_logo(self) -> None:
        asset_path, _ = QFileDialog.getOpenFileName(
            self, "เลือก Logo", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not asset_path:
            return
        self._append_overlay(OverlayType.TEXT)
        self._append_overlay(OverlayType.IMAGE, asset_path)

    def _append_overlay(self, overlay_type: OverlayType, asset_path: str = "") -> None:
        number = len(self._overlays) + 1
        item = {
            "id": f"overlay-{number}", "type": overlay_type,
            "position_mode": PositionMode.PRESET,
            "position": (
                Position.TOP_RIGHT
                if overlay_type is OverlayType.IMAGE
                else Position.MIDDLE_CENTER
            ),
            "x_percent": 50.0, "y_percent": 50.0,
            "opacity": 100, "rotation": 0, "font_size": 32,
            "font": self.font.currentText(), "logo_size": 12,
            "text": "ข้อความตัวอย่าง" if overlay_type is OverlayType.TEXT else "",
            "asset_path": asset_path, "color": "#000000",
        }
        self._overlays.append(item)
        label = "Text" if overlay_type is OverlayType.TEXT else "Logo"
        list_item = QListWidgetItem(f"{label} {number}")
        list_item.setData(Qt.ItemDataRole.UserRole, item["id"])
        self.overlay_list.addItem(list_item)
        self.overlay_list.setCurrentItem(list_item)
        self._update_pipeline()

    def _save_overlay_settings(self) -> None:
        if not self._overlays:
            QMessageBox.information(
                self,
                "ยังไม่มี Settings",
                "กรุณาเพิ่ม Text หรือ Logo ก่อนบันทึก Settings",
            )
            return
        initial_folder = self._settings_initial_folder()
        initial = str(initial_folder / "mtpdflogo-settings.toml")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึก Overlay Settings",
            initial,
            "MTPDFLogo settings (*.toml)",
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".toml":
            target = target.with_suffix(".toml")
        self._save_overlay_settings_to_file(target)

    def _save_default_overlay_settings(self) -> None:
        if not self._overlays:
            QMessageBox.information(
                self,
                "ยังไม่มี Settings",
                "กรุณาเพิ่ม Text หรือ Logo ก่อนบันทึก Default",
            )
            return
        target = self._preferences.default_settings_file
        if target is None:
            initial_folder = self._settings_initial_folder()
            path, _ = QFileDialog.getSaveFileName(
                self,
                "บันทึก Default Overlay Settings",
                str(initial_folder / "default-mtpdflogo-settings.toml"),
                "MTPDFLogo settings (*.toml)",
            )
            if not path:
                return
            target = Path(path)
            if target.suffix.lower() != ".toml":
                target = target.with_suffix(".toml")
            self._preferences.default_settings_file = target
        elif target.exists():
            answer = QMessageBox.question(
                self,
                "บันทึกทับ Default Settings?",
                f"ต้องการบันทึกทับ Default Settings เดิมหรือไม่?\n{target}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._save_overlay_settings_to_file(target)
        self.statusBar().showMessage(f"บันทึก Default Settings แล้ว: {target}")

    def _save_overlay_settings_to_file(self, target: Path) -> None:
        save_overlay_preset(target, self._overlays, self._page_filter_settings())
        self._preferences.remember_settings_file(target)
        save_preferences(self._preferences)
        self._update_recent_settings_control()
        self.statusBar().showMessage(f"บันทึก Settings แล้ว: {target}")

    def _load_overlay_settings(self) -> None:
        initial_folder = self._settings_initial_folder()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "โหลด Overlay Settings",
            str(initial_folder),
            "MTPDFLogo settings (*.toml)",
        )
        if not path:
            return
        self._load_overlay_settings_file(Path(path))

    def _load_default_overlay_settings(self) -> None:
        target = self._preferences.default_settings_file
        if target is None:
            QMessageBox.information(
                self,
                "ยังไม่มี Default Settings",
                "กรุณากด บันทึก Default ก่อน",
            )
            return
        if not target.exists():
            self.statusBar().showMessage(f"Default Settings หาไม่พบ: {target}")
            QMessageBox.warning(self, "Default Settings หาไม่พบ", str(target))
            return
        self._load_overlay_settings_file(target)

    def _load_recent_overlay_settings(self, index: int) -> None:
        path = self.recent_settings.itemData(index)
        if not path:
            return
        source = Path(path)
        if not source.exists():
            self._preferences.recent_settings_files = [
                item for item in self._preferences.recent_settings_files if item != source
            ]
            save_preferences(self._preferences)
            self._update_recent_settings_control()
            self.statusBar().showMessage(f"Recent Settings หาไม่พบ: {source.name}")
            QMessageBox.warning(self, "Recent Settings หาไม่พบ", str(source))
            return
        self._load_overlay_settings_file(source)
        self.recent_settings.setCurrentIndex(0)

    def _load_overlay_settings_file(self, source: Path) -> bool:
        try:
            loaded = load_overlay_preset(source)
            page_filter = load_page_filter_options(source)
        except Exception as error:
            QMessageBox.critical(self, "โหลด Settings ไม่สำเร็จ", str(error))
            return False
        missing_logos = self._missing_logo_paths(loaded)
        self._preferences.remember_settings_file(source)
        save_preferences(self._preferences)
        self._update_recent_settings_control()
        self._overlays = loaded
        self._rebuild_overlay_list()
        self._apply_page_filter_settings(page_filter)
        self._refresh_preview()
        self.statusBar().showMessage(
            f"โหลด Settings: {source.name} ({len(loaded)} รายการ)"
        )
        self._update_pipeline(f"โหลด Settings: {source.name}")
        if missing_logos:
            QMessageBox.warning(
                self,
                "Logo ใน Settings หาไม่พบ",
                "ไฟล์ Logo ต่อไปนี้ไม่มีอยู่แล้ว:\n" + "\n".join(missing_logos[:8]),
            )
        return True

    def _page_filter_settings(self) -> dict[str, Any]:
        return {
            "enabled": self.page_filter_enabled.isChecked(),
            "keyword": self.page_filter_keyword.text(),
            "use_regex": self.page_filter_regex.isChecked(),
            "min_occurrences": self.page_filter_min.value(),
            "max_occurrences": self.page_filter_max.value(),
            "page_ranges": self.page_filter_ranges.text(),
        }

    def _apply_page_filter_settings(self, settings: dict[str, Any]) -> None:
        controls = [
            self.page_filter_enabled,
            self.page_filter_keyword,
            self.page_filter_regex,
            self.page_filter_min,
            self.page_filter_min_slider,
            self.page_filter_max,
            self.page_filter_max_slider,
            self.page_filter_ranges,
        ]
        for control in controls:
            control.blockSignals(True)
        self.page_filter_enabled.setChecked(bool(settings.get("enabled", False)))
        self.page_filter_keyword.setText(str(settings.get("keyword", "")))
        self.page_filter_regex.setChecked(bool(settings.get("use_regex", False)))
        self.page_filter_min.setValue(int(settings.get("min_occurrences", 1)))
        self.page_filter_min_slider.setValue(self.page_filter_min.value())
        self.page_filter_max.setValue(int(settings.get("max_occurrences", 10)))
        self.page_filter_max_slider.setValue(self.page_filter_max.value())
        self.page_filter_ranges.setText(str(settings.get("page_ranges", "")))
        for control in controls:
            control.blockSignals(False)
        self._page_filter_changed()

    def _settings_initial_folder(self) -> Path:
        folder = self._preferences.settings_folder
        if folder and folder.exists() and folder.is_dir():
            return folder
        return Path.home()

    def _update_recent_settings_control(self) -> None:
        if not hasattr(self, "recent_settings"):
            return
        self.recent_settings.blockSignals(True)
        self.recent_settings.clear()
        self.recent_settings.addItem("Recent Settings...", "")
        for path in self._preferences.recent_settings_files[:5]:
            self.recent_settings.addItem(path.name, str(path))
            self.recent_settings.setItemData(
                self.recent_settings.count() - 1,
                str(path),
                Qt.ItemDataRole.ToolTipRole,
            )
        self.recent_settings.setEnabled(len(self._preferences.recent_settings_files) > 0)
        self.recent_settings.blockSignals(False)

    @staticmethod
    def _missing_logo_paths(overlays: list[dict[str, Any]]) -> list[str]:
        return missing_logo_paths(overlays)

    def _has_effective_overlay(self) -> bool:
        return has_effective_overlay(self._overlays)

    def _show_about_dev(self) -> None:
        QMessageBox.about(self, "About Dev", self._about_dev_text())

    @staticmethod
    def _about_dev_text() -> str:
        return (
            "MTPDFLogo — PDF/Image Overlay Studio\n\n"
            "Developer: Masteriii (MT)\n"
            "Role: Senior software/process engineering driven development\n"
            "Focus: Batch watermark workflow, reliable presets, and cross-platform usability\n\n"
            "Privacy note: This About page intentionally avoids personal contact details "
            "or identity-sensitive information."
        )

    def _rebuild_overlay_list(self) -> None:
        self.overlay_list.clear()
        for index, item in enumerate(self._overlays, 1):
            label = "Text" if item["type"] is OverlayType.TEXT else "Logo"
            list_item = QListWidgetItem(f"{label} {index}")
            list_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.overlay_list.addItem(list_item)
        if self.overlay_list.count():
            self.overlay_list.setCurrentRow(0)

    def _selected_model(self) -> dict[str, Any] | None:
        current = self.overlay_list.currentItem()
        if current is None:
            return None
        item_id = current.data(Qt.ItemDataRole.UserRole)
        return next((item for item in self._overlays if item["id"] == item_id), None)

    def _select_overlay_by_id(self, overlay_id: str) -> None:
        for row in range(self.overlay_list.count()):
            list_item = self.overlay_list.item(row)
            if list_item.data(Qt.ItemDataRole.UserRole) == overlay_id:
                if self.overlay_list.currentRow() != row:
                    self.overlay_list.setCurrentRow(row)
                return

    def _select_overlay(self, _row: int) -> None:
        item = self._selected_model()
        self._updating_properties = True
        if item is None:
            self.selected_item_label.setText("ยังไม่มีรายการที่เลือก — กด + Text หรือ + Logo")
            self.type_value.setText("—")
            self.text_input.clear()
            self.logo_value.setText("ยังไม่ได้เลือกไฟล์")
            self.opacity_label.setText("0%")
            self.color_button.setText("เลือกสี")
            self.color_button.setStyleSheet("")
        else:
            is_text = item["type"] is OverlayType.TEXT
            selected = self.overlay_list.currentItem()
            self.selected_item_label.setText(
                f"กำลังแก้: {selected.text() if selected else item['id']}"
            )
            self.type_value.setText("Text" if is_text else "Logo")
            self.text_input.setText(item["text"])
            self.logo_value.setText(item["asset_path"] or "ยังไม่ได้เลือกไฟล์")
            self.position.setCurrentIndex(self.position.findData(item["position"]))
            self.position_mode.setCurrentIndex(
                self.position_mode.findData(item.get("position_mode", PositionMode.PRESET))
            )
            self.x_percent.setValue(float(item.get("x_percent", 50.0)))
            self.y_percent.setValue(float(item.get("y_percent", 50.0)))
            if item["font"] and self.font.findText(item["font"]) < 0:
                self.font.addItem(item["font"])
            self.font.setCurrentText(item["font"])
            self.font_size.setValue(item["font_size"])
            self.logo_size.setValue(item["logo_size"])
            self.opacity.setValue(item["opacity"])
            self.opacity_label.setText(f"{item['opacity']}%")
            self.rotation.setValue(item["rotation"])
            self._set_color_button(item["color"])
        self._sync_property_controls(item)
        self._updating_properties = False
        self._refresh_preview()

    def _sync_property_controls(self, item: dict[str, Any] | None) -> None:
        has_item = item is not None
        is_text = has_item and item["type"] is OverlayType.TEXT
        is_logo = has_item and item["type"] is OverlayType.IMAGE
        for control in (self.position, self.opacity, self.rotation):
            control.setEnabled(has_item)
        position_mode = (
            item.get("position_mode", PositionMode.PRESET) if item else PositionMode.PRESET
        )
        is_absolute = has_item and position_mode is PositionMode.ABSOLUTE
        self.position_mode.setEnabled(has_item)
        self.x_percent.setEnabled(is_absolute)
        self.y_percent.setEnabled(is_absolute)
        self.reset_to_preset.setEnabled(is_absolute)
        self.text_input.setEnabled(is_text)
        self.font.setEnabled(is_text)
        self.font_size.setEnabled(is_text)
        self.color_button.setEnabled(is_text)
        self.logo_button.setEnabled(is_logo)
        self.logo_value.setEnabled(is_logo)
        self.logo_size.setEnabled(is_logo)

    def _set_color_button(self, color_name: str) -> None:
        color = QColor(color_name)
        red, green, blue = color.red(), color.green(), color.blue()
        contrast = "#ffffff" if (red * 299 + green * 587 + blue * 114) < 128000 else "#000000"
        self.color_button.setText(color_name)
        self.color_button.setStyleSheet(
            f"background-color: {color_name}; color: {contrast};"
        )

    def _property_changed(self, _value: Any = None) -> None:
        if self._updating_properties:
            return
        item = self._selected_model()
        if item is None:
            return
        position = self.position.currentData()
        item.update(
            text=self.text_input.text(), position=Position(str(position)),
            font=self.font.currentText(), font_size=self.font_size.value(),
            logo_size=self.logo_size.value(), opacity=self.opacity.value(),
            rotation=self.rotation.value(),
        )
        self.opacity_label.setText(f"{self.opacity.value()}%")
        self._refresh_preview()

    def _preset_position_changed(self, _value: Any = None) -> None:
        if self._updating_properties:
            return
        item = self._selected_model()
        if item is None:
            return
        position = self.position.currentData()
        item["position"] = Position(str(position))
        item["position_mode"] = PositionMode.PRESET
        self._updating_properties = True
        self.position_mode.setCurrentIndex(self.position_mode.findData(PositionMode.PRESET))
        self._updating_properties = False
        self._sync_property_controls(item)
        self._refresh_preview()

    def _position_mode_changed(self, _value: Any = None) -> None:
        if self._updating_properties:
            return
        item = self._selected_model()
        if item is None:
            return
        mode = self.position_mode.currentData()
        item["position_mode"] = PositionMode(str(mode))
        item.setdefault("x_percent", self.x_percent.value())
        item.setdefault("y_percent", self.y_percent.value())
        self._sync_property_controls(item)
        self._refresh_preview()

    def _absolute_position_changed(self, _value: Any = None) -> None:
        if self._updating_properties:
            return
        item = self._selected_model()
        if item is None:
            return
        item["position_mode"] = PositionMode.ABSOLUTE
        item["x_percent"] = self.x_percent.value()
        item["y_percent"] = self.y_percent.value()
        self._updating_properties = True
        self.position_mode.setCurrentIndex(self.position_mode.findData(PositionMode.ABSOLUTE))
        self._updating_properties = False
        self._sync_property_controls(item)
        self._refresh_preview()

    def _reset_selected_to_preset(self) -> None:
        item = self._selected_model()
        if item is None:
            return
        item["position_mode"] = PositionMode.PRESET
        self._updating_properties = True
        self.position_mode.setCurrentIndex(self.position_mode.findData(PositionMode.PRESET))
        self._updating_properties = False
        self._sync_property_controls(item)
        self._refresh_preview()

    def _choose_logo(self) -> None:
        item = self._selected_model()
        if item is None or item["type"] is not OverlayType.IMAGE:
            return
        path, _ = QFileDialog.getOpenFileName(self, "เลือก Logo", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            item["asset_path"] = path
            self.logo_value.setText(path)
            self._refresh_preview()

    def _choose_color(self) -> None:
        item = self._selected_model()
        if item is None or item["type"] is not OverlayType.TEXT:
            return
        color = QColorDialog.getColor(QColor(item["color"]), self, "เลือกสีข้อความ")
        if color.isValid():
            item["color"] = color.name()
            self._set_color_button(color.name())
            self._refresh_preview()

    def _to_specs(self) -> list[PdfOverlaySpec]:
        return overlays_to_specs(self._overlays, self._font_path)

    def _export_single(self) -> None:
        if self._source_path is None:
            QMessageBox.information(self, "ยังไม่ได้เปิดไฟล์", "กรุณาเลือกไฟล์ก่อน Export")
            return
        initial_folder = str(self._preferences.output_folder or self._source_path.parent)
        output = QFileDialog.getExistingDirectory(self, "เลือก Output Folder", initial_folder)
        if not output:
            return
        output_folder = Path(output)
        self.batch_output_folder.setText(str(output_folder))
        self._preferences.output_folder = output_folder
        save_preferences(self._preferences)
        destination = self._destination_for(self._source_path, output_folder)[1]
        jobs = [(self._source_path, destination)]
        self._populate_queue(jobs)
        self._start_export(jobs)

    def _start_pending_batch(self) -> None:
        self._refresh_batch_readiness()
        if not self._pending_batch_jobs:
            return
        jobs = list(self._pending_batch_jobs)
        if self._start_export(jobs):
            self.start_batch_action.setEnabled(False)
            self._update_queue_summary()

    def _start_export(self, jobs: list[tuple[Path, Path]]) -> bool:
        output_text = self.batch_output_folder.text().strip()
        output_root = Path(output_text) if output_text else jobs[0][1].parent
        specs = self._to_specs()
        page_text_rule = self._page_text_rule()
        preflight = preflight_batch_export(
            jobs=jobs,
            input_root=self._input_root,
            output_root=output_root,
            has_effective_overlay=self._has_effective_overlay(),
            page_filter_error=self._page_filter_error(),
            missing_logo_paths=self._missing_logo_paths(self._overlays),
            specs=specs,
            page_text_rule=page_text_rule,
            overwrite=self.overwrite_outputs.isChecked(),
            resume_enabled=self._config.resume_enabled,
        )
        if not preflight.ok:
            QMessageBox.warning(
                self,
                preflight.title or "Batch Preflight ไม่ผ่าน",
                preflight.message or "ไม่สามารถเริ่ม Batch ได้",
            )
            self._refresh_batch_readiness()
            return False
        if preflight.manifest_path is None:
            self._refresh_batch_readiness()
            return False
        self._last_export_jobs = jobs
        self._thread = QThread(self)
        self._worker = ExportWorker(
            jobs,
            specs,
            page_text_rule,
            preflight.manifest_path,
            self.worker_count.value(),
            self._config.resume_enabled,
        )
        self.cancel_action.setEnabled(True)
        self._update_pipeline("กำลังประมวลผล")
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("0% — เริ่มประมวลผล")
        self._worker.progress.connect(self._update_batch_progress)
        self._worker.file_failed.connect(
            lambda name, error: self._show_file_error(name, error)
        )
        self._worker.file_updated.connect(self._update_queue_file)
        self._worker.file_progress.connect(self._update_queue_progress)
        self._worker.finished.connect(self._export_finished)
        self._worker.failed.connect(self._export_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._export_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        return True

    def _export_finished(self, message: str) -> None:
        self.cancel_action.setEnabled(False)
        if message.startswith("ยกเลิกแล้ว"):
            self._mark_unfinished_rows_cancelled()
        self._refresh_batch_readiness()
        self.statusBar().showMessage(message)
        if self._last_export_jobs and self._source_path == self._last_export_jobs[0][1]:
            self._load_source(self._last_export_jobs[0][0], preview_overlays=True)
            self.statusBar().showMessage(
                f"เสร็จสิ้น — Settings ยังแก้ต่อได้: {self._last_export_jobs[0][1]}"
            )
        if self._is_successful_finish_message(message):
            self.batch_progress.setValue(100)
            self.batch_progress.setFormat("100% — เสร็จสิ้น")
            self._open_finished_output_folder()
        self._update_pipeline("เสร็จสิ้น — ตรวจ Output ได้แล้ว")
        QMessageBox.information(self, "เสร็จสิ้น", message)

    @staticmethod
    def _is_successful_finish_message(message: str) -> bool:
        return message.startswith("สำเร็จ") and "ล้มเหลว 0 ไฟล์" in message

    def _open_finished_output_folder(self) -> None:
        if not self.open_output_folder_on_finish.isChecked() or not self._last_export_jobs:
            return
        output_folder = self._last_export_jobs[0][1].parent
        if output_folder.exists() and output_folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_folder)))

    def _export_failed(self, message: str) -> None:
        self.cancel_action.setEnabled(False)
        self._refresh_batch_readiness()
        self.batch_progress.setFormat("Export ไม่สำเร็จ")
        self.statusBar().showMessage("Export ไม่สำเร็จ")
        self._update_pipeline("Export ไม่สำเร็จ")
        QMessageBox.critical(self, "Export ไม่สำเร็จ", message)

    def _cancel_export(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._mark_active_rows_stopping()
            self.statusBar().showMessage("กำลังหยุดหลังจากงานที่กำลังทำเสร็จ...")
            self._update_pipeline("กำลังหยุด Batch")

    def _export_thread_finished(self) -> None:
        self._worker = None
        self._thread = None

    def _show_file_error(self, source_key: str, error: str) -> None:
        self._update_queue_file(source_key, "Failed", 0)
        row = self._queue_row_for_source(source_key)
        if row is not None:
            self.queue_table.item(row, 6).setText(error)
            self.queue_table.item(row, 6).setToolTip(error)
        self.statusBar().showMessage(f"ข้าม {Path(source_key).name}: {error}")

    def _show_selected_queue_error(self) -> None:
        row = self.queue_table.currentRow()
        if row < 0:
            return
        source_item = self.queue_table.item(row, 1)
        error_item = self.queue_table.item(row, 6)
        error = error_item.text() if error_item else ""
        if not error:
            QMessageBox.information(self, "ไม่มี Error", "รายการนี้ไม่มีรายละเอียด Error")
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("รายละเอียด Error")
        dialog.setIcon(QMessageBox.Icon.Critical)
        source_name = source_item.text() if source_item else f"แถว {row + 1}"
        dialog.setText(f"ไฟล์: {source_name}")
        dialog.setInformativeText("คัดลอกข้อความด้านล่างเพื่อส่งให้ผู้พัฒนาหรือใช้ตรวจสอบต่อได้")
        dialog.setDetailedText(error)
        dialog.exec()

    def _delete_selected(self) -> None:
        row = self.overlay_list.currentRow()
        if row < 0:
            return
        item_id = self.overlay_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._overlays = [item for item in self._overlays if item["id"] != item_id]
        self.overlay_list.takeItem(row)
        self._refresh_preview()
        self._update_pipeline()

    def _zoom_preview_in(self) -> None:
        self._set_preview_zoom(self._preview_zoom * 1.25)

    def _zoom_preview_out(self) -> None:
        self._set_preview_zoom(self._preview_zoom / 1.25)

    def _fit_preview(self) -> None:
        self._set_preview_zoom(1.0)

    def _set_preview_zoom(self, zoom: float) -> None:
        self._preview_zoom = min(4.0, max(0.25, zoom))
        self._apply_preview_zoom()

    def _apply_preview_zoom(self) -> None:
        if not hasattr(self, "preview") or self._scene.sceneRect().isEmpty():
            return
        self.preview.resetTransform()
        self.preview.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if self._preview_zoom != 1.0:
            self.preview.scale(self._preview_zoom, self._preview_zoom)
        if hasattr(self, "zoom_label"):
            label = "Fit" if self._preview_zoom == 1.0 else f"{round(self._preview_zoom * 100)}%"
            self.zoom_label.setText(label)

    def _refresh_preview(self) -> None:
        self._scene.clear()
        if self._image_path is not None:
            self._update_page_controls()
            pixmap = QPixmap(str(self._image_path))
            if pixmap.isNull():
                return
            self._scene.addPixmap(pixmap)
            if self._preview_bakes_overlays:
                self._draw_preview_overlays(pixmap.width(), pixmap.height())
            self._scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self._apply_preview_zoom()
            return
        if self._document is None or self._document.page_count == 0:
            self._update_page_controls()
            self._show_empty_preview_state()
            return
        self._update_page_controls()
        page = self._document[self._preview_page_index]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        ).copy()
        self._scene.addPixmap(QPixmap.fromImage(image))
        if not self._preview_bakes_overlays:
            self._scene.setSceneRect(0, 0, pixmap.width, pixmap.height)
            self._apply_preview_zoom()
            return
        self._draw_preview_overlays(pixmap.width, pixmap.height)
        self._scene.setSceneRect(0, 0, pixmap.width, pixmap.height)
        self._apply_preview_zoom()

    def _show_empty_preview_state(self) -> None:
        self._scene.setSceneRect(0, 0, 640, 420)
        message = self._scene.addText(
            "เลือก PDF/รูปภาพ เพื่อเริ่ม\n"
            "จากนั้นเพิ่ม Text หรือ Logo แล้วลากบน preview เพื่อวางอิสระ"
        )
        message.setDefaultTextColor(QColor("#f3f4f6"))
        message.setTextWidth(460)
        font = QFont()
        font.setPointSize(14)
        message.setFont(font)
        rect = message.boundingRect()
        message.setPos((640 - rect.width()) / 2, (420 - rect.height()) / 2)
        self._apply_preview_zoom()

    def _draw_preview_overlays(self, preview_width: int, preview_height: int) -> None:
        selected = self._selected_model()
        selected_id = selected["id"] if selected else None
        for item in self._overlays:
            if item["type"] is OverlayType.TEXT:
                graphic = DraggableTextItem(item["text"], item["id"], self)
                graphic.setDefaultTextColor(QColor(item["color"]))
                graphic.setFont(self._preview_font(item["font"], item["font_size"]))
                graphic.setOpacity(item["opacity"] / 100)
                graphic.setRotation(item["rotation"])
                text_rect = graphic.boundingRect()
                x, y = self._preview_position(
                    item, text_rect.width(), text_rect.height(), preview_width, preview_height
                )
                graphic.setPos(x, y)
                graphic.setSelected(item["id"] == selected_id)
                self._scene.addItem(graphic)
            elif item["asset_path"]:
                logo = QPixmap(item["asset_path"])
                if not logo.isNull():
                    width = int(preview_width * item["logo_size"] / 100)
                    scaled_logo = logo.scaledToWidth(
                        width,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    graphic = DraggablePixmapItem(scaled_logo, item["id"], self)
                    graphic.setOpacity(item["opacity"] / 100)
                    graphic.setRotation(item["rotation"])
                    x, y = self._preview_position(
                        item,
                        graphic.boundingRect().width(),
                        graphic.boundingRect().height(),
                        preview_width,
                        preview_height,
                    )
                    graphic.setPos(x, y)
                    graphic.setSelected(item["id"] == selected_id)
                    self._scene.addItem(graphic)

    def _preview_position(
        self,
        item: dict[str, Any],
        width: float,
        height: float,
        page_width: float,
        page_height: float,
        margin: float = 20.0,
    ) -> tuple[float, float]:
        return resolve_overlay_top_left(
            page_width=page_width,
            page_height=page_height,
            overlay_width=width,
            overlay_height=height,
            position=item["position"],
            position_mode=item.get("position_mode", PositionMode.PRESET),
            x_percent=float(item.get("x_percent", 50.0)),
            y_percent=float(item.get("y_percent", 50.0)),
            margin=margin,
        )

    def _preview_item_dropped(
        self,
        overlay_id: str,
        graphic: QGraphicsTextItem | QGraphicsPixmapItem,
    ) -> None:
        scene_rect = self._scene.sceneRect()
        if scene_rect.width() <= 0 or scene_rect.height() <= 0:
            return
        item = next((overlay for overlay in self._overlays if overlay["id"] == overlay_id), None)
        if item is None:
            return
        bounding = graphic.boundingRect()
        center_x = graphic.pos().x() + bounding.width() / 2 - scene_rect.x()
        center_y = graphic.pos().y() + bounding.height() / 2 - scene_rect.y()
        x_percent, y_percent = point_to_percent(
            x=center_x,
            y=center_y,
            page_width=scene_rect.width(),
            page_height=scene_rect.height(),
        )
        item["position_mode"] = PositionMode.ABSOLUTE
        item["x_percent"] = round(x_percent, 2)
        item["y_percent"] = round(y_percent, 2)
        self._select_overlay_by_id(overlay_id)
        self._updating_properties = True
        self.position_mode.setCurrentIndex(self.position_mode.findData(PositionMode.ABSOLUTE))
        self.x_percent.setValue(item["x_percent"])
        self.y_percent.setValue(item["y_percent"])
        self._updating_properties = False
        self._sync_property_controls(item)
        self.statusBar().showMessage(
            f"วางอิสระแล้ว: X {item['x_percent']:.2f}%, Y {item['y_percent']:.2f}%"
        )

    def closeEvent(self, event: Any) -> None:
        if self._worker is not None and self.cancel_action.isEnabled():
            answer = QMessageBox.question(
                self,
                "Batch กำลังทำงาน",
                "ต้องการหยุด Batch ก่อนปิดโปรแกรมหรือไม่?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cancel_export()
            event.ignore()
            return
        if self._document:
            self._document.close()
        event.accept()
