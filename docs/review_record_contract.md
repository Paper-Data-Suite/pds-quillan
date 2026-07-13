# Quillan Submission Review Record Contract

## Purpose and Boundary

The Quillan submission review record stores teacher-entered review data for
one student submission. Its canonical workspace-relative path is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

`review.json` is separate from the adjacent `submission.json` evidence
manifest and the associated `assignment.json` assignment configuration:

* `submission.json` answers what evidence exists, where it came from, which
  evidence is selected, and what evidence-management state it is in.
* `assignment.json` answers what the teacher assigned, which Focus Standards
  are active, which review-unit labels should be used, which rating scale
  applies, and what minimum requirements exist.
* `review.json` answers what the teacher recorded about the selected
  submission evidence for that assignment.

Teacher review must not rewrite or duplicate the evidence manifest. In
particular, `review.json` may reference evidence by `evidence_id`, page number,
review-unit sequence, and workspace-relative paths, but it does not copy routed
evidence files or retained-source records.

This document defines the active submission review schema version `2` for the
v0.8.6 standards-based workflow redesign.

Schema version `2` supersedes the older v0.7 review model centered on generic
notes, tags, criterion scores, selected comments, and requirement checks. In
the v0.8.6 model, the central review relationship is:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

The redesigned review record stores:

* minimum requirement checks;
* minimum-requirement outcome;
* review units;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* feedback composition choices organized by Focus Standard;
* student-facing feedback comments organized by Focus Standard;
* private teacher notes when needed; and
* export metadata for derived student-facing feedback files.

For the standards-based redesign rationale, see:

* [`standards_based_review_redesign.md`](standards_based_review_redesign.md)
* [`adr/0001-standards-based-review-model.md`](adr/0001-standards-based-review-model.md)
* [`assignment_contract.md`](assignment_contract.md)

## Status

This is the active review record contract for v0.8.6. Runtime validators,
review menus, exports, reports, and tests now use schema version `2` review
records. Future migration helpers may still be added if legacy classroom data
ever needs conversion.

The older schema version `1` contract remains legacy development history. It
is summarized later in this document, but it is not the active architecture for
new standards-based review work.

## Canonical Path

The canonical active review record path remains:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

The adjacent evidence manifest remains:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

The associated assignment record normally remains:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The review record must reference the submission manifest and assignment record
using workspace-relative paths.

## Relationship to `submission.json`

`submission.json` is the evidence-management record. It owns:

* expected pages;
* selected evidence;
* candidate evidence;
* duplicate evidence;
* missing-page state;
* needs-rescan state;
* excluded evidence;
* retained-source provenance; and
* submission-management state.

`review.json` must not duplicate routed evidence paths, retained-source paths,
or page-candidate structures from `submission.json`.

A review record may reference an evidence candidate by `evidence_id` when a
teacher wants to connect a review unit, observation, note, or feedback choice
to a specific evidence item.

Opening evidence does not create, score, complete, or export a review record.

## Relationship to `assignment.json`

A schema version `2` review record depends on a schema version `2` assignment
record.

The assignment record defines:

* `student_prompt`;
* `writing_type`;
* `standards_profile_id`;
* `focus_standard_ids`;
* `review_unit`;
* `rating_scale`;
* `basic_requirements`; and
* `minimum_requirement_policy`.

The review record uses those assignment-defined values. It should not duplicate
the full assignment configuration unless a later snapshot policy explicitly
requires that behavior.

The review record stores `assignment_path` so that review data remains
traceable to the assignment contract used when the review was created.

## Top-Level Structure

Every schema version `2` review record contains:

