"""User-writable TOML preferences for convenient file selection."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class UserPreferences:
    pdf_folder: Path | None = None
    output_folder: Path | None = None


def preferences_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "MTPDFLogo" / "preferences.toml"


def load_preferences(path: Path | None = None) -> UserPreferences:
    path = path or preferences_path()
    if not path.exists():
        return UserPreferences()
    try:
        with path.open("rb") as preferences_file:
            data = tomllib.load(preferences_file)
    except (OSError, tomllib.TOMLDecodeError):
        return UserPreferences()
    paths = data.get("paths", {})
    return UserPreferences(
        pdf_folder=Path(paths["pdf_folder"]) if paths.get("pdf_folder") else None,
        output_folder=Path(paths["output_folder"]) if paths.get("output_folder") else None,
    )


def save_preferences(preferences: UserPreferences, path: Path | None = None) -> None:
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf_folder = json.dumps(str(preferences.pdf_folder) if preferences.pdf_folder else "")
    output_folder = json.dumps(
        str(preferences.output_folder) if preferences.output_folder else ""
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(f"[paths]\npdf_folder = {pdf_folder}\noutput_folder = {output_folder}\n")
    temporary_path.replace(path)
