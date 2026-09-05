# QA Test Report - MTPDFLogo

วันที่ทดสอบ: 2026-09-05 10:35 +07:00  
Branch: `feature/free-position-drag-drop`  
Commit: report is stored in the Git commit that contains this file; run `git log -1 --oneline -- docs/QA_TEST_REPORT_2026-09-05.md` to verify  
Python: 3.12.4  
Delivery artifact: `dist/MTPDFLogo-installer.zip`  
Artifact SHA256: 4D3EE35DCE369839C74DD9CA26C10EFDF8FA0DF3675999489ED0AD71F3A0C1D9

หมายเหตุ slice ล่าสุด: การปรับ Batch Workspace เป็น 2 panel ซ้าย-ขวาเป็น source-only UI refactor
ตามคำสั่งผู้ใช้ว่า “ยังไม่ต้องทำตัว install”; artifact hash ด้านบนจึงเป็น installer zip จาก release gate ก่อนหน้า
ไม่ใช่ zip ที่ rebuild จาก source commit ล่าสุด

## Executive Summary

สถานะรอบนี้: **ผ่าน release-governed quality gate สำหรับ workflow หลัก**

โปรแกรมถูกทดสอบครอบคลุม pipeline สำคัญตั้งแต่ source code quality, runtime dependency,
unit/integration workflow, coverage gate, build zip, ตรวจ zip cleanliness และ clean-machine
installer smoke จาก zip จริง

หมายเหตุสำคัญ: รายงานนี้ไม่ claim ว่าทดสอบทุก edge case 100% ของโลกจริงแล้ว
แต่ครอบคลุม use cases หลักที่เป็น acceptance criteria ของ release นี้ และบันทึก remaining risks ไว้ชัดเจน

## Quality Gates Executed

| Gate | Command | Result |
| --- | --- | --- |
| Lint | `.venv\Scripts\python.exe -m ruff check app tests` | Passed |
| Unit/Integration + coverage | `.venv\Scripts\python.exe -m pytest -q` | Passed: 140 passed, 3 skipped |
| Coverage gate | configured in `pyproject.toml` | Passed: 79.41% >= 75% |
| Build source installer zip | `build.bat` | Passed |
| Installer smoke from zip | `.venv\Scripts\python.exe -m pytest tests\smoke -q --no-cov --run-installer-smoke --installer-zip dist\MTPDFLogo-installer.zip --installer-smoke-cache-dir build\installer-smoke-cache` | Passed: 3 passed |
| Zip cleanliness | archive inspection | Passed: BAD_COUNT 0 |

## Pipeline Coverage

### Source and dependency pipeline

Covered:

- Python 3.12 venv runtime
- Runtime imports: `fitz`, `PySide6`, `PIL`, `mtpdflogo`
- `pip check` verifies no broken requirements
- package resources resolve config and bundled fonts

Evidence:

- CI workflow: `.github/workflows/windows-ci.yml`
- Resource tests: `tests/unit/test_config_loader.py`
- PyInstaller contract tests: `tests/unit/test_pyinstaller_spec_contract.py`
- Release tests: `tests/unit/test_release_package.py`
- Smoke tests: `tests/smoke/test_source_zip_installer.py`

### Core engine policy pipeline

Covered:

- batch readiness can be evaluated without PySide widgets
- preflight blocks missing jobs, invalid page filters, missing logo assets, unsafe nested output folders, invalid jobs, missing effective overlays, writeability failures, and output conflicts
- preflight returns manifest path and settings fingerprint for worker startup
- `MainWindow` now acts more like an adapter for readiness/preflight decisions
- batch export engine runs outside the Qt UI module
- Qt worker adapter maps engine callbacks to the existing signal contract
- worker process routing remains a top-level function for Windows spawn/PyInstaller compatibility

Evidence:

- `app/mtpdflogo/application/export_engine.py`
- `app/mtpdflogo/application/export_policy.py`
- `app/mtpdflogo/presentation/qt_export_worker.py`
- `tests/unit/test_export_engine.py`
- `tests/unit/test_qt_export_worker.py`
- `tests/unit/test_export_policy.py`

### PDF/image selection and batch planning

