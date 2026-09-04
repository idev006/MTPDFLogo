"""Export policy helpers kept independent from the Qt presentation layer."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from mtpdflogo.application.batch import BatchJob, job_key, load_manifest
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec


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
