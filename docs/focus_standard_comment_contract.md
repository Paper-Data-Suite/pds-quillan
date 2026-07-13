# Quillan Reusable Focus Standard Comment Contract

## Purpose and Boundary

Reusable Focus Standard comments are teacher-authored feedback language for
Quillan's v0.8.6 standards-based review workflow.

They replace generic prebuilt comment banks as the active reusable feedback
model for standards-based review.

The old model treated reusable comments as generic review materials prepared
before review. The new model treats reusable comments as language that can grow
naturally from actual teacher feedback composition.

A teacher should be able to:

1. review a student submission;
2. rate one or more Focus Standards;
3. compose student-facing feedback under a Focus Standard;
4. write a useful custom comment;
5. optionally save that comment for reuse;
6. edit out student-specific details before saving; and
7. later find that reusable comment by standard, writing type, rating level,
   and related metadata.

Reusable Focus Standard comments are source material. They are not student
review records, scores, grades, automatic suggestions, or generated feedback.

When selected for a student review, reusable comment text is copied into
`review.json` as a stable snapshot. Later edits to the reusable source must not
silently change prior student review records or previously generated feedback.

The direct `feedback add-comment --save-for-reuse` workflow uses the canonical
purposes and shared teacher-tag normalization defined here. Current-rating
tagging is opt-in; without `--tag-current-rating true`, the saved comment has
no rating restriction. `feedback use-reusable-comment` applies the existing
profile, writing-type, standard, rating, active, and student-facing lookup
rules, then increments `times_used` and updates `last_used_at` exactly once
after a successful selection.

## Status

This is the active reusable Focus Standard comment contract for the v0.8.6
standards-based workflow redesign.

Runtime validators, lookup, reusable-comment selection from feedback
composition, saving for reuse, usage tracking, safe writes, and tests now use
this contract. Future migration helpers may still be added if legacy classroom
data ever needs conversion.

## Design Context

This contract follows the standards-based redesign direction established in:

* [`standards_based_review_redesign.md`](standards_based_review_redesign.md)
* [`adr/0001-standards-based-review-model.md`](adr/0001-standards-based-review-model.md)
* [`assignment_contract.md`](assignment_contract.md)
* [`review_record_contract.md`](review_record_contract.md)

The central review relationship is:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Reusable Focus Standard comments support the final feedback part of that
relationship. They do not replace teacher judgment.

## Target Storage Location

Reusable Focus Standard comment sets are stored at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

This location is intentionally distinct from the legacy generic comment-bank
location:

```text
shared/comment_banks/<bank_id>.json
```

A comment set is a reusable source file. It is not a student record and is not
stored inside a specific student submission folder.

## Top-Level Structure

Every reusable Focus Standard comment set uses schema version `1`.

Example:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "focus_standard_comment_set",
  "comment_set_id": "english10_literary_analysis_focus_comments",
  "title": "English 10 Literary Analysis Focus Standard Comments",
  "description": "Reusable teacher-authored comments for English 10 literary analysis assignments.",
  "standards_profile_id": "english10_2023_njsls_ela",
  "writing_types": ["literary_analysis"],
  "grade_band": "9-10",
  "comments": [],
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required top-level fields are:

* `schema_version`;
* `module`;
* `record_type`;
* `comment_set_id`;
* `title`;
* `description`;
* `standards_profile_id`;
* `writing_types`;
* `grade_band`;
* `comments`;
* `created_at`;
* `updated_at`; and
* `module_details`.

Unknown top-level fields are not part of schema version `1`. A future contract
change must use a new schema version when it changes the meaning or required
shape of existing data.

## Top-Level Field Rules

### `schema_version`

`schema_version` must be the string `"1"`.

This is the first reusable Focus Standard comment-set schema. It is separate
from legacy comment-bank schema versions.

### `module`

`module` must be the string `"quillan"`.

### `record_type`

`record_type` must be the string `"focus_standard_comment_set"`.

### `comment_set_id`

`comment_set_id` is the durable identifier for the reusable comment set.

Rules:

* must be a non-empty string;
* must follow the shared `pds-core` identifier policy;
* must match the `<comment_set_id>` path segment where the file is stored;
* should be stable after creation.

Example:

```json
"comment_set_id": "english10_literary_analysis_focus_comments"
```

### `title`