Covered:

- one input maps to one output
- no PDF merging
- PDF and image suffix discovery
- recursive folder discovery
- max-depth limit
- preserve subfolder structure
- output naming with `-watermask`
- unsupported files ignored or rejected

Evidence:

- `tests/unit/test_batch.py`
- `app/mtpdflogo/application/batch.py`

### Overlay settings and positioning

Covered:

- independent text/logo overlay model
- opacity validation
- absolute position requires valid percent coordinates
- preset positioning and absolute positioning
- preview drag updates only dragged item
- click without drag keeps preset mode
- preview geometry uses shared `point_to_percent` calculation

Evidence:

- `tests/unit/test_domain_models.py`
- `tests/unit/test_positioning.py`
- `tests/integration/test_main_window_ui.py`

### PDF export correctness

Covered:

- text overlay export
- logo overlay export
- text + logo together
- Thai/Unicode text rendered through selected real font instead of becoming question marks
- portrait/landscape geometry
- rotated logo regression
- page-level progress callback
- page text filtering by keyword/regex
- page text filtering by explicit page ranges such as `1-3,5,10-`
- page range-only filtering without keyword/regex
- search preview and export share the same page range parser
- cached normalized keyword/compiled regex reuse for large page searches
- early stop when occurrences exceed configured max count
- batch search preview summarizes matched PDF files/pages/occurrences across the queue

Evidence:

- `tests/integration/test_overlay_service.py`
- `tests/unit/test_page_search.py`
- `app/mtpdflogo/infrastructure/pdf/overlay_service.py`
- `app/mtpdflogo/application/page_search.py`

### Image export correctness

Covered:

- image watermark output
- text + logo on image
- absolute logo positioning
- output differs from source
- supported image extensions

Evidence:

- `tests/integration/test_image_overlay_service.py`
- `app/mtpdflogo/infrastructure/image_overlay_service.py`

### UI workflow and state management

Covered:

- single `เลือกไฟล์` button
- separate input folder and output folder controls
- output path can be chosen or pasted into textbox
- queue table shows rows for selected files
- batch workspace uses a two-panel layout: settings tabs on the left and queue monitor on the right
- file/output, search/page range, and processing controls remain reachable through native tabs with local scrolling
- queue actions, summary, overall progress, and queue table stay visible together in the right-side monitor panel
- input/output folder fields use longer full-width rows in the left settings panel
- numeric batch controls expose sliders synchronized with spin boxes for fast and precise adjustment
- search occurrence thresholds use one synchronized range slider plus spin boxes, preventing invalid min > max states
- queue summary uses Thai user-facing status names
- disabled `เริ่ม Batch` action explains its blocker through tooltip/status tip
- overall progress bar reports batch-level progress
- queue error details can be opened and copied from the selected row
- preview/properties empty states guide first-time users
- rows can be removed/cleared
- start button does not auto-run after selection
- start/cancel button state during and after batch
- output conflict warning
- output folder inside input folder blocked
- output folder writeability checked
- missing logo blocked before export
- no effective overlay blocked before export
- output folder auto-open preference
- About Dev dialog
- save/load/default/recent settings workflow
- user preferences isolated in tests

Evidence:

- `tests/integration/test_main_window_ui.py`
- `app/mtpdflogo/presentation/main_window.py`

### Release and installer pipeline

Covered:

- `install.bat` exists and supports non-interactive CI path
- `start.bat` exists
- `start-debug.bat` exists for visible traceback
- `install.sh` and `start.sh` exist for POSIX/Linux source zip installs
- `build.bat` installs dev dependencies before lint/test/build
- built zip contains required source/config/font files
- built zip does not contain `.venv`, cache folders, bytecode, `.egg-info`, `build/`, or `dist/`
- clean install from extracted zip creates `.venv`
- installed zip runtime imports dependencies and resources
- installer smoke uses zip SHA256 cache and can reinstall when zip changes

Evidence:

- `build.bat`
- `install.bat`
- `start.bat`
- `start-debug.bat`
- `install.sh`
- `start.sh`
- `.github/workflows/linux-ci.yml`
- `tests/smoke/test_source_zip_installer.py`
- `.github/workflows/windows-ci.yml`

