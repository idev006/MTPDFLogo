from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REQUIRED_ZIP_ENTRIES = {
    "MTPDFLogo/install.bat",
    "MTPDFLogo/start.bat",
    "MTPDFLogo/start-debug.bat",
    "MTPDFLogo/README_DISTRIBUTION_TH.md",
    "MTPDFLogo/pyproject.toml",
    "MTPDFLogo/app/mtpdflogo/__main__.py",
    "MTPDFLogo/app/mtpdflogo/resources/config/app.toml",
    "MTPDFLogo/app/mtpdflogo/resources/assets/fonts/Mali/Mali-Regular.ttf",
}

FORBIDDEN_ZIP_PATTERNS = (
    "/.git/",
    "/.venv/",
    "/build/",
    "/dist/",
    "/.pytest_cache/",
    "/.ruff_cache/",
    "/__pycache__/",
    ".pyc",
    ".pyo",
    ".egg-info/",
)


@pytest.fixture()
def installer_zip(pytestconfig: pytest.Config) -> Path:
    if not pytestconfig.getoption("--run-installer-smoke"):
        pytest.skip("use --run-installer-smoke after building an installer zip")
    path = Path(str(pytestconfig.getoption("--installer-zip"))).resolve()
    if not path.exists():
        pytest.skip(f"installer zip not found: {path}")
    return path


def test_source_zip_has_clean_expected_layout(installer_zip: Path) -> None:
    with zipfile.ZipFile(installer_zip) as archive:
        names = set(archive.namelist())

    assert REQUIRED_ZIP_ENTRIES <= names
    assert {name.split("/", 1)[0] for name in names if name} == {"MTPDFLogo"}
    forbidden = [
        name
        for name in names
        if any(pattern in f"/{name}" for pattern in FORBIDDEN_ZIP_PATTERNS)
    ]
    assert forbidden == []


def test_installer_and_start_scripts_are_ci_friendly(installer_zip: Path) -> None:
    with zipfile.ZipFile(installer_zip) as archive:
        install_bat = archive.read("MTPDFLogo/install.bat").decode("utf-8")
        start_bat = archive.read("MTPDFLogo/start.bat").decode("utf-8")
        start_debug_bat = archive.read("MTPDFLogo/start-debug.bat").decode("utf-8")

    assert "MTPDFLOGO_NO_PAUSE" in install_bat
    assert ".venv\\Scripts\\pythonw.exe" in start_bat
    assert ".venv\\Scripts\\python.exe" in start_debug_bat
    assert "PYTHONPATH=%PROJECT_DIR%app" in start_bat
    assert "PYTHONPATH=%PROJECT_DIR%app" in start_debug_bat


@pytest.fixture()
def installed_source_zip(
    installer_zip: Path,
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> Path:
    digest = hashlib.sha256(installer_zip.read_bytes()).hexdigest()[:16]
    cache_option = str(pytestconfig.getoption("--installer-smoke-cache-dir"))
    cache_root = Path(cache_option).resolve() if cache_option else tmp_path
    install_root = cache_root / f"mtpdflogo-installer-smoke-{digest}"
    marker = install_root / ".installer-smoke-sha256"
    app_root = install_root / "MTPDFLogo"
    python_exe = app_root / ".venv" / "Scripts" / "python.exe"

    if (
        pytestconfig.getoption("--force-installer-reinstall")
        or not python_exe.exists()
        or not marker.exists()
        or marker.read_text(encoding="utf-8") != digest
    ):
        if install_root.exists():
            shutil.rmtree(install_root)
        install_root.mkdir(parents=True)
        with zipfile.ZipFile(installer_zip) as archive:
            archive.extractall(install_root)
        env = os.environ.copy()
        env["MTPDFLOGO_NO_PAUSE"] = "1"
        subprocess.run(
            ["cmd", "/c", "install.bat"],
            cwd=app_root,
            env=env,
            check=True,
            timeout=600,
        )
        marker.write_text(digest, encoding="utf-8")

    return app_root


@pytest.mark.installer_smoke
def test_clean_machine_install_imports_runtime_resources(installed_source_zip: Path) -> None:
    python_exe = installed_source_zip / ".venv" / "Scripts" / "python.exe"
    probe = (
        "import fitz, PySide6, PIL, mtpdflogo; "
        "from mtpdflogo.config.resources import config_path, font_directory; "
        "assert config_path().exists(), config_path(); "
        "assert font_directory().exists(), font_directory(); "
        "print('installer runtime smoke ok')"
    )

    subprocess.run([str(python_exe), "-m", "pip", "check"], cwd=installed_source_zip, check=True)
    subprocess.run([str(python_exe), "-c", probe], cwd=installed_source_zip, check=True)
