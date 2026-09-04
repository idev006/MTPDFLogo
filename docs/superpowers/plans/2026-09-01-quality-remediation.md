# Quality Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise MTPDFLogo from feature-complete prototype quality to release-ready desktop-batch quality for PDF/image watermark workflows.

**Architecture:** Keep the current PySide6 application shape, but deepen the batch/export and resource modules enough to remove release-blocking risk. Use focused tests around output policy, resource resolution, cancellation, preview placement, and PDF/image geometry.

**Tech Stack:** Python 3.12, PySide6, PyMuPDF, Pillow, pytest, pytest-qt, ruff, Windows batch zip installer.

## Global Constraints

- Desktop application for Windows and Linux.
- Source code under `app/`.
- GUI uses PySide6.
- Runtime configuration uses TOML.
- PDF/Image batch outputs one output per input; no merge/combine.
- Text/logo position must be calculated from each real page/image size.
- Thai/Unicode text export must not degrade to question marks.
- Every new feature or fix must have tests.

---

### Task 1: Resource and Installer Path Correctness

**Files:**
- Modify: `build.bat`, `install.bat`, `start.bat`
- Modify: `app/mtpdflogo/config/loader.py`
- Create: `app/mtpdflogo/config/resources.py`
- Test: `tests/unit/test_config_loader.py`

**Interfaces:**
- Produces: `resource_path(*parts: str) -> Path`, `config_path() -> Path`, `font_directory() -> Path`
- Consumes: current `load_config(path: Path | None = None)`

- [x] Replace frozen-executable delivery with a zip installer that creates `.venv` using `py -3.12`.
- [x] Add runtime resolver for source-tree and installed source package paths.
- [x] Route config/font loading through resolver.
- [x] Add tests for explicit config load and fallback defaults.

### Task 2: Output Policy and Batch Preflight

**Files:**
- Modify: `app/mtpdflogo/config/loader.py`
- Modify: `app/mtpdflogo/application/batch.py`
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/unit/test_batch.py`, `tests/integration/test_main_window_ui.py`

**Interfaces:**
- Produces: `AppConfig.output_suffix`, `overwrite`, `resume_enabled`, `preserve_subfolders`
- Produces: `validate_jobs(..., overwrite: bool, input_root: Path | None, output_root: Path | None)`

- [x] Load config fields already present in `config/app.toml`.
- [x] Use config suffix instead of hardcoded `-watermask`.
- [x] Block output folders inside input folders.
- [x] Enforce overwrite policy or skip only through resume manifest.
- [x] Validate at least one effective overlay before export.

### Task 3: Export Correctness

**Files:**
- Modify: `app/mtpdflogo/infrastructure/pdf/overlay_service.py`
- Modify: `app/mtpdflogo/infrastructure/image_overlay_service.py`
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/integration/test_overlay_service.py`, `tests/integration/test_image_overlay_service.py`

**Interfaces:**
- Consumes: `PdfOverlaySpec`
- Produces: stable logo sizing/rotation contract and safer `PageTextRule` regex handling.

- [x] Fix cached xref rotation by pre-transforming once and inserting cache hits without `rotate=`.
- [x] Add multi-page rotated-logo regression test.
- [x] Validate normalized regex, not only raw regex.
- [x] Fail fast if text font cannot be loaded for export.

### Task 4: Cancellation and UI Workflow Safety

**Files:**
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/integration/test_main_window_ui.py`

**Interfaces:**
- Produces: process-safe cancel token passed into worker jobs.
- Produces: drag threshold so clicking does not change placement mode.

- [x] Pass a multiprocessing-safe cancel flag into each processor.
- [x] Submit jobs incrementally so cancel prevents new work from starting.
- [x] Track finished/cancelled rows based on real future outcomes.
- [x] Prevent plain click on preview item from changing preset to absolute.
- [x] Intercept window close during active export.

### Task 5: Documentation and Lessons Learned

**Files:**
- Modify: `docs/SSOT.md`
- Create: `docs/QUALITY_REMEDIATION.md`
- Create: `docs/LESSONS_LEARNED.md`

**Interfaces:**
- Produces: release gates, known limitations, and maintenance lessons.

- [x] Update SSOT with page filtering, regex, preview page navigation, zoom, and stricter output policy.
- [x] Write a how-to/reference quality remediation note.
- [x] Write lessons learned from audit and fixes.

## 2026-09-05 QA Governance Update

- [x] Full automated suite verified: 80 tests passing on Python 3.12.
- [x] Ruff quality gate verified.
- [x] Runtime dependency smoke verified with `pip check`.
- [x] Coverage governance introduced with an initial 75% fail-under gate.
- [x] Added `start-debug.bat` for visible startup failure diagnostics.
- [x] Updated build flow to install `[dev]` dependencies before lint/test gates.

Deferred follow-up:

- [ ] Add CI on Windows.
- [ ] Add clean-machine zip install smoke test.
- [ ] Split batch orchestration/readiness out of `main_window.py`.
- [ ] Add explicit retry-failed workflow and state-machine documentation.
