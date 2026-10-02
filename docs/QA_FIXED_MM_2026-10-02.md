# Physical positioning QA - 2026-10-02

## Result

- Windows, project Python 3.12.4, Qt offscreen: **221 passed, 3 skipped** in 38.55s.
- Branch-aware coverage: **81.59%**, above the 75% project gate.
- `python -m ruff check app tests`: passed.
- `git diff --check`: passed.
- Installer smoke tests intentionally skipped: no installer rebuilt in this slice.
- First visible-desktop UI run had a preview-height failure caused by available screen geometry;
  the same layout test passed with the deterministic offscreen platform. This is not a full
  manual desktop acceptance test or evidence of testing on other operating systems.

## Regression evidence

`tests/unit/test_fixed_mm_engine.py` covers mixed Legal/A4, 0/90/180/270 page rotations,
visible CropBox origin, bounds/filter agreement, atomic output preservation on failure,
96-dpi image coordinates, fingerprint invalidation, unchanged percent behavior, and raster reuse.

`tests/integration/test_fixed_mm_ui.py` covers percent-to-mm center conversion, control binding,
drag commit, resize commit, page switching, settings roundtrip, export mapping, bounds warning,
and independent text/logo settings. Existing mouse-event resize tests remain passing.

`tests/unit/test_fixed_mm_presets.py` covers schema 1/2/3 compatibility, invalid physical values,
independent position/size modes, and unsupported versions. The existing roundtrip expectation
now includes schema-3 default fields while retaining every original setting.

Synthetic Legal/A4 output pages were rendered with PyMuPDF and visually inspected: the colored
logo has the same center and physical width, with no clipping. Scratch renders are in ignored
`build/fixed-mm-qa`; no customer document or screenshot is included in Git.

## Read-only source investigation

The supplied 256-page PDF was opened without modification. Pages 1-2 measure 612 x 1008 pt;
pages 3-10 measure 595.32 x 841.92 pt. All first ten pages have rotation 0.
Pages 1 and 6 both pass the exact-three-occurrence rule. A read-only physical preflight with
a synthetic text spec at (100, 70) mm passed for applicable pages. This is geometry validation,
not a claim that the user's existing logo/settings were exported and visually approved.

## User operation

1. Open the source and select a text/logo item.
2. In Layout select **พิกัดคงที่ (มม.)**. X/Y measure the center from the visible top-left.
3. Drag into place or type X/Y. For logos choose **ความกว้างคงที่ (มม.)** independently.
4. Compare a Legal page with an A4 page. Fixed coordinates stay unchanged.
5. Save the TOML preset, then start Batch. Bounds violations identify the file/page.

Keep percent mode for proportional watermarks. Fixed mm does not follow a keyword if the
underlying form layout moves. Existing ZIP installers are unchanged and do not contain this slice.