`title` is the teacher-facing name of the comment set.

Rules:

* must be a non-empty string after trimming surrounding whitespace;
* should be suitable for menu display.

Example:

```json
"title": "English 10 Literary Analysis Focus Standard Comments"
```

### `description`

`description` explains the scope of the comment set.

Rules:

* must be a non-empty string after trimming surrounding whitespace;
* should describe the intended course, assignment type, writing type, or
  standards focus.

Example:

```json
"description": "Reusable teacher-authored comments for English 10 literary analysis assignments."
```

### `standards_profile_id`

`standards_profile_id` identifies the pds-core standards profile these
comments were written against.

Rules:

* must be a non-empty string;
* should identify a profile in the workspace standards library owned by
  `pds-core`;
* Quillan stores the reference but does not own, mutate, import, retire, or
  authoritatively validate the standards universe.

Example:

```json
"standards_profile_id": "english10_2023_njsls_ela"
```

### `writing_types`

`writing_types` identifies the writing types for which the comment set is
intended.

Rules:

* must be an array of non-empty strings;
* may be empty only if the comment set is intentionally writing-type agnostic;
* values should use the same lowercase snake-case convention as
  `assignment.json` `writing_type` values;
* duplicate values are invalid.

Example:

```json
"writing_types": ["literary_analysis"]
```

An empty array means the comment set is not limited to a specific writing type:

```json
"writing_types": []
```

### `grade_band`

`grade_band` identifies the intended grade band, when useful.

Rules:

* must be either `null` or a non-empty string;
* should use a compact teacher-readable value such as `"9-10"`, `"11-12"`,
  `"middle_school"`, or `"secondary"`;
* does not replace `standards_profile_id`.

Example:

```json
"grade_band": "9-10"
```

If the comment set is not grade-band specific:

```json
"grade_band": null
```

### `comments`

`comments` is an array of reusable Focus Standard comment records.

Rules:

* must be an array;
* may be empty;
* each `comment_id` must be unique within the set.

### `created_at` and `updated_at`

`created_at` records when the comment set was created.

`updated_at` records the most recent change anywhere in the comment set.

Rules:

* both must be ISO 8601 strings with explicit timezone offsets;
* naive timestamps are invalid;
* `updated_at` must not precede `created_at`.

Example:

```json
"created_at": "2026-07-02T00:00:00+00:00",
"updated_at": "2026-07-02T00:00:00+00:00"
```

### `module_details`

`module_details` is an object reserved for compatible Quillan extensions.

Rules:

* must be an object;
* may be empty;
* consumers must not require unknown keys inside `module_details`.

## Reusable Comment Structure

Each reusable Focus Standard comment stores teacher-authored language and
metadata for lookup.

Example:

```json
{
  "comment_id": "evidence_relevant_explanation_general",
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "writing_types": ["literary_analysis"],
  "rating_values": [2, 3],
  "label": "Relevant evidence, explanation needs development",
  "text": "Your evidence is relevant, but your explanation needs to make the connection to your claim clearer.",
  "purpose": "next_step",
  "student_facing": true,
  "active": true,
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "source": {
    "type": "teacher_saved_from_feedback",
    "class_id": "english_10_simulation",
    "assignment_id": "coming-of-age_literary_analysis",
    "student_id": "10001",
    "review_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
    "feedback_comment_id": "feedback_comment_0001",
    "saved_at": "2026-07-02T00:00:00+00:00"
  },
  "usage": {
    "times_used": 0,
    "last_used_at": null
  },
  "module_details": {}
}
```

Required comment fields are:

* `comment_id`;
* `standard_id`;
* `writing_types`;
* `rating_values`;
* `label`;
* `text`;
* `purpose`;
* `student_facing`;
* `active`;
* `created_at`;
* `updated_at`;
* `source`;
* `usage`; and
* `module_details`.

## Reusable Comment Field Rules

### `comment_id`

`comment_id` is the durable identifier for a reusable comment within the set.

Rules:

* must be a non-empty string;
* must follow the shared `pds-core` identifier policy;
* must be unique within `comments`;
* should be stable after creation.

Example:

```json
"comment_id": "evidence_relevant_explanation_general"
```

### `standard_id`

`standard_id` identifies the Focus Standard this comment supports.

Rules:

