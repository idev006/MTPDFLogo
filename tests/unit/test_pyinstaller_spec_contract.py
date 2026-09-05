from __future__ import annotations

from pathlib import Path


def test_pyinstaller_spec_uses_repo_root_and_matching_resource_layout() -> None:
    spec = Path("scripts/mtpdflogo.spec").read_text(encoding="utf-8")

    assert "project_root = Path(SPECPATH).parent.parent" in spec
    assert 'resource_root = app_root / "mtpdflogo" / "resources"' in spec
    assert '(str(resource_root / "assets"), "app/assets")' in spec
    assert '(str(resource_root / "config"), "config")' in spec
