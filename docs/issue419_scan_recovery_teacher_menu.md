# Issue #419 Slice 7 — Teacher-facing Scan Review recovery

## Baseline and scope

Base commit: `414a5ee` on branch `419-recover-failed-scan-pages`.

The new **Recover Retained Scan Pages** screen sits alongside existing Core
review, assignment-scoped review, and post-dispatch review. Current routing
resolution actions remain available and unchanged. The recovery screen lists
valid unresolved/deferred Core failures and latest `resolved` *route* choices
only; resolved rescan/dismissal/evidence-filed decisions are not replayable.

Teachers deliberately select one physical failure, choose an existing registered
Quillan response-page route (for unresolved records) or reuse its exact verified
historical decision, inspect preflight, and confirm with `y` before writing.
`B` returns without mutation; all screen-level choices are bounded to the
selected failure. Core resolution metadata is never appended/rewritten by this
workflow. The existing route picker still confirms selection separately.

## Evidence status semantics

A historical `resolved` routing status is **not** evidence recovery. The screen
shows the Slice 6 observation/manifest status: `evidence_missing`,
`assembly_pending`, `ready_for_review`, `selection_needed`,
`teacher_action_needed`, or `blocked`. Blocked historical records cannot be
replayed from the menu. Replay rechecks the **exact latest resolution ID**
before dispatch; superseded teacher choices are rejected.

Successful execution reports verified observation ID and whether submission
assembly created, updated, or reused the manifest. `ready_for_review` means the
recovered evidence is selected and verified for Open Evidence; it does **not**
claim that a desktop viewer has been opened. `selection_needed` and
`teacher_action_needed` explicitly require teacher input and preserve existing
selections, exclusion and rescan decisions.

An error identifies the failed stage and any positively verified observation ID
from the Slice 5 receipt; no uncertain evidence artifact is presented as a
successful recovery. The menu never decodes a failed QR, infers a route, runs
bulk repairs, or changes a teacher's review/evaluation state.

## Navigation hooks

* Global Scan Review scope: `R. Recover retained Core scan pages`.
* Scoped combined source chooser: `4. Recover retained Core scan pages`.
* Core unresolved review list: `R. Recover retained Core scan pages`.
* Core empty review list: `R` remains available so historical resolved-only
  failures can still be recovered; Enter or `B` returns.
* Post-dispatch-only review list: `R. Recover retained Core scan pages`.
* Recovery listing, route selection, and confirmation support `B = Back`.

## Acceptance boundaries

New focused tests cover explicit teacher confirmation, no-write cancellation,
current-route recovery, historical replay, blocked/integrity failures,
selection preservation, stage failures, and navigation from Scan Review.
The existing scan-resolution menus and discovery/persistence/assembly code are
otherwise unchanged. CLI exposure and installed-wheel acceptance belong to
Slices 8 and 9.
