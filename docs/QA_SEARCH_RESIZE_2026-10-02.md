# Search/export consistency and mouse resizing

## Root cause

Search preview accepted any positive occurrence count and ignored minimum/maximum thresholds.
Export applied the thresholds correctly. With maximum=2, the counter stops at 3 (max+1),
so the screenshot's 256 pages / 768 occurrences is consistent with 256 overflowing pages,
not evidence that they satisfy the requested 2..2 range. The original user PDF was not supplied.

A read-only QA subagent independently reproduced the counting/threshold mismatch and reviewed
zero/unlimited semantics. The implementation now shares `PageTextRule.matches_count` between
Search and export. Accepted-page totals remain exact, even though rejected counts may be capped.

Additional fix: upper bound 0 means unlimited for legacy UI presets. It now displays
“ไม่จำกัด”, preserves the minimum, and maps to the slider's right edge. Search summaries are
invalidated after criteria changes. No-match results explicitly say the file will not be marked.

## Mouse resizing

Select a text/logo item and drag its lower-right square. Live scaling preserves aspect ratio;
release commits to the existing size field (text 6..240, logo 1..100%). Zoom and rotation are
accounted for through scene coordinates. Existing preset/absolute placement and rotation remain.
Saved presets and export read the same fields; there is no separate display-only size.
Selection from the preview no longer destroys the item inside its mouse-press handler.

## Verification

- Ruff passed; full suite: 165 passed, 3 installer smoke tests skipped; coverage 81.07%.
- Literal and regex acceptance tests: counts 0/1/2/3/10 with exact, inclusive-zero and unlimited thresholds.
- Real PDFs: Search's page list equals pages receiving both rendered text and a logo.
- Generated 256-page Thai PDFs reproduce the screenshot-shaped case, now correctly returning zero qualifying pages for 2..2.
- Qt mouse press/move/release tests cover text and logo, rotated 30°, preset and absolute modes, and zoom 0.75/1.25.
- Resize leaves the other overlay unchanged; controls, save/load and rendered PDF output reflect the new size.
- Offscreen preview screenshot reviewed for the visible corner affordance.

This is a source update. The September installer in releases/ is unchanged and does not contain this fix.
