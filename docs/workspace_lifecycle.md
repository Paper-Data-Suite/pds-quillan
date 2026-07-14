# Quillan Workspace Layout and File Lifecycle

## Overview

Quillan uses the shared Paper Data Suite workspace root. Class, assignment,
and submission records are centered under:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/
```

This is the active, local-first workspace for teacher-controlled instructional
records. It is intended to support paper-first and restricted-technology
workflows as well as writing captured directly as text. Quillan preserves
student work as evidence, keeps teacher-review artifacts separate, and
organizes files without substituting software decisions for teacher judgment.

The shared `pds-core` contracts define assignment and submission locations as
well as the active scan source-retention and routing-review layout.
Quillan-specific files remain inside those shared routes.

Quillan is subject-agnostic. The workspace layout supports written-response
review across disciplines. For the prepared-review sequence and
subject-neutral storage map, see
[`prepared_review_workflow.md`](prepared_review_workflow.md).

## Workspace vs. Installation

The PDS workspace root is teacher-controlled data storage. It is separate from
the Quillan source checkout, the Python virtual environment used for
development, and the location where the Quillan package is installed. None of
those code or environment locations should be treated as the workspace root.

Quillan uses shared `pds-core` APIs to show, set, validate/create, and reset the
Paper Data Suite workspace root through its Workspace Settings menu and
matching direct commands. It does not maintain Quillan-specific workspace
configuration. Setting a root does not migrate existing files, and resetting
the saved preference does not delete workspace files. `PDS_WORKSPACE_ROOT`
continues to take precedence over the saved preference when set.

## Core Directory Layout

The expected current and reserved layout is:

```text
<PDS workspace root>/
  scans_inbox/
  scans/
    source/
      YYYY-MM-DD/
    review/
  classes/
    <class_id>/
      roster.csv
      assignments/
        <assignment_id>/
          assignment.json
          templates/
            printable_response_pages.pdf
          scans/
          submissions/
            <student_id>/
              submission.json
              review.json
              exports/
                feedback.pdf
                feedback.md
          exports/
            student_performance_summary.csv
            class_summary.csv
            standards_summary.csv
          debug/
