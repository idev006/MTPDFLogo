"""Stable overlay identity rules independent from Qt and preset storage."""

from collections.abc import Callable, Iterable
from typing import Any
from uuid import uuid4


def new_overlay_id(existing_ids: Iterable[object] = ()) -> str:
    """Return a UUID-backed ID that is not present in ``existing_ids``."""
    existing = {str(value) for value in existing_ids if value is not None}
    while True:
        candidate = f"overlay-{uuid4().hex}"
        if candidate not in existing:
            return candidate


def ensure_unique_overlay_ids(
    overlays: Iterable[dict[str, Any]],
    *,
    id_factory: Callable[[Iterable[object]], str] = new_overlay_id,
) -> list[dict[str, Any]]:
    """Copy overlays and repair missing or duplicate IDs while preserving valid IDs."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in overlays:
        copied = dict(item)
        candidate = str(copied.get("id", "")).strip()
        if not candidate or candidate in seen:
            candidate = id_factory(seen)
        copied["id"] = candidate
        seen.add(candidate)
        normalized.append(copied)
    return normalized
