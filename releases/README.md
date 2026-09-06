# MTPDFLogo installer — 2026-09-06

[Download ZIP](MTPDFLogo-installer.zip)

## Windows

1. Install Python 3.12 with the `py` launcher (`py -3.12 --version`).
2. Extract the ZIP to a writable folder.
3. Open `MTPDFLogo/install.bat`; it creates a virtual environment and installs required libraries automatically. Internet access is required for installation.
4. Open `MTPDFLogo/start.bat` to use the application. Use `start-debug.bat` if startup fails.

Linux scripts are included: `sh install.sh`, then `sh start.sh` (Python 3.12 and venv required).

This is a source installer, not a standalone executable or offline bundle.

## Contents and verification

- Application source: `80fce0f`, including three-tab workspace, lifecycle guards and numeric progress bars.
- Distribution guide updated for the new workspace.
- Build lint passed; application tests: 150 passed, 3 installer tests deferred to the separate installer run; coverage 80.64%.
- Separate installer smoke: 3 passed in 106.35 seconds. Windows `install.bat` ran from a freshly extracted ZIP, created its own venv, installed dependencies and passed `pip check` plus resource/import probes.
- Installed-package UI startup passed offscreen, including three tabs and the native progress delegate. Linux scripts are included but were not executed on a Linux machine in this release run.
- Archive size: 2,924,044 bytes.
- SHA256: `6D7CAFAC65775D130E7E305B83367176DFE936947AA0BA5E8AD49B6129903B83`

The archive is immutable for this report. QA documents inside it describe their historical source slices; post-build installer evidence is recorded alongside the ZIP to avoid changing its checksum.
