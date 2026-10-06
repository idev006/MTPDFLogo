# Agile Kanban — Compound Conditions

Date: 2026-10-06  
Branch: `codex/compound-rule-conditions`

## Definition of Ready

- SSOT defines AND/OR/NOT, empty-condition behavior, scope, migration, and first-match semantics.
- Existing v0.2 branch is committed, pushed, and green.
- Schema-5 compatibility and legacy schema-1..4 behavior are protected by tests.

## Backlog

| ID | Slice | Acceptance |
|---|---|---|
| CC-01 | Done | RuleCondition + ConditionLogic are immutable and serializable |
| CC-02 | Done | N conditions support ALL/ANY/NOT with cached counts |
| CC-03 | Done | Invalid ranges/regex/empty active stacks block preflight |
| CC-04 | Done | Schema 6 round-trip; schema 5 migrates without data loss |
| CC-05 | Done | Condition Stack add/delete/enable/select, ALL/ANY and NOT controls |
| CC-06 | Done | Show each condition count/result and matched Branch |
| CC-07 | Done | Different compound branches render correct layers in one output |
| CC-08 | Done | Ruff, full pytest, coverage gate, startup smoke |

## Evidence

- Ruff: passed.
- Full pytest: 252 passed, 3 installer-only tests skipped.
- Branch coverage: 81.41% (gate 75%).
- Windows runtime and headless Qt MainWindow smoke: passed.
- Detailed report: `docs/QA_COMPOUND_CONDITIONS_2026-10-06.md`.

## Work in progress policy

- Execute in ID order because every downstream slice consumes the previous contract.
- Maximum one architectural slice and one test/document slice in progress.
- A slice moves to Done only with automated evidence and SSOT alignment.

## Definition of Done

- Every acceptance item is tested headlessly where possible.
- UI behavior is covered by pytest-qt.
- Existing single-condition schema 5 opens as editable one-condition Branches.
- Full suite and coverage gate pass.
- QA report records exact evidence and known remaining backlog.
