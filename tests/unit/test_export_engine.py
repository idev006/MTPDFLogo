from pathlib import Path

from mtpdflogo.application.batch import BatchJob, job_key, load_manifest, save_manifest
from mtpdflogo.application.export_engine import (
    ExportCallbacks,
    ExportEngine,
    process_file_job,
)
from mtpdflogo.application.export_policy import settings_fingerprint
from mtpdflogo.domain.models import OverlayType, Position
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec


class FakeCancelEvent:
    def __init__(self) -> None:
        self.was_checked = False

    def is_set(self) -> bool:
        self.was_checked = True
        return False


class FakeProgressQueue:
    def __init__(self) -> None:
        self.items: list[tuple[str, int, int]] = []

    def put(self, item: tuple[str, int, int]) -> None:
        self.items.append(item)


def _text_spec() -> PdfOverlaySpec:
    return PdfOverlaySpec(
        overlay_type=OverlayType.TEXT,
        position=Position.MIDDLE_CENTER,
        text="approved",
    )


def test_process_file_job_routes_pdf_processor(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out.pdf"
    rule = PageTextRule(keyword="total")
    cancel_event = FakeCancelEvent()
    progress_queue = FakeProgressQueue()
    calls: list[tuple[Path, Path, PageTextRule | None]] = []

    def fake_apply_overlays(
        source_path,
        destination_path,
        specs,
        *,
        page_text_rule,
        cancel_check,
        progress_callback,
    ) -> None:
        calls.append((source_path, destination_path, page_text_rule))
        assert specs == [_text_spec()]
        assert not cancel_check()
        progress_callback(2, 3)

    monkeypatch.setattr("mtpdflogo.application.export_engine.apply_overlays", fake_apply_overlays)

    process_file_job(source, destination, [_text_spec()], rule, cancel_event, progress_queue)

    assert calls == [(source, destination, rule)]
    assert cancel_event.was_checked
    assert progress_queue.items == [(str(source), 2, 3)]


def test_process_file_job_routes_image_processor(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "input.PNG"
    destination = tmp_path / "out.png"
    cancel_event = FakeCancelEvent()
    progress_queue = FakeProgressQueue()
    calls: list[tuple[Path, Path]] = []

    def fake_apply_image_overlays(
        source_path,
        destination_path,
        specs,
        *,
        cancel_check,
        progress_callback,
    ) -> None:
        calls.append((source_path, destination_path))
        assert specs == [_text_spec()]
        assert not cancel_check()
        progress_callback(1, 1)

    monkeypatch.setattr(
        "mtpdflogo.application.export_engine.apply_image_overlays",
        fake_apply_image_overlays,
    )

    process_file_job(source, destination, [_text_spec()], None, cancel_event, progress_queue)

    assert calls == [(source, destination)]
    assert progress_queue.items == [(str(source), 1, 1)]


def test_export_engine_resume_skip_emits_completed_without_process_pool(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    manifest_path = tmp_path / "out" / ".mtpdflogo-batch-status.json"
    source.write_bytes(b"source")
    destination.parent.mkdir()
    destination.write_bytes(b"output")
    source_stat = source.stat()
    specs = [_text_spec()]
    fingerprint = settings_fingerprint(specs, None)
    save_manifest(
        manifest_path,
        {
            job_key(BatchJob(source, destination)): {
                "status": "completed",
                "source_size": source_stat.st_size,
                "source_mtime_ns": source_stat.st_mtime_ns,
                "settings_fingerprint": fingerprint,
            }
        },
    )
    file_updates: list[tuple[str, str, int]] = []
    file_progress: list[tuple[str, int, int]] = []

    result = ExportEngine(
        [(source, destination)],
        specs,
        None,
        manifest_path,
        worker_count=8,
        callbacks=ExportCallbacks(
            file_updated=lambda name, status, progress: file_updates.append(
                (name, status, progress)
            ),
            file_progress=lambda name, current, total: file_progress.append(
                (name, current, total)
            ),
        ),
    ).run()

    assert result.message == "ไม่มีไฟล์ใหม่ — ข้าม 1 ไฟล์ที่เสร็จแล้ว"
    assert result.completed == 1
    assert result.skipped == 1
    assert result.worker_count == 0
    assert file_updates == [(str(source), "Completed", 100)]
    assert file_progress == [(str(source), 1, 1)]


def test_export_engine_source_stat_failure_is_isolated(tmp_path: Path) -> None:
    source = tmp_path / "missing.pdf"
    destination = tmp_path / "out" / "missing-watermask.pdf"
    manifest_path = tmp_path / "out" / ".mtpdflogo-batch-status.json"
    failures: list[tuple[str, str]] = []
    updates: list[tuple[str, str, int]] = []

    result = ExportEngine(
        [(source, destination)],
        [_text_spec()],
        None,
        manifest_path,
        worker_count=2,
        callbacks=ExportCallbacks(
            file_updated=lambda name, status, progress: updates.append(
                (name, status, progress)
            ),
            file_failed=lambda name, error: failures.append((name, error)),
        ),
    ).run()

    manifest = load_manifest(manifest_path)
    assert result.failures == 1
    assert updates == [(str(source), "Failed", 0)]
    assert failures and failures[0][0] == str(source)
    assert manifest[job_key(BatchJob(source, destination))]["status"] == "failed"
