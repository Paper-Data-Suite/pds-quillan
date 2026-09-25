# v0.10.3 Candidate Acceptance Checklist

Classification: **active #415 patch-release procedure**.

## Preparation

- [x] Candidate identity is Quillan `0.10.3`.
- [x] Runtime dependency remains `pds-core>=0.6.2,<0.7`.
- [x] `pypdf>=5,<7` remains a bounded runtime dependency.
- [x] Released v0.10.1 batch-assembly evidence remains historical.
- [x] Historical v0.10.0 physical-paper evidence remains unchanged.
- [x] Core 0.6.2 and 0.6.3 exact wheels authenticated.
- [x] Full source/static/documentation gates pass for the current repair
  worktree; repeat from the reconciled candidate commit before artifact build.
- [ ] Exactly one v0.10.3 wheel/sdist pair built from the qualified commit.
- [ ] Twine and artifact inspection pass for that pair.
- [ ] Candidate filenames, lengths, and SHA-256 values recorded.

## Issue #415 source acceptance

- [x] Assignment action 8 and the direct CLI share one structured read service.
- [x] One redraw-scoped assignment review context is used.
- [x] Exactly one strict routed-observation pass occurs per redraw.
- [x] Every routed evidence file is path-checked, read, and SHA-256 verified.
- [x] Later physical intake remains visible even when bytes match.
- [x] Pending assembly, multiple rescans, selection, dismissal, and cancel pass.
- [x] Selecting authoritative evidence makes prior feedback stale.
- [x] Candidate routing, assembly, and dismissal leave feedback current.
- [x] Full immutable observation and retained-source projection is shared by
  assembly, inbox, resolution, and exact opening.
- [x] Exact opening performs fresh action-time byte/hash/provenance validation.
- [x] Initial intake is excluded and dismissal requires a current selection.
- [x] Representative 30-student read-amplification coverage remains bounded.
- [x] Inbox read/refresh/open/cancel remains read-only.

## Installed acceptance

- [ ] Core 0.6.2 isolated install passes.
- [ ] Core 0.6.3 isolated install passes.
- [ ] No source checkout or `PYTHONPATH` shadowing.
- [ ] Installed `quillan` console entry point verified.
- [ ] Existing routing/publication/module-operation/class-set gates pass.
- [ ] Installed resubmission-inbox acceptance passes for Core 0.6.2.
- [ ] Installed resubmission-inbox acceptance passes for Core 0.6.3.
- [ ] Installed workflow matches the active
  [v0.10.3 acceptance contract](v0.10.3_installed_resubmission_inbox_acceptance.md).
- [ ] Exact tested wheel/sdist persisted outside the repository.

## Physical boundary

- [x] #415 does not intentionally touch generation, routing, scan intake,
  retained-source handling, or physical-paper interpretation.
- [x] Implementation diff reconfirmed not to invalidate that conclusion.
- [x] Additional physical acceptance not triggered; v0.10.0 evidence remains
  applicable.

## Authority

- [ ] Reconciled release commit qualified.
- [ ] Installed acceptance passed against exact recorded bytes.
- [ ] Artifact hashes recorded.
- [ ] Owner explicitly authorized `v0.10.3`.
- [ ] Tag and repository release use those exact artifacts.

## Invalidated 2026-09-24 pre-commit evidence

- The earlier wheel `quillan-0.10.3-py3-none-any.whl`, 534041 bytes,
  SHA-256 `0ce217f2050ccb6255e69300ae419bcb16dfddac89a3c6c93282896777db4f93`.
- The earlier sdist `quillan-0.10.3.tar.gz`, 816835 bytes,
  SHA-256 `3a25e0cd2af9ef78ee6d9a227803346b00eda4b38beffc029e58d6b4a988ffb7`.
- Those artifacts were built before a candidate commit and before the repair
  pass described above. They are explicitly invalid and must not be released.
- No replacement artifacts may be qualified until a reconciled release commit
  exists. Release authorization remains not granted.

## 2026-09-24 repair-worktree evidence

- Full pytest: 2972 passed, 23 skipped.
- Ruff, strict mypy across 172 source files, compileall, `pip check`,
  documentation integrity, release compatibility, and diff hygiene passed.
- Focused #415 repair coverage proves current feedback before selection, stale
  feedback after selection, current feedback after candidate assembly/dismissal,
  full projection validation, action-time tamper rejection, initial-intake
  suppression, dismissal safety, multi-rescan comparison UX, and the
  representative 30-student read boundary.
- Installed-wheel and artifact checkboxes intentionally remain open until a
  reconciled candidate commit exists.

Do not upload to an external package index without separate explicit
authorization.

This checklist does not itself authorize a tag, GitHub Release, upload,
publication, or deployment.
