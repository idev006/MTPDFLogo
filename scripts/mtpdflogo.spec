# PyInstaller spec: run from the repository root with the project .venv.
from pathlib import Path

project_root = Path(SPECPATH).parent
app_root = project_root / "app"

a = Analysis(
    [str(app_root / "mtpdflogo" / "__main__.py")],
    pathex=[str(app_root)],
    binaries=[],
    datas=[
        (str(app_root / "assets"), "assets"),
        (str(project_root / "config"), "config"),
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
