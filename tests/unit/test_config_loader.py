from pathlib import Path

from mtpdflogo.config.loader import AppConfig, load_config
from mtpdflogo.config.resources import _first_existing, config_path, font_directory, runtime_root


def test_load_config_reads_batch_policy_fields(tmp_path: Path) -> None:
    config = tmp_path / "app.toml"
    config.write_text(
        """
[app]
name = "Custom"
language = "th"

[batch]
max_workers = 4
continue_on_error = false
resume_enabled = false
overwrite = true
output_suffix = "-signed"
preserve_subfolders = false

[performance]
preview_dpi = 144
progress_interval_ms = 250
""",
        encoding="utf-8",
    )

    loaded = load_config(config)

    assert loaded == AppConfig(
        app_name="Custom",
        language="th",
        preview_dpi=144,
        max_workers=4,
        progress_interval_ms=250,
        continue_on_error=False,
        resume_enabled=False,
        overwrite=True,
        output_suffix="-signed",
        preserve_subfolders=False,
    )


def test_default_resource_paths_point_to_repository_files() -> None:
    assert config_path().name == "app.toml"
    assert config_path().exists()
    assert font_directory().name == "fonts"
    assert font_directory().exists()


def test_runtime_root_uses_frozen_meipass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

    assert runtime_root() == tmp_path


def test_first_existing_returns_first_candidate_when_none_exist(tmp_path: Path) -> None:
    first = tmp_path / "missing-first"
    second = tmp_path / "missing-second"

    assert _first_existing(first, second) == first