* must be a non-empty string;
* should be a durable pds-core `standard_id`;
* should belong to the comment set's `standards_profile_id`;
* is the primary lookup key for standards-based feedback composition.

Example:

```json
"standard_id": "njsls-ela:RL.CR.9-10.1"
```

Reusable Focus Standard comments are single-standard comments in schema version
`1`. If a teacher wants similar language for multiple standards, the language
should be represented as separate comment records, one per `standard_id`.

### `writing_types`

`writing_types` identifies writing types for which this comment is useful.

Rules:

* must be an array of non-empty strings;
* may be empty to indicate that the comment is not writing-type specific;
* values should use the same lowercase snake-case convention as assignment
  `writing_type`;
* duplicate values are invalid.

Example:

```json
"writing_types": ["literary_analysis"]
```

A comment's `writing_types` may be narrower than the comment set's top-level
`writing_types`.

### `rating_values`

`rating_values` identifies the rating levels for which this comment is useful.

Rules:

* must be an array of finite numbers;
* may be empty;
* duplicate values are invalid;
* values should correspond to `value` entries in the assignment's
  `rating_scale.levels`.

Example applying to one rating value:

```json
"rating_values": [2]
```

Example applying to multiple rating values:

```json
"rating_values": [2, 3]
```

An empty array means the comment is not rating-specific:

```json
"rating_values": []
```

The contract uses numeric rating values instead of hardcoding labels such as
`Developing`, `Approaching`, `Meeting`, or `Exceeding`, because rating labels
may vary by assignment. Teacher-facing workflows may display labels by
resolving values against the assignment's `rating_scale`.

### `label`

`label` is the short teacher-facing title for the reusable comment.

Rules:

* must be a non-empty string after trimming surrounding whitespace;
* should be concise enough for menu display;
* should summarize the feedback move.

Example:

```json
"label": "Relevant evidence, explanation needs development"
```

### `text`

`text` is the student-facing reusable feedback language.

Rules:

* must be a non-empty string after trimming surrounding whitespace;
* should be written to a student;
* must not contain real student-identifying information;
* should avoid assignment-specific language unless that specificity is
  intentional and safe for reuse.

Example:

```json
"text": "Your evidence is relevant, but your explanation needs to make the connection to your claim clearer."
```

### `purpose`

`purpose` is a stable, broad feedback-function enum for teacher-facing
organization. It describes the feedback move, not the assignment's writing
type or genre.

Allowed values are:

* `praise`;
* `next_step`;
* `clarification`;
* `evidence`;
* `reasoning`;
* `organization`;
* `style`;
* `conventions`;
* `revision`; and
* `general`.

Example:

```json
"purpose": "next_step"
```

Purpose is teacher-facing organization only. It must not imply automatic
scoring and is not required for automatic comment selection. `general` is the
appropriate value when none of the stable categories fits. For example, a
creative-writing comment about character or dialogue may use `general` plus
optional teacher tags rather than forcing genre vocabulary into `purpose`.

Writing-type compatibility remains represented by `writing_types`, including
creative writing, narrative writing, poetry, multimedia writing, and
teacher-defined assignment types.

### `student_facing`

`student_facing` indicates whether the comment is appropriate for student
feedback.

Rules:

* must be a boolean;
* comments with `student_facing: false` should not be shown by default during
  student-facing feedback composition.

Example:

```json
"student_facing": true
```

### `active`

`active` controls whether the comment is offered by default during feedback
composition.

Rules:

* must be a boolean;
* inactive comments remain preserved;
* inactive comments should not be shown by default in ordinary lookup results.

Example:

```json
"active": true
```

Deactivation is preferred over deletion as the ordinary lifecycle action.

### `created_at` and `updated_at`

`created_at` records when the reusable comment was created.

`updated_at` records the most recent change to that comment.

Rules:

* both must be ISO 8601 strings with explicit timezone offsets;
* `updated_at` must not precede `created_at`.

### `module_details`

`module_details` is an object reserved for compatible Quillan extensions.

Rules:

* must be an object;
* may be empty;
* consumers must not require unknown keys inside `module_details`.

Quillan may store optional teacher-facing, writing-type-specific organization
tags under `module_details.teacher_tags`:

```json
"module_details": {
  "teacher_tags": ["character", "dialogue"]
}
```