```

Reusable Focus Standard comments live outside individual assignments:

```text
<PDS workspace root>/shared/focus_standard_comments/<comment_set_id>.json
```

The active scan paths, assignment directory, `assignment.json`,
`submissions/`, and each student's submission directory follow shared PDS
contracts. The other directories and files shown above are assignment-local
Quillan records or reserved locations for future workflows. A directory does
not need to exist until a workflow has a reason to create it.

## File Responsibilities

### `roster.csv`

The canonical active class roster uses the shared `pds-core` roster contract.
Quillan's Roster Management menu can create, view, edit, and validate this
file. Required columns are `class_id`, `student_id`, `last_name`,
`first_name`, and `period`; optional columns are preserved. Leading-zero
student IDs remain strings. Menu edits are staged until explicit `SAVE`, and
discarded edits are not written.

Removing a student from this active roster does not delete or modify
assignments, submissions, printable PDFs, scans, review records, reports,
feedback exports, or historical evidence.

### `assignment.json`

The teacher-created assignment configuration. Active schema version `2`
assignments define the task, writing type, connected class IDs, student
prompt, standards profile reference, Focus Standard IDs, review-unit
configuration, rating scale, basic requirements, and minimum-requirement
policy.

Quillan's Assignment Management menu can create this file from prompts after
the teacher selects a class with an existing canonical roster. It uses the
existing assignment validation contract and the shared assignment route:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The menu can also load, validate, and summarize an explicit assignment JSON
path without rewriting it. Existing configs require exact `OVERWRITE`
confirmation before replacement. This workflow does not edit or delete
assignments and does not perform scoring, feedback, reporting, scan routing,
OCR, AI, or printable packet
generation.

### `templates/`

A shared assignment-local directory for generated or teacher-facing printable
materials. The Python API, Printable Response Pages menu, and direct
`quillan printable-responses generate` command create
`templates/printable_response_pages.pdf` as one combined class packet of
roster-aware writing-response pages. Both entry points share packet planning
and generation services and require an existing canonical roster and assignment
config. The menu protects replacement with exact `OVERWRITE` confirmation; the
non-interactive CLI requires `--overwrite --yes`. CLI dry-run performs full
preflight validation without creating the directory or PDF. Generation does
not rewrite either source file. Generated PDFs are local workspace artifacts
and should not be committed. The response-page contract is defined in
[`printable_response_template.md`](printable_response_template.md).

### Workspace `scans/source/YYYY-MM-DD/`

The shared canonical store for active retained source scans, date-bucketed by
the PDS intake date in UTC. The direct `route-scan` workflow copies its
selected readable source here before Quillan-specific routing, leaves the
teacher's original selected file untouched, avoids silent overwrites, and
preserves provenance from routed evidence back to this retained source.

### Workspace `scans/review/`

The shared workspace-level location for canonical routing failure records and
optional problem artifacts. The direct `route-scan` workflow uses the shared
`pds-core` metadata shape and failure categories, with Quillan-specific
details under `module_details`, when a routing input can be safely preserved
for teacher review.

### Assignment `scans/`

The assignment-local directory for routed scan evidence. It is not the
canonical retained source location. The direct `route-scan` workflow files a
selected source here only when the caller supplies an already-decoded
canonical PDS1 payload. The validation, naming, collision, provenance, and
failure-review behavior is defined in
[`scan_routing_design.md`](scan_routing_design.md). Quillan does not perform
OCR or evaluate writing from scan contents.

### `submissions/<student_id>/submission.json`

The Quillan version `1` submission manifest for one student's routed
evidence for one assignment. It identifies the class, assignment, and student;
represents expected, missing, duplicate, replacement, damaged, or excluded
pages; preserves retained-source provenance; and records teacher-controlled
submission-management state without containing private notes, Focus Standard
ratings, feedback composition, or feedback exports.

Loading, validation, canonical path computation, safe writing, and
new-manifest assembly from caller-provided evidence metadata are implemented
in modules distinct from the legacy text-oriented loader. The direct
`assemble-submissions` command discovers already-routed evidence by filename
and creates missing manifests; it does not merge into existing manifests or
choose among ambiguous duplicates. `set-review-state` provides an explicit,
metadata-only teacher-controlled state update.

### `submissions/<student_id>/review.json`

The canonical active schema version `2` teacher-review record for one
submission. It stores minimum-requirement checks and outcome, review units,
review-unit Focus Standard observations, overall Focus Standard ratings, Focus
Standard feedback composition, private notes, export metadata, and an explicit
`review_state`. It references the adjacent `submission.json` and evidence IDs
without copying routed evidence paths.

`review_state` is independent of `submission_state`; neither state
automatically determines the other. The complete record contract is defined
in [`review_record_contract.md`](review_record_contract.md). Loading, writing,
guided teacher-facing menu review, and derived exports are implemented by the
runtime.

Earlier separate `tags.json`, `scores.json`, and schema version `1` review
designs are historical and are not alternate active v0.8.6 paths.

### `submissions/<student_id>/exports/feedback.pdf` and `feedback.md`

Student-readable feedback exports derived from valid matching `assignment.json`,
`submission.json`, and schema version `2` `review.json`. They remain traceable
to `review.json` and must not be treated as independent review records or a
replacement for teacher judgment. Existing output is protected unless
overwrite is explicitly requested.

### `exports/`

The assignment-local location for derived teacher-facing reports. Implemented
reports are Student Performance Summary
(`student_performance_summary.csv`), Comprehensive Class Summary
(`class_summary.csv`), and Standards Summary (`standards_summary.csv`). Reports
summarize records; they do not replace the underlying source evidence or
teacher-review artifacts.

### `debug/`

A reserved location for future assignment-local diagnostic outputs, if
needed. Debug files are operational aids and must not be treated as
authoritative instructional records, source evidence, scores, feedback, or
reports.

## Submission Review States

The version `1` manifest's `submission_state` is one of `unreviewed`,
`in_progress`, `needs_rescan`, or `reviewed`. Page and evidence entries carry
their own narrower evidence-management states. Replacement, duplicate,
damaged, and excluded artifacts remain in the manifest for traceability.

These states do not encode a score, grade, rubric result, feedback status,
tagging status, OCR result, AI judgment, or automatic grading decision. See
[`data_contracts.md`](data_contracts.md#submission-manifest) for the complete
contract.

## Source Evidence vs. Teacher-Review Artifacts

Quillan keeps three record categories distinct.

### Source Evidence

Source evidence is the student-produced work and the manifest needed to
identify routed artifacts and their retained-source provenance:

* `submission.json`

The manifest is part of the evidentiary record because
it establishes identity, provenance, page state, and teacher-controlled
submission-management state. It does not contain the teacher's notes, score,
Focus Standard ratings, feedback composition, or feedback export.

### Teacher-Review Artifacts

Teacher-review artifacts are records created by the teacher or confirmed
through teacher review:

* `review.json`

These records support efficient review while preserving the teacher as the
source of evaluative judgment. They should remain connected to, but separate
from, the source evidence. `review.json` is the canonical active schema version
`2` container for minimum requirements, review units, Focus Standard
observations, overall ratings, feedback composition, private notes, and export
metadata.

### Derived Exports and Reports

Derived outputs are generated from teacher-reviewed records:

* `submissions/<student_id>/exports/feedback.pdf`
* `submissions/<student_id>/exports/feedback.md`
* `exports/student_performance_summary.csv`
* `exports/class_summary.csv`
* `exports/standards_summary.csv`

Exports and reports should be reproducible from the applicable reviewed
records and should not become the sole copy of submission evidence or teacher
decisions.

## Active Records vs. Historical Preservation

The Quillan workspace described here contains active records for current
instructional use. Normal capture, review, correction, supersession, and
validation all occur within this active lifecycle.

The term "archive" is reserved for inactive historical preservation and future
`pds-sunset` workflows. It does not describe active scan intake, retained
source scans, routing review, or current-year teacher-working records. Moving a
record into historical preservation must not be assumed from its current
lifecycle status.

## Relationship to `docs/data_contracts.md`

[`data_contracts.md`](data_contracts.md) defines the content and validation
expectations for individual JSON, text, Markdown, and CSV records. This
document defines where those records belong in the shared PDS workspace and
how they relate to one another over time.

[`teacher_review_model.md`](teacher_review_model.md) defines what source
evidence, teacher-review artifacts, Focus Standard ratings, feedback, and
derived reports mean within Quillan's teacher-controlled review process.

[`printable_response_template.md`](printable_response_template.md) defines the
required structure, identity fields, PDS1 payload use, writing area, and
implemented `templates/printable_response_pages.pdf` output for printable
writing-response pages.

[`scan_routing_design.md`](scan_routing_design.md) defines how decoded response
payloads are validated and how Quillan routed evidence fits the shared
`pds-core` active scan contract. The direct `route-scan` command supports
caller-supplied decoded payloads and QR-aware image, PDF, or non-recursive
folder intake. Canonical retained sources belong in `scans/source/YYYY-MM-DD/`,
canonical failure records belong in `scans/review/`, and assignment-level
`scans/` contains routed evidence. OCR remains outside Quillan's scope.

## Scan Intake and Submission Assembly

`scans_inbox/` is the shared teacher drop zone for scans awaiting routing. Quillan
creates it on entry to Scan Intake and never moves or deletes its source files.
Routed assignment evidence belongs under the assignment's `scans/` directory.
That evidence is not review-ready until explicit assembly writes
`submissions/<student_id>/submission.json`. Assembly skips existing submission
files by default; regenerating an existing submission is an explicit destructive
choice because it can replace the submission record.
