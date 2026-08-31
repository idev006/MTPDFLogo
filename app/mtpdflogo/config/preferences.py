"""User-writable TOML preferences for convenient file selection."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MAX_RECENT_SETTINGS = 5


@dataclass(slots=True)
class UserPreferences:
    pdf_folder: Path | None = None
    output_folder: Path | None = None
    settings_folder: Path | None = None
    default_settings_file: Path | None = None
    recent_settings_files: list[Path] = field(default_factory=list)
    open_output_folder_on_finish: bool = False

    def remember_settings_file(self, path: Path) -> None:
        resolved = path.resolve()
        self.settings_folder = resolved.parent
        self.recent_settings_files = [
            item for item in self.recent_settings_files if item.resolve() != resolved
        ]
        self.recent_settings_files.insert(0, resolved)
        self.recent_settings_files = self.recent_settings_files[:MAX_RECENT_SETTINGS]


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
    behavior = data.get("behavior", {})
    recent = data.get("recent", {})
    return UserPreferences(
        pdf_folder=Path(paths["pdf_folder"]) if paths.get("pdf_folder") else None,
        output_folder=Path(paths["output_folder"]) if paths.get("output_folder") else None,
        settings_folder=Path(paths["settings_folder"]) if paths.get("settings_folder") else None,
        default_settings_file=(
            Path(paths["default_settings_file"]) if paths.get("default_settings_file") else None
        ),
        recent_settings_files=[
            Path(value) for value in recent.get("settings_files", []) if value
        ][:MAX_RECENT_SETTINGS],
        open_output_folder_on_finish=bool(
            behavior.get("open_output_folder_on_finish", False)
        ),
    )


def save_preferences(preferences: UserPreferences, path: Path | None = None) -> None:
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf_folder = json.dumps(str(preferences.pdf_folder) if preferences.pdf_folder else "")
    output_folder = json.dumps(
        str(preferences.output_folder) if preferences.output_folder else ""
    )
    settings_folder = json.dumps(
        str(preferences.settings_folder) if preferences.settings_folder else ""
    )
    default_settings_file = json.dumps(
        str(preferences.default_settings_file) if preferences.default_settings_file else ""
    )
    recent_settings_files = ", ".join(
        json.dumps(str(path), ensure_ascii=False)
        for path in preferences.recent_settings_files[:MAX_RECENT_SETTINGS]
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(
            "[paths]\n"
            f"pdf_folder = {pdf_folder}\n"
            f"output_folder = {output_folder}\n"
            f"settings_folder = {settings_folder}\n"
            f"default_settings_file = {default_settings_file}\n"
            "\n[recent]\n"
            f"settings_files = [{recent_settings_files}]\n"
            "\n[behavior]\n"
            "open_output_folder_on_finish = "
            f"{str(preferences.open_output_folder_on_finish).lower()}\n"
        )
    temporary_path.replace(path)
