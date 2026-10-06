"""Qt adapter for the headless export engine."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from mtpdflogo.application.export_engine import ExportCallbacks, ExportEngine
from mtpdflogo.domain.rules import RuleGroup
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec


class ExportWorker(QObject):
    progress = Signal(int, str)
    file_progress = Signal(str, int, int)
    file_updated = Signal(str, str, int)
    file_failed = Signal(str, str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        jobs: list[tuple[Path, Path]],
        specs: list[PdfOverlaySpec],
        page_text_rule: PageTextRule | None,
        manifest_path: Path,
        worker_count: int,
        resume_enabled: bool = True,
        rule_groups: list[RuleGroup] | tuple[RuleGroup, ...] | None = None,
    ) -> None:
        super().__init__()
        options = {
            "callbacks": ExportCallbacks(
                progress=self.progress.emit,
                file_progress=self.file_progress.emit,
                file_updated=self.file_updated.emit,
                file_failed=self.file_failed.emit,
            )
        }
        if rule_groups is not None:
            options["rule_groups"] = rule_groups
        self._engine = ExportEngine(
            jobs,
            specs,
            page_text_rule,
            manifest_path,
            worker_count,
            resume_enabled,
            **options,
        )

    def cancel(self) -> None:
        self._engine.cancel()

    def run(self) -> None:
        try:
            result = self._engine.run()
        except Exception as error:  # pragma: no cover - worker/UI boundary
            self.failed.emit(str(error))
            return
        self.finished.emit(result.message)
