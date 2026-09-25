# v0.10.3 Release Process

Classification: **active authority for the v0.10.3 patch candidate**.

Issue #415 owns the assignment-level resubmission/rescan inbox, explicit
evidence resolution, feedback freshness after selection, exact-candidate
installed acceptance, and release preparation. Passing automation does not
itself grant tag or GitHub Release authority.

## Exact candidate construction

1. Reconcile the release commit with `origin/main` and require a clean tree.
2. Authenticate the supported Core endpoint wheels for 0.6.2 and 0.6.3.
3. Run full source pytest, Ruff, strict mypy, compileall, documentation checks,
   release compatibility, `pip check`, and diff hygiene.
4. Build exactly one pair from that commit:
   - `quillan-0.10.3-py3-none-any.whl`
   - `quillan-0.10.3.tar.gz`
5. Run Twine and archive inspection against that exact pair.
6. Install the same wheel bytes into isolated Core 0.6.2 and Core 0.6.3
   environments outside the checkout.
7. Verify console entry point, Core routing, publication, module operations,
   existing class-set workflows, release edges, and the selected-review
   redraw/read boundary.
8. Run the sdist smoke without rebuilding the candidate pair.
9. Persist the exact tested pair outside the repository and record filenames,
   lengths, and SHA-256 values.

A rebuild has a different artifact identity and invalidates installed evidence
for the previous bytes.

## Resubmission inbox acceptance

The source qualification includes newer candidate evidence, pending assembly,
identical-byte later intake, feedback chronology, multiple rescans, explicit
selection/dismissal, cancellation, and bounded attention states. One inbox
redraw must perform exactly one assignment-context load, one roster load, one
strict observation discovery pass, and one verification/hash per routed file.

The installed acceptance runs from the exact candidate wheel against both Core
0.6.2 and Core 0.6.3 outside the checkout. It exercises initial assembly,
real PDF/Markdown feedback export, later rescan, pre- and post-assembly
freshness, inbox discovery, action-time verified exact evidence opening,
explicit selection, a fresh empty inbox, and stale-feedback reporting.

The [v0.10.2 Installed Selected-Review Read Acceptance](v0.10.2_installed_selected_review_read_acceptance.md)
remains historical evidence for the unchanged redraw-scoped read boundary.
See [v0.10.3 Installed Resubmission Inbox Acceptance](v0.10.3_installed_resubmission_inbox_acceptance.md)
for the active exact-wheel workflow.

## Historical patch evidence

The released v0.10.1 batch-feedback acceptance remains historical evidence for
the unchanged feedback-assembly workflow:

[v0.10.1 Installed Batch Feedback Acceptance](v0.10.1_installed_batch_feedback_acceptance.md).

## Physical acceptance boundary

Issue #415 adds a derived evidence-management workflow; it does not
change PDS2 generation, route registration, scan intake, retained-source
handling, routed-evidence creation, printable packet generation, or physical
page interpretation. The exact v0.10.0 physical-paper acceptance therefore
remains applicable and is not repeated. Any later implementation change that
crosses one of those boundaries invalidates that waiver and requires affected
physical requalification.

See the historical [v0.10.0 Physical Acceptance](physical_acceptance_v0.10.0.md).

## Core and publication compatibility

Runtime compatibility remains exactly `pds-core>=0.6.2,<0.7`. Issue #415 adds no
Core API, Academic Work registration, Academic Result, Publication Record,
Meridian handoff, grading, proficiency, or portfolio behavior. The workflow is
a redraw-scoped projection only; no inbox cache survives a user action.

## Release authority

After qualification, an owner must explicitly authorize the v0.10.3 release.
Only then may the normal process create/push tag `v0.10.3` and make the exact
qualified wheel/sdist available in the repository's release channel. Do not
upload Quillan to an external package index without separate explicit
authorization.