When present, `teacher_tags` must be an array of unique, non-empty lowercase
snake-case strings. Quillan normalizes teacher input such as `Scene
Development` to `scene_development`. Tags are optional; consumers must tolerate
their absence, and existing schema version `1` comments with empty
`module_details` remain valid. Consumers must not require teacher tags for
lookup or automatic selection.

## Source and Provenance

`source` records how the reusable comment entered the comment set.

Example saved from feedback:

```json
{
  "type": "teacher_saved_from_feedback",
  "class_id": "english_10_simulation",
  "assignment_id": "coming-of-age_literary_analysis",
  "student_id": "10001",
  "review_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
  "feedback_comment_id": "feedback_comment_0001",
  "saved_at": "2026-07-02T00:00:00+00:00"
}
```

Example manually authored comment:

```json
{
  "type": "manual",
  "class_id": null,
  "assignment_id": null,
  "student_id": null,
  "review_path": null,
  "feedback_comment_id": null,
  "saved_at": "2026-07-02T00:00:00+00:00"
}
```

Required `source` fields are:

* `type`;
* `class_id`;
* `assignment_id`;
* `student_id`;
* `review_path`;
* `feedback_comment_id`; and
* `saved_at`.

Allowed `source.type` values are:

* `manual`;
* `teacher_saved_from_feedback`;
* `migration`; and
* `starter_material`.

Field rules:

* `type` must be one of the controlled values above.
* `saved_at` must be a timezone-aware ISO 8601 timestamp.
* When `type` is `teacher_saved_from_feedback`, `class_id`, `assignment_id`,
  `student_id`, `review_path`, and `feedback_comment_id` should be non-empty.
* When `type` is `manual`, `class_id`, `assignment_id`, `student_id`,
  `review_path`, and `feedback_comment_id` should be `null`.
* When `type` is `migration` or `starter_material`, those fields may be `null`
  unless a later migration or starter-material workflow defines specific
  provenance requirements.
* `review_path`, when present, must be a safe workspace-relative path.

Source provenance is for auditability and teacher context. It must not be used
to expose real student data in committed examples.

## Usage Metadata

`usage` records convenience metadata about reuse.

Example:

```json
{
  "times_used": 0,
  "last_used_at": null
}
```

Required `usage` fields are:

* `times_used`;
* `last_used_at`.

Field rules:

* `times_used` must be a non-negative integer.
* `last_used_at` must be either `null` or a timezone-aware ISO 8601 timestamp.
* `last_used_at` should be `null` when `times_used` is `0`.
* `last_used_at` should be non-null when `times_used` is greater than `0`.

Usage metadata is convenience metadata only. It must not determine student
score, rating, standards performance, feedback quality, or report outcomes.

If implemented later, usage counts should update only when a teacher actually
selects the reusable comment for a student review.

## Lookup and Filtering

Reusable Focus Standard comments should support lookup by:

* `standard_id`;
* `writing_type`;
* `rating_value`;
* `active`;
* `student_facing`.

Optional lookup filters may include:

* `grade_band`;
* `purpose`;
* `comment_set_id`;
* course or class context if future contracts define that metadata;
* usage recency; and
* usage count.

Teacher tags are display and organization metadata, not durable lookup keys.
Lookup must not require them. Stable matching remains based on the comment
set's `standards_profile_id` and durable comment/assignment fields such as
`writing_type`, `standard_id`, optional `rating_value`, `active`, and
`student_facing` status. `purpose` may support an explicit future teacher
filter, but is not required for automatic comment selection.

A typical feedback-composition workflow should use the current assignment and
review context:

* assignment `standards_profile_id`;
* assignment `writing_type`;
* assignment `focus_standard_ids`;
* assignment `rating_scale`;
* selected Focus Standard;
* selected overall rating value, when available.

Example lookup intent:

```text
Show active, student-facing comments for standard njsls-ela:RL.CR.9-10.1,
writing type literary_analysis, and rating value 2.
```

Matching logic should generally prefer:

1. comments with the exact selected `standard_id`;
2. comments whose `writing_types` includes the assignment `writing_type`, or
   whose `writing_types` is empty;
3. comments whose `rating_values` includes the selected rating value, or whose
   `rating_values` is empty;
4. active comments;
5. student-facing comments.

Quillan may display matching comments for teacher selection, but it must not
automatically choose comments for the teacher.

