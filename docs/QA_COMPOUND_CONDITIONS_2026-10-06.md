# QA Report — Compound Rule Conditions v0.3.0

Date: 2026-10-06  
Branch: `codex/compound-rule-conditions`  
Scope: N conditions per IF/ELIF Branch, ALL/ANY/NOT, persistence, preview and export

## Result

PASS. The feature meets the SSOT acceptance contract and the existing legacy/single-condition
workflow remains green.

## Automated evidence

| Check | Result |
|---|---|
| Ruff over `app` and `tests` | Passed |
| Full pytest on Windows/Python 3.12.4 | 252 passed, 3 skipped |
| Branch coverage | 81.41%, above the 75% gate |
| Compileall | Passed |
| Runtime dependency import smoke | Passed |
| Headless Qt MainWindow construction | Passed |

The three skipped tests are opt-in clean-machine installer tests. No installer was built in this
slice, per project scope.

## Use cases verified

- One Branch owns 1..N independent Conditions.
- ALL requires every enabled Condition; ANY requires at least one.
- NOT reverses the inclusive-range result.
- A disabled Condition retains its settings and is ignored during evaluation.
- A normal Branch with no enabled Conditions is invalid and cannot match.
- First matching IF/ELIF wins; enabled Else remains the fallback.
- Repeated search expressions reuse a per-page count cache.
- Page- and document-scoped Conditions can coexist in one Branch.
- Invalid regex, unsafe nested quantifier, empty keyword, invalid range and duplicate IDs are
  reported by validation/preflight.
- Schema 6 preserves Condition logic, enabled state, NOT, scope, ranges and Branch Layers.
- Schema 5 loads as one editable Condition per normal Branch and saves forward as schema 6.
- A real PDF integration test confirms an Overlay is rendered only on the page matching both
  compound Conditions; nonmatching pages remain unchanged.
- Existing PDF/image, queue lifecycle, resize, fixed-mm, search/regex, preset and release package
  regression tests remain green.

## UI acceptance

- Branch and Condition are separate concepts and use separate add/delete actions.
- Condition Stack shows a readable sentence instead of programming syntax.
- AND/OR uses a named dropdown; NOT and enabled state are explicit controls.
- Selecting another Condition repopulates all controls from that Condition only.
- Preview status reports each evaluated count with pass/fail marker and the matched Branch.
- Native OS theme and the existing resizable workspace are retained.
- A 1100x650 responsive-layout regression verifies that the Rule Editor scrolls vertically and
  the final range control remains inside the Condition Stack instead of being clipped.

## Remaining backlog (not release blockers)

- Drag-reorder Branches/Conditions/Layers.
- Copy/paste Layers across Branches and Solo preview.
- Undo/Redo command stack for destructive edits.
- Queue-wide decision-table diagnostics showing the matched Branch for every page before export.
