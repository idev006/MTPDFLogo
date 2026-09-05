"""Headless batch export engine.

This module owns the batch processing loop, resume manifest updates, progress
events, and cooperative cancellation. It deliberately contains no Qt imports so
the behavior can be tested and reused outside the desktop UI.
"""

from __future__ import annotations

import multiprocessing
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, CancelledError, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any

from mtpdflogo.application.batch import (
    SUPPORTED_IMAGE_SUFFIXES,
    BatchJob,
    job_key,
    load_manifest,
    save_manifest,
)
from mtpdflogo.application.export_policy import settings_fingerprint
from mtpdflogo.infrastructure.image_overlay_service import apply_image_overlays
from mtpdflogo.infrastructure.pdf.overlay_service import (
    PageTextRule,
    PdfOverlaySpec,
    apply_overlays,
)

ProgressCallback = Callable[[int, str], None]
FileProgressCallback = Callable[[str, int, int], None]
FileUpdatedCallback = Callable[[str, str, int], None]
FileFailedCallback = Callable[[str, str], None]


@dataclass(slots=True)
class ExportCallbacks:
    progress: ProgressCallback | None = None
    file_progress: FileProgressCallback | None = None
    file_updated: FileUpdatedCallback | None = None
    file_failed: FileFailedCallback | None = None


@dataclass(frozen=True, slots=True)
class ExportRunResult:
    message: str
    completed: int
    failures: int
    worker_count: int
    cancelled: bool = False
    skipped: int = 0


def process_file_job(
    source: Path,
    destination: Path,
    specs: list[PdfOverlaySpec],
    page_text_rule: PageTextRule | None,
    cancel_event: Any,
    progress_queue: Any,
) -> None:
    """Top-level worker function so it is safe for Windows spawn/PyInstaller."""
    processor = (
        apply_image_overlays
        if source.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        else apply_overlays
    )
    if source.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
        processor(
            source,
            destination,
            specs,
            cancel_check=cancel_event.is_set,
            progress_callback=lambda current, total: progress_queue.put(
                (str(source), current, total)
            ),
        )
    else:
        processor(
            source,
            destination,
            specs,
            page_text_rule=page_text_rule,
            cancel_check=cancel_event.is_set,
            progress_callback=lambda current, total: progress_queue.put(
                (str(source), current, total)
            ),
        )


