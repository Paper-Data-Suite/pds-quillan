# v0.10.5 Candidate Acceptance Checklist

Classification: **active #417 patch-release procedure**.

## Preparation

- [x] Candidate identity is Quillan `0.10.5`.
- [x] Runtime dependency remains `pds-core>=0.6.2,<0.7`.
- [x] Core 0.6.2 and Core 0.6.3 released endpoint contracts remain authenticated.
- [x] Released Core 0.6.4 endpoint is authenticated from release commit
  `152d1c65064c4f8fe55249ff2ca3379d7c4d6ccb`.
- [x] Released Core 0.6.4 wheel SHA-256 is
  `48cea9317f2967bdc0f2d4c14349a56677c7c3f8211f0f33978ccb1a1c75859b`.
- [ ] Full source/static/documentation gate passes from the v0.10.5 candidate.
- [ ] Exactly one v0.10.5 wheel/sdist pair is built and inspected.
- [ ] Candidate filenames, lengths, and SHA-256 values are recorded.

## Issue #417 source acceptance

- [x] One immutable reporting snapshot drives the report family.
- [x] Student Performance, Comprehensive Class, and Focus Standard CSV semantics
  remain compatible.
- [x] Spreadsheet CSV writers use UTF-8 with exactly one BOM.
- [x] Assignment Review PDF and Assignment Results JSON are implemented.
- [x] Whole-packet generation uses one snapshot and one generation timestamp.
- [x] Packet preflight preserves create-only overwrite safety.
- [x] Reporting does not mutate canonical academic/review state.
- [x] Missing, returned, invalid, and unrated states remain distinct.
- [x] Descriptive percentages use explicit rated-student denominators and are
  not Grades/mastery/proficiency.
- [x] Successful review-stage terminal actions unwind to Selected Student Review.
- [x] Fresh continuation is recalculated after successful completion.
- [x] Cancellation/failure/no-change does not falsely advance review state.
- [x] Review navigation uses shared `B. Back`, `M. Main Menu`, `Q. Quit` and
  removes numbered/hidden numeric Back aliases.
- [x] Assignment-reporting documentation is reconciled with the implemented
  consolidated PDF and percentage contract.

## Installed acceptance

At released Core 0.6.2, 0.6.3, and 0.6.4 endpoints:

- [ ] exact Quillan 0.10.5 wheel installs without source shadowing;
- [ ] existing installed application/producer/operations/class-set/release-edge
  gates pass;
- [ ] selected-review and resubmission acceptance pass;
- [ ] #417 installed reporting/review acceptance passes;
- [ ] all five report artifacts are created at canonical paths;
- [ ] CSV BOM/Unicode round-trip passes;
- [ ] PDF and JSON are readable and privacy-bounded;
- [ ] reporting leaves canonical source files byte-identical;
- [ ] installed B/M/Q navigation contract passes.

At released Core 0.6.4:

- [ ] historical #416 scan-path acceptance still passes;
- [ ] exact Quillan sdist installation/smoke passes.

## Package/release gate

- [ ] Full pytest, Ruff, strict mypy, documentation, and diff hygiene pass.
- [ ] wheel and sdist build.
- [ ] `twine check` and archive inspection pass.
- [ ] clean-wheel qualification passes at all three Core endpoints.
- [ ] clean-sdist installation/smoke passes.
- [ ] release compatibility audit passes.
- [ ] exact tested wheel/sdist is persisted outside the repository.

## Authority

- [ ] Reconciled v0.10.5 release commit qualified.
- [ ] Quillan artifact hashes recorded.
- [ ] Owner explicitly authorized `v0.10.5`.
- [ ] Tag and repository release use those exact artifacts.

This checklist does not itself authorize a tag, GitHub Release, external
package-index upload, publication, or deployment.
