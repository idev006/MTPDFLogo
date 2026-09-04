from pathlib import Path

from mtpdflogo.config.loader import AppConfig, load_config
from mtpdflogo.config.resources import config_path, font_directory


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
