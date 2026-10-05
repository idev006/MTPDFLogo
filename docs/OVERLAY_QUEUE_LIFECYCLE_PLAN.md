# Overlay and queue lifecycle plan - 2026-10-02

## Problem

The application supports repeated queue runs, but new overlays used `len(overlays) + 1` as their
internal ID. Deleting a non-final item and adding another could therefore duplicate an existing ID.
Selection, dragging, resizing, and deletion all resolve by ID, so a duplicate can target the wrong
model even though the visible list looks valid.

## SSOT invariants

1. Every in-memory overlay ID is a non-empty unique string.
2. New and duplicated overlays use UUID-backed IDs; display numbering is separate from identity.
3. Loading an old or malformed preset preserves the first valid ID and repairs missing/duplicate
   IDs before the list or preview is rebuilt.
4. Selecting files or loading a folder replaces the queue. It does not clear overlays or results.
5. Clearing the queue clears jobs and input-root ownership only. It preserves overlay settings,
   output folder, editable preview, and the latest result snapshot.
6. Queue-changing commands are rejected while a worker/thread owns the run. After thread cleanup,
   controls are recalculated from current state and are ready for the next run.
7. The remembered input and output folders are visible after application startup; neither folder
   is scanned until the user explicitly selects files or clicks load.

## Implementation slices

- Application: pure unique-ID allocation/repair helper.
- Presentation: use the helper for add, duplicate, preset load/list rebuild, and show remembered
  input folder.
- Tests: delete-middle/add, malformed preset repair, repeated folder replacement, queue-state
  reset, settings roundtrip, and existing two-run export regression.

## Acceptance

- Repeating delete/add at least 100 times never creates duplicate IDs.
- Editing/deleting a newly added item cannot change an older item.
- Loading duplicate IDs results in unique models and unique list item data.
- Loading folder B after folder A leaves only B files in the queue while overlays remain intact.
- Full test suite, lint, and diff checks pass before commit/push.
