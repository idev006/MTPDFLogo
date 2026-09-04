# Quality Remediation

## Purpose

This document records the remediation work applied after the quality audit. It is a release-readiness reference for developers maintaining MTPDFLogo.

## Release Gates

Before a Windows release, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest -q
.\build.bat
```

`pytest` is configured with coverage reporting and an initial minimum coverage gate of 75%.
The next target is to raise this to 85% after worker-level and preview/export parity tests are expanded.

The installer zip must install on a clean Windows machine, create `.venv` with `py -3.12`, and start with bundled fonts and `config/app.toml`.
The current supported delivery format is `dist/MTPDFLogo-installer.zip`, not a frozen executable.

## Fixed Risks

### Resource Resolution

Runtime resources now have a resolver in `app/mtpdflogo/config/resources.py`.

The resolver supports:

- source tree execution
- editable installs
- package installs with bundled `mtpdflogo/resources`
- zip installer layout

The zip installer contains `install.bat`, `start.bat`, source files, config, docs, and tests.
`install.bat` creates `.venv` with `py -3.12` and installs the project into that environment.
`start-debug.bat` is included for visible startup diagnostics when `start.bat` exits silently.
The Windows CI workflow runs runtime smoke, lint, pytest coverage gate, source zip build,
zip-layout verification, and explicit installer smoke with `--no-cov`.

### Output Policy

The application now reads batch policy from `config/app.toml`:

- `output_suffix`
- `overwrite`
- `resume_enabled`
- `preserve_subfolders`
- `continue_on_error`

The UI exposes overwrite explicitly. If overwrite is off, existing outputs are blocked unless the resume manifest confirms the same input and same settings fingerprint.

Output folders inside input folders are blocked to prevent recursive files such as `file-watermask-watermask.pdf`.

### Overlay Preflight

Batch export requires at least one effective overlay:

- text overlays need non-empty text
- logo overlays need an existing logo file

Logo items with blank or missing files are rejected before worker processes start.

### PDF/Image Export Correctness

PDF logo export now resizes the source logo first, rotates the resized bitmap, and caches the transformed image. Cache hits insert the cached image without a second PyMuPDF rotation.

Thai and other non-ASCII text overlays require a real font path. The application fails fast instead of silently falling back to a font that cannot render the glyphs.

### Page Filtering

Page filtering counts matches anywhere in a page text layer.

Plain text matching normalizes with Unicode NFKD and removes whitespace before matching, so Thai text such as `จำนวนเงิน` can match extracted forms such as `จํานวนเงิน`.

Regex matching normalizes the pattern and page content with Unicode NFKD. UI validation compiles the same normalized pattern used during export.

### Batch Cancellation

Batch cancellation is now cooperative:

- a process-safe cancel event is passed into worker processes
- PDF processing checks cancel per page
- image processing checks cancel before work
- the worker submits jobs incrementally instead of submitting the entire batch up front

Closing the application during an active batch asks the user to cancel first and keeps the window open while cancellation begins.

### Preview Workflow

Preview now supports:

- page selection for PDFs
- zoom in, zoom out, and fit
- Ctrl + mouse wheel zoom
- drag/drop positioning on the currently selected preview page

Clicking an overlay without moving it no longer changes the item from preset positioning to absolute positioning.

## Remaining Follow-Up

These are not release blockers after the current remediation, but they should be considered next:

- add GitHub Actions for Windows CI
- add a clean-machine zip installer smoke test
- split `main_window.py` into batch worker, preview controller, and overlay mapping modules
- add optional OCR mode for scanned PDFs with no text layer
- add visual regression tests for rotated text/logo preview parity
- raise the coverage gate from 75% to 85%, then 90%, as orchestration tests mature

Implemented in the 2026-09-05 governance pass:

- Windows CI workflow at `.github/workflows/windows-ci.yml`
- clean source zip smoke tests under `tests/smoke/`
- export policy extraction under `app/mtpdflogo/application/export_policy.py`
- build zip exclusions for `.egg-info`, cache folders, and bytecode

Still deferred:

- split `ExportWorker` and QThread/process orchestration out of `main_window.py`
- add explicit Retry Failed workflow and persisted attempt metadata
- add visual regression tests for preview/export parity
