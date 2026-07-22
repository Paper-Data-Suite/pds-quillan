# Module-qualified record services

Quillan identifies assignment work with an exact `ModuleWorkRef` whose module is
`quillan`. The only supported work root is:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/
```

The unqualified development-era `classes/<class_id>/assignments/` tree is not a
fallback, migration source, conflict source, or write destination. Quillan does
not inspect it. Class rosters remain Core-owned at `classes/<class_id>/roster.csv`.

## Records and contexts

`quillan.work_paths` is the path-construction authority. `quillan.record_context`
loads an assignment or a coherent assignment/submission/review context after
preflighting the complete path chain. It distinguishes missing, invalid, orphaned,
identity-mismatched, and unsafe records and returns recursively immutable record
data. Every loaded record is a `LoadedJsonRecord` that binds its canonical path,
workspace-relative path, exact source bytes, and parsed immutable model. Each file
is read once per logical snapshot. Review loading explicitly requires, permits, or
forbids an existing review.

Canonical records are:

```text
<work root>/assignment.json
<work root>/submissions/<student_id>/submission.json
<work root>/submissions/<student_id>/review.json
```

Review records retain schema version 2 and must embed the exact module-qualified
workspace-relative assignment and submission paths. Submission manifests retain
schema version 1. Identity-based writers exclusively create or revision-guard the
canonical record and verify the durable result. Updates acquire a same-directory
guard, re-preflight, compare the snapshot revision, displace that exact revision,
and install the prepared bytes exclusively. A concurrent target always wins. An
installed target is never blindly rolled back; verification uncertainty reports
the exact possibly durable path. Guard-cleanup failures separately report the
stale lock path; a verified installed record remains in place, while an unchanged
operation does not claim that it installed new bytes.

Plain-paper submissions use the same record paths. They contain no issuance,
route, page observation, retained scan, or routed evidence. Creation treats the
empty manifest and review as a paired operation and compensates only a manifest
proven to have been created by that operation. Review installation, contradictory
bytes, or uncertain review durability always preserves the manifest so the
operation cannot create an orphan review. Multi-class assignment writes journal
each confirmed absence or original snapshot and conservatively compensate only
bytes still proven to belong to the incomplete batch.

## Review mutation and exports

Review-unit, observation, rating, feedback, note, requirement, workflow-state,
and export-metadata services load the shared context and persist through the
canonical review writer. Page-management services update only the canonical
manifest while preserving review data and teacher-controlled state.

Student feedback is written only to:

```text
<work root>/submissions/<student_id>/exports/feedback.md
<work root>/submissions/<student_id>/exports/feedback.pdf
```

Stored export metadata must equal those exact canonical paths. Assignment reports
are written only to `exports/class_summary.csv`, `exports/standards_summary.csv`,
and `exports/student_performance_summary.csv` beneath the work root. Report
discovery considers only validated direct student directories beneath the
canonical `submissions/` directory.

## Scan-review ownership

Core owns workspace-level routing-failure and scan-resolution records. Quillan
interprets Core schema-version-2 metadata, establishes ownership from the exact
route locator or target (or the bounded pre-dispatch ownership marker), derives
work identity from the locator, and writes resolutions through Core's v2 factory
and writer. Evidence must be an existing ordinary file at an exact canonical
POSIX workspace-relative path.

Failures after successful dispatch are not Core routing failures. Quillan stores
each attributable observation, routed-evidence, assembly, mixed-issuance, or
manifest failure as an append-only occurrence at:

```text
<work root>/scans/review/post_dispatch/<failure_id>.json
```

These records retain complete deterministic tuples of issuance, page, route,
observation, scan, source-page, and possible-path provenance and are discovered
through a distinct typed service. Each persisted result also carries its validated
workspace root and exact Quillan work reference, which reconstruct both its
absolute and relative paths. Core routing resolutions are never written for them. A teacher UI
for resolving these occurrences belongs to issue #341; this service migration
does not redesign commands, help, menus, or dashboards.
