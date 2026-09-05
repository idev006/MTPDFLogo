from pathlib import Path

from mtpdflogo.application.batch import BatchJob, job_key, save_manifest
from mtpdflogo.application.export_policy import (
    evaluate_batch_readiness,
    file_fingerprint,
    is_resume_match,
    output_conflict_issues,
    output_root_write_error,
    preflight_batch_export,
    settings_fingerprint,
)
from mtpdflogo.domain.models import OverlayType, Position
from mtpdflogo.infrastructure.pdf.overlay_service import PageTextRule, PdfOverlaySpec


def test_settings_fingerprint_changes_when_text_changes() -> None:
    first = [
        PdfOverlaySpec(
            overlay_type=OverlayType.TEXT,
            position=Position.MIDDLE_CENTER,
            text="draft",
        )
    ]
    second = [
        PdfOverlaySpec(
            overlay_type=OverlayType.TEXT,
            position=Position.MIDDLE_CENTER,
            text="final",
        )
    ]

    assert settings_fingerprint(first, None) != settings_fingerprint(second, None)


def test_settings_fingerprint_includes_page_text_rule() -> None:
    specs = [
        PdfOverlaySpec(
            overlay_type=OverlayType.TEXT,
            position=Position.MIDDLE_CENTER,
            text="approved",
        )
    ]

    assert settings_fingerprint(specs, None) != settings_fingerprint(
        specs,
        PageTextRule(keyword="total", min_occurrences=1),
    )


def test_file_fingerprint_tracks_size_and_mtime(tmp_path: Path) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(b"logo")

    fingerprint = file_fingerprint(path)

    assert fingerprint is not None
    assert fingerprint["size"] == 4
    assert "mtime_ns" in fingerprint
    assert file_fingerprint(tmp_path / "missing.png") is None


def test_resume_match_requires_completed_same_source_and_settings(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    source.write_bytes(b"source")
    destination.parent.mkdir()
    destination.write_bytes(b"output")
    source_stat = source.stat()
    fingerprint = "same-settings"
    manifest = {
        job_key(BatchJob(source, destination)): {
            "status": "completed",
            "source_size": source_stat.st_size,
            "source_mtime_ns": source_stat.st_mtime_ns,
            "settings_fingerprint": fingerprint,
        }
    }

    assert is_resume_match(source, destination, manifest, fingerprint)
    assert not is_resume_match(source, destination, manifest, "changed-settings")


def test_output_conflict_policy_allows_resume_match(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    destination = tmp_path / "out" / "input-watermask.pdf"
    manifest_path = tmp_path / "out" / ".mtpdflogo-batch-status.json"
    source.write_bytes(b"source")
    destination.parent.mkdir()
    destination.write_bytes(b"output")
    source_stat = source.stat()
    fingerprint = "same-settings"
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

    assert (
        output_conflict_issues(
            [(source, destination)],
            manifest_path,
            fingerprint,
            overwrite=False,
            resume_enabled=True,
        )
        == []
    )
    assert output_conflict_issues(
        [(source, destination)],
        manifest_path,
        "changed-settings",
        overwrite=False,
        resume_enabled=True,
    ) == [str(destination)]
    assert (
        output_conflict_issues(
            [(source, destination)],
            manifest_path,
            "changed-settings",
            overwrite=True,
            resume_enabled=True,
        )
        == []
    )


def test_output_root_write_error_creates_writable_folder(tmp_path: Path) -> None:
    output_root = tmp_path / "new-output"

    assert output_root_write_error(output_root) is None
    assert output_root.is_dir()


def test_evaluate_batch_readiness_explains_blocking_reason() -> None:
    assert (
        evaluate_batch_readiness(
            has_jobs=False,
            is_running=False,
            page_filter_error=None,
            has_effective_overlay=True,
        ).reason
        == "missing_jobs"
    )
    assert (
        evaluate_batch_readiness(
            has_jobs=True,
            is_running=True,
            page_filter_error=None,
            has_effective_overlay=True,
        ).reason
        == "running"
    )
    assert (
        evaluate_batch_readiness(
            has_jobs=True,
            is_running=False,
            page_filter_error="bad regex",
            has_effective_overlay=True,
        ).reason
        == "invalid_page_filter"
    )
    assert evaluate_batch_readiness(
        has_jobs=True,
        is_running=False,
        page_filter_error=None,
        has_effective_overlay=True,
    ).can_start


def test_preflight_blocks_missing_jobs_before_ui_starts_worker(tmp_path: Path) -> None:
    result = preflight_batch_export(
        jobs=[],
        input_root=None,
        output_root=tmp_path / "out",
        has_effective_overlay=True,
        page_filter_error=None,
        missing_logo_paths=[],
        specs=[],
        page_text_rule=None,
        overwrite=False,
        resume_enabled=True,
    )

    assert not result.ok
    assert result.title == "ยังไม่มีไฟล์"


def test_preflight_blocks_page_filter_error(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.touch()
    result = preflight_batch_export(
        jobs=[(source, tmp_path / "out" / "input-watermask.pdf")],
        input_root=None,
        output_root=tmp_path / "out",
        has_effective_overlay=True,
        page_filter_error="ใส่คำหรือ regex",
        missing_logo_paths=[],
        specs=[],
        page_text_rule=None,
        overwrite=False,
        resume_enabled=True,
    )

    assert not result.ok
    assert result.title == "เงื่อนไขหน้ายังไม่ครบ"


def test_preflight_blocks_missing_logo_before_validation(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.touch()
    result = preflight_batch_export(
        jobs=[(source, tmp_path / "out" / "input-watermask.pdf")],
        input_root=None,
        output_root=tmp_path / "out",
        has_effective_overlay=True,
        page_filter_error=None,
        missing_logo_paths=["logo.png"],
        specs=[],
        page_text_rule=None,
        overwrite=False,
        resume_enabled=True,
    )

    assert not result.ok
    assert result.title == "Logo หาไม่พบ"
    assert "logo.png" in result.message


def test_preflight_blocks_output_inside_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = input_root / "out"
    source = input_root / "input.pdf"
    source.parent.mkdir()
    source.touch()

    result = preflight_batch_export(
        jobs=[(source, output_root / "input-watermask.pdf")],
        input_root=input_root,
        output_root=output_root,
        has_effective_overlay=True,
        page_filter_error=None,
        missing_logo_paths=[],
        specs=[],
        page_text_rule=None,
        overwrite=False,
        resume_enabled=True,
    )

    assert not result.ok
    assert result.title == "Output Folder ไม่ปลอดภัย"


def test_preflight_allows_valid_request_and_returns_manifest_contract(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    output_root = tmp_path / "out"
    specs = [
        PdfOverlaySpec(
            overlay_type=OverlayType.TEXT,
            position=Position.MIDDLE_CENTER,
            text="approved",
        )
    ]
    source.touch()

    result = preflight_batch_export(
        jobs=[(source, output_root / "input-watermask.pdf")],
        input_root=None,
        output_root=output_root,
        has_effective_overlay=True,
        page_filter_error=None,
        missing_logo_paths=[],
        specs=specs,
        page_text_rule=None,
        overwrite=False,
        resume_enabled=True,
    )

    assert result.ok
    assert result.manifest_path == output_root / ".mtpdflogo-batch-status.json"
    assert result.settings_fingerprint == settings_fingerprint(specs, None)
