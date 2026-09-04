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

- [ ] Replace frozen-executable delivery with a zip installer that creates `.venv` using `py -3.12`.
- [ ] Add runtime resolver for source-tree and installed source package paths.
- [ ] Route config/font loading through resolver.
- [ ] Add tests for explicit config load and fallback defaults.

### Task 2: Output Policy and Batch Preflight

**Files:**
- Modify: `app/mtpdflogo/config/loader.py`
- Modify: `app/mtpdflogo/application/batch.py`
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/unit/test_batch.py`, `tests/integration/test_main_window_ui.py`

**Interfaces:**
- Produces: `AppConfig.output_suffix`, `overwrite`, `resume_enabled`, `preserve_subfolders`
- Produces: `validate_jobs(..., overwrite: bool, input_root: Path | None, output_root: Path | None)`

- [ ] Load config fields already present in `config/app.toml`.
- [ ] Use config suffix instead of hardcoded `-watermask`.
- [ ] Block output folders inside input folders.
- [ ] Enforce overwrite policy or skip only through resume manifest.
- [ ] Validate at least one effective overlay before export.

### Task 3: Export Correctness

**Files:**
- Modify: `app/mtpdflogo/infrastructure/pdf/overlay_service.py`
- Modify: `app/mtpdflogo/infrastructure/image_overlay_service.py`
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/integration/test_overlay_service.py`, `tests/integration/test_image_overlay_service.py`

**Interfaces:**
- Consumes: `PdfOverlaySpec`
- Produces: stable logo sizing/rotation contract and safer `PageTextRule` regex handling.

- [ ] Fix cached xref rotation by pre-transforming once and inserting cache hits without `rotate=`.
- [ ] Add multi-page rotated-logo regression test.
- [ ] Validate normalized regex, not only raw regex.
- [ ] Fail fast if text font cannot be loaded for export.

### Task 4: Cancellation and UI Workflow Safety

**Files:**
- Modify: `app/mtpdflogo/presentation/main_window.py`
- Test: `tests/integration/test_main_window_ui.py`

**Interfaces:**
- Produces: process-safe cancel token passed into worker jobs.
- Produces: drag threshold so clicking does not change placement mode.

- [ ] Pass a multiprocessing-safe cancel flag into each processor.
- [ ] Submit jobs incrementally so cancel prevents new work from starting.
- [ ] Track finished/cancelled rows based on real future outcomes.
- [ ] Prevent plain click on preview item from changing preset to absolute.
- [ ] Intercept window close during active export.

### Task 5: Documentation and Lessons Learned

**Files:**
- Modify: `docs/SSOT.md`
- Create: `docs/QUALITY_REMEDIATION.md`
- Create: `docs/LESSONS_LEARNED.md`

**Interfaces:**
- Produces: release gates, known limitations, and maintenance lessons.

- [ ] Update SSOT with page filtering, regex, preview page navigation, zoom, and stricter output policy.
- [ ] Write a how-to/reference quality remediation note.
- [ ] Write lessons learned from audit and fixes.
