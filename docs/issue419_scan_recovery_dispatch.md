# Issue #419 Slice 2 — Explicit Core Recovery Dispatch

Slice 2 adds `quillan.scan_recovery_dispatch.dispatch_prepared_scan_recovery`.
It accepts an exact `PreparedScanRecovery` produced by Slice 1, plus the
existing workspace root and optionally a prevalidated application-owned Core
module registry. Without a supplied registry, Quillan uses installed module
registry discovery.

## Contract

1. A preview is not authority. Re-run Slice 1 preflight immediately before
   dispatch, preserving explicit versus historical-recorded route semantics.
2. Reject changed/expired previews before calling Core.
3. Construct **one** `RouteDispatchRequest` containing the original verified
   `RetainedSourceScan`, original physical page number and selected locator.
4. Call Core's `dispatch_route`, allowing Core to enforce its current route
   registration, module-contract, route-status and Quillan handler checks.
5. Independently verify returned request, module profile, resolution and
   Quillan response-page identity against immutable page/issuance authority.
6. Re-run preflight after dispatch to reject changed source or route inputs.
7. Return `DispatchedScanRecovery` with the exact Core success and Quillan
   page result, or raise `ScanRecoveryDispatchError`.

All operations are read-only with respect to canonical workspace state.
The code does not perform QR detection, source re-retention, routed evidence
persistence, observation persistence, submission assembly, resolution writes,
or teacher review changes. **Successful dispatch is not completed recovery.**

## Later-slice handoff

Slice 3 should consume `DispatchedScanRecovery.success` and its `request`,
without fabricating an intake QR result. It must revalidate current authority
at the point of evidence persistence rather than treating a previously
returned dispatch result as permanent permission to write. Slice 4 will
assemble the resulting verified observation; subsequent slices own final
recovery status and historical reconciliation.

## Focused qualification

```powershell
python -m pytest -q -rs `
  tests/test_scan_recovery_dispatch_issue419.py `
  tests/test_scan_recovery_preflight_issue419.py
python -m ruff check `
  quillan/scan_recovery_dispatch.py `
  tests/test_scan_recovery_dispatch_issue419.py
python -m mypy quillan/scan_recovery_dispatch.py
```
