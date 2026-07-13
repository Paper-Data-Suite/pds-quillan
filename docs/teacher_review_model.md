# Quillan Teacher-Review Model

## Overview

Quillan's review model is teacher-controlled. It preserves student evidence,
records teacher judgments, formats teacher-approved feedback, and summarizes
confirmed review records. It does not replace the teacher's professional
judgment.

The active v0.8.6 review model is standards-based:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Quillan does not implement AI tagging, AI scoring, AI feedback, automatic
requirements evaluation, OCR, handwriting recognition, automatic grading, or
automatic mastery calculation.

## Record Roles

Quillan keeps source evidence, teacher review artifacts, and derived exports
separate.

Source evidence:

```text
submission.json
routed evidence files under classes/<class_id>/assignments/<assignment_id>/scans/
```

Teacher review artifact:

```text
submissions/<student_id>/review.json
```

Derived exports and reports:

```text
submissions/<student_id>/exports/feedback.pdf
submissions/<student_id>/exports/feedback.md
exports/student_performance_summary.csv
exports/class_summary.csv
exports/standards_summary.csv
```

Source evidence describes what was submitted and how it is managed. It does
not contain teacher ratings, feedback composition, or private notes.

Derived exports are not independent evidence and do not replace
`review.json`.

## Active Review Record

The active teacher-review artifact is schema version `2` `review.json`,
defined by [`review_record_contract.md`](review_record_contract.md).

It stores:

* identity fields;
* `submission_manifest_path`;
* `assignment_path`;
* `review_state`;
* `minimum_requirement_checks`;
* `minimum_requirement_outcome`;
* `review_units`;
* `review_units[].standard_observations`;
* `overall_standard_ratings`;
* `feedback.standard_feedback`;
* `private_notes`;
* `exports.feedback_pdf`; and
* `exports.feedback_markdown`.

The adjacent `submission.json` remains the canonical evidence manifest. The
associated `assignment.json` remains the source of truth for student prompt,
writing type, standards profile, Focus Standards, review-unit labels, rating
scale, basic requirements, and minimum-requirement policy.

## Minimum Requirements

Minimum-requirement checks document teacher-entered decisions about basic
assignment conditions. They are stored in:

```text
review.json.minimum_requirement_checks
review.json.minimum_requirement_outcome
```

Requirement checks do not measure writing quality. Quillan does not count
words, count paragraphs, parse writing, run OCR, or infer whether a required
element is present. Missing checks are not automatically treated as unmet.

The return-without-full-review path is explicit and requires a teacher note
when used.

## Review Units

Review units are teacher-defined pieces of the response: paragraphs, sections,
slides, problems, stanzas, or another assignment-appropriate unit.

Each review unit can contain Focus Standard observations. Observations can
record applicability, evidence presence, an optional rating, a rationale, and
whether that observation should be included in feedback consideration.

Review-unit observations help the teacher reason about evidence. They do not
automatically become overall ratings.

## Overall Focus Standard Ratings

Overall Focus Standard ratings are stored in:

```text
review.json.overall_standard_ratings
```

Ratings are teacher-entered, assignment-local judgments for each Focus
Standard. Rating values come from the assignment `rating_scale`.

Quillan must not infer overall ratings from review-unit observations,
requirement checks, private notes, reusable comments, tags, prior exports, or
student writing.

## Feedback

Feedback is student-readable teacher communication stored before export in:

```text
review.json.feedback.standard_feedback
```

For each Focus Standard, the teacher controls whether to include the overall
rating, overall rationale, selected observation IDs, custom comments, and
snapshotted reusable Focus Standard comments.

Reusable Focus Standard comments are source material stored at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

They are not student records and do not generate feedback by themselves. When
selected, their text is copied into the review record as a stable snapshot.
Later changes to the reusable source do not rewrite prior reviews or exports.

Feedback exports exclude private notes, internal review IDs, reusable-comment
provenance, routed evidence paths, unselected observations, and unselected
comments.

## Reports

Reports summarize teacher-reviewed records for one assignment.

The Student Performance Summary is the compact ordinary teacher-facing
student-by-standard table. The Comprehensive Class Summary at
`class_summary.csv` reports submission status, review status,
minimum-requirement outcomes, returned-without-full-review state, overall
Focus Standard ratings, feedback PDF/Markdown status, and warnings.

The Focus Standard summary reports assignment-local rating distributions,
missing-rating counts, returned-without-full-review counts, and feedback
coverage by Focus Standard.

Reports do not inspect writing, calculate grades, calculate percentages,
infer mastery, combine assignments, or serve as a gradebook.

## Legacy Material

The old schema version `1` model centered on top-level `notes`, `tags`,
`comments`, `scores`, and `requirement_checks`. The old direct workflows
`add-tag`, `add-comment`, and `set-score` are historical/compatibility
material only and are not the active v0.8.6 review path.

The generic tag, comment-bank, rubric, and criterion-score runtime modules,
examples, and contracts have been removed.

## Review Readiness

Routed scan evidence and an assembled submission are distinct. Before review,
Quillan requires a review-ready `submission.json`. Assembly neither evaluates
evidence nor changes review state, review records, feedback, or exports.

Selected-student review actions clear and reframe major action screens, support
Back cancellation, and avoid writing until the teacher confirms the specific
action.

Updating submission review state is an explicit workflow status change.
Quillan does not infer review state from observations, ratings, notes,
feedback, or exports.

Submission page management is an evidence-metadata workflow separate from
teacher judgment. The menu and direct `pages` commands share one service for
listing, excluding, restoring, and marking pages as needing rescan. Excluded
pages and their routed evidence are retained, not deleted. Restoration recovers
preserved evidence roles and states when available and uses a conservative
legacy fallback otherwise. These changes do not update top-level submission
state or mutate review records, ratings, observations, feedback, or exports.

## Related Docs

* [`data_contracts.md`](data_contracts.md)
* [`prepared_review_workflow.md`](prepared_review_workflow.md)
* [`assignment_contract.md`](assignment_contract.md)
* [`review_record_contract.md`](review_record_contract.md)
* [`feedback_export_contract.md`](feedback_export_contract.md)
* [`assignment_reporting_contract.md`](assignment_reporting_contract.md)
* [`workspace_lifecycle.md`](workspace_lifecycle.md)

## Plain-paper evidence under teacher control

Quillan can initialize the standards-based review model for work written on
plain paper outside Quillan. The submission has no digital pages; the teacher
retains and reviews the physical paper, then records judgments through the
same review units, Focus Standards, feedback, private notes, and workflow
states used for scanned submissions.
