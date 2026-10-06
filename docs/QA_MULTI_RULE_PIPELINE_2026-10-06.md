# QA report: Multi-Rule Overlay Pipeline v0.2

Date: 2026-10-06  
Branch: `codex/multi-rule-overlay-pipeline`

## Verified use cases

- Inclusive intervals: `[3,3]` matches exactly 3 occurrences.
- Ordered first-match `if/elif/else` semantics.
- Disabled Branch falls through while retaining its Layers.
- Disabled Rule Group produces no Layers.
- Multiple Rule Groups can contribute Layers to the same page.
- Page and document count scopes with page-range filtering.
- Overlap, invalid interval, duplicate ID, multiple Else, page-range, and regex validation.
- Different pages in one PDF select different Branch Layers and export in one pass.
- Branches own independent Layer collections.
- Layer visibility and lock state survive schema-5 TOML save/load.
- Legacy schema-1..4 presets and Page Filter remain available.
- Resume fingerprint includes Rule hierarchy, layer state, fonts, and Logo file metadata.
- Existing repeated-run, queue, search, fixed-mm, image, installer-contract, and UI regression tests.

## Automated pipeline

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests
git diff --check
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Result:

- Ruff: passed
- Diff whitespace check: passed
- Tests: 245 passed
- Skipped: 3 opt-in installer smoke tests (installer not built in this slice)
- Coverage: 81.51% (required gate: 75%)

## Release boundary

This slice implements the usable rule engine, initial Decision Ladder UI, branch-local Layers,
visibility, locking, ordering, live match diagnostics, schema-5 persistence, and export integration.
Direct drag-reorder, Undo/Redo, cross-Branch clipboard, Solo preview, and whole-Queue decision-table
diagnostics remain explicitly tracked in `docs/MULTI_RULE_OVERLAY_PIPELINE.md`; they are not silently
claimed as complete.

## Decision

Accepted as v0.2 development branch. Do not replace the stable distributable until interactive
user acceptance and installer smoke tests are completed.
