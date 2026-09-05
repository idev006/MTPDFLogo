"""Export policy helpers kept independent from the Qt presentation layer."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mtpdflogo.application.batch import (
    BatchJob,
    job_key,
    load_manifest,
    output_is_inside_input,
    validate_jobs,
)
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec


@dataclass(frozen=True, slots=True)
class BatchReadiness:
    can_start: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BatchPreflightResult:
    ok: bool
    title: str | None = None
    message: str | None = None
    manifest_path: Path | None = None
    settings_fingerprint: str | None = None


def evaluate_batch_readiness(
    *,
    has_jobs: bool,
    is_running: bool,
    page_filter_error: str | None,
    has_effective_overlay: bool,
) -> BatchReadiness:
    """Return the start-button readiness decision without depending on Qt widgets."""
    if is_running:
        return BatchReadiness(False, "running")
    if not has_jobs:
        return BatchReadiness(False, "missing_jobs")
    if page_filter_error is not None:
        return BatchReadiness(False, "invalid_page_filter")
    if not has_effective_overlay:
        return BatchReadiness(False, "missing_overlay")
    return BatchReadiness(True, "ready")


def preflight_batch_export(
    *,
    jobs: list[tuple[Path, Path]],
    input_root: Path | None,
    output_root: Path,
    has_effective_overlay: bool,
    page_filter_error: str | None,
    missing_logo_paths: list[str],
    specs: list[PdfOverlaySpec],
    page_text_rule: PageTextRule | None,
    overwrite: bool,
    resume_enabled: bool,
) -> BatchPreflightResult:
    """Validate an export request before the UI starts any worker threads."""
    if not jobs:
        return BatchPreflightResult(False, "ยังไม่มีไฟล์", "กรุณาเพิ่มไฟล์ลง Queue ก่อนเริ่ม Batch")
    if page_filter_error:
        return BatchPreflightResult(False, "เงื่อนไขหน้ายังไม่ครบ", page_filter_error)
    if missing_logo_paths:
        return BatchPreflightResult(
            False,
            "Logo หาไม่พบ",
            "กรุณาเลือกไฟล์ Logo ใหม่ก่อน Export:\n" + "\n".join(missing_logo_paths[:8]),
        )
    issues = validate_jobs(BatchJob(source, destination) for source, destination in jobs)
    if issues:
        details = "\n".join(f"{issue.source}: {issue.message}" for issue in issues)
        return BatchPreflightResult(False, "Batch Preflight ไม่ผ่าน", details)
    if output_is_inside_input(input_root, output_root):
        return BatchPreflightResult(
            False,
            "Output Folder ไม่ปลอดภัย",
            "Output Folder ต้องไม่อยู่ภายใน Input Folder เพื่อกันการประมวลผลไฟล์ output ซ้ำ",
        )
    if not has_effective_overlay:
        return BatchPreflightResult(
            False,
            "ยังไม่มี Overlay",
            "กรุณาเพิ่มข้อความหรือเลือกไฟล์ Logo ก่อน Export",
        )
    write_error = output_root_write_error(output_root)
    if write_error:
        return BatchPreflightResult(
            False,
            "Output Folder เขียนไม่ได้",
            f"ไม่สามารถเขียนไฟล์ทดสอบใน Output Folder ได้:\n{write_error}",
        )
    current_settings_fingerprint = settings_fingerprint(specs, page_text_rule)
    manifest_path = output_root / ".mtpdflogo-batch-status.json"
    output_conflicts = output_conflict_issues(
        jobs,
        manifest_path,
        current_settings_fingerprint,
        overwrite=overwrite,
        resume_enabled=resume_enabled,
    )
    if output_conflicts:
        return BatchPreflightResult(
            False,
            "Output มีอยู่แล้ว",
            "พบ output เดิมและยังไม่ได้เปิดเขียนทับ:\n"
            + "\n".join(output_conflicts[:8]),
        )
    return BatchPreflightResult(
        True,
        manifest_path=manifest_path,
        settings_fingerprint=current_settings_fingerprint,
    )


def settings_fingerprint(
    specs: list[PdfOverlaySpec],
    page_text_rule: PageTextRule | None,
) -> str:
    """Return a stable fingerprint for resume-safe batch decisions."""
    payload = {
        "overlays": [
            {
                "overlay_type": str(spec.overlay_type),
                "position": str(spec.position),
                "position_mode": str(spec.position_mode),
                "x_percent": spec.x_percent,
                "y_percent": spec.y_percent,
                "text": spec.text,
                "asset_path": str(spec.asset_path) if spec.asset_path else None,
                "asset_stat": file_fingerprint(spec.asset_path),
                "font_size": spec.font_size,
                "font_path": str(spec.font_path) if spec.font_path else None,
                "font_stat": file_fingerprint(spec.font_path),
                "color": spec.color,
                "opacity": spec.opacity,
                "rotation": spec.rotation,
                "width_percent": spec.width_percent,
                "margin_pt": spec.margin_pt,
                "enabled": spec.enabled,
                "z_index": spec.z_index,
            }
            for spec in specs
        ],
        "page_text_rule": (
            {
                "keyword": page_text_rule.keyword,
                "min_occurrences": page_text_rule.min_occurrences,
                "max_occurrences": page_text_rule.max_occurrences,
                "case_sensitive": page_text_rule.case_sensitive,
                "use_regex": page_text_rule.use_regex,
                "page_ranges": page_text_rule.page_ranges,
            }
            if page_text_rule
            else None
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_fingerprint(path: Path | None) -> dict[str, int] | None:
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def is_resume_match(
    source: Path,
    destination: Path,
    manifest: dict[str, dict[str, str | int]],
    current_settings_fingerprint: str,
) -> bool:
    """Return True when an existing output can be safely treated as already done."""
    try:
        source_stat = source.stat()
    except OSError:
        return False
    record = manifest.get(job_key(BatchJob(source, destination)), {})
    return (
        record.get("status") == "completed"
        and record.get("source_size") == source_stat.st_size
        and record.get("source_mtime_ns") == source_stat.st_mtime_ns
        and record.get("settings_fingerprint") == current_settings_fingerprint
    )


def output_conflict_issues(
    jobs: list[tuple[Path, Path]],
    manifest_path: Path,
    current_settings_fingerprint: str,
    *,
    overwrite: bool,
    resume_enabled: bool,
) -> list[str]:
    """List existing outputs that must block export before any write starts."""
    if overwrite:
        return []
    manifest = load_manifest(manifest_path) if resume_enabled else {}
    issues: list[str] = []
    for source, destination in jobs:
        if not destination.exists():
            continue
        if resume_enabled and is_resume_match(
            source,
            destination,
            manifest,
            current_settings_fingerprint,
        ):
            continue
        issues.append(str(destination))
    return issues


def output_root_write_error(output_root: Path) -> str | None:
    """Return an OS error message if output_root cannot be created or written."""
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_root, delete=True):
            pass
    except OSError as error:
        return str(error)
    return None
