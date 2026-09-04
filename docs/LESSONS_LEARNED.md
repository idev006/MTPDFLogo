# Lessons Learned

## 2026-09-01 Quality Audit

### Packaging Must Be Tested Like Runtime Code

The application could pass local tests while the installer path still had different resource assumptions from the source tree. Build scripts, installer scripts, and resource resolution are part of the product, not afterthoughts.

Future rule: every release branch needs a build command that runs lint, tests, creates the installer zip, and verifies the zip can create `.venv` with `py -3.12` on a clean Windows machine.

### UI Readiness Must Reflect Real Export Preconditions

Start buttons should not mean "the queue has files"; they should mean "this export can produce the intended output." Missing overlays, blank logo paths, invalid regex, unsafe output folders, and overwrite conflicts all belong in preflight.

Future rule: if a worker can fail before touching document content, catch it before the worker starts.

### Resume Logic Needs the Same Inputs as Export Logic

Resume originally checked the source file and output existence but not enough of the settings and resource state. That can skip stale output when a logo or font changes in place.

Future rule: manifest fingerprints must include every input that changes output bytes: overlay settings, page filter, logo path/stat, and font path/stat.

### Cancellation Across Processes Is a Protocol

A thread-local event does not stop child processes. Process-pool cancellation needs a process-safe signal, cooperative checks inside the processor, and incremental scheduling so queued jobs are not already committed.

Future rule: any long-running worker must have a tested cancel path before it is wired to UI controls.

### Preview And Export Need One Geometry Contract

Preview, PDF export, and image export can drift when rotation and scaling are implemented separately. The safer contract is to size content first, rotate second, then anchor by the transformed bounds.

Future rule: any positioning feature must have parity tests for preview assumptions and exported output behavior.

### Thai PDF Text Requires Unicode Normalization

Visible Thai words may extract with different Unicode forms. `จำนวนเงิน` and `จํานวนเงิน` look equivalent to users but are not the same raw string.

Future rule: user-facing text search in PDF content must normalize Unicode before comparing.

### Local Samples Are Useful, But Not CI Tests

The local sample PDF helped diagnose real behavior, but absolute local paths make tests non-portable.

Future rule: convert real-world discoveries into synthetic fixtures or committed anonymized fixtures. If a local sample is optional, mark it with `pytest.skip()` and keep it outside normal CI.

### Large UI Modules Hide Policy Drift

`main_window.py` accumulated UI controls, preview rendering, batch orchestration, manifest policy, config mapping, and resource lookup. That made small features easy to add but harder to audit.

Future rule: once a UI module owns more than one policy, extract a deeper module with a smaller interface and test that interface directly.
