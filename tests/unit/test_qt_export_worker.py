from pathlib import Path

from mtpdflogo.application.export_engine import ExportRunResult
from mtpdflogo.presentation import qt_export_worker


def test_qt_export_worker_maps_engine_callbacks_to_signals(
    monkeypatch,
    qtbot,
    tmp_path: Path,
) -> None:
    class FakeEngine:
        def __init__(
            self,
            jobs,
            specs,
            page_text_rule,
            manifest_path,
            worker_count,
            resume_enabled,
            callbacks,
        ) -> None:
            self.callbacks = callbacks

        def cancel(self) -> None:
            pass

        def run(self) -> ExportRunResult:
            self.callbacks.progress(50, "input.pdf")
            self.callbacks.file_progress("input.pdf", 1, 2)
            self.callbacks.file_updated("input.pdf", "Processing", 50)
            self.callbacks.file_failed("input.pdf", "boom")
            return ExportRunResult("done", completed=1, failures=0, worker_count=1)

    monkeypatch.setattr(qt_export_worker, "ExportEngine", FakeEngine)
    worker = qt_export_worker.ExportWorker([], [], None, tmp_path / "status.json", 1)
    events: list[tuple] = []
    worker.progress.connect(lambda percent, name: events.append(("progress", percent, name)))
    worker.file_progress.connect(
        lambda name, current, total: events.append(("file_progress", name, current, total))
    )
    worker.file_updated.connect(
        lambda name, status, progress: events.append(("file_updated", name, status, progress))
    )
    worker.file_failed.connect(lambda name, error: events.append(("file_failed", name, error)))
    worker.finished.connect(lambda message: events.append(("finished", message)))

    worker.run()

    assert events == [
        ("progress", 50, "input.pdf"),
        ("file_progress", "input.pdf", 1, 2),
        ("file_updated", "input.pdf", "Processing", 50),
        ("file_failed", "input.pdf", "boom"),
        ("finished", "done"),
    ]


def test_qt_export_worker_emits_failed_when_engine_raises(
    monkeypatch,
    qtbot,
    tmp_path: Path,
) -> None:
    class FakeEngine:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def cancel(self) -> None:
            pass

        def run(self) -> ExportRunResult:
            raise RuntimeError("engine failed")

    monkeypatch.setattr(qt_export_worker, "ExportEngine", FakeEngine)
    worker = qt_export_worker.ExportWorker([], [], None, tmp_path / "status.json", 1)
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == ["engine failed"]
