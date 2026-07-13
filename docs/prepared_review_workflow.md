# Standards-Based Review Workflow

## Purpose

Quillan's active v0.8.6 workflow is a local-first, teacher-controlled review
process for written student work:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Quillan helps organize review decisions. It does not read student work,
generate feedback, score automatically, infer mastery, run OCR, or use AI.

This document replaces the removed generic tag, comment-bank, rubric, and
criterion-score workflow.

## Subject-Agnostic Design

Quillan is designed for teacher review of written responses across disciplines:
ELA, history / social studies, science, computer science, technical writing,
world languages, arts/humanities, and interdisciplinary writing tasks.

The active workflow is organized around assignment-local Focus Standards and
teacher-defined review units, not around a subject-specific grading scheme.

## Before Review

1. Create or select a local Paper Data Suite workspace.
2. Create or load a class roster.
3. Create a schema version `2` assignment.
4. Select a pds-core standards profile.
5. Select assignment Focus Standards in `focus_standard_ids`.
6. Configure the review unit and rating scale.
7. Configure `basic_requirements` and `minimum_requirement_policy`.
8. Generate printable response pages if using paper.
9. Route QR-bearing scans and assemble submissions.
10. Confirm each selected student has reviewable evidence.

The assignment record is the source of truth for the student prompt, writing
type, standards profile, Focus Standards, review-unit labels, rating scale,
basic requirements, and minimum-requirement return policy.

## During Review

1. Select class, assignment, and student.
2. Open selected submission evidence.
3. Review minimum requirements.
4. Define or replace review units.
5. Record review-unit Focus Standard observations.
6. Enter overall Focus Standard ratings.
7. Compose Focus Standard feedback.
8. Add private teacher notes when needed.
9. Update submission review state when appropriate.
10. Export student feedback.
11. Export assignment-local summaries when needed.

Opening evidence does not mark a submission reviewed. Exporting feedback does
not rescore work or create teacher judgments.

## Minimum Requirements

Minimum-requirement checks are generated from assignment `basic_requirements`
and stored in:

```text
review.json.minimum_requirement_checks
```

The teacher records whether each requirement was met. Missing checks are not
treated as unmet automatically.

The overall minimum-requirement decision is stored in:

```text
review.json.minimum_requirement_outcome
```

Supported outcome statuses are `met`, `unmet_continue_review`, and
`returned_without_full_review`. Returning work without full standards review
requires a teacher note when the assignment policy permits that path.

Teachers may use either the interactive review menu or the direct,
non-interactive `quillan requirements list`, `set-check`, and `set-outcome`
commands. Both paths share assignment-derived requirement definitions and
outcome eligibility rules. Direct commands require an assembled canonical
`submission.json`; they never assemble submissions, inspect writing, count
text, run OCR or AI, or infer a teacher judgment. Listing is read-only, while
the set commands may change only the submission's canonical `review.json`.

Minimum-requirement checks do not count words, count paragraphs, parse writing,
run OCR, use AI, change ratings, or calculate grades.

## Review Units And Observations

Review units are teacher-defined segments of the response, such as paragraphs,
sections, slides, problems, stanzas, or another assignment-appropriate unit.
They are stored in:

```text
review.json.review_units
```

Each unit can contain Focus Standard observations:

```text
review.json.review_units[].standard_observations
```

Observations are teacher-entered. They can record whether the standard applies,
whether evidence is present, an optional rating, a rationale, and whether the
observation should be considered for student feedback.

Ratings on review-unit observations are optional. Overall Focus Standard
ratings are entered separately.

Teachers may define or inspect units through the interactive menu or the
direct, non-interactive `quillan review-units` commands. `show` performs no
writes. `set --count N` creates assignment-derived sequences `1..N`, while
`set --units units.json` permits explicit sequences, custom labels, and
optional manifest-backed page/evidence references. Both paths require an
assembled canonical submission manifest and use the same atomic review-unit
service. Stable unit IDs preserve observations; removed-unit observations and
their stale feedback references are removed. These commands never inspect
evidence content, run OCR or AI, or infer segmentation, labels, observations,
ratings, feedback, grades, or scores.

