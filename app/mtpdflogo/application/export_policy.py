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
from mtpdflogo.application.physical_preflight import (
    validate_physical_source,
    validate_rule_physical_source,
)
from mtpdflogo.application.rule_pipeline import blocking_rule_issues
from mtpdflogo.domain.rules import RuleGroup
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
    rule_groups: list[RuleGroup] | tuple[RuleGroup, ...] | None = None,
) -> BatchPreflightResult:
    """Validate an export request before the UI starts any worker threads."""
    if not jobs:
        return BatchPreflightResult(False, "ยังไม่มีไฟล์", "กรุณาเพิ่มไฟล์ลง Queue ก่อนเริ่ม Batch")
    if page_filter_error:
        return BatchPreflightResult(False, "เงื่อนไขหน้ายังไม่ครบ", page_filter_error)
    if rule_groups is not None:
        rule_issues = blocking_rule_issues(rule_groups)
        if rule_issues:
            return BatchPreflightResult(
                False,
                "Rule Pipeline ยังไม่พร้อม",
                "\n".join(rule_issues[:8]),
            )
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
    try:
        for source, _ in jobs:
            if rule_groups is not None:
                validate_rule_physical_source(source, rule_groups)
            else:
                validate_physical_source(source, specs, page_text_rule)
    except (ValueError, OSError, RuntimeError) as error:
        return BatchPreflightResult(False, "ตรวจสอบพิกัดมิลลิเมตรไม่ผ่าน", str(error))
    current_settings_fingerprint = settings_fingerprint(
        specs, page_text_rule, rule_groups=rule_groups
    )
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
    *,
    rule_groups: list[RuleGroup] | tuple[RuleGroup, ...] | None = None,
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
                "x_mm": spec.x_mm,
                "y_mm": spec.y_mm,
                "width_mm": spec.width_mm,
                "anchor_mode": spec.anchor_mode,
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
        "rule_groups": _rule_groups_payload(rule_groups),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rule_groups_payload(
    groups: list[RuleGroup] | tuple[RuleGroup, ...] | None,
) -> list[dict[str, object]] | None:
    if groups is None:
        return None
    payload: list[dict[str, object]] = []
    for group in groups:
        payload.append(
            {
                "id": group.id,
                "name": group.name,
                "keyword": group.keyword,
                "enabled": group.enabled,
                "use_regex": group.use_regex,
                "case_sensitive": group.case_sensitive,
                "page_ranges": group.page_ranges,
                "scope": str(group.scope),
                "branches": [
                    {
                        "id": branch.id,
                        "name": branch.name,
                        "enabled": branch.enabled,
                        "is_else": branch.is_else,
                        "min_occurrences": branch.min_occurrences,
                        "max_occurrences": branch.max_occurrences,
                        "overlays": [
                            _rule_overlay_payload(overlay) for overlay in branch.overlays
                        ],
                    }
                    for branch in group.branches
                ],
            }
        )
    return payload


def _rule_overlay_payload(overlay: object) -> object:
    if not isinstance(overlay, PdfOverlaySpec):
        return repr(overlay)
    return {
        "overlay_type": str(overlay.overlay_type),
        "position": str(overlay.position),
        "position_mode": str(overlay.position_mode),
        "x_percent": overlay.x_percent,
        "y_percent": overlay.y_percent,
        "x_mm": overlay.x_mm,
        "y_mm": overlay.y_mm,
        "width_mm": overlay.width_mm,
        "anchor_mode": overlay.anchor_mode,
        "text": overlay.text,
        "asset_path": str(overlay.asset_path) if overlay.asset_path else None,
        "asset_stat": file_fingerprint(overlay.asset_path),
        "font_size": overlay.font_size,
        "font_path": str(overlay.font_path) if overlay.font_path else None,
        "font_stat": file_fingerprint(overlay.font_path),
        "color": overlay.color,
        "opacity": overlay.opacity,
        "rotation": overlay.rotation,
        "width_percent": overlay.width_percent,
        "margin_pt": overlay.margin_pt,
        "enabled": overlay.enabled,
        "z_index": overlay.z_index,
    }


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
