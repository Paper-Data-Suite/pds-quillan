# Quillan #419 — Slice 5: truthful recovery completion and retry

**Baseline:** `419-recover-failed-scan-pages` at `42eb04e` (Slice 4).

This slice is a pure coordination boundary. It **does not** change Core scan
failure/resolution metadata, Quillan QR intake, the retained source, registered
routes, observations, existing submission assembler, teacher selection, menu, or CLI.

## Public API

- `recover_scan_review_page(root, failure_id, *, route_locator, target, registry)`:
  explicitly named route and target; alternatively pass `use_recorded_route=True`
  *alone* to use the latest verified historical route decision. Does not guess a
  missing QR or choose a route automatically.
- `execute_prepared_scan_recovery(root, prepared, *, registry)`:
  execute a previously selected read-only preview; execution revalidates all
  durable authority, including retained bytes and registration.
- `CompletedScanRecovery` is returned **only after** a verified observation,
  verified evidence bytes, and authoritative student submission assembly.
  Its `completion_state` is exactly `ready_for_review`, `selection_needed`, or
  `teacher_action_needed`. `reviewable=True` means the recovered evidence is
  currently selected and active, **not** that a viewer was opened or that the
  teacher accepted the submission. `observation_status` is `created` or
  `existing`; `submission_status` is `created`, `updated`, or `unchanged`.
- `ScanRecoveryExecutionError.stage` is `preflight`, `dispatch`, `persistence`,
  or `assembly`. The original error is retained as `__cause__`.
  `verified_observation_id` is set **only** after the persistence function has
  returned a verified pair. `possible_observation_path` and
  `possible_evidence_path` are diagnostic leads, not authoritative proof if
  `verified_observation_id is None`.

## Crash/retry semantics

Retry the same explicit route or deliberately request the verified recorded
route. Never infer success from `ScanResolutionMetadata.resolution_status` or
from a pending/uncertain error path. Every invocation reauthorizes through
preflight and Core, validates the original source digest, verifies the existing
observation/evidence transaction (or creates it exclusively), and reassembles
from *all* relevant observations with issuance and manifest-CAS checks.

- Failure before evidence persistence: no new recovery evidence is claimed.
- Failure during persistence: no completion receipt; preserve existing
  integrity/collision errors and possible durable paths in the chained cause.
- Failure after persistence but before manifest assembly: a verified
  observation pair exists, but no assembled/reviewable result is claimed.
- Failure after manifest installation but before acknowledgment: a new attempt
  detects the exact existing observation and unchanged manifest; it must not
  duplicate evidence or override teacher decisions.
- A duplicate candidate or teacher-controlled `needs_rescan`/`excluded` page
  is a **materialized** result requiring a separate teacher decision. Never
  silently select or reactivate it.

## Non-goals / next slices

No durable recovery-completion metadata, no changes to historical route
resolutions, no background worker, no automatic page selection, no menu or CLI.
Slice 6 reviews historical decision discovery and replay at the teacher-facing
boundary; Slice 7 integrates menu confirmation; Slice 8 integrates CLI; Slice 9
provides installed-wheel acceptance.

## Focused qualification

Run `tests/test_scan_recovery_completion_issue419.py` alongside Slice 1–4 tests,
submission assembly and transactional persistence regressions. Run Ruff, mypy,
`git diff --check`. Reserve full suite and wheel qualification for Slice 9.
