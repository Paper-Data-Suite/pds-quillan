# v0.10.1 Release Process

Classification: **active authority for the v0.10.1 patch candidate**.

Issue #412 owns implementation, exact-candidate qualification, installed
feedback-assembly acceptance, and release preparation. Passing automation does
not itself grant tag or GitHub Release authority.

## Exact candidate construction

1. Reconcile the release commit with `origin/main` and require a clean tree.
2. Authenticate the supported Core endpoint wheels for 0.6.2 and 0.6.3.
3. Run full source pytest, Ruff, strict mypy, compileall, documentation checks,
   release compatibility, `pip check`, and diff hygiene.
4. Build exactly one pair from that commit:
   - `quillan-0.10.1-py3-none-any.whl`
   - `quillan-0.10.1.tar.gz`
5. Run Twine and archive inspection against that exact pair.
6. Install the same wheel bytes into isolated Core 0.6.2 and Core 0.6.3
   environments outside the checkout.
7. Verify console entry point, Core routing, publication, module operations,
   existing class-set workflows, release edges, and the new batch-feedback
   assembly workflow.
8. Run the sdist smoke without rebuilding the candidate pair.
9. Persist the exact tested pair outside the repository and record filenames,
   lengths, and SHA-256 values.

A rebuild has a different artifact identity and invalidates installed evidence
for the previous bytes.

## Installed feedback-assembly acceptance

The installed console script must create/load synthetic class and assignment
state with at least two current canonical feedback PDFs, dry-run whole-class
assembly without creating output, create both a print packet and sharing ZIP,
verify roster page order and ZIP member bytes, and prove canonical review,
submission, feedback, Academic Work, and publication state did not change.

See [v0.10.1 Installed Batch Feedback Acceptance](v0.10.1_installed_batch_feedback_acceptance.md).

## Physical acceptance boundary

Issue #412 does not intentionally modify PDS2, routing, scan intake,
response-page generation, physical evidence assembly, review semantics, or
publication semantics. The exact v0.10.0 physical-paper acceptance therefore
remains applicable and is not repeated. Any implementation change that crosses
one of those boundaries invalidates that waiver and requires affected physical
requalification.

See the historical [v0.10.0 Physical Acceptance](physical_acceptance_v0.10.0.md).

## Core and publication compatibility

Runtime compatibility remains exactly `pds-core>=0.6.2,<0.7`. Feedback batch
assembly adds no Core API, Academic Work registration, Academic Result,
Publication Record, Meridian handoff, grading, or proficiency behavior.

## Release authority

After qualification, an owner must explicitly authorize the v0.10.1 release.
Only then may the normal process create/push tag `v0.10.1` and make the exact
qualified wheel/sdist available in the repository's release channel. Do not
upload Quillan to an external package index without separate explicit
authorization.