Comment lookup is assistance, not automatic feedback generation.

## Relationship to `review.json`

Schema version `2` `review.json` stores student-specific feedback comments as
snapshots under:

```text
review.json.feedback.standard_feedback[].comments[]
```

A reusable Focus Standard comment is source material. It is not the canonical
student review record.

When a teacher selects a reusable Focus Standard comment for a student review,
Quillan should copy the reusable comment text into the student review record.

The student review record should preserve:

* the copied text;
* `source: "reusable_focus_standard_comment"`;
* the reusable comment ID;
* the teacher's include/exclude choice;
* the created timestamp; and
* any module details needed for provenance.

Example student-review feedback comment after selection:

```json
{
  "feedback_comment_id": "feedback_comment_0004",
  "source": "reusable_focus_standard_comment",
  "text": "Your evidence is relevant, but your explanation needs to make the connection to your claim clearer.",
  "reusable_comment_id": "evidence_relevant_explanation_general",
  "save_for_reuse": false,
  "include_in_feedback": true,
  "created_at": "2026-07-02T00:00:00+00:00",
  "module_details": {
    "comment_set_id": "english10_literary_analysis_focus_comments"
  }
}
```

Later edits to the reusable comment source must not silently change prior
student review records.

Generated feedback exports must use the snapshotted student review record, not
a live lookup into reusable comment sets.

## Relationship to `assignment.json`

Reusable Focus Standard comments should be filtered using assignment context.

The assignment provides:

* `standards_profile_id`;
* `focus_standard_ids`;
* `writing_type`;
* `rating_scale`;
* `review_unit`;
* class identity; and
* possibly later course or grade-band metadata.

Comment lookup should generally show comments that match:

* the assignment's `standards_profile_id`;
* one of the assignment's `focus_standard_ids`;
* the assignment's `writing_type`;
* the teacher's selected rating value, when available.

The assignment does not need to activate comment sets in advance for the target
v0.8.6 model. A later workflow may add explicit assignment-level comment-set
activation if that proves useful, but this contract does not require it.

## Relationship to Legacy Comment Banks

Legacy generic comment banks are stored at:

```text
shared/comment_banks/<bank_id>.json
```

Reusable Focus Standard comments are stored at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

Legacy comment banks may remain readable for old workflows until removed or
migrated.

The new reusable Focus Standard comment model supersedes generic comment banks
for the standards-based review workflow.

Key differences:

* legacy comment banks are generic review materials;
* Focus Standard comments are tied directly to `standard_id`;
* legacy banks encourage prebuilding reusable material before review;
* Focus Standard comments can grow from actual teacher feedback composition;
* legacy selected comments are stored in schema version `1`
  `review.json.comments`;
* Focus Standard comment selections are snapshotted into schema version `2`
  `review.json.feedback.standard_feedback[].comments[]`.

This contract does not delete legacy comment-bank documentation or
implementation. It defines the target direction for v0.8.6.

## Lifecycle

The basic reusable comment lifecycle is:

```text
active -> inactive
```

Active comments should be shown by default during ordinary lookup.

Inactive comments remain preserved but should not be shown by default.

Hard deletion should not be the ordinary teacher workflow. Deactivation
preserves history, avoids breaking provenance, and allows later reactivation if
a workflow supports it.

Later implementation may add workflows for:

* editing reusable comments;
* deactivating comments;
* reactivating comments;
* merging duplicates;
* viewing usage history;
* moving comments between sets; and
* migrating legacy comment-bank comments.

## Privacy and Data Hygiene

Reusable comments must not contain student-identifying information.

Reusable comments must not store or expose:

* real student names;
* parent or guardian names;
* student ID numbers inside comment text;
* health information;
* disability information;
* accommodation information;
* discipline information;
* attendance information;
* private family information;
* grades;
* exact copied student writing unless it is synthetic example content; or
* any personally identifiable student information.

A comment saved from feedback should be teacher-reviewed before being stored
for reuse. The save workflow should give the teacher a chance to edit out
student-specific details.

Committed examples must use synthetic data only.

