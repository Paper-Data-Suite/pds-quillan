# Quillan #419 Slice 8 — Direct CLI recovery contract

## Command surface

The direct commands use the same Slice 1–6 service boundaries as the Scan Review menu. No separate evidence writer, QR re-decoding, route inference, Core resolution updates, or teacher decision changes are introduced.

```powershell
quillan list-scan-recoveries [--format text|json]
quillan preflight-scan-recovery <failure_id> (--recorded-route | --route-id <route_id> --route-class-id <class_id> --route-assignment-id <assignment_id>) [--format text|json]
quillan recover-scan-review <failure_id> --route-id <route_id> --route-class-id <class_id> --route-assignment-id <assignment_id> --yes [--format text|json]
quillan replay-scan-recovery <failure_id> --expected-resolution-id <resolution_id> --yes [--format text|json]
```

`list` and `preflight` are read-only and never dispatch a QR payload or write state. Explicit-route recovery requires a concrete registered route and target, rechecked at execution. `--recorded-route` is only for read-only preflight and cannot be mixed with explicit routing flags. Historical replay uses exactly the latest verified route decision and rejects a superseded resolution ID. `--yes` is mandatory for either mutating command; there is no interactive fallback or implied confirmation.

## Output and error contract

Text is the default. `--format json` emits exactly one compact schema-version `"1"` JSON object to stdout on success, with stable keys and deterministic ordering for unchanged workspace data. Read-only inventory returns `items` in Core's deterministic discovery order and diagnostic `warnings`; it does not include scanned page image bytes, student writing, or raw QR text. A preflight result identifies the source scan/hash, original physical page, immutable page ID, student, work, route origin, and historical resolution ID if any.

Completion JSON includes `status="completed"`, `failure_id`, `completion_state`, `reviewable`, `evidence_id`, `observation_status` (`created`/`existing`), `submission_status` (`created`/`updated`/`unchanged`), `historical_route_reused`, and bounded student/work/page/route identifiers. Completion states are `ready_for_review`, `selection_needed`, and `teacher_action_needed`. A successful command never implies a viewer has been opened or a teacher made a selection. A historic Core `resolved` route alone is never presented as evidence completion.

On service failure, text errors go to stderr; JSON mode emits one `status="error"` JSON object to stderr with `operation`, `stage`, and error description. Failed command execution returns exit code 1. Missing `--yes` returns code 2 with `stage="confirmation"` and no mutations; parser syntax errors also exit 2. Stage exceptions after dispatch retain the canonical `ScanRecoveryExecutionError.stage` (`dispatch`, `persistence`, or `assembly`) and may expose a `verified_observation_id` for a fully verified persisted pair. The caller must treat uncertain evidence paths as diagnostic only.

## Safety and compatibility

Every execution revalidates the authoritative retained physical source, SHA-256, route registration, issued response-page context and Core dispatch result. Evidence is installed through the existing idempotent observation transaction; the submission assembler retains prior selections and teacher-controlled `needs_rescan` and exclusion states. Failed assembly can be retried without duplicating evidence. Historical decisions remain immutable and unaltered. These CLI commands are not bulk migration, QR extraction, automatic grading, or a repair utility for corrupt records.

`docs/cli_contract_inventory.json` is regenerated with `scripts/generate_cli_contract_inventory.py` by the Slice 8 guarded installer, to match the exact new argparse tree. Run `tests/test_cli_contract_docs.py` with the focused CLI tests.
