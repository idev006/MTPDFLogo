from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_windows_source_installer_entrypoints_exist() -> None:
    expected_files = [
        "install.bat",
        "start.bat",
        "start-debug.bat",
        "build.bat",
        "README_DISTRIBUTION_TH.md",
        "pyproject.toml",
    ]

    missing = [name for name in expected_files if not (PROJECT_ROOT / name).is_file()]

    assert missing == []


def test_build_package_includes_debug_start_script() -> None:
    build_script = (PROJECT_ROOT / "build.bat").read_text(encoding="utf-8")

    assert "start-debug.bat" in build_script
    assert "pip install -e" in build_script
    assert ".[dev]" in build_script


def test_runtime_package_data_contract_keeps_fonts_and_config() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "resources/config/*.toml" in pyproject
    assert "resources/assets/fonts/**/*.ttf" in pyproject
    assert "resources/assets/fonts/**/*.txt" in pyproject
