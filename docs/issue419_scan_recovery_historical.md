# Quillan Issue #419 — Slice 6: Historical Recovery

## Problem

Existing Quillan scan-review menu actions `route_selected` and `route_corrected` wrote **immutable Core schema-v2 resolution metadata**. A routing failure may therefore display `resolved` even though **no evidence was persisted or assembled**. Historical decisions must not be mistaken for an executed recovery.

## Read-only inventory

`discover_historical_scan_recoveries(workspace_root) -> HistoricalScanRecoveryInventory` reads the canonical Core failure/resolution history with `include_resolved=True` and checks only each failure's **latest** resolution. It reports only decisions whose latest status is `resolved` and action is a route selection/correction; other teacher decisions are not replay candidates. Discovery preserves strict reader warnings. It does not decode QR, dispatch, persist, assemble, modify an existing record, or launch a viewer.

For each candidate it reuses the exact Slice 1 historical preflight (original retained-source bytes/SHA-256, physical page, current route registration and issued response-page authority) and checks the deterministic observation ID, full observation identity/provenance, contextual routed-evidence file and SHA-256, and canonical student submission manifest evidence projection.

| Status | Meaning |
| --- | --- |
| `evidence_missing` | No canonical observation at the deterministic ID. Prior Core `resolved` is **not** evidence of materialization. |
| `assembly_pending` | Verified observation and evidence exist, but the submission lacks the recovered evidence projection or canonical manifest. |
| `ready_for_review` | Recovered observation/evidence are verified, active and selected in the submission. |
| `selection_needed` | Verified recovered evidence exists as an unselected active candidate; preserve the existing teacher selection. |
| `teacher_action_needed` | Verified recovered evidence is in a page marked `needs_rescan` or `excluded`. No teacher decision is overridden. |
| `blocked` | Source, route, issued-page authority, observation, evidence bytes, or manifest is contradictory/unsafe. A reason accompanies the item; do not claim success. |

`requires_replay` is true only for `evidence_missing`/`assembly_pending` **at discovery time**; actual execution must always reauthorize. The inventory is a read-only snapshot, not a durable completion record or permission grant. Unreferenced orphan evidence is handled by the canonical persistence writer's fail-closed collision checks on replay.

## Explicit historical replay

`replay_historical_scan_recovery(root, failure_id, *, expected_resolution_id, registry=None) -> CompletedScanRecovery` requires the caller to present the **exact immutable latest route resolution ID** seen during discovery. It independently reruns Slice 1 historical preflight, rejects changed/superseded decisions, then delegates to `execute_prepared_scan_recovery` (Slice 5). There is **no automatic bulk replay**, route guessing, QR decoding, additional Core resolution write, or teacher evidence selection.

On first use it can create an observation and submission; on an exact retry it verifies and reuses them. An interruption after observation persistence may appear as `assembly_pending`; a later explicit replay can assemble that verified evidence. A snapshot saying `ready_for_review` is contingent on current teacher decisions and evidence integrity, not evidence that a file viewer opened.

## Boundaries

- New files only: `quillan/scan_recovery_historical.py`, focused tests and this document.
- No changes to `scan_review_resolution.py`, Core's writer/history, normal QR intake, observation persistence, or manifest assembly.
- The UI/menu confirmation and action routing belong to Slice 7; CLI and installed qualification belong to Slices 8 and 9.
- Discovery warnings and per-item blocked reasons are diagnostic. A malformed item cannot be counted as materialized.
