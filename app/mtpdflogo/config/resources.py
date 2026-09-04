"""Runtime resource path resolution for source and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def runtime_root() -> Path:
    """Return the application resource root for source-tree or PyInstaller runs."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str) -> Path:
    return runtime_root().joinpath(*parts)


def config_path() -> Path:
    return _first_existing(
        resource_path("config", "app.toml"),
        _package_resource_root() / "config" / "app.toml",
    )


def font_directory() -> Path:
    return _first_existing(
        resource_path("app", "assets", "fonts"),
        _package_resource_root() / "assets" / "fonts",
    )


def _package_resource_root() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


def _first_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
