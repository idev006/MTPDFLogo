# QA report: repeated queue and overlay lifecycle

Date: 2026-10-06  
Branch: `feature/free-position-drag-drop`

## Scope

- Add, duplicate, delete, and add overlays again without duplicate internal IDs.
- Repair missing or duplicate overlay IDs when loading old/malformed presets.
- Replace queue contents when a new input folder is loaded while preserving overlays.
- Run a second export without clearing the queue or restarting the application.
- Preserve the latest result snapshot when the active queue is cleared.
- Restore controls after worker/thread cleanup.
- Show remembered input/output folder paths without automatically scanning either folder.

## Automated evidence

Command:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Result:

- 232 passed
- 3 skipped installer smoke tests (opt-in; no installer was built in this slice)
- Coverage: 81.39% (required: 75%)
- Ruff: passed
- `git diff --check`: passed

## Lifecycle decision

- Selecting files or loading a folder replaces the active queue.
- Clearing the queue does not delete overlay settings, output folder, or the latest results.
- Loading settings replaces the overlay collection after repairing its identities.
- A completed/cancelled run becomes reusable only after thread cleanup; readiness is then
  recalculated from the current queue, overlays, and output settings.
- Queue-changing operations remain blocked while a run owns the worker/thread.

## Status

Accepted for integration. Installer packaging was intentionally outside this change.
