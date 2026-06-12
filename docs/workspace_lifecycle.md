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

The shared `pds-core` route helpers define the assignment and submission
locations. Quillan-specific files remain inside those shared routes.

## Core Directory Layout

The expected MVP layout is:

```text
<PDS workspace root>/
  classes/
    <class_id>/
      assignments/
        <assignment_id>/
          assignment.json
          templates/
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

The assignment directory, `assignment.json`, `submissions/`, and each
student's submission directory follow shared PDS route conventions. The other
directories and files shown above are assignment-local Quillan records or
reserved locations for future workflows. A directory does not need to exist
until a workflow has a reason to create it.

## File Responsibilities

### `assignment.json`

The teacher-created assignment configuration. It defines the task, writing
type, connected class IDs, standards profile reference, focus standards,
basic requirements, tagging mode, and rubric reference.

### `templates/`

A reserved assignment-local directory for future generated or teacher-facing
printable materials. Template or printable-material generation is not part of
the current lifecycle implementation. The contract for future printable
writing-response pages and their use of this directory is defined in
[`printable_response_template.md`](printable_response_template.md).

### `scans/`

A reserved assignment-local directory for future scan inputs or scan-related
files. Its presence does not imply that Quillan currently routes scans,
performs OCR, or files captured pages.

### `submissions/<student_id>/submission.json`

Submission metadata for the student's writing artifact. It identifies the
assignment, class, student, source type, text file, capture time, lifecycle
status, and version. It describes provenance and workflow state without
containing scores or feedback.

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

## File Lifecycle States

The `status` field in `submission.json` describes whether a submission record
is usable and where it is in the teacher-controlled review workflow. A status
change does not, by itself, require moving the submission to another
directory.

### `captured`

The writing evidence has been collected or imported and has submission
metadata. Capture establishes the record and its provenance; it does not mean
that teacher review is complete.

### `needs_review`

The submission exists but still requires teacher review. This may be used
after capture when the record is ready to enter the teacher's review queue.

### `reviewed`

The teacher has reviewed the submission or confirmed the relevant review
artifacts. This state represents teacher confirmation, not a software-made
judgment about achievement.

### `superseded`

A newer version or corrected record has replaced this record for current use.
The older record may remain in place so its provenance and relationship to
later records can be traced.

### `invalid`

The record should not be used for scoring or reporting because it is
incomplete, misfiled, corrupt, mismatched, or otherwise unusable. Retaining an
invalid record may still be useful for diagnosis and traceability.

These are the active MVP lifecycle states. `archived` is not an active
submission status.

## Versioning and Supersession

The `version` field in `submission.json` is a positive integer that identifies
the version of the submission record. A newer version may supersede an older
version when writing is recaptured, corrected, or replaced.

At MVP level:

* version numbers begin at `1` and remain positive integers;
* a higher version can replace a lower version for current instructional use;
* an older record can be marked `superseded` and retained for traceability;
* version and status should be read together rather than assuming every
  higher number is automatically teacher-approved; and
* no versioned directory structure or automatic file movement is required.

Because the current shared route is student-local, this contract does not
prescribe how multiple retained versions must be named or arranged inside the
student directory. That routing decision requires a separate design before
implementation.

## Source Evidence vs. Teacher-Review Artifacts

Quillan keeps three record categories distinct.

### Source Evidence

Source evidence is the student-produced writing and the metadata needed to
identify what was submitted and how it entered the workflow:

* `submission.txt`
* `submission.json`

The metadata is part of the evidentiary record because it establishes identity,
provenance, status, and version. It does not contain the teacher's score or
feedback.

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

The term "archive" is reserved for a future inactive or historical
preservation design. If long-term preservation is needed, it should be
specified separately and may live outside Quillan's immediate active-year
workflow. Moving a record into historical preservation must not be assumed
from its current lifecycle status.

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
intended `templates/` location for future printable writing-response pages.

