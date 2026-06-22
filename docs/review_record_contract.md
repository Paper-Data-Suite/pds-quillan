# Quillan Submission Review Record Contract

## Purpose and Boundary

The Quillan submission review record stores teacher-entered evaluation data
for one student submission. Its canonical workspace-relative path is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

`review.json` is separate from the adjacent `submission.json` evidence
manifest:

* `submission.json` answers what evidence exists, where it came from, which
  evidence is selected, and what evidence-management state it is in.
* `review.json` answers what the teacher recorded about that evidence,
  including notes, tags, scores, selected comments, and review/export state.

Teacher review must not rewrite or duplicate the evidence manifest. In
particular, `review.json` references evidence by `evidence_id` and optional
page number rather than copying routed evidence paths.

This document defines submission review schema version `1` for the v0.7
contract. Runtime loading and validation are implemented by
`quillan.review_record`. Canonical path computation and safe writing are
implemented by `quillan.review_record_paths`. Teacher-facing commands and
exports remain future work.

## Top-Level Structure

Every version `1` review record contains:

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
  "created_at": "2026-06-22T00:00:00+00:00",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

All fields shown above are required, including arrays that are initially
empty.

Field requirements are:

* `schema_version`: the string `"1"`;
* `module`: the string `"quillan"`;
* `record_type`: the string `"submission_review"`;
* `class_id`, `assignment_id`, and `student_id`: identifiers matching the
  associated submission manifest;
* `submission_manifest_path`: the canonical workspace-relative path to that
  submission's `submission.json`;
* `review_state`: one of the controlled values below;
* `notes`, `tags`, `scores`, and `comments`: arrays of the records defined
  below;
* `created_at`: the review-record creation timestamp;
* `updated_at`: the timestamp of the most recent change anywhere in the
  review record; and
* `module_details`: an object reserved for compatible Quillan extensions.

Unknown top-level fields are not part of schema version `1`. A future contract
change must use a new schema version when it changes the meaning or required
shape of existing data.

## Identity and Submission Reference

`class_id`, `assignment_id`, and `student_id` use the shared `pds-core`
identifier policy. They are case-sensitive strings, and student identifiers
remain strings so leading zeros are preserved.

The three identifiers must match both:

1. the values in the referenced `submission.json`; and
2. the corresponding path segments in `submission_manifest_path`.

For a review record with identity `<class_id>`, `<assignment_id>`, and
`<student_id>`, the only valid manifest reference is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

Review-local identifiers such as `note_id`, `tag_id`, `score_id`, and
`comment_record_id` are opaque, non-empty strings. Each identifier must be
unique within its own array. Consumers must not derive ordering, timestamps,
or meaning from an identifier's spelling.

When present:

* `evidence_id` must identify an evidence candidate in the referenced
  `submission.json`;
* `page_number` must identify the page entry containing that evidence when
  both fields are present;
* `standard_code` should identify an active standard in the assignment's
  standards profile; and
* `criterion_id` should identify a criterion in the assignment rubric or
  rubric profile.

These references do not copy the referenced records into `review.json`.

## Review State

Allowed `review_state` values are:

* `not_started`: no substantive teacher-review artifacts have been entered;
* `in_progress`: the teacher has begun entering or revising review artifacts;
* `ready_for_export`: the teacher has explicitly marked the current review
  data ready for feedback or report export; and
* `exported`: feedback or reporting output has been exported from the review
  record.

`review_state` describes teacher-entered review artifacts. It is distinct from
`submission_state` in `submission.json`, which describes evidence and
submission management. Neither state determines or automatically changes the
other. Later workflows must make any state change explicit.

The state is not inferred merely because an array is empty or populated.
Writers are responsible for keeping the explicit state meaningful. For
example, an add-note command may explicitly move `not_started` to
`in_progress`, but validation must not silently make that decision.

`ready_for_export` and `exported` do not assert that a submission is complete,
that evidence is unambiguous, or that a particular score exists. Exported
files are derived artifacts and are not stored as paths in schema version `1`.

## Notes

`notes` contains private, teacher-entered freeform observations. A note is not
student-readable feedback unless the teacher later chooses to include its
content in an export. A note does not score or tag work by itself.

Each note contains:

