# Quillan Development Plan

Quillan now has the complete producer-side foundation through #362:
Academic Result Manifest v1, privacy projection, revision policy, Core 0.6
compatibility, explicit Academic Work Registration, explicit immutable workspace
manifest generation/replay, and installed publication-producer compatibility.
Core publication lifecycle and consumer-neutral reading remain #363–#364.

Classification: **active authority** for the v0.8.9 release candidate.

## Current status

Quillan v0.8.9 is a local-first, teacher-controlled writing-evidence module for
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
manifest generation/replay, direct CLI commands, and the compact teacher menu.

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
Registration itself does not generate manifests. A separate explicit #361
workflow now validates native state and creates/replays immutable producer-owned
Academic Result manifest revisions under
`exports/manifests/academic_results/`. That workflow does not publish through
Core, create Publication Records or withdrawals, rebuild the academic catalog,
assign Academic Period membership, calculate proficiency or Grades, or create
portfolio Candidates. #362–#365 own the remaining producer integration;
#366 owns the final release audit.

## Core 0.6 academic-publication milestone status

```text
#359 Core 0.6 adoption                         complete
#360 Academic Work Registration                complete
#361 immutable manifest generation/validation complete
#362 publication producer profile              complete
#363 publication lifecycle                     remaining
#364 consumer-neutral reader                   remaining
#365 installed end-to-end producer acceptance  remaining
#366 release audit/version closeout             remaining
```

## Release closeout

The remaining v0.8.9 work is release evidence rather than a new domain feature:

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