## Use Cases Verified

- ผู้ใช้เลือกไฟล์เดียวแล้ว preview/export
- ผู้ใช้เลือกหลายไฟล์แล้ว batch export
- ผู้ใช้เลือก input folder พร้อม recursive/depth
- ผู้ใช้ตั้ง output folder แยกจาก input
- ผู้ใช้วาง output path ลง textbox
- ผู้ใช้เพิ่ม Text
- ผู้ใช้เพิ่ม Logo
- ผู้ใช้ใช้ Text และ Logo พร้อมกัน
- ผู้ใช้ปรับ font, size, color, opacity, rotation
- ผู้ใช้เลือกตำแหน่ง preset 9 จุด
- ผู้ใช้ลากวางตำแหน่ง absolute บน preview
- ผู้ใช้บันทึก/โหลด settings TOML
- ผู้ใช้ใช้ recent/default settings
- ผู้ใช้หยุด batch และโปรแกรมกลับสู่ state พร้อมใช้งาน
- ผู้ใช้ export PDF แนวตั้ง/แนวนอน
- ผู้ใช้ export image PNG/JPG/JPEG
- ผู้ใช้แจกจ่าย source zip แล้วติดตั้งด้วย `install.bat`
- ผู้ใช้บน Linux มี source zip entrypoint ผ่าน `install.sh` และ `start.sh`
- ผู้ใช้ทดสอบ Search/Regex กับไฟล์ preview ปัจจุบันและเห็นหน้าที่ match, จำนวนครั้ง, และเวลา
- ผู้ใช้จำกัดการวางลายน้ำด้วยช่วงหน้า เช่น `1-3,5,10-`
- ผู้ใช้ทดสอบ Search/Regex ทั้ง Queue โดยข้ามรูปภาพอย่างถูกต้อง
- ผู้ใช้เปิดรายละเอียด Error ต่อไฟล์จาก Queue ได้

## Not Fully Claimed / Remaining Risks

ยังไม่ถือว่าทดสอบครบแบบ exhaustive ในประเด็นต่อไปนี้:

- PDF ที่เข้ารหัสหรือ corrupt
- scanned PDF ที่ไม่มี text layer และต้องใช้ OCR
- corpus จริงระดับหลายพัน/หมื่นหน้าในหลายรูปแบบเอกสาร
- disk full, permission denied แบบ OS-level ที่เกิดระหว่างเขียนไฟล์จริง
- race condition ระดับสูงมากใน process pool เมื่อไฟล์ fail/ถูก cancel พร้อมกันจำนวนมาก
- visual regression แบบ pixel-perfect สำหรับ preview/export parity ทุก rotation/opacity/font
- Linux GUI smoke บน display server จริงยังไม่ถูก claim; รอบนี้ครอบคลุม Linux headless CI/import/test/launcher contract และ Qt MainWindow smoke แบบ offscreen
- regex แบบ catastrophic backtracking จาก pattern ที่ผู้ใช้กำหนดยังไม่มี timeout guard เต็มรูปแบบ

## World-class Follow-up Backlog

P1:

- เพิ่ม worker-level tests สำหรับ `ExportWorker` หลายไฟล์จริง: success, one fail, cancel, resume skip
- เพิ่ม Retry Failed workflow พร้อม attempt metadata ใน manifest
- เพิ่ม safe-regex policy หรือ timeout/process isolation สำหรับ regex ที่เสี่ยง catastrophic backtracking

P2:

- เพิ่ม visual regression golden/region assertions สำหรับตำแหน่ง, opacity, rotation
- เพิ่ม tests สำหรับ corrupt/encrypted PDF และ permission failure
- เพิ่ม Linux GUI smoke ด้วย xvfb หรือเครื่อง Linux จริง
- ยกระดับ coverage gate จาก 75% เป็น 85% แล้วค่อยไป 90%

## Verdict

MTPDFLogo ผ่าน quality gate สำหรับ release-governed Windows source zip installer แล้ว
และ workflow หลักของ PDF/image watermark batch ผ่าน automated regression suite

สถานะ: **Ready for controlled release/testing by users**