```json
{
  "schema_version": "2",
  "module": "quillan",
  "record_type": "submission_review",
  "class_id": "english_10_simulation",
  "assignment_id": "coming-of-age_literary_analysis",
  "student_id": "10001",
  "submission_manifest_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/submission.json",
  "assignment_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/assignment.json",
  "review_state": "not_started",
  "minimum_requirement_checks": [],
  "minimum_requirement_outcome": {
    "status": "not_checked",
    "returned_without_full_review": false,
    "teacher_note": null,
    "updated_at": null
  },
  "review_units": [],
  "overall_standard_ratings": [],
  "feedback": {
    "include_review_unit_observations": false,
    "include_overall_standard_ratings": true,
    "standard_feedback": []
  },
  "exports": {
    "feedback_pdf": null,
    "feedback_markdown": null
  },
  "private_notes": [],
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required top-level fields are:

* `schema_version`;
* `module`;
* `record_type`;
* `class_id`;
* `assignment_id`;
* `student_id`;
* `submission_manifest_path`;
* `assignment_path`;
* `review_state`;
* `minimum_requirement_checks`;
* `minimum_requirement_outcome`;
* `review_units`;
* `overall_standard_ratings`;
* `feedback`;
* `exports`;
* `private_notes`;
* `created_at`;
* `updated_at`; and
* `module_details`.

Unknown top-level fields are not part of schema version `2`. A future contract
change must use a new schema version when it changes the meaning or required
shape of existing data.

## Identity and References

`class_id`, `assignment_id`, and `student_id` use the shared `pds-core`
identifier policy. They are case-sensitive strings, and student identifiers
remain strings so leading zeros are preserved.

The three identity fields must match:

1. the values in the referenced `submission.json`;
2. the corresponding path segments in `submission_manifest_path`;
3. the corresponding assignment path segments in `assignment_path`; and
4. the directory path containing this `review.json`.

For a review record with identity `<class_id>`, `<assignment_id>`, and
`<student_id>`, the canonical submission manifest reference is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

The canonical assignment reference is:

```text
classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Review-local identifiers such as `requirement_check_id`, `unit_id`,
`observation_id`, `feedback_comment_id`, and `private_note_id` are opaque,
non-empty strings. Each identifier must be unique within its relevant scope.
Consumers must not derive ordering, timestamps, or meaning from an identifier's
spelling.

When present:

* `standard_id` must identify a Focus Standard from the assignment's
  `focus_standard_ids`;
* `evidence_id` must identify an evidence candidate in the referenced
  `submission.json`;
* `page_number` must identify the page entry containing that evidence when
  both fields are present;
* `rating` must use a `value` from the assignment's `rating_scale.levels`; and
* `unit_type` should match the assignment's `review_unit.type`.

## Review State

Allowed schema version `2` `review_state` values are:

* `not_started`;
* `requirements_checked`;
* `returned_without_full_review`;
* `observations_in_progress`;
* `observations_complete`;
* `ratings_complete`;
* `feedback_composed`;
* `ready_for_export`; and
* `exported`.

State meanings:

* `not_started`: no substantive teacher-review data has been entered.
* `requirements_checked`: minimum requirements have been checked, but full
  standards review has not begun.
* `returned_without_full_review`: the teacher has chosen to return the work
  without full standards review because minimum requirements were not met.
* `observations_in_progress`: review-unit Focus Standard observations have
  begun but are not complete.
* `observations_complete`: review-unit Focus Standard observations are
  complete enough for the teacher to move to overall ratings.
* `ratings_complete`: overall Focus Standard ratings have been entered.
* `feedback_composed`: student-facing feedback choices and comments have been
  composed.
* `ready_for_export`: the teacher has explicitly marked the current review
  data ready for export.
* `exported`: one or more student-facing feedback exports have been generated
  from the review record.

`review_state` describes teacher review work. It is distinct from
`submission_state` in `submission.json`, which describes evidence and
submission management. Neither state determines or automatically changes the
other.

The state is not inferred merely because an array is empty or populated.
Writers are responsible for making explicit state changes.

Opening evidence does not mark review started.

Exporting feedback does not rescore work.

Returning a submission without full review is a distinct review state. It must
not be treated as a score, zero, completed standards rating, or ordinary
completed review.

## Minimum Requirement Checks

`minimum_requirement_checks` records teacher-entered checks against the
assignment's `basic_requirements`.

These checks remain separate from writing-quality ratings.

Quillan may prompt from configured assignment requirements such as:

* `paragraphs_min`;
* `paragraphs_max`;
* `word_count_min`;
* `word_count_max`; and
* individual `required_elements`.

Quillan must not:

* count paragraphs automatically;
* count words automatically;
* parse student writing;
* run OCR to determine whether requirements are met;
* use AI to detect required elements; or
* infer whether a requirement is met.

The teacher records whether each requirement was met.

Example:

