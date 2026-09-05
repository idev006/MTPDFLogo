# PyInstaller spec: run from the repository root with the project .venv.
from pathlib import Path

project_root = Path(SPECPATH).parent.parent
app_root = project_root / "app"
resource_root = app_root / "mtpdflogo" / "resources"

a = Analysis(
    [str(app_root / "mtpdflogo" / "__main__.py")],
    pathex=[str(app_root)],
    binaries=[],
    datas=[
        (str(resource_root / "assets"), "app/assets"),
        (str(resource_root / "config"), "config"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mtpdflogo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