Teachers may likewise inspect or record unit-standard observations through
the direct, non-interactive `quillan observations list` and `quillan
observations set` commands. Listing shows the complete active matrix in unit
sequence and assignment Focus Standard order and never writes. Setting
requires an existing unit, an assignment Focus Standard, explicit
applicability, and explicit evidence presence for applicable observations.
Applicable unit ratings remain optional and, when supplied, are validated
against the assignment rating scale. Not-applicable observations store null
evidence presence and rating. Updates replace editable values while preserving
the observation ID. Feedback eligibility does not compose feedback or change
included-observation lists, and observation writes never create or alter
overall Focus Standard ratings.

Both observation commands require an assembled canonical submission manifest.
Only `set` writes, and it may change only the canonical `review.json`. Returned
without-full-review records can be listed but cannot be changed until the
minimum-requirements outcome changes. These commands do not inspect evidence,
run OCR, handwriting recognition, or AI, infer judgments, calculate ratings,
grades, or scores, mark observations complete, or generate feedback.

## Overall Focus Standard Ratings

Overall ratings are stored in:

```text
review.json.overall_standard_ratings
```

Each rating belongs to one assignment Focus Standard and uses a value from the
assignment `rating_scale`. Ratings are teacher-entered and are not inferred
from review-unit observations, requirement checks, notes, exports, or evidence
metadata.

Marking ratings complete is an explicit teacher action.

## Focus Standard Feedback

Feedback composition is stored in:

```text
review.json.feedback.standard_feedback
```

For each Focus Standard, the teacher can choose whether to include the overall
rating, include the overall rationale, include selected observation IDs, add
custom comments, select reusable Focus Standard comments, and save suitable
custom comments for reuse.

Reusable Focus Standard comments live at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

When selected, reusable comments are snapshotted into `review.json`; feedback
exports use the copied text, not a live lookup into the reusable source file.

Generic legacy comment banks are not used by the active v0.8.6 feedback
composition workflow.

## Exports And Reports

Student feedback exports are derived artifacts:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

Returned-work feedback can be exported when a review is returned without full
standards review.

Assignment-local summaries are also derived artifacts:

```text
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

Student Performance Summary is the compact teacher-facing student-by-standard
report. Comprehensive Class Summary (`class_summary.csv`) is the
audit/troubleshooting report. Standards Summary is the Focus Standard
aggregate report.

The class summary reports submission/review status, minimum-requirement
outcomes, returned-without-full-review status, overall Focus Standard ratings,
and feedback PDF/Markdown status.

The Focus Standard summary reports assignment-local rating distributions,
missing ratings, returned-without-full-review counts, and feedback coverage.

Reports do not calculate grades, percentages, mastery, or cross-assignment
results.

## Storage Map

```text
classes/<class_id>/assignments/<assignment_id>/assignment.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
shared/focus_standard_comments/<comment_set_id>.json
```

`submission.json` is evidence metadata. `review.json` is the teacher-review
artifact. Exports and reports are derived from canonical records.

## Legacy Materials

Legacy comment-bank, tag-bank, and rubric files may remain in the repository
as historical or compatibility material. They should be clearly labeled as
legacy/inactive where linked from current docs.

Active v0.8.6 docs and examples should not tell teachers to use generic
comment banks, tag banks, rubric criteria, top-level `review.json.tags`,
top-level `review.json.comments`, top-level `review.json.scores`, or old direct
write commands.

## Safety Boundaries

Quillan preserves the teacher-controlled model:

* source evidence, review artifacts, reusable comments, and exports stay
  distinct;
* exports are derived from teacher-confirmed review records;
* standards references are durable pds-core IDs;
* examples and tests use synthetic data only.

Do not commit real student names, rosters, writing, grades, scans, review
notes, feedback, exports, or personally identifiable information.

## Related Docs

* [`data_contracts.md`](data_contracts.md)
* [`assignment_contract.md`](assignment_contract.md)
* [`review_record_contract.md`](review_record_contract.md)
* [`focus_standard_comment_contract.md`](focus_standard_comment_contract.md)
* [`feedback_export_contract.md`](feedback_export_contract.md)
* [`assignment_reporting_contract.md`](assignment_reporting_contract.md)
* [`teacher_review_model.md`](teacher_review_model.md)
* [`workspace_lifecycle.md`](workspace_lifecycle.md)

## Work completed on plain paper

For a roster student with neither routed evidence nor a manifest, the selected
student review screen can create a plain-paper manual submission after teacher
confirmation. This creates only `submission.json` and `review.json`; it does
not route scans, attach images, run OCR, or invent evidence paths. Continue
with the existing minimum-requirement, review-unit, Focus Standard, feedback,
note, state, and export actions while reviewing the physical paper.