```json
{
  "requirement_check_id": "requirement_check_0001",
  "requirement_key": "paragraphs_min",
  "label": "Minimum paragraphs",
  "expected": 1,
  "met": true,
  "teacher_note": null,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required element example:

```json
{
  "requirement_check_id": "requirement_check_0002",
  "requirement_key": "required_elements:textual_evidence",
  "label": "Required element: textual evidence",
  "expected": "textual evidence",
  "met": true,
  "teacher_note": null,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required fields:

* `requirement_check_id`;
* `requirement_key`;
* `label`;
* `expected`;
* `met`;
* `updated_at`; and
* `module_details`.

Optional fields:

* `teacher_note`.

Field rules:

* `requirement_check_id` is unique within `minimum_requirement_checks`.
* `requirement_key` is non-empty and unique within
  `minimum_requirement_checks`.
* `label` is a non-empty teacher-facing string.
* `expected` is a finite number or non-empty string copied from assignment
  configuration.
* `met` is a boolean.
* `teacher_note`, when present, is either `null` or a non-empty string.
* `updated_at` is the last teacher update timestamp for that requirement
  check.
* `module_details` is an object.

Requirement checks are mutable by `requirement_key`. Updating a check preserves
its `requirement_check_id`, replaces the recorded boolean and optional teacher
note, updates top-level `updated_at`, and preserves unrelated review data.

## Minimum Requirement Outcome

`minimum_requirement_outcome` records the teacher's decision after minimum
requirement checks.

The direct `quillan requirements` commands use the same assignment-aware
services as the teacher menu. Configured keys, labels, expected values, and
outcome eligibility derive from the current assignment. Arbitrary or stale
keys cannot be written or used to satisfy outcome eligibility. These commands
require an existing canonical submission manifest and preserve every unrelated
section of an existing schema-version-2 review. They do not inspect evidence or
infer checks, outcomes, ratings, or feedback.

Example:

```json
{
  "status": "met",
  "returned_without_full_review": false,
  "teacher_note": null,
  "updated_at": "2026-07-02T00:00:00+00:00"
}
```

Required fields:

* `status`;
* `returned_without_full_review`;
* `teacher_note`; and
* `updated_at`.

Allowed `status` values are:

* `not_checked`;
* `met`;
* `unmet_continue_review`; and
* `returned_without_full_review`.

Field rules:

* `status` must be one of the controlled values above.
* `returned_without_full_review` is a boolean.
* `teacher_note` is either `null` or a non-empty string.
* `updated_at` is either `null` when `status` is `not_checked`, or a
  timezone-aware ISO 8601 timestamp.

When `status` is `returned_without_full_review`,
`returned_without_full_review` must be `true`.

When `returned_without_full_review` is `true`, the top-level `review_state`
should be `returned_without_full_review`.

Returning work without full review must not be treated as:

* a zero;
* a grade;
* a completed standards review;
* completed Focus Standard scoring;
* a normal reviewed submission; or
* an automatic judgment.

It is a separate teacher-controlled outcome indicating that the submission was
not ready for full standards-based review.

## Review Units

`review_units` stores the actual review units used for the student's
submission.

The assignment defines the review-unit type and teacher-facing labels. The
review record stores the units the teacher created or confirmed for this
student's submission.

Example:

```json
{
  "unit_id": "paragraph_1",
  "sequence": 1,
  "label": "Paragraph 1",
  "unit_type": "paragraph",
  "page_number": 1,
  "evidence_id": "evidence_001",
  "standard_observations": [],
  "module_details": {}
}
```

Required fields:

* `unit_id`;
* `sequence`;
* `label`;
* `unit_type`;
* `standard_observations`; and
* `module_details`.

Optional fields:

* `page_number`;
* `evidence_id`;

Field rules:

* `unit_id` is unique within `review_units`.
* `sequence` is a positive integer.
* `label` is a non-empty teacher-facing string.
* `unit_type` should match the assignment's `review_unit.type`.
* `page_number`, when present, is a positive integer.
* `evidence_id`, when present, references the submission manifest.
* `standard_observations` is an array of review-unit Focus Standard
  observations.
* `module_details` is an object.
* Review units should be ordered by `sequence`.

Review units are teacher-created or teacher-confirmed. Quillan must not parse
student writing, run OCR, or automatically infer how many review units a
student wrote.

The direct `review-units set` command replaces the complete array through the
shared review-unit service. It accepts either an explicit count or constrained
JSON definitions containing only `sequence`, `label`, `page_number`, and
`evidence_id`. The assignment always supplies `unit_type`; `unit_id` is always
`<unit_type>_<sequence>`. Matching IDs preserve observations. Removed IDs
remove their observations and any stale feedback observation references,
while unrelated review data and the original `created_at` remain unchanged.
Page and evidence references are checked against the canonical submission
manifest without opening evidence files. This does not change schema version
`2`.

For an assignment whose review unit is paragraphs, a teacher-facing prompt
should use the assignment's configured plural label:

```text
How many paragraphs did the student write?
```

not:

```text
How many review units did the student write?
```

## Review-Unit Focus Standard Observations

`standard_observations` is the central new record type in schema version `2`.

Each observation records a teacher's judgment about one Focus Standard in one
review unit.

Example:

```json
{
  "observation_id": "observation_0001",
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "applicable": true,
  "evidence_present": true,
  "rating": 2,
  "rationale": "The paragraph uses evidence from the story, but the explanation is still general.",
  "include_in_feedback": false,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required fields:

* `observation_id`;
* `standard_id`;
* `applicable`;
* `evidence_present`;
* `rating`;
* `rationale`;
* `include_in_feedback`;
* `updated_at`; and
* `module_details`.

Field rules:

* `observation_id` is unique within all observations in the review record.
* `standard_id` must be one of the assignment's `focus_standard_ids`.
* `applicable` is a boolean.
* `evidence_present` is a boolean when `applicable` is `true`.
* `evidence_present` may be `null` only when `applicable` is `false`.
* when `applicable` is `true`, `rating` is either `null` or a value from the
  assignment's `rating_scale.levels`;
* when `applicable` is `false`, `rating` must be `null`.
* `rationale` is either `null` or a non-empty string.
* `include_in_feedback` is a boolean.
* `updated_at` is the most recent teacher update timestamp for the observation.
* `module_details` is an object.

Each review unit should have at most one observation per Focus Standard.

Important distinctions:

* `applicable: false` means the teacher decided the standard does not apply to
  that review unit.
* `evidence_present: false` means the standard applies, but the teacher did
  not find evidence of it in that unit.
* `evidence_present: true` does not mean the standard was met.
* `rating` is a standards-performance judgment, not a grade.
* `include_in_feedback` controls whether the observation may appear in
  student-facing feedback.

Observations are teacher-entered or teacher-confirmed judgments. Quillan must
not infer observations from student writing, tags, comments, OCR, handwriting
recognition, or AI.

## Overall Focus Standard Ratings

`overall_standard_ratings` stores the teacher's overall rating for each Focus
Standard assessed by the assignment.

These ratings are the primary scoring object in the v0.8.6 standards-based
review model.

Example:

```json
{
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "rating": 3,
  "rationale": "Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.",
  "include_in_feedback": true,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required fields:

* `standard_id`;
* `rating`;
* `rationale`;
* `include_in_feedback`;
* `updated_at`; and
* `module_details`.

Field rules:

* `standard_id` must be one of the assignment's `focus_standard_ids`.
* Each Focus Standard may appear at most once in `overall_standard_ratings`.
* `rating` must be a value from the assignment's `rating_scale.levels`.
* `rationale` is either `null` or a non-empty string.
* `include_in_feedback` is a boolean.
* `updated_at` is the most recent teacher update timestamp for that rating.
* `module_details` is an object.

Overall Focus Standard ratings are teacher judgments. Quillan must not
calculate them automatically from review-unit observations. The teacher may
use the review-unit observation summary as evidence, but the overall rating is
not an average, weighted score, percentage, grade, or mastery calculation.

Completing the overall-rating phase is an explicit teacher action and is
permitted when configured Focus Standards are still unrated. Completion
reports the current configured rating count and missing count; it does not
create placeholders, copy observation ratings, or otherwise fill missing
ratings. Ratings for standards no longer configured by the assignment remain
auditable but do not count toward current assignment completion.

Old generic criterion scores are superseded by overall Focus Standard ratings.

## Feedback Composition

`feedback` stores teacher choices for student-facing feedback.

Feedback is organized around Focus Standards.

Example:

```json
{
  "include_review_unit_observations": false,
  "include_overall_standard_ratings": true,
  "standard_feedback": [
    {
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "include_overall_rating": true,
      "include_overall_rationale": true,
      "included_observation_ids": [],
      "comments": [
        {
          "feedback_comment_id": "feedback_comment_0001",
          "source": "custom",
          "text": "Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.",
          "reusable_comment_id": null,
          "save_for_reuse": false,
          "include_in_feedback": true,
          "created_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        }
      ],
      "module_details": {}
    }
  ]
}
```

Required top-level `feedback` fields:

* `include_review_unit_observations`;
* `include_overall_standard_ratings`; and
* `standard_feedback`.

Field rules:

* `include_review_unit_observations` is a boolean default choice.
* `include_overall_standard_ratings` is a boolean default choice.
* `standard_feedback` is an array of standard-specific feedback records.

### Standard Feedback Records

Each item in `standard_feedback` contains:

* `standard_id`;
* `include_overall_rating`;
* `include_overall_rationale`;
* `included_observation_ids`;
* `comments`; and
* `module_details`.

Field rules:

* `standard_id` must be one of the assignment's `focus_standard_ids`.
* Each Focus Standard may appear at most once in `standard_feedback`.
* `include_overall_rating` is a boolean.
* `include_overall_rationale` is a boolean.
* `included_observation_ids` is an ordered array of unique `observation_id`
  values from the same review record. Each selected observation must belong to
  this record's `standard_id` and must itself have `include_in_feedback: true`.
  Excluded observations must be changed through the observation workflow
  before they can be selected.
* `comments` is an array of feedback comment records.
* `module_details` is an object.

### Feedback Comment Records

Each feedback comment contains:

* `feedback_comment_id`;
* `source`;
* `text`;
* `reusable_comment_id`;
* `save_for_reuse`;
* `include_in_feedback`;
* `created_at`; and
* `module_details`.

Field rules:

* `feedback_comment_id` is unique within all feedback comments in the review
  record.
* `source` is one of `custom` or `reusable_focus_standard_comment`.
* `text` is a non-empty string.
* `reusable_comment_id` is `null` for custom comments and a non-empty string
  for reusable comment selections.
* `save_for_reuse` is a boolean.
* `include_in_feedback` is a boolean.
* `created_at` is a timezone-aware ISO 8601 timestamp.
* `module_details` is an object.

Feedback comments are teacher-authored or teacher-selected. Quillan must not
generate feedback automatically.

Direct composition uses the same shared services as the teacher-facing menu.
Options replace a standard's full selection while preserving comments;
custom and reusable selections append review-wide sequential comment IDs.
Reusable text is copied as a stable snapshot and successful selection updates
source usage metadata. Explicit composition completion may proceed with
missing ratings, records, observations, or comments and never exports output.

If a teacher writes a new custom comment and sets `save_for_reuse` to `true`,
a later reusable-comment workflow may offer to save that language into a
reusable Focus Standard comment store. The review record remains a stable
snapshot of the feedback text used for this student.

Reusable comments are not live references. Later edits to reusable comment
sources must not silently change existing review records or exports.

Teacher-only rationales and review-unit observations do not become
student-facing unless the teacher chooses to include them.

## Private Notes

`private_notes` contains optional private teacher notes that are not part of
the central standards-based scoring model.

Example:

```json
{
  "private_note_id": "private_note_0001",
  "text": "Student has the right interpretation but needs more precise quote integration.",
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required fields:

* `private_note_id`;
* `text`;
* `created_at`;
* `updated_at`; and
* `module_details`.

Field rules:

* `private_note_id` is unique within `private_notes`.
* `text` is a non-empty string.
* `created_at` and `updated_at` are timezone-aware ISO 8601 timestamps.
* `updated_at` must not precede `created_at`.
* `module_details` is an object.

Private notes are not student-facing feedback unless a later explicit workflow
copies their content into a feedback comment.

Private notes do not score work, prove standards performance, or drive
automatic ratings.

## Export Metadata

`exports` records metadata for derived student-facing feedback exports.

Example:

```json
{
  "feedback_pdf": {
    "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/exports/feedback.pdf",
    "generated_at": "2026-07-02T00:00:00+00:00",
    "source_review_updated_at": "2026-07-02T00:00:00+00:00",
    "module_details": {}
  },
  "feedback_markdown": null
}
```

Required fields:

* `feedback_pdf`;
* `feedback_markdown`.

Each export field is either `null` or an export metadata object.

Export metadata object fields:

* `path`;
* `generated_at`;
* `source_review_updated_at`; and
* `module_details`.

Field rules:

* `path` is a workspace-relative path.
* `generated_at` is a timezone-aware ISO 8601 timestamp.
* `source_review_updated_at` records the top-level `updated_at` value of the
  review record used to generate the export.
* `module_details` is an object.

The active v0.8.6 model treats PDF feedback as a first-class student-facing
export. Markdown may remain available as an optional derived export.

Export files are derived artifacts. They do not replace `review.json`.

Generating an export may update `exports`, top-level `updated_at`, and
`review_state` if the implementation defines export as a state-changing
workflow. An export writer must validate the complete proposed `review.json`
before writing updated export metadata.

If a review record changes after export, the export may be stale. Staleness can
be detected by comparing the export metadata's `source_review_updated_at` with
the current top-level `updated_at`.

## Timestamp Policy

Every timestamp is an ISO 8601 string with an explicit timezone offset, for
example:

```text
2026-07-02T00:00:00+00:00
2026-07-02T13:45:30-04:00
```

Naive timestamps are invalid. Equivalent offsets are allowed; UTC is
recommended for stable serialization.

Top-level `created_at` records creation of `review.json` and never changes.
Top-level `updated_at` changes whenever any top-level field or nested review
artifact changes. It must not precede `created_at`.

Nested records use `created_at`, `updated_at`, or both according to their
record type. A nested update also updates top-level `updated_at`.

`minimum_requirement_outcome.updated_at` may be `null` only when the outcome
status is `not_checked`.

## Workspace-Relative Path Policy

Every stored path in `review.json` is interpreted from the resolved active PDS
workspace root. Paths must use forward slashes in serialized JSON and must not
contain:

* an absolute or rooted path;
* a Windows drive-letter path;
* `.` or `..` path components;
* null bytes; or
* any value that resolves outside the workspace root.

These requirements apply to:

* `submission_manifest_path`;
* `assignment_path`;
* export metadata paths; and
* any future workspace-relative paths stored inside `module_details`.

Schema version `2` does not copy routed evidence paths or retained-source
paths from `submission.json`.

## Module Extension Policy

`module_details` is an object reserved for compatible Quillan extensions.

Rules:

* `module_details` must be an object wherever it appears.
* It may be empty.
* Consumers must not require unknown keys inside `module_details`.
* Future compatible additions may use `module_details` when they do not change
  the core meaning of the record.

A change that alters required fields, identity semantics, review-state
meaning, observation semantics, rating semantics, or feedback/export semantics
requires a new schema version.

## Mutation and Preservation Policy

Later writers must validate the complete proposed record before replacing an
existing `review.json` and must use safe-write behavior.

At the data-model level:

* minimum requirement checks are mutable by `requirement_key`;
* minimum requirement outcome is explicitly replaceable;
* review units are explicitly replaceable only through review-unit management
  workflows;
* review-unit Focus Standard observations are mutable by `observation_id`;
* overall Focus Standard ratings are mutable by `standard_id`;
* feedback choices are explicitly replaceable through feedback-composition
  workflows;
* feedback comments are append-only unless a later editing workflow is defined;
* private notes are append-only unless a later editing workflow is defined;
* export metadata is replaceable by export workflows; and
* every artifact change also replaces top-level `updated_at`.

No command may silently discard teacher-entered records. Editing or deleting
append-only records requires a future explicit contract and workflow.

## Deprecated and Superseded Schema Version 1 Fields

Schema version `1` review records centered on:

```text
notes
tags
scores
comments
requirement_checks
review_state
```

Those fields are no longer the center of the v0.8.6 target model.

### `tags`

Old generic `tags` are superseded by review-unit Focus Standard observations.

The useful idea inside tags was teacher observation. In the new model, that
observation is recorded directly against:

```text
review unit + Focus Standard
```

### `scores`

Old generic `scores` are superseded by overall Focus Standard ratings.

The useful idea inside scores was teacher scoring judgment. In the new model,
that judgment is attached directly to a Focus Standard and uses the
assignment's rating scale.

### `comments`

Old generic `comments` are superseded by Focus Standard feedback composition.

The useful idea inside comments was reusable or custom student-facing
feedback. In the new model, feedback comments are organized under Focus
Standards.

### `notes`

Old `notes` are superseded by `private_notes`.

Private teacher notes remain useful, but they are not the center of the review
model and are not student-facing unless explicitly copied into feedback.

### `requirement_checks`

Old `requirement_checks` are superseded by `minimum_requirement_checks`.

The concept remains important. The new field name makes clear that these are
minimum requirement checks and not writing-quality ratings.

## Backward Compatibility and Migration

Schema version `2` is a breaking review-record change.

The old schema version `1` shape is considered legacy development/test data
for the v0.8.6 redesign.

Because Quillan is still pre-pilot and no production classroom data is
expected to depend on the old review contract, v0.8.6 may treat this as a
breaking cleanup with no production-data migration.

Later implementation work must decide one of the following:

1. reject old schema version `1` review records with clear guidance;
2. read old records as legacy records but prevent new standards-based review
   workflows from editing them;
3. provide a migration helper from schema version `1` to schema version `2`;
   or
4. support a temporary compatibility layer while the redesign is implemented.

The target architecture is schema version `2`.

The old review shape should not remain the long-term active contract.

## Runtime Status

At the time this target contract is introduced, current runtime loading,
validation, direct CLI commands, menu workflows, feedback export, class summary
export, standards summary export, and tests may still reflect the old schema
version `1` model.

This document defines the target contract. It does not by itself update:

* `quillan.review_record`;
* `quillan.review_record_paths`;
* review menus;
* assignment review workflows;
* feedback export code;
* summary export code;
* examples;
* validators; or
* tests.

Those implementation changes belong in later v0.8.6 issues.

## Complete English 10 Example

The following synthetic example uses the English 10 standards-based redesign
simulation.

```json
{
  "schema_version": "2",
  "module": "quillan",
  "record_type": "submission_review",
  "class_id": "english_10_simulation",
  "assignment_id": "coming-of-age_literary_analysis",
  "student_id": "10001",
  "submission_manifest_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/submission.json",
  "assignment_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/assignment.json",
  "review_state": "feedback_composed",
  "minimum_requirement_checks": [
    {
      "requirement_check_id": "requirement_check_0001",
      "requirement_key": "paragraphs_min",
      "label": "Minimum paragraphs",
      "expected": 1,
      "met": true,
      "teacher_note": null,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    },
    {
      "requirement_check_id": "requirement_check_0002",
      "requirement_key": "required_elements:textual_evidence",
      "label": "Required element: textual evidence",
      "expected": "textual evidence",
      "met": true,
      "teacher_note": null,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    },
    {
      "requirement_check_id": "requirement_check_0003",
      "requirement_key": "required_elements:explanation",
      "label": "Required element: explanation",
      "expected": "explanation",
      "met": true,
      "teacher_note": null,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    }
  ],
  "minimum_requirement_outcome": {
    "status": "met",
    "returned_without_full_review": false,
    "teacher_note": null,
    "updated_at": "2026-07-02T00:00:00+00:00"
  },
  "review_units": [
    {
      "unit_id": "paragraph_1",
      "sequence": 1,
      "label": "Paragraph 1",
      "unit_type": "paragraph",
      "page_number": 1,
      "evidence_id": "evidence_001",
      "standard_observations": [
        {
          "observation_id": "observation_0001",
          "standard_id": "njsls-ela:RL.CR.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph uses relevant evidence from the story and connects it to the claim.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0002",
          "standard_id": "njsls-ela:RL.CI.9-10.2",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph begins explaining how objects carry memory and grief.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0003",
          "standard_id": "njsls-ela:W.AW.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph supports an arguable claim with evidence and explanation.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        }
      ],
      "module_details": {}
    },
    {
      "unit_id": "paragraph_2",
      "sequence": 2,
      "label": "Paragraph 2",
      "unit_type": "paragraph",
      "page_number": 1,
      "evidence_id": "evidence_001",
      "standard_observations": [
        {
          "observation_id": "observation_0004",
          "standard_id": "njsls-ela:RL.CR.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 4,
          "rationale": "The paragraph uses specific evidence about Yongjun's clothing and explains its significance.",
          "include_in_feedback": true,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0005",
          "standard_id": "njsls-ela:RL.CI.9-10.2",
          "applicable": true,
          "evidence_present": true,
          "rating": 4,
          "rationale": "The paragraph clearly connects the object motif to grief, family memory, and hidden truth.",
          "include_in_feedback": true,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0006",
          "standard_id": "njsls-ela:W.AW.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph develops the argument clearly, though some wording could be more precise.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        }
      ],
      "module_details": {}
    },
    {
      "unit_id": "paragraph_3",
      "sequence": 3,
      "label": "Paragraph 3",
      "unit_type": "paragraph",
      "page_number": 1,
      "evidence_id": "evidence_001",
      "standard_observations": [
        {
          "observation_id": "observation_0007",
          "standard_id": "njsls-ela:RL.CR.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph includes relevant textual evidence but would benefit from more precise quote integration.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0008",
          "standard_id": "njsls-ela:RL.CI.9-10.2",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph explains sewing as a form of power and survival.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0009",
          "standard_id": "njsls-ela:W.AW.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph supports the central argument and maintains logical organization.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        }
      ],
      "module_details": {}
    },
    {
      "unit_id": "paragraph_4",
      "sequence": 4,
      "label": "Paragraph 4",
      "unit_type": "paragraph",
      "page_number": 1,
      "evidence_id": "evidence_001",
      "standard_observations": [
        {
          "observation_id": "observation_0010",
          "standard_id": "njsls-ela:RL.CR.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The concluding paragraph returns to evidence from the story without simply repeating the earlier claim.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0011",
          "standard_id": "njsls-ela:RL.CI.9-10.2",
          "applicable": true,
          "evidence_present": true,
          "rating": 4,
          "rationale": "The moonlight and family garments are interpreted as a strong final image of memory and love.",
          "include_in_feedback": true,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        },
        {
          "observation_id": "observation_0012",
          "standard_id": "njsls-ela:W.AW.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 3,
          "rationale": "The paragraph closes the argument coherently and maintains focus on the central interpretation.",
          "include_in_feedback": false,
          "updated_at": "2026-07-02T00:00:00+00:00",
          "module_details": {}
        }
      ],
      "module_details": {}
    }
  ],
  "overall_standard_ratings": [
    {
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "rating": 3,
      "rationale": "Across the response, the evidence is relevant and usually well connected to the interpretation.",
      "include_in_feedback": true,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    },
    {
      "standard_id": "njsls-ela:RL.CI.9-10.2",
      "rating": 4,
      "rationale": "The response gives a strong interpretation of how objects carry memory, grief, family history, and power.",
      "include_in_feedback": true,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    },
    {
      "standard_id": "njsls-ela:W.AW.9-10.1",
      "rating": 3,
      "rationale": "The argument is focused and organized, with clear claims, evidence, and explanation.",
      "include_in_feedback": true,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    }
  ],
  "feedback": {
    "include_review_unit_observations": false,
    "include_overall_standard_ratings": true,
    "standard_feedback": [
      {
        "standard_id": "njsls-ela:RL.CR.9-10.1",
        "include_overall_rating": true,
        "include_overall_rationale": true,
        "included_observation_ids": ["observation_0004"],
        "comments": [
          {
            "feedback_comment_id": "feedback_comment_0001",
            "source": "custom",
            "text": "Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.",
            "reusable_comment_id": null,
            "save_for_reuse": true,
            "include_in_feedback": true,
            "created_at": "2026-07-02T00:00:00+00:00",
            "module_details": {}
          }
        ],
        "module_details": {}
      },
      {
        "standard_id": "njsls-ela:RL.CI.9-10.2",
        "include_overall_rating": true,
        "include_overall_rationale": true,
        "included_observation_ids": ["observation_0005", "observation_0011"],
        "comments": [
          {
            "feedback_comment_id": "feedback_comment_0002",
            "source": "custom",
            "text": "Your strongest work is your interpretation of how ordinary objects become carriers of memory, grief, and family history.",
            "reusable_comment_id": null,
            "save_for_reuse": true,
            "include_in_feedback": true,
            "created_at": "2026-07-02T00:00:00+00:00",
            "module_details": {}
          }
        ],
        "module_details": {}
      },
      {
        "standard_id": "njsls-ela:W.AW.9-10.1",
        "include_overall_rating": true,
        "include_overall_rationale": true,
        "included_observation_ids": [],
        "comments": [
          {
            "feedback_comment_id": "feedback_comment_0003",
            "source": "custom",
            "text": "Your essay stays focused on a clear interpretation. For the next essay, keep working on making each paragraph's claim as precise as possible.",
            "reusable_comment_id": null,
            "save_for_reuse": true,
            "include_in_feedback": true,
            "created_at": "2026-07-02T00:00:00+00:00",
            "module_details": {}
          }
        ],
        "module_details": {}
      }
    ]
  },
  "exports": {
    "feedback_pdf": null,
    "feedback_markdown": null
  },
  "private_notes": [
    {
      "private_note_id": "private_note_0001",
      "text": "Strong simulation response. Use as an example of the standards-based review flow.",
      "created_at": "2026-07-02T00:00:00+00:00",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    }
  ],
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

## Legacy Schema Version 1 Summary

Schema version `1` review records used this top-level shape:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "submission_review",
  "class_id": "english12_p3_synthetic",
  "assignment_id": "essay_01_synthetic",
  "student_id": "00107",
  "submission_manifest_path": "classes/english12_p3_synthetic/assignments/essay_01_synthetic/submissions/00107/submission.json",
  "review_state": "not_started",
  "notes": [],
  "tags": [],
  "scores": [],
  "comments": [],
  "requirement_checks": [],
  "created_at": "2026-06-22T00:00:00+00:00",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

That shape reflected the old prepared-review model. It is not the target
v0.8.6 standards-based review model.

Schema version `1` records may remain useful as legacy examples during the
transition, but new standards-based review work should target schema version
`2`.

## Derived Artifacts

`review.json` is the canonical active teacher-review record.

Student-facing feedback files are derived artifacts. In the v0.8.6 target
model, expected derived feedback paths include:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

Assignment-level reports are also derived artifacts. They do not replace
`review.json`.

Derived exports may be regenerated from canonical assignment, submission, and
review records. They are not independent evidence and must not silently change
teacher-entered review data.

## Synthetic Data Policy

Committed examples must use synthetic data only.

Do not commit:

* real student names;
* real rosters;
* real student writing;
* real grades;
* real parent contact information;
* real scanned student work;
* real accommodation data;
* real disciplinary or attendance information; or
* any personally identifiable student information.

## Explicit Non-Goals

This contract does not implement:

* runtime loading or validation for schema version `2`;
* review menu workflows;
* assignment creation workflows;
* review-unit creation workflows;
* feedback export generation;
* report generation;
* migration from schema version `1`;
* editing or deletion of append-only feedback comments or private notes;
* automatic score calculation;
* overall, weighted, percentage, grade, or mastery score calculation;
* AI scoring, feedback, comments, suggestions, or automated grading;
* automatic standard detection;
* OCR, handwriting recognition, PDF text extraction, or automatic paragraph
  detection;
* evidence selection or duplicate resolution;
* email sending;
* LMS integration;
* dashboards; or
* report visualization.

The record describes teacher-entered or teacher-confirmed judgment only.

## Plain-paper entry

The plain-paper workflow immediately creates a normal schema-version-2 empty
review record pointing to the canonical submission manifest. Its
`module_details` contains `review_entry_method: "plain_paper_manual"` and
`created_by_workflow: "plain_paper_submission"`. It does not add top-level
fields or prefill checks, units, observations, ratings, feedback, or notes.
