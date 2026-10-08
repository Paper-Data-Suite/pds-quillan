# Issue #419 Slice 3 — Recovered Page Observation Persistence

This slice exposes `persist_dispatched_scan_recovery(workspace_root, dispatched, *, registry=None)`.

A `DispatchedScanRecovery` from Slice 2 is *not* a durable evidence artifact. The
new entry point reruns exact Slice 2 verification (including original retained
source SHA-256, current registered route and issuance) before writing, then
passes the verified Core `RouteDispatchSuccess` to Quillan's canonical
observation/evidence transaction.

The existing writer, `response_page_observation_persistence.py`, now accepts
both ordinary `QuillanScanPageOutcome` success and exact Core
`RouteDispatchSuccess` through one shared authoritative-result validator and
one unchanged transaction body. A manual recovery does not invent QR payload
text or a synthetic successful QR-intake outcome.

Successful return contains a canonical `PersistedQuillanPageObservation` with
status `created` or verified `existing`. Existing observations, evidence,
content hashes, source provenance, collision handling, and rollback rules use
the same writer as normal intake. Original Core failures and historical
resolution records remain unchanged.

Failures before the transaction raise `ScanRecoveryPersistenceError`. Errors
from the shared writer retain their existing typed exception and possible
artifact paths to support future retry handling.

**Not yet implemented:** submission assembly, candidate/selected evidence
policy, teacher menus, CLI recovery commands, or operational completion
metadata. These remain in subsequent slices. A persisted observation alone
is not evidence that the page is visible through `Open Evidence`.