```json
{
  "note_id": "note_0001",
  "text": "The essay has a clear central claim but needs stronger evidence explanation.",
  "created_at": "2026-06-22T00:00:00+00:00",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

All note fields shown above are required.

* `note_id` is unique within `notes`.
* `text` is a non-empty string after trimming surrounding whitespace.
* `created_at` records original creation and is preserved.
* `updated_at` initially equals `created_at` and changes only if a future
  editing workflow explicitly supports note edits.
* `module_details` is an object.

Notes are append-only for the MVP. Editing and deletion are reserved for a
future contract or explicitly defined command; later commands must not
silently replace existing notes.

## Tags

`tags` contains teacher-created or teacher-confirmed observations. A tag may
refer to a standard, reusable comment, page, evidence candidate, location, or
the whole submission. It is not a score, proof that a standard was met or
missed, or an instruction to calculate a score.

Each tag contains:

```json
{
  "tag_id": "tag_0001",
  "standard_code": "W.AW.11-12.1",
  "comment_id": "evidence_needs_explanation",
  "label": "Evidence needs more explanation",
  "polarity": "developing",
  "severity": 2,
  "teacher_note": "The quotation is relevant, but the analysis does not explain how it supports the claim.",
  "page_number": 1,
  "evidence_id": "evidence_001",
  "location": {
    "type": "paragraph",
    "value": 2
  },
  "created_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

Required tag fields are:

* `tag_id`;
* `label`;
* `polarity`;
* `created_at`; and
* `module_details`.

Optional tag fields are:

* `standard_code`;
* `comment_id`;
* `severity`;
* `teacher_note`;
* `page_number`;
* `evidence_id`; and
* `location`.

Tag field rules are:

* `tag_id` is unique within `tags`.
* `label` is a non-empty, teacher-readable string.
* `polarity` is one of `positive`, `developing`, `negative`, or `neutral`.
* `severity`, when present, is a non-negative integer used for organization,
  not a score.
* `teacher_note`, when present, is a non-empty string.
* `page_number`, when present, is a positive integer.
* `standard_code` and `comment_id`, when present, are non-empty strings.
  Together they may identify reusable language in a standards profile.
* `evidence_id`, when present, is a non-empty reference to the submission
  manifest as described above.
* `module_details` is an object.

### Tag Locations

`location`, when present, contains exactly a controlled `type` and a `value`:

```json
{
  "type": "paragraph",
  "value": 2
}
```

Allowed location types are:

* `whole_submission`;
* `page`;
* `paragraph`;
* `sentence`;
* `line`;
* `section`;
* `scene`;
* `stanza`; and
* `custom`.

For `whole_submission`, `value` must be `null`. For `page`, `paragraph`,
`sentence`, and `line`, `value` must be a positive integer. For `section`,
`scene`, `stanza`, and `custom`, `value` must be either a positive integer or
a non-empty string. A `page` location must agree with `page_number` when both
are present.

Tags are append-only for the MVP. Editing, deletion, deduplication, and any
interpretation of severity are future work. Tags must never calculate or
compel scores.

## Scores

`scores` is an array of criterion score records. The array form is canonical
for schema version `1` because it supports validation and focused updates
without replacing an unrelated score.

Each score contains:

```json
{
  "score_id": "score_0001",
  "criterion_id": "evidence",
  "label": "Evidence",
  "score": 3,
  "max_score": 4,
  "scale": "4_point",
  "teacher_note": "Evidence is relevant but unevenly explained.",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

Required score fields are:

* `score_id`;
* `criterion_id`;
* `label`;
* `score`;
* `max_score`;
* `updated_at`; and
* `module_details`.

Optional score fields are:

* `scale`; and
* `teacher_note`.

Score field rules are:

* `score_id` is unique within `scores`.
* `criterion_id` is non-empty and unique within `scores`. When a rubric is
  available, it should reference one rubric criterion.
* `label` is a non-empty, teacher-readable string.
* `score` is a finite number greater than or equal to zero.
* `max_score` is a finite number greater than zero.
* `score` is less than or equal to `max_score`.
* `scale` and `teacher_note`, when present, are non-empty strings.
* `updated_at` records the most recent teacher update to that criterion.
* `module_details` is an object.

Scores are teacher-entered or teacher-confirmed decisions. Quillan must not
infer a score from student writing, tags, requirements, comments, or other
records.

Scores are mutable by `criterion_id` for the MVP. A later set-score workflow
updates the matching criterion record and its `updated_at`, preserves its
`score_id`, and updates top-level `updated_at`. It appends a new score only
when the criterion is not already present. It must not replace the entire
`scores` array or erase unrelated criteria.

## Comments

`comments` contains teacher-selected reusable language or teacher-entered
custom language intended for possible feedback export.

Each comment contains:

```json
{
  "comment_record_id": "comment_0001",
  "comment_id": "evidence_needs_explanation",
  "standard_code": "W.AW.11-12.1",
  "label": "Evidence needs more explanation",
  "text": "The evidence is relevant, but the explanation needs to show more clearly how it supports the claim.",
  "source": "standards_profile",
  "include_in_feedback": true,
  "created_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

Required comment fields are:

* `comment_record_id`;
* `label`;
* `text`;
* `source`;
* `include_in_feedback`;
* `created_at`; and
* `module_details`.

Optional comment fields are:

* `comment_id`; and
* `standard_code`.

Comment field rules are:

* `comment_record_id` is unique within `comments`.
* `comment_id` may identify reusable language in a standards profile or
  comment bank.
* `standard_code` may identify the associated profile standard.
* `label` and `text` are non-empty strings.
* `source` is one of `standards_profile`, `comment_bank`, or `custom`.
* `include_in_feedback` is a boolean expressing the teacher's export choice.
* `module_details` is an object.

Comments are teacher-selected or teacher-entered; they are not generated from
student writing or supplied as AI judgments. Comments are append-only for the
MVP. Editing, deletion, and toggling export inclusion are reserved for future
explicit workflows, which must not silently erase other comment records.

## Timestamp Policy

Every timestamp is an ISO 8601 string with an explicit timezone offset, for
example:

```text
2026-06-22T00:00:00+00:00
2026-06-22T13:45:30-04:00
```

Naive timestamps are invalid. Equivalent offsets are allowed; UTC is
recommended for stable serialization.

Top-level `created_at` records creation of `review.json` and never changes.
Top-level `updated_at` changes whenever any top-level field or nested review
artifact changes. It must not precede `created_at`.

Append-only notes, tags, and comments preserve their original `created_at`.
Notes also reserve `updated_at` for future explicit editing. Mutable score
records update their own `updated_at`. A nested update also updates top-level
`updated_at`.

## Workspace-Relative Path Policy

Every stored path in `review.json` is interpreted from the resolved active PDS
workspace root. Paths must use forward slashes in serialized JSON and must
not contain:

* an absolute or rooted path;
* a Windows drive-letter path;
* `.` or `..` path components;
* null bytes; or
* any value that resolves outside the workspace root.

Schema version `1` stores only `submission_manifest_path`. It does not copy
routed evidence paths, retained-source paths, export paths, or report paths.
Runtime validation rejects unsafe paths and requires the canonical manifest
path matching the record's own class, assignment, and student identifiers.

## Runtime API

`quillan.review_record` provides:

* `load_review_record(path)` for UTF-8 JSON loading and complete validation;
* `validate_review_record(record)` for isolated schema validation; and
* `ReviewRecordError` for review-record loading and validation failures.

`quillan.review_record_paths` provides:

* `review_record_dir(...)` and `review_record_path(...)` for canonical active
  paths;
* `write_review_record(path, record, overwrite=False)` for validated,
  atomic, readable UTF-8 JSON writes; and
* `ReviewRecordPathError` for path and write failures.

Version `1` rejects unknown fields in the top-level and defined nested record
shapes. Module-specific extension data belongs in each record's
`module_details` object. The writer creates missing parent directories and
refuses to replace an existing file unless `overwrite=True`.

## Mutation and Preservation Policy

Later writers must validate the complete proposed record before replacing an
existing `review.json` and must use safe-write behavior. At the data-model
level:

* notes are append-only;
* tags are append-only;
* comments are append-only;
* scores are appended or updated by unique `criterion_id`;
* top-level metadata and `review_state` are explicitly replaceable; and
* every artifact change also replaces top-level `updated_at`.

No command may silently discard teacher-entered records. Editing or deleting
append-only records requires a future, explicit contract and workflow.

## Derived Artifacts and Historical Names

`review.json` is the canonical active v0.7 teacher-review record for notes,
tags, criterion scores, and selected comments.

Earlier design documents used separate `tags.json` and `scores.json` files.
Those names are historical design background, not alternate active v0.7
contracts. Implementations must not split or mirror canonical review data
across those files.

`feedback.md`, `reports/class_summary.csv`, and
`reports/standards_summary.csv` are derived export artifacts. They may be
generated from teacher-controlled review records in later issues, but they do
not replace `review.json` and are not authoritative independent evidence.
`requirements.json` remains a separate reserved structural-check record
because requirements checks are not teacher evaluation artifacts in this
schema.

## Synthetic Example

A complete fake record with a note, two tags, one criterion score, and one
selected comment is stored in
[`review_record_synthetic.json`](../examples/submissions/review_record_synthetic.json).

## Explicit Non-Goals

This contract does not implement:

* `add-note`, `add-tag`, `set-score`, or other review commands;
* comment-bank lookup or reusable-comment management;
* feedback, class-summary, or standards-summary export;
* CLI or terminal-menu review workflows;
* editing or deletion of append-only review artifacts;
* AI scoring, feedback, comments, suggestions, or automated grading;
* automatic standard detection;
* OCR, handwriting recognition, PDF text extraction, or QR extraction;
* evidence selection or duplicate resolution;
* email sending, LMS integration, dashboards, or report visualization.

The record describes teacher-entered or teacher-confirmed judgment only.
