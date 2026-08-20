# Quillan Development Plan

Quillan now has the complete producer-side foundation through #365:
Academic Result Manifest v1, privacy projection, revision policy, Core 0.6
compatibility, explicit Academic Work Registration, explicit immutable workspace
manifest generation/replay, installed publication-producer compatibility, and
explicit Core publication/supersession/withdrawal/republication with full catalog
reconciliation, consumer-neutral manifest/artifact reading through #364, and
clean-wheel installed producer lifecycle acceptance through #365.

Classification: **active authority** for the v0.9.0 release candidate.

## Current status

Quillan v0.9.0 is a local-first, teacher-controlled writing-evidence module for
PDS Core 0.6. Its supported workflow is:

```text
PDS2 locator -> immutable Core route -> Quillan page context
-> retained-once scan intake -> Core dispatch -> observation/evidence
-> issuance-authoritative submission -> teacher review -> feedback/reports
```

All assignment-owned records live below
`classes/<class_id>/modules/quillan/work/<assignment_id>/`. Quillan neither reads
nor writes the retired unqualified tree. It has no retired-schema parser, generator,
planner, compatibility reader, migration utility, fallback, or dual-path mode.

The current product includes canonical assignment and roster workflows,
immutable printable packet identities and per-page routes, continuation pages,
regeneration, installed module-profile discovery, retained-once image/PDF/folder
intake, Core routing review, Quillan post-dispatch review, digital and plain-paper
submissions, teacher-controlled page management and standards-based review,
feedback export, three assignment-local reports, dashboard schema version 2,
student review status schema version 1, explicit immutable Academic Result
manifest generation/replay, a pure installed manifest reader, separately authorized
selected student-work/feedback artifact resolution, clean-wheel end-to-end producer
acceptance, direct CLI commands, and the compact teacher menu.

## Product boundaries

Quillan records teacher judgments; it does not infer requirement outcomes,
evidence sufficiency, page selection, ratings, feedback, workflow completion,
route corrections, or review resolutions. OCR, handwriting recognition, AI
grading or feedback, LMS/gradebook integration, cloud collaboration, district
dashboards, and cross-assignment analytics are outside this milestone.

PDF scan intake uses `pdf2image` and requires Poppler on the host. Supported
Python versions are CPython 3.11 through 3.14. Runtime Core compatibility is
`pds-core>=0.6,<0.7`, with released Core 0.6.0 as the qualification baseline.

Quillan supports explicit Academic Work Registration for eligible managed
assignments through Core under `quillan_academic_work_v1`; ordinary assignment,
PDS2, review, feedback, and reporting workflows never register work implicitly.
Registration itself does not generate manifests. The explicit #361 workflow
validates native state and creates/replays immutable producer-owned Academic Result
manifest revisions under `exports/manifests/academic_results/`. #363 owns explicit
Core publication lifecycle and #364 owns consumer-neutral parsing plus separately
authorized producer artifact lookup. These boundaries do not assign Academic Period
membership, calculate proficiency or Grades, or create portfolio Candidates. #365's
installed end-to-end producer acceptance is complete; #366 owns the final release
audit.

## Core 0.6 academic-publication milestone status

```text
#359 Core 0.6 adoption                         complete
#360 Academic Work Registration                complete
#361 immutable manifest generation/validation complete
#362 publication producer profile              complete
#363 publication lifecycle                     complete
#364 consumer-neutral reader                   complete
#365 installed end-to-end producer acceptance  complete
#366 release audit/version closeout             remaining
```

## Release closeout

The remaining v0.9.0 work is release evidence rather than a new domain feature:

1. keep package, runtime, CLI, documentation, and artifact versions aligned;
2. run source, documentation, path-safety, packaging, and clean-install gates;
3. execute the installed synthetic workflow and visual layout matrix;
4. have the owner execute the physical printed-and-scanned checklist; and
5. obtain explicit owner release authorization before tagging or publishing.

Automated validation, visual acceptance, physical acceptance, and release
authorization are independent statuses. Preparing the candidate does not grant
authority to tag, publish, deploy, or close the release issues.

## Historical record

Earlier v0.6-v0.8.6 planning described generic tags, comment banks, rubric or
criterion scores, plain-text submissions, filename-authoritative assembly, and
future scan/review menus. Those plans are superseded. The curated history remains
in [the changelog](../CHANGELOG.md), design context remains in the documents
explicitly classified as historical, and current operating contracts are indexed
by [Data contracts](data_contracts.md) and [CLI contract](cli_contract.md).

## v0.10.0 teacher-workflow milestone

The post-v0.9.0 teacher-workflow milestone begins from the reproducible #379
baseline in `v0.10.0_teacher_workflow_audit.md`. Issue #380 adds safe assignment
copying as the first implementation step: a teacher can reuse an existing
assignment's stable review configuration in a fresh class-qualified work identity
without inheriting student, evidence, print, routing, export, registration,
manifest, or publication state. Named reusable presets remain #381.

The #379 numerical baseline remains historical evidence and is not regenerated by
#380; #394 owns the final before/after milestone audit.


## v0.10.0 repeated-setup efficiency: review-configuration presets (#381)

Issue #381 implements the reusable review-configuration layer identified by the
#379 teacher-workflow audit. It complements #380 assignment copying:

- #380 reuses approved configuration from one exact existing assignment.
- #381 reuses a named workspace-level configuration preset independently of any
  source assignment.

Preset schema v1 contains only writing type, Core profile/Focus Standard
references, review unit, rating scale, basic requirements, and
minimum-requirement policy. Feedback composition and reusable comment text are
deliberately excluded.

Teachers can create presets directly, save them from an exact assignment, list
and inspect valid/invalid/stale records, and explicitly select/review a current
preset during assignment creation. Preset application snapshots values into a
normal schema-v2 assignment and creates no live inheritance relationship.
Manual assignment creation remains first-class.

The #379 baseline remains historical evidence; #381 recorder-backed acceptance
asserts semantic removal of reusable configuration re-entry rather than
rewriting baseline counts. Final quantitative comparison remains #394.
