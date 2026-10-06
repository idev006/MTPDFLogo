# Multi-Rule Overlay Pipeline v0.2

สถานะ: Implementing  
Branch: `codex/multi-rule-overlay-pipeline`  
SSOT owner: `docs/SSOT.md`

## Pain point

เอกสารหนึ่งไฟล์อาจมีรูปแบบหน้าหลายชนิด แต่ละชนิดต้องวาง Text/Logo คนละจำนวนและ
คนละตำแหน่ง เวอร์ชันเดิมทำได้หนึ่งเงื่อนไขต่อหนึ่งรอบ ผู้ใช้จึงต้องนำ output รอบก่อนกลับมา
เป็น input และทำซ้ำ N รอบ ซึ่งช้า เสี่ยงเลือก Settings ผิด และลดคุณภาพจากการเขียนไฟล์ซ้ำ

## Goal

ผู้ใช้กำหนด Rule Group หลายกลุ่มและ Branch แบบ `if/elif/else` ได้ จากนั้นระบบอ่าน PDF
หนึ่งครั้ง เลือก Layers ที่ถูกต้องต่อหน้า และเขียน output สุดท้ายเพียงครั้งเดียว

## Canonical example

```text
IF   count("จำนวนเงิน") in [3,3]   THEN Layers X1, X2
ELIF count("จำนวนเงิน") in [5,5]   THEN Layers X3, X4
ELIF count("จำนวนเงิน") in [7,7]   THEN Layers X5, X6
ELIF count("จำนวนเงิน") in [9,9]   THEN Layers X7, X8
ELIF count("จำนวนเงิน") in [11,11] THEN Layers X9, X10
ELSE no layers
```

`[a,b]` เป็น inclusive interval: `a <= occurrence_count <= b`.

## Domain hierarchy

```text
Project
 └─ Rule Groups [0..N]
     └─ Branches [0..N], ordered
         └─ Overlay Layers [0..N], ordered
```

### Rule Group

- Stable UUID-backed ID and user-visible name.
- `enabled`, `keyword`, `use_regex`, `case_sensitive`.
- `scope = page | document`.
- Optional `page_ranges`.
- Ordered Branches.

### Branch

- Stable UUID-backed ID and user-visible name.
- `enabled` and `is_else`.
- Inclusive `min_occurrences` and `max_occurrences` for normal branches.
- Independent Overlay Layers collection.
- First enabled matching normal Branch wins; enabled Else is fallback.

### Layer

- Text or Logo with all legacy styling/positioning controls.
- Independent `enabled`, `locked`, and `z_index`.
- Position modes remain `preset`, `absolute`, and `fixed_mm`.
- Top item in Layer panel is visually in front of lower items.

## Enabled-state contract

| Level | Disabled behavior | Data retained |
|---|---|---|
| Rule Group | Skip every Branch in the Group | Yes |
| Branch | Continue to the next Branch/Else | Yes |
| Layer | Do not preview or export that Layer | Yes |

Deleting is separate from disabling and requires explicit user intent. Disabled state is persisted.

## Evaluation algorithm

```text
Open one input document
  -> cache document text only when a document-scoped Group needs it
  -> for each page
       -> extract page text
       -> for each enabled Group
            -> count normalized keyword/regex in selected scope
            -> scan enabled Branches in order
            -> select first match, otherwise enabled Else
            -> append enabled Layers
       -> stable-sort selected Layers by z_index
       -> render selected Layers
       -> emit page progress
  -> atomic-save output once
```

Parallelism remains per input file. Rules inside one file are evaluated in the same worker to avoid
concurrent writes to one PDF.

## UI contract

Main tabs remain:

1. ออกแบบลายน้ำ
2. ไฟล์และการประมวลผล
3. ผลลัพธ์

The design workspace uses a resizable three-panel splitter:

```text
Rules / Layers | Large live preview | Selected layer properties
```

Left panel tabs:

- `เงื่อนไข`: Rule Group selector, Group settings, Decision Ladder, Branch range controls.
- `Layers`: branch-local layer list, visibility, lock, order, add/duplicate/delete.

The Preview status must state occurrence count, actual matched Branch, and Branch currently being
edited. Editing a Branch is allowed even when the current sample page matches a different Branch.

## Validation

Block export for malformed regex, malformed page ranges, invalid intervals, duplicate IDs, missing
Logo files, or no effective enabled Layer. Overlapping enabled intervals produce a visible issue;
the deterministic fallback remains first-match order.

## Persistence and migration

- Schema 5: hierarchical multi-rule TOML.
- Schemas 1-4: legacy flat overlays and optional Page Filter.
- Loading schema 1-4 does not silently rewrite it; saving in legacy mode remains compatible.
- Saving after Rule Groups are created writes schema 5.
- IDs, enabled state, lock state, layer order, positioning, fonts, opacity, rotation, and asset paths
  are persisted.

## Sequence: export

```text
User -> UI: Start Batch
UI -> Preflight: validate queue/output/rules/assets
Preflight --> UI: ready
UI -> Qt Worker: immutable RuleGroup snapshot
Qt Worker -> Headless ExportEngine: run jobs
ExportEngine -> Process Worker: one file + rule snapshot
Process Worker -> Rule Evaluator: page text + ordered groups
Rule Evaluator --> Process Worker: selected layers
Process Worker -> PDF Service: render layers and atomic save
Process Worker --> UI: real page/file progress
UI: restore controls after thread cleanup
```

## Kanban slices

- [x] Domain RuleGroup/RuleBranch records.
- [x] Pure ordered evaluator and validation.
- [x] Conditional PDF/image export integration.
- [x] Schema 5 TOML save/load.
- [x] Initial Decision Ladder and branch-local Layer editor.
- [x] Group/Branch/Layer enable state, layer lock and z-order controls.
- [x] Live matched-branch diagnostic.
- [ ] Drag reorder directly inside Layer/Branch lists.
- [ ] Undo/Redo command stack for destructive edits.
- [ ] Copy/Paste Layers across Branches and Solo preview.
- [x] Visual dual-handle 0-100 range control plus exact Min/Max spinboxes.
- [ ] Full decision-table search diagnostics across the Queue.

## Acceptance criteria

- Pages matching 3 and 5 occurrences in the same PDF receive different Branch Layers in one export.
- `[3,3]` matches exactly 3 and not 2 or 4.
- Disabling a Branch falls through without deleting its Layers.
- Disabling a Layer removes it from Preview and Export, then restoring it requires no reconfiguration.
- Multi-rule Settings round-trip without losing hierarchy/state.
- Legacy Settings and legacy Page Filter continue to pass regression tests.
- Full lint/test/coverage pipeline passes before push.
