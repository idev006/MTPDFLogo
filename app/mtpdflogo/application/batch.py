"""Batch job planning primitives.

The planner deliberately keeps input PDFs independent: it never combines files.
The execution callback is injected so the same queue can be used by the GUI,
CLI, and a future process-pool worker without coupling it to Qt.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
SUPPORTED_INPUT_SUFFIXES = {".pdf", *SUPPORTED_IMAGE_SUFFIXES}


class BatchStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class BatchJob:
    source: Path
    destination: Path
    status: BatchStatus = BatchStatus.PENDING


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    source: Path | None
    message: str


def discover_pdf_files(source: Path, recursive: bool = True) -> list[Path]:
    """Return deterministic PDF input files from a file or directory."""
    if source.is_file():
        return [source] if source.suffix.lower() == ".pdf" else []
    if not source.is_dir():
        return []
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path for path in source.glob(pattern) if path.is_file())


def discover_supported_files(
    source: Path,
    recursive: bool = True,
    max_depth: int | None = None,
) -> list[Path]:
    """Return deterministic PDF/image input files from a file or directory."""
    if source.is_file():
        return [source] if source.suffix.lower() in SUPPORTED_INPUT_SUFFIXES else []
    if not source.is_dir():
        return []
    if not recursive:
        max_depth = 0
    root = source.resolve()
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in source.glob(pattern)
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES
            and _within_depth(path, root, max_depth)
        )
    )


def _within_depth(path: Path, root: Path, max_depth: int | None) -> bool:
    if max_depth is None:
        return True
    try:
        relative_parent = path.resolve().parent.relative_to(root)
    except ValueError:
        return False
    return len(relative_parent.parts) <= max(0, max_depth)


def build_jobs(
    sources: Iterable[Path],
    output_folder: Path,
    suffix: str = "_marked",
    preserve_subfolders: bool = False,
    input_root: Path | None = None,
) -> list[BatchJob]:
    """Map each source file to exactly one output file."""
    output_folder = output_folder.resolve()
    root = input_root.resolve() if input_root else None
    jobs: list[BatchJob] = []
    for source in sources:
        source = source.resolve()
        relative_parent = (
            source.parent.relative_to(root)
            if preserve_subfolders and root
            else Path()
        )
        destination_dir = output_folder / relative_parent
        destination = destination_dir / f"{source.stem}{suffix}{source.suffix.lower()}"
        jobs.append(BatchJob(source=source, destination=destination))
    return jobs


def validate_jobs(jobs: Iterable[BatchJob]) -> list[PreflightIssue]:
    """Validate a batch before any PDF is opened or written."""
    issues: list[PreflightIssue] = []
    seen_destinations: set[Path] = set()
    for job in jobs:
        if not job.source.exists():
            issues.append(PreflightIssue(job.source, "input file does not exist"))
        elif job.source.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            issues.append(PreflightIssue(job.source, "input file is not a supported PDF/image"))
        destination = job.destination.resolve()
        if destination in seen_destinations:
            issues.append(PreflightIssue(job.source, f"duplicate output: {destination}"))
        seen_destinations.add(destination)
        if job.source.resolve() == destination:
            issues.append(PreflightIssue(job.source, "output must not overwrite input"))
    return issues


def job_key(job: BatchJob) -> str:
    return f"{job.source.resolve()}::{job.destination.resolve()}"


def load_manifest(path: Path) -> dict[str, dict[str, str | int]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_manifest(path: Path, manifest: dict[str, dict[str, str | int]]) -> None:
    """Atomically persist batch status without requiring a database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        json.dump(manifest, temporary, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


class BatchRunner:
    """Run independent jobs through an injected PDF processor."""

    def __init__(self, processor: Callable[[Path, Path], None]) -> None:
        self._processor = processor

    def run(self, jobs: Iterable[BatchJob]) -> list[BatchJob]:
        results: list[BatchJob] = []
        for job in jobs:
            try:
                job.destination.parent.mkdir(parents=True, exist_ok=True)
                self._processor(job.source, job.destination)
            except Exception:
                results.append(BatchJob(job.source, job.destination, BatchStatus.FAILED))
            else:
                results.append(BatchJob(job.source, job.destination, BatchStatus.COMPLETED))
        return results
