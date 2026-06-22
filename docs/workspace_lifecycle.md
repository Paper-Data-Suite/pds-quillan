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
              submission.txt
              requirements.json
              tags.json
              scores.json
              feedback.md
          reports/
            standards_summary.csv
            class_summary.csv
          debug/
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
assignments, submissions, printable PDFs, scans, reports, tags, scores,
feedback, or historical evidence.

### `assignment.json`

The teacher-created assignment configuration. It defines the task, writing
type, connected class IDs, standards profile reference, focus standards,
basic requirements, tagging mode, and rubric reference.

Quillan's Assignment Management menu can create this file from prompts after
the teacher selects a class with an existing canonical roster. It uses the
existing assignment validation contract and the shared assignment route:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The menu can also load, validate, and summarize an explicit assignment JSON
path without rewriting it. Existing configs require exact `OVERWRITE`
confirmation before replacement. This workflow does not edit or delete
assignments and does not perform scoring, feedback, tagging execution,
requirements checking, reporting, scan routing, OCR, AI, or printable packet
generation.

### `templates/`

A shared assignment-local directory for generated or teacher-facing printable
materials. The Python API and Printable Response Pages menu create
`templates/printable_response_pages.pdf` as one combined class packet of
roster-aware writing-response pages. The menu requires an existing canonical
roster and assignment config and protects replacement with exact `OVERWRITE`
confirmation. Generation does not rewrite either source file. Generated PDFs
are local workspace artifacts and should not be committed. A dedicated
printable-response CLI is not implemented. The response-page contract is
defined in
[`printable_response_template.md`](printable_response_template.md).

### Workspace `scans/source/YYYY-MM-DD/`

The shared canonical store for active retained source scans, date-bucketed by
the PDS intake date in UTC. A future scan workflow must copy every readable
selected source here before Quillan-specific parsing or routing, leave the
teacher's original selected file untouched, avoid silent overwrites, and
preserve provenance from routed evidence back to this retained source.

### Workspace `scans/review/`

The shared workspace-level location for canonical routing failure records and
optional problem artifacts. Future Quillan failures must use the shared
`pds-core` metadata shape and failure categories, with Quillan-specific details
under `module_details`. Quillan does not currently create or process this
directory.

### Assignment `scans/`

A reserved assignment-local directory for routed scan evidence. It is not the
canonical retained source location. The future validation, naming, collision,
provenance, and failure-review behavior is defined in
[`scan_routing_design.md`](scan_routing_design.md). Its presence does not imply
that Quillan currently routes scans, performs OCR, or files captured pages.

### `submissions/<student_id>/submission.json`

The Quillan version `1` submission manifest for one student's routed
evidence for one assignment. It identifies the class, assignment, and student;
represents expected, missing, duplicate, replacement, damaged, or excluded
pages; preserves retained-source provenance; and records teacher-controlled
review state without containing scores, tags, or feedback.

Loading, validation, canonical path computation, safe writing, and
new-manifest assembly from caller-provided evidence metadata are implemented
in modules distinct from the legacy text-oriented loader. Scan-folder
discovery, merging, and state-changing review workflows are not implemented.

### `submissions/<student_id>/submission.txt`

The student-produced writing evidence in plain text. It remains separate from
requirements results, review tags, scores, feedback, and reports so the source
evidence is not rewritten as teacher judgment is added.

### `submissions/<student_id>/requirements.json`

A future requirements-check result for basic teacher-defined assignment
requirements. It should record whether requirements were met, partially met,
not met, or not checked. It is a teacher-review support artifact, not a score.
Requirements checking is not implemented by this document.

### `submissions/<student_id>/tags.json`

A future collection of teacher-review evidence tags. Each tag should connect a
teacher observation to a location in the writing, a standard, a reusable
comment, and a polarity. Tags organize reviewed evidence; they do not
determine a score. Tagging is not implemented by this document.

### `submissions/<student_id>/scores.json`

A future teacher scoring record. Scores are teacher judgment artifacts and are
not automatically determined by tags, requirement results, or other software
outputs. Scoring is not implemented by this document.

### `submissions/<student_id>/feedback.md`

A future student-readable feedback record reflecting teacher review. It should
remain traceable to the teacher-reviewed submission and should not be treated
as a replacement for teacher judgment. Feedback generation is not implemented
by this document.

### `reports/`

The assignment-local location for future reports derived from
teacher-reviewed records. Expected MVP report names are
`standards_summary.csv` and `class_summary.csv`. Reports summarize records;
they do not replace the underlying source evidence or teacher-review
artifacts. Report generation is not implemented by this document.

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

* `submission.txt`
* `submission.json`

`submission.txt` remains an optional text-oriented evidence artifact for
workflows that use it. The manifest is part of the evidentiary record because
it establishes identity, provenance, page state, and teacher-controlled review
state. It does not contain the teacher's score, tags, or feedback.

### Teacher-Review Artifacts

Teacher-review artifacts are records created by the teacher or confirmed
through teacher review:

* `requirements.json`
* `tags.json`
* `scores.json`
* `feedback.md`

These records support efficient review while preserving the teacher as the
source of evaluative judgment. They should remain connected to, but separate
from, the source evidence.

### Derived Reports

Derived reports aggregate teacher-reviewed records:

* `reports/standards_summary.csv`
* `reports/class_summary.csv`

Reports should be reproducible from the applicable reviewed records and should
not become the sole copy of submission evidence or teacher decisions.

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
evidence, teacher-review artifacts, scores, feedback, and derived reports mean
within Quillan's teacher-controlled review process.

[`printable_response_template.md`](printable_response_template.md) defines the
required structure, identity fields, PDS1 payload use, writing area, and
implemented `templates/printable_response_pages.pdf` output for printable
writing-response pages.

[`scan_routing_design.md`](scan_routing_design.md) defines how a future router
should validate decoded response payloads and create Quillan routed evidence
under the shared `pds-core` active scan contract. Canonical retained sources
belong in `scans/source/YYYY-MM-DD/`, canonical failure records belong in
`scans/review/`, and assignment-level `scans/` contains routed evidence.

