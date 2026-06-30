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
  including notes, tags, scores, selected comments, requirement checks, and
  review/export state.

Teacher review must not rewrite or duplicate the evidence manifest. In
particular, `review.json` references evidence by `evidence_id` and optional
page number rather than copying routed evidence paths.

This document defines submission review schema version `1` for the v0.7
contract. Runtime loading and validation are implemented by
`quillan.review_record`. Canonical path computation and safe writing are
implemented by `quillan.review_record_paths`. Teacher-facing commands and
derived exports are implemented for the v0.7 review workflows.

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
  "requirement_checks": [],
  "created_at": "2026-06-22T00:00:00+00:00",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

All fields shown above except `requirement_checks` are required, including
arrays that are initially empty. `requirement_checks` is optional for older
schema version `1` records; new records written by current review workflows
include it as an empty array until the teacher records checks.

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
* `requirement_checks`: optional array of teacher-entered assignment
  requirement checks;
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
`comment_record_id` are opaque, non-empty strings. Requirement checks use
`requirement_check_id`. Each identifier must be unique within its own array.
Consumers must not derive ordering, timestamps, or meaning from an
identifier's spelling.

When present:

* `evidence_id` must identify an evidence candidate in the referenced
  `submission.json`;
* `page_number` must identify the page entry containing that evidence when
  both fields are present;
* `standard_id` should identify a pds-core standard in the assignment's
  selected pds-core profile; and
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
refer to a standard, reusable tag template, reusable comment, page, evidence
candidate, location, or the whole submission. It is not a score, proof that a
standard was met or missed, or an instruction to calculate a score.

Each tag contains:

