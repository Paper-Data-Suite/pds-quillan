# Issue #419 — Slice 1: Retained-page recovery preflight

## Scope

`quillan.scan_recovery_preflight.prepare_scan_review_recovery()` builds a
**read-only** preview of one exact Quillan-owned Core-v2 routing failure and
one explicit current registered response-page route. Alternatively, with
`use_recorded_route=True`, it reuses the latest strictly verified historical
`route_selected` / `route_corrected` resolution. The old route decision is
**not** treated as proof that any evidence was recovered.

The preflight checks Core's canonical failure/resolution provenance, original
retained-source identity and SHA-256, physical image/PDF page bounds, strict
workspace/path safety, current registered route, Quillan registration contract,
immutable response-page/issuance context, and authoritative class/work scope.
A QR decode is not required. A successful result identifies the student and
logical page from the canonical registered route, never from a filename.

## Non-effects

This slice adds **no** CLI or teacher-menu options and intentionally changes
**no** existing Scan Review behavior. Preflight does not dispatch, scan again,
retain a new source, create evidence/observations, assemble submissions, write
resolutions, or declare recovery complete. It does not validate current
submission selection state; that belongs to the assembly/review slices.

A returned `PreparedScanRecovery` is a preview only; later execution must
revalidate all authority and source bytes immediately before performing writes.
The historical resolver continues to have metadata-only semantics until
execution, reconciliation, and menu changes in later Issue #419 slices.

## Focused acceptance

```powershell
python -m pytest -q tests/test_scan_recovery_preflight_issue419.py
python -m ruff check quillan/scan_recovery_preflight.py tests/test_scan_recovery_preflight_issue419.py
git diff --check
```

No repository-wide or installed acceptance is required for this additive slice.
