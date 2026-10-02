# Fixed physical positioning — 2026-10-02

## Implemented contract (SSOT: docs/SSOT.md)

- Add `fixed_mm` positioning. Origin `(0,0)` is the visible page's top-left and X/Y default to the overlay's top-left, in millimeters. Existing `preset` and percent-based `absolute` remain unchanged. Schema-3 center anchors migrate explicitly.
- Logo size has an independent percent/mm choice. Text retains point size. Use 72 PDF points per inch. Raster-image physical mode uses a documented 96 dpi coordinate convention.
- Mode switching converts the current preview geometry to avoid jumping. Mouse movement and corner resizing update the same persisted fields used by export.
- Fixed coordinates must not silently clamp into the page; report an out-of-bounds error. Preflight should warn before processing applicable pages; engine remains authoritative before output write.
- Preset schema3 accepts versions1/2 unchanged. New coordinates and physical width must participate in export fingerprints.

## Parallel implementation

1. Core engineer: positioning, PDF/image engines, bounds handling, fingerprints, mixed-page regressions.
2. Settings engineer: schema3, migration compatibility, mapping and roundtrip tests.
3. Main agent: settings controls, preview conversion/drag/resize, integration review and UI tests.

Execution note: helper agents reached their usage limit. The main agent completed core/UI work,
reviewed the partial settings changes, and ran the integrated verification. No independent final
review by the helper agents is claimed.

## Acceptance

- Same fixed logo/text center on Legal and A4, independent of match count.
- Existing percent mode still scales placement with page size.
- Convert percent to mm on current preview without positional jump; moving to a different page retains physical values.
- Independent logo width units, save/load, mouse drag and resize work end to end.
- No user PDF mutation, private sample data committed, or installer rebuild in this slice.

## Workflow

```mermaid
sequenceDiagram
    actor User
    participant UI
    participant Settings as Model / TOML
    participant Preflight
    participant Engine
    User->>UI: Select fixed mm; drag or enter X/Y
    UI->>Settings: Store center in mm (not screen pixels)
    UI->>Engine: Shared physical raster for preview
    User->>UI: Start Batch
    UI->>Preflight: Specs + source files + page rule
    Preflight->>Preflight: Check bounds on matching pages
    alt Invalid bounds
        Preflight-->>UI: File/page error; do not start workers
    else Valid
        UI->>Engine: Existing batch pipeline
        Engine->>Engine: Reuse raster/xref; place per visible page
        Engine->>Engine: Atomic destination write
        Engine-->>UI: Existing progress / completion events
    end
```

## Scope limits

- Physical placement is not keyword-relative anchoring. If the form content itself moves,
  users must adjust coordinates or use separate presets.
- Converting logo mm back to percent rounds to the existing integer percent control.
- Bounds preflight currently runs synchronously; a future large-queue slice can move it to
  a cancellable worker. Raster dimensions are cached per spec/page width within each file.
- This slice does not package an installer or certify Linux execution.