class ExportEngine:
    """Run independent export jobs while exposing plain-Python progress events."""

    def __init__(
        self,
        jobs: list[tuple[Path, Path]],
        specs: list[PdfOverlaySpec],
        page_text_rule: PageTextRule | None,
        manifest_path: Path,
        worker_count: int,
        resume_enabled: bool = True,
        callbacks: ExportCallbacks | None = None,
    ) -> None:
        self.jobs = jobs
        self.specs = specs
        self.page_text_rule = page_text_rule
        self.manifest_path = manifest_path
        self.worker_count = worker_count
        self.resume_enabled = resume_enabled
        self.callbacks = callbacks or ExportCallbacks()
        self.settings_fingerprint = settings_fingerprint(specs, page_text_rule)
        self.cancel_event = threading.Event()
        self.process_cancel_event: Any | None = None

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.process_cancel_event is not None:
            self.process_cancel_event.set()

    def run(self) -> ExportRunResult:
        """Run jobs while forwarding real page-level progress to callbacks."""
        total = len(self.jobs)
        completed = 0
        failures = 0
        skipped = 0
        manifest = load_manifest(self.manifest_path)
        pending_jobs: list[tuple[Path, Path]] = []
        for source, destination in self.jobs:
            key = job_key(BatchJob(source, destination))
            try:
                source_stat = source.stat()
            except OSError as error:
                failures += 1
                manifest[key] = {"status": "failed", "error": str(error)}
                save_manifest(self.manifest_path, manifest)
                self._emit_file_updated(str(source), "Failed", 0)
                self._emit_file_failed(str(source), str(error))
                continue
            record = manifest.get(key, {})
            if (
                self.resume_enabled
                and record.get("status") == "completed"
                and record.get("source_size") == source_stat.st_size
                and record.get("source_mtime_ns") == source_stat.st_mtime_ns
                and record.get("settings_fingerprint") == self.settings_fingerprint
                and destination.exists()
            ):
                completed += 1
                skipped += 1
                self._emit_file_progress(str(source), 1, 1)
                self._emit_file_updated(str(source), "Completed", 100)
            else:
                pending_jobs.append((source, destination))
        if not pending_jobs:
            return ExportRunResult(
                f"ไม่มีไฟล์ใหม่ — ข้าม {completed} ไฟล์ที่เสร็จแล้ว",
                completed=completed,
                failures=failures,
                worker_count=0,
                skipped=skipped,
            )
        worker_count = min(max(1, self.worker_count), len(pending_jobs))
        context = multiprocessing.get_context("spawn")
        with multiprocessing.Manager() as manager:
            progress_queue = manager.Queue()
            self.process_cancel_event = manager.Event()
            if self.cancel_event.is_set():
                self.process_cancel_event.set()
            with ProcessPoolExecutor(max_workers=worker_count, mp_context=context) as pool:
                completed, failures = self._run_pool(
                    pending_jobs=pending_jobs,
                    total=total,
                    completed=completed,
                    failures=failures,
                    manifest=manifest,
                    progress_queue=progress_queue,
                    pool=pool,
                )
            self.process_cancel_event = None
        if self.cancel_event.is_set():
            return ExportRunResult(
                f"ยกเลิกแล้ว: สำเร็จ {completed} ไฟล์ | Workers: {worker_count}",
                completed=completed,
                failures=failures,
                worker_count=worker_count,
                cancelled=True,
                skipped=skipped,
            )
        return ExportRunResult(
            f"สำเร็จ {completed} ไฟล์, ล้มเหลว {failures} ไฟล์ | Workers: {worker_count}",
            completed=completed,
            failures=failures,
            worker_count=worker_count,
            skipped=skipped,
        )

    def _run_pool(
        self,
        *,
        pending_jobs: list[tuple[Path, Path]],
        total: int,
        completed: int,
        failures: int,
        manifest: dict[str, dict[str, str | int]],
        progress_queue: Any,
        pool: ProcessPoolExecutor,
    ) -> tuple[int, int]:
        job_queue = list(pending_jobs)
        futures: dict[Any, tuple[Path, Path]] = {}

        def submit_next() -> Any | None:
            if self.cancel_event.is_set() or not job_queue:
                return None
            source, destination = job_queue.pop(0)
            future = pool.submit(
                process_file_job,
                source,
                destination,
                self.specs,
                self.page_text_rule,
                self.process_cancel_event,
                progress_queue,
            )
            futures[future] = (source, destination)
            return future

        for _ in range(min(max(1, self.worker_count), len(pending_jobs))):
            submit_next()
        pending = set(futures)
        while pending:
            self._drain_progress_queue(progress_queue)
            if self.cancel_event.is_set():
                self.process_cancel_event.set()
                for future in pending:
                    future.cancel()
            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                source, destination = futures[future]
                completed, failures = self._handle_finished_future(
                    future=future,
                    source=source,
                    destination=destination,
                    total=total,
                    completed=completed,
                    failures=failures,
                    manifest=manifest,
                )
                next_future = submit_next()
                if next_future is not None:
                    pending.add(next_future)
        return completed, failures

    def _drain_progress_queue(self, progress_queue: Any) -> None:
        try:
            while True:
                name, current, pages = progress_queue.get_nowait()
                self._emit_file_progress(name, current, pages)
        except Empty:
            pass

    def _handle_finished_future(
        self,
        *,
        future: Any,
        source: Path,
        destination: Path,
        total: int,
        completed: int,
        failures: int,
        manifest: dict[str, dict[str, str | int]],
    ) -> tuple[int, int]:
        key = job_key(BatchJob(source, destination))
        try:
            source_stat = source.stat()
            future.result()
        except CancelledError:
            self._emit_file_updated(str(source), "Cancelled", 0)
            return completed, failures
        except Exception as error:
            if self.cancel_event.is_set() and "batch cancelled" in str(error):
                self._emit_file_updated(str(source), "Cancelled", 0)
                return completed, failures
            failures += 1
            try:
                source_stat = source.stat()
                source_size = source_stat.st_size
                source_mtime_ns = source_stat.st_mtime_ns
            except OSError:
                source_size = 0
                source_mtime_ns = 0
            manifest[key] = {
                "status": "failed",
                "error": str(error),
                "source_size": source_size,
                "source_mtime_ns": source_mtime_ns,
                "settings_fingerprint": self.settings_fingerprint,
            }
            save_manifest(self.manifest_path, manifest)
            self._emit_file_updated(str(source), "Failed", 0)
            self._emit_file_failed(str(source), str(error))
        else:
            completed += 1
            manifest[key] = {
                "status": "completed",
                "source_size": source_stat.st_size,
                "source_mtime_ns": source_stat.st_mtime_ns,
                "settings_fingerprint": self.settings_fingerprint,
            }
            save_manifest(self.manifest_path, manifest)
            self._emit_file_progress(str(source), 1, 1)
            self._emit_file_updated(str(source), "Completed", 100)
        self._emit_progress(int((completed + failures) * 100 / total), source.name)
        return completed, failures

    def _emit_progress(self, percent: int, name: str) -> None:
        if self.callbacks.progress is not None:
            self.callbacks.progress(percent, name)

    def _emit_file_progress(self, source: str, current: int, total: int) -> None:
        if self.callbacks.file_progress is not None:
            self.callbacks.file_progress(source, current, total)

    def _emit_file_updated(self, source: str, status: str, progress: int) -> None:
        if self.callbacks.file_updated is not None:
            self.callbacks.file_updated(source, status, progress)

    def _emit_file_failed(self, source: str, error: str) -> None:
        if self.callbacks.file_failed is not None:
            self.callbacks.file_failed(source, error)