## Complete Synthetic Example

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "focus_standard_comment_set",
  "comment_set_id": "english10_literary_analysis_focus_comments",
  "title": "English 10 Literary Analysis Focus Standard Comments",
  "description": "Reusable teacher-authored comments for English 10 literary analysis assignments.",
  "standards_profile_id": "english10_2023_njsls_ela",
  "writing_types": ["literary_analysis"],
  "grade_band": "9-10",
  "comments": [
    {
      "comment_id": "evidence_relevant_explanation_general",
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "writing_types": ["literary_analysis"],
      "rating_values": [2, 3],
      "label": "Relevant evidence, explanation needs development",
      "text": "Your evidence is relevant, but your explanation needs to make the connection to your claim clearer.",
      "purpose": "next_step",
      "student_facing": true,
      "active": true,
      "created_at": "2026-07-02T00:00:00+00:00",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "source": {
        "type": "teacher_saved_from_feedback",
        "class_id": "english_10_simulation",
        "assignment_id": "coming-of-age_literary_analysis",
        "student_id": "10001",
        "review_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
        "feedback_comment_id": "feedback_comment_0001",
        "saved_at": "2026-07-02T00:00:00+00:00"
      },
      "usage": {
        "times_used": 0,
        "last_used_at": null
      },
      "module_details": {}
    },
    {
      "comment_id": "interpretation_objects_memory_strength",
      "standard_id": "njsls-ela:RL.CI.9-10.2",
      "writing_types": ["literary_analysis"],
      "rating_values": [3, 4],
      "label": "Strong interpretation of object motif",
      "text": "Your interpretation clearly explains how ordinary objects become connected to memory, grief, and family history.",
      "purpose": "praise",
      "student_facing": true,
      "active": true,
      "created_at": "2026-07-02T00:00:00+00:00",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "source": {
        "type": "teacher_saved_from_feedback",
        "class_id": "english_10_simulation",
        "assignment_id": "coming-of-age_literary_analysis",
        "student_id": "10001",
        "review_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
        "feedback_comment_id": "feedback_comment_0002",
        "saved_at": "2026-07-02T00:00:00+00:00"
      },
      "usage": {
        "times_used": 0,
        "last_used_at": null
      },
      "module_details": {}
    },
    {
      "comment_id": "argument_claim_precision_next_step",
      "standard_id": "njsls-ela:W.AW.9-10.1",
      "writing_types": ["literary_analysis"],
      "rating_values": [2, 3],
      "label": "Make paragraph claims more precise",
      "text": "Your essay stays focused on a clear interpretation. For the next essay, work on making each paragraph's claim as precise as possible.",
      "purpose": "next_step",
      "student_facing": true,
      "active": true,
      "created_at": "2026-07-02T00:00:00+00:00",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "source": {
        "type": "teacher_saved_from_feedback",
        "class_id": "english_10_simulation",
        "assignment_id": "coming-of-age_literary_analysis",
        "student_id": "10001",
        "review_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
        "feedback_comment_id": "feedback_comment_0003",
        "saved_at": "2026-07-02T00:00:00+00:00"
      },
      "usage": {
        "times_used": 0,
        "last_used_at": null
      },
      "module_details": {}
    },
    {
      "comment_id": "evidence_quote_integration_manual",
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "writing_types": ["literary_analysis"],
      "rating_values": [],
      "label": "Improve quote integration",
      "text": "When you use a quotation, introduce it smoothly and follow it with analysis that explains why it matters.",
      "purpose": "revision",
      "student_facing": true,
      "active": true,
      "created_at": "2026-07-02T00:00:00+00:00",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "source": {
        "type": "manual",
        "class_id": null,
        "assignment_id": null,
        "student_id": null,
        "review_path": null,
        "feedback_comment_id": null,
        "saved_at": "2026-07-02T00:00:00+00:00"
      },
      "usage": {
        "times_used": 0,
        "last_used_at": null
      },
      "module_details": {}
    }
  ],
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

## Legacy Status

Legacy generic comment banks and schema version `1` `review.json.comments`
remain historical/compatibility material. They are not the active v0.8.6
student-feedback composition workflow.

## Explicit Non-Goals

This contract does not define:

* automatic comment suggestions;
* automatic feedback generation;
* AI-generated comments;
* AI feedback drafting;
* automatic scoring;
* automatic standards detection;
* deletion of legacy comment-bank documentation;
* tag-bank redesign;
* report changes; or
* cross-assignment comment analytics.

Reusable Focus Standard comments are teacher-authored source material only.
They support teacher feedback work but do not replace teacher judgment.
