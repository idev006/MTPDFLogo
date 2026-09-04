from pathlib import Path

from mtpdflogo.application.batch import BatchJob, job_key, save_manifest
from mtpdflogo.application.export_policy import (
    file_fingerprint,
    is_resume_match,
    output_conflict_issues,
    output_root_write_error,
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
