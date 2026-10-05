"""Overlay IDs remain unique across destructive editing and legacy settings."""

from mtpdflogo.application.overlay_identity import (
    ensure_unique_overlay_ids,
    new_overlay_id,
)


def test_new_overlay_ids_remain_unique_across_many_cycles() -> None:
    ids: set[str] = set()
    for _ in range(200):
        identifier = new_overlay_id(ids)
        assert identifier.startswith("overlay-")
        assert identifier not in ids
        ids.add(identifier)


def test_normalize_preserves_first_valid_id_and_repairs_bad_ids_without_mutation() -> None:
    source = [
        {"id": "same", "text": "first"},
        {"id": "same", "text": "duplicate"},
        {"id": "", "text": "empty"},
        {"text": "missing"},
        {"id": "unique", "text": "last"},
    ]
    replacements = iter(["repaired-1", "repaired-2", "repaired-3"])

    result = ensure_unique_overlay_ids(
        source, id_factory=lambda _existing: next(replacements)
    )

    assert [item["id"] for item in result] == [
        "same", "repaired-1", "repaired-2", "repaired-3", "unique"
    ]
    assert len({item["id"] for item in result}) == len(result)
    assert source[1]["id"] == "same"
    assert "id" not in source[3]