```json
{
  "tag_id": "tag_0001",
  "standard_id": "njsls-ela:W.AW.11-12.1",
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

* `source`;
* `tag_bank_id`;
* `tag_template_id`;
* `criterion_id`;
* `standard_id`;
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
* `source`, when present, is one of `tag_bank` or `custom`.
* `tag_bank_id` and `tag_template_id` are required when `source` is
  `tag_bank`. They identify the source file under
  `shared/tag_banks/<tag_bank_id>.json` and the selected template inside that
  bank.
* `criterion_id`, when present, is optional rubric/scoring metadata and is not
  validated against a rubric profile in schema version `1`.
* `standard_id` and `comment_id`, when present, are non-empty strings.
  `standard_id` is pds-core provenance; `comment_id` identifies reusable
  Quillan comment-bank language when paired with `bank_id`.
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
`sentence`, and `line`, a single-value `value` must be a positive integer.
For `paragraph`, `value` may also be a non-empty list of unique positive
integers:

```json
{
  "type": "paragraph",
  "value": [2, 3, 4]
}
```

The preferred convention is to store one paragraph as an integer and multiple
paragraphs as a list. Existing single-integer paragraph locations remain
valid. For `section`, `scene`, `stanza`, and `custom`, `value` must be either
a positive integer or a non-empty string. A `page` location must agree with
`page_number` when both are present. Paragraph targets are teacher-entered
metadata; Quillan does not parse writing, count paragraphs, run OCR, or infer
where a tag applies.

### Reusable Tag Snapshots

When a teacher selects a reusable tag from a Quillan tag bank, the review
record stores a snapshot, not a live reference:

```json
{
  "tag_id": "tag_0001",
  "source": "tag_bank",
  "tag_bank_id": "general_written_response_tags",
  "tag_template_id": "explanation_needs_more_detail",
  "label": "Explanation needs more detail",
  "polarity": "developing",
  "criterion_id": "explanation",
  "severity": 2,
  "teacher_note": "The explanation names the idea but does not explain why it matters.",
  "created_at": "2026-06-26T00:00:00+00:00",
  "module_details": {}
}
```

Later edits to the source tag bank do not rewrite prior review records.
Optional reusable-template `standard_ids` remain pds-core durable references
only, and optional `criterion_ids` remain rubric/scoring metadata only.
Existing direct CLI tags may omit `source` and all tag-bank provenance fields.

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
* `criterion_id` is non-empty and unique within `scores`. Schema version `1`
  validates this field intrinsically; rubric-profile lookup is workflow-level
  context, not a review-record schema requirement.
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

Scores are mutable by `criterion_id` for the MVP. The `set-score` workflow
updates the matching criterion record and its `updated_at`, preserves its
`score_id`, and updates top-level `updated_at`. It appends a new score only
when the criterion is not already present. It does not replace the entire
`scores` array or erase unrelated criteria. Omitting optional `scale` or
`teacher_note` values removes prior values from the updated criterion so the
record reflects the latest explicit teacher input.

Review mode can also set a criterion score from a valid shared rubric resolved
through the assignment's `rubric_id`. That workflow snapshots the selected
criterion and level into the same score shape. It does not store a live
reference that changes when the rubric is later edited, and rubric level
`student_facing_feedback` does not automatically create a comment or feedback
export entry.

## Requirement Checks

`requirement_checks` records teacher-entered boolean checks against the
assignment's `basic_requirements`. Quillan prompts from configured
`paragraphs_min`, `paragraphs_max`, `word_count_min`, `word_count_max`, and
individual `required_elements`, but it does not count paragraphs, count words,
parse writing, run OCR, or use AI. The teacher records whether each
requirement is met.

Example:

```json
{
  "requirement_check_id": "requirement_check_0001",
  "requirement_key": "paragraphs_min",
  "label": "Minimum paragraphs",
  "expected": 5,
  "met": true,
  "updated_at": "2026-06-29T00:00:00+00:00",
  "module_details": {}
}
```

Required elements use a key that includes the element value:

```json
{
  "requirement_check_id": "requirement_check_0002",
  "requirement_key": "required_elements:thesis_statement",
  "label": "Required element: thesis_statement",
  "expected": "thesis_statement",
  "met": false,
  "updated_at": "2026-06-29T00:00:00+00:00",
  "module_details": {},
  "teacher_note": "Missing a clear thesis statement."
}
```

Field requirements:

* `requirement_check_id` is unique within `requirement_checks`;
* `requirement_key` is non-empty and unique within `requirement_checks`;
* `label` is a non-empty teacher-facing label;
* `expected` is a finite number or non-empty string copied from assignment
  configuration;
* `met` is a boolean;
* `updated_at` is the last teacher update timestamp; and
* `module_details` is an object.

Requirement checks are mutable by `requirement_key`. Updating a check
preserves its `requirement_check_id`, replaces the recorded boolean and
optional note, updates top-level `updated_at`, and preserves notes, tags,
scores, comments, review state semantics, and evidence references.

## Comments

`comments` contains teacher-selected reusable language or teacher-entered
custom language intended for possible feedback export. Reusable source
comments come from a shared Quillan comment bank
defined by [`comment_bank_contract.md`](comment_bank_contract.md).

Each comment contains:

```json
{
  "comment_record_id": "comment_0001",
  "bank_id": "argument_writing",
  "comment_id": "evidence_needs_explanation",
  "standard_id": "njsls-ela:W.AW.11-12.1",
  "label": "Evidence needs more explanation",
  "text": "The evidence is relevant, but the explanation needs to show more clearly how it supports the claim.",
  "source": "comment_bank",
  "include_in_feedback": true,
  "page_number": 1,
  "location": {
    "type": "paragraph",
    "value": [2, 3]
  },
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

* `bank_id`;
* `comment_id`;
* `standard_id`;
* `page_number`;
* `evidence_id`; and
* `location`.

Comment field rules are:

* `comment_record_id` is unique within `comments`.
* `bank_id`, when present, is a valid shared identifier naming the source at
  `shared/comment_banks/<bank_id>.json`.
* `comment_id` identifies reusable language within its source bank; it is not
  globally unique across comment banks.
* `standard_id`, when present, is durable pds-core provenance for the
  associated standard.
* `page_number`, when present, is a positive integer.
* `evidence_id`, when present, is a non-empty reference to the submission
  manifest as described above.
* `location`, when present, uses the same controlled shape and paragraph
  rules as tag locations. Comments may target a paragraph, multiple
  paragraphs, a page, page plus paragraphs, evidence, or the whole
  submission.
* `label` and `text` are non-empty strings.
* `source` is one of `comment_bank` or `custom`.
* `include_in_feedback` is a boolean expressing the teacher's export choice.
* `module_details` is an object.

Source-specific rules are:

* `comment_bank` comments require both `bank_id` and `comment_id`;
  `bank_id + comment_id` identifies the reusable source comment.
* `custom` comments must omit `bank_id`, `comment_id`, and `standard_id`.

Comments are teacher-selected or teacher-entered; they are not generated from
student writing or supplied as AI judgments. Comment targets are optional,
teacher-entered context; Quillan does not parse student writing to determine
paragraph numbers or infer which paragraph a comment applies to. Comments are
append-only for the MVP. Editing, deletion, and toggling export inclusion are
reserved for future explicit workflows, which must not silently erase other
comment records.

For a shared-bank selection, `source` must be `"comment_bank"`. `bank_id` is
provenance metadata only: validation does not load or look up the bank file.
`label` and `text` must be copied into this record rather than resolved as a
live display reference. The selected record is a submission-specific snapshot,
so later edits to the shared bank cannot silently alter an existing review or
export.

The direct `add-comment` workflow validates the source bank first and accepts
only `student_facing: true` comments. It uses the bank's
`include_in_feedback_default` unless the teacher explicitly includes or
excludes the selected comment. A sole source `standard_id` is copied
automatically; with multiple source standards, one is stored only when the
teacher specifies it.

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

## Quick Teacher Notes

The direct quick-note command is:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
```

It appends one teacher-entered note to the canonical `review.json`. A missing
review record is created only after the adjacent canonical `submission.json`
loads, validates, and matches the requested identity. New records begin in
`in_progress`; an existing `not_started` record advances to `in_progress`, while
`in_progress`, `ready_for_export`, and `exported` are preserved.

Quick notes receive sequential local IDs such as `note_0001`, trim surrounding
whitespace from non-empty teacher text, and use one timezone-aware timestamp
for the note's initial `created_at` and `updated_at`. The operation preserves
existing notes, tags, scores, comments, module details, and top-level
`created_at`, validates the complete proposed record before an atomic write,
and does not mutate the submission manifest, routed evidence, or retained
source scans.

## Structured Teacher Tags

The direct structured-tag command is:

```powershell
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity developing
```

It appends one teacher-entered tag to `tags`, using sequential IDs such as
`tag_0001`. Optional references to pages and evidence IDs are validated
against the adjacent submission manifest. Optional paragraph targets may name
one paragraph or multiple paragraphs, but they are not checked against parsed
student writing. Optional standard references use shared `pds-core`
`standard_id` values from the workspace standards library.
Reusable comment references remain Quillan-owned module data; their labels and
polarities must match the stored Quillan comment/profile values.

The command follows the same creation, timestamp, state-transition, complete
record validation, safe-write, preservation, and non-mutation policies as
quick notes. Tags organize teacher judgment only; they do not calculate
scores, prove mastery, analyze student writing, or generate feedback.

## Teacher-Entered Criterion Scores

The direct score command is:

```powershell
quillan set-score <class_id> <assignment_id> <student_id> --criterion evidence --label "Evidence" --score 3 --max-score 4
```

Optional `--scale` and `--note` values are descriptive teacher-entered
metadata. A new criterion receives the next stable local ID such as
`score_0001`. An existing criterion updates in place by `criterion_id`,
preserves its `score_id`, and does not move or replace unrelated scores.

The workflow requires a valid matching adjacent `submission.json`, creates a
missing review record in `in_progress`, advances only `not_started` to
`in_progress`, and preserves `ready_for_export` and `exported`. It preserves
unrelated notes, tags, scores, comments, top-level metadata, and
`created_at`; validates the complete proposed record before an atomic write;
and never mutates submission manifests, routed evidence, or retained scans.

Criterion IDs are validated only as non-empty local identifiers in the review
record schema. The assignment's `rubric_id` may resolve to a shared rubric for
menu selection, but unresolved rubric IDs remain structurally valid. Quillan
does not infer criterion scores or calculate an overall, weighted, percentage,
grade, or mastery score.

## Reusable Comment Selection

The direct reusable-comment command is:

```powershell
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
```

It validates the shared bank at `shared/comment_banks/<bank_id>.json`, selects
one student-facing teacher-authored comment, and appends a stable snapshot to
`review.json.comments`. The snapshot preserves `bank_id + comment_id`
provenance and copies the source label and text so later bank edits do not
change an existing review. The teacher may choose a valid source standard and
may override the bank's feedback-inclusion default.

Selection requires a valid matching adjacent `submission.json`, creates a
missing review record using the same state and preservation rules as notes and
tags, and does not mutate the source bank, submission manifest, evidence, or
retained scans. It does not export feedback, select comments automatically,
analyze writing, score work, or infer mastery.

Selected comments may also store optional `page_number`, `evidence_id`, and
`location` fields using the same target model as tags. Page and evidence
references are validated against the adjacent submission manifest when
supplied. Paragraph numbers are teacher-entered metadata only.

## Derived Artifacts and Historical Names

`review.json` is the canonical active teacher-review record for notes, tags,
criterion scores, selected comments, and teacher-entered requirement checks.

Earlier design documents used separate `tags.json` and `scores.json` files.
Those names are historical design background, not alternate active v0.7
contracts. Implementations must not split or mirror canonical review data
across those files.

`submissions/<student_id>/exports/feedback.md`,
`assignments/<assignment_id>/exports/class_summary.csv`, and
`assignments/<assignment_id>/exports/standards_summary.csv` are derived export
artifacts. They may be
generated from teacher-controlled review records, but they do
not replace `review.json` and are not authoritative independent evidence.
Earlier design documents reserved `requirements.json` for structural checks.
Current teacher-entered assignment requirement checks are stored in
`review.json.requirement_checks`; implementations must not write a sibling
`requirements.json` for this workflow.

The Markdown feedback export requires valid matching canonical
`submission.json` and `review.json` records and uses only snapshotted review
content. It includes criterion scores and comments whose
`include_in_feedback` value is `true`; it excludes notes, tags, score
`teacher_note` values, excluded comments, and source/provenance fields. Source
comment banks are neither required nor read.

Export does not mutate the review record, update timestamps, or advance
`review_state` to `exported`. It writes only the derived feedback file and
refuses to replace an existing file unless overwrite is explicitly requested.

The class summary export similarly reads existing canonical records without
mutating them. It reports missing, invalid, and identity-mismatched records as
CSV status rows and includes only simple counts and arithmetic totals from
teacher-entered review data. It does not inspect evidence or comment banks,
calculate grades or mastery, or perform standards or roster reporting.

The standards summary export validates the same per-student canonical records
and aggregates only tags and selected comments that contain `standard_id`.
It reports tag polarity, comment feedback inclusion, distinct-student counts,
and assignment-level missing/invalid counts. It excludes scores and notes and
does not inspect evidence, read comment banks, infer
mastery, calculate grades, use a roster, or mutate canonical records.

## Synthetic Example

A complete fake record with a note, two tags, one criterion score, and one
selected comment is stored in
[`review_record_synthetic.json`](../examples/submissions/review_record_synthetic.json).

## Explicit Non-Goals

This contract does not implement:

* overall, weighted, percentage, grade, or mastery score calculation;
* assignment-driven comment-bank activation, bank editing, or guided
  reusable-comment management;
* roster-aware missing-student reporting;
* terminal-menu review workflows or review CLI commands beyond those listed;
* editing or deletion of append-only review artifacts;
* AI scoring, feedback, comments, suggestions, or automated grading;
* automatic standard detection;
* OCR, handwriting recognition, PDF text extraction, or QR extraction;
* evidence selection or duplicate resolution;
* email sending, LMS integration, dashboards, or report visualization.

The record describes teacher-entered or teacher-confirmed judgment only.
