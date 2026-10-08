# Issue #419 — Slice 4: Recovered observation assembly

Slice 4 adds `quillan.scan_recovery_assembly.assemble_persisted_scan_recovery`.

## Boundaries

- Input is the exact `PersistedScanRecovery` from Slice 3, **not** a fabricated QR-intake outcome.
- The service reauthorizes the original dispatch and verifies the existing durable observation/evidence pair before assembly.
- It calls the existing `assemble_quillan_submission_manifests(..., observation_ids=(exact_id,))`; the assembler discovers **all** the affected student's canonical observations, enforces issuance consistency, and performs canonical manifest concurrency checks.
- It then reloads the real submission evidence inventory and SHA-256-verifies the routed evidence at the canonical contextual path.
- It never opens a desktop viewer, selects a candidate, modifies a teacher decision, or records a Core scan resolution. These are explicit later workflow stages.

## Distinct outcomes

- `ready_for_review`: This recovered observation is the currently selected active evidence. The existing **Open Evidence** workflow can open it.
- `selection_needed`: The recovered observation is active but unselected (e.g. the teacher already selected another occurrence, or duplicate evidence is unselected). The existing evidence selection workflow owns the choice.
- `teacher_action_needed`: The page remains `needs_rescan` or `excluded`, even though recovered evidence is durably available. No teacher override is silently reversed.

`AssembledScanRecovery.reviewable` is true **only** for `ready_for_review`. The other two states are not failures of observation persistence; they require explicit teacher decisions.

## Failures and retries

Assembly failures remain failures even when Slice 3 successfully persisted evidence. The error explains that evidence exists and assembly is incomplete. Existing Core failure/resolution records and student review decisions remain untouched. An exact retry first rechecks dispatch and durable evidence, then reuses the existing issuer-authoritative manifest assembler. It does not write duplicate observations or needlessly revise an unchanged manifest.

Conflicting source bytes, unsafe evidence paths, mixed issuances, plain-paper collisions, malformed records, and manifest concurrency issues fail closed through existing services. Historical metadata-only route decisions remain unchanged.

## Not yet delivered

Completion bookkeeping and crash-retry reporting (Slice 5), historical recovery discovery/menu placement (Slices 6–7), and direct recovery CLI (Slice 8). End-to-end installed acceptance is Slice 9.
