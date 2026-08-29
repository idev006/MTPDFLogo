"""TOML configuration loader; this is the runtime configuration SSOT."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str = "MTPDFLogo"
    language: str = "th"
    preview_dpi: int = 120
    max_workers: int = 2
    progress_interval_ms: int = 500


def load_config(path: Path | None = None) -> AppConfig:
    """Load TOML settings, falling back to safe defaults."""
    if path is None:
        path = Path(__file__).resolve().parents[3] / "config" / "app.toml"
    if not path.exists():
        return AppConfig()

    with path.open("rb") as config_file:
        raw = tomllib.load(config_file)
    app = raw.get("app", {})
    performance = raw.get("performance", {})
    batch = raw.get("batch", {})
    return AppConfig(
        app_name=app.get("name", "MTPDFLogo"),
        language=app.get("language", "th"),
        preview_dpi=int(performance.get("preview_dpi", 120)),
        max_workers=max(1, int(batch.get("max_workers", 2))),
        progress_interval_ms=max(100, int(performance.get("progress_interval_ms", 500))),
    )
