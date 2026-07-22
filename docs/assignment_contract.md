# Quillan Assignment Contract

## Purpose

This document defines the v0.8.6 Quillan assignment contract.

The assignment record describes what the teacher asked students to do and how Quillan should structure review for that assignment. Under the standards-based redesign, the assignment is the source of truth for:

* assignment identity;
* class identity;
* student-facing prompt;
* writing type;
* standards profile;
* Focus Standards;
* review-unit type and teacher-facing labels;
* standards rating scale;
* minimum requirements; and
* minimum-requirement return policy.

This contract follows the standards-based review direction established in:

* [`standards_based_review_redesign.md`](standards_based_review_redesign.md)
* [`adr/0001-standards-based-review-model.md`](adr/0001-standards-based-review-model.md)

The central review relationship is:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

## Status

This is the active assignment contract for the v0.8.6 standards-based workflow redesign.

It supersedes the old tag/comment/rubric-centered assignment shape that used `tagging_mode`, `focus_standards`, and `rubric_id` as central fields.

Runtime validation, assignment creation, assignment discovery, and tests use
this schema version `2` shape. Validation is strict: Quillan does not silently
add missing fields or rewrite older assignment files during load, show, or
validation. Future migration helpers may still be added if legacy classroom
data ever needs conversion.

## Canonical Path

The current assignment file location remains:

```text
<PDS workspace root>/classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
```

The assignment record contains `class_ids`, which may include one or more class IDs.

For the current local workspace layout, an assignment file is still stored under a class assignment directory. If the same assignment is used across multiple classes, later implementation work must define whether Quillan writes one canonical assignment record per class, synchronizes copies, or introduces a shared assignment location. This contract allows multiple `class_ids`, but it does not by itself finalize the storage strategy for multi-class assignment management.

## Top-Level Structure

A v0.8.6 standards-based assignment record uses schema version `2`.

Example:

```json
{
  "schema_version": "2",
  "module": "quillan",
  "record_type": "assignment",
  "assignment_id": "coming-of-age_literary_analysis",
  "title": "Coming-of-Age Literary Analysis",
  "class_ids": ["english_10_simulation"],
  "writing_type": "literary_analysis",
  "student_prompt": "Using evidence from the story, explain how Nghi Vo turns ordinary objects into carriers of memory, grief, and power.",
  "standards_profile_id": "english10_2023_njsls_ela",
  "focus_standard_ids": [
    "njsls-ela:RL.CR.9-10.1",
    "njsls-ela:RL.CI.9-10.2",
    "njsls-ela:W.AW.9-10.1"
  ],
  "review_unit": {
    "type": "paragraph",
    "singular_label": "paragraph",
    "plural_label": "paragraphs"
  },
  "rating_scale": {
    "scale_id": "standards_4_level",
    "levels": [
      {
        "value": 1,
        "label": "Developing",
        "description": "The work shows limited or emerging evidence of the standard."
      },
      {
        "value": 2,
        "label": "Approaching",
        "description": "The work shows partial evidence of the standard but is uneven, general, or incomplete."
      },
      {
        "value": 3,
        "label": "Meeting",
        "description": "The work shows clear and sufficient evidence of the standard."
      },
      {
        "value": 4,
        "label": "Exceeding",
        "description": "The work shows especially strong, precise, or sophisticated evidence of the standard."
      }
    ]
  },
  "basic_requirements": {
    "paragraphs_min": 1,
    "required_elements": [
      "textual evidence",
      "explanation"
    ]
  },
  "minimum_requirement_policy": {
    "allow_return_without_full_review": true
  },
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

## Required Fields

Every schema version `2` assignment record must contain:

* `schema_version`
* `module`
* `record_type`
* `assignment_id`
* `title`
* `class_ids`
* `writing_type`
* `student_prompt`
* `standards_profile_id`
* `focus_standard_ids`
* `review_unit`
* `rating_scale`
* `basic_requirements`
* `minimum_requirement_policy`
* `created_at`
* `updated_at`
* `module_details`

Unknown top-level fields are not part of schema version `2`. A future contract change must use a new schema version when it changes the meaning or required shape of existing data.

## Field Rules

### `schema_version`

`schema_version` must be the string `"2"`.

Schema version `2` is a breaking assignment-contract change from the old pre-v0.8.6 assignment shape.

### `module`

`module` must be the string `"quillan"`.

### `record_type`

`record_type` must be the string `"assignment"`.

### `assignment_id`

`assignment_id` is the durable assignment identifier.

Rules:

* must be a non-empty string;
* must follow the shared `pds-core` identifier policy;
* must match the `<assignment_id>` path segment where the assignment is stored;
* should be stable after creation.

Example:

```json
"assignment_id": "coming-of-age_literary_analysis"
```

### `title`

`title` is the teacher-facing assignment title.

Rules:

* must be a non-empty string after trimming surrounding whitespace;
* should be suitable for display in menus, summaries, exports, and reports.

Example:

```json
"title": "Coming-of-Age Literary Analysis"
```

### `class_ids`

`class_ids` identifies the class or classes using the assignment.

Rules:

* must be a non-empty array of strings;
* every value must follow the shared `pds-core` identifier policy;
* duplicate class IDs are invalid;
* if the assignment is stored under `classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json`, the path class ID must appear in `class_ids`.

Example:

```json
"class_ids": ["english_10_simulation"]
```

Multi-class assignment authoring may not be fully implemented yet. Until implementation catches up, validators and workflows may restrict assignment writing to one selected class even though this target contract allows multiple class IDs.

### `writing_type`

`writing_type` identifies the general kind of writing or response being reviewed.

Rules:

* must be a non-empty string;
* should use lowercase snake case;
* should avoid spaces;
* should be stable enough for reusable comments, reporting, and future workflow filtering.

Recommended examples:

```text
literary_analysis
argument
constructed_response
compare_contrast
reflection
research
lab_explanation
technical_explanation
design_rationale
journal_response
```

The writing type is not a standards profile and not a grading rubric. It is assignment context.

### `student_prompt`

`student_prompt` stores the prompt students received.

Rules:

* must be a non-empty string;
* should preserve the actual student-facing task as closely as practical;
* may contain multiple sentences;
* may contain line breaks if needed.

Example:

```json
"student_prompt": "Using evidence from the story, explain how Nghi Vo turns ordinary objects into carriers of memory, grief, and power."
```

The student prompt should appear in assignment summaries and review context where useful.

Printable response packets should not automatically include the prompt unless a later issue explicitly changes packet-generation behavior.

### `standards_profile_id`

`standards_profile_id` identifies the standards profile from which Focus Standards are selected.

Rules:

* must be a non-empty string;
* must identify a profile in the workspace standards library owned by `pds-core`;
* Quillan stores the reference but does not own, mutate, import, retire, or authoritatively validate the standards universe.

Example:

```json
"standards_profile_id": "english10_2023_njsls_ela"
```

### `focus_standard_ids`

`focus_standard_ids` lists the standards assessed by this assignment.

Rules:

* must be a non-empty array of strings;
* every value must be a durable `pds-core` `standard_id`;
* duplicate standard IDs are invalid;
* every value should belong to the selected `standards_profile_id`;
* order is meaningful for teacher-facing review workflows.

Example:

```json
"focus_standard_ids": [
  "njsls-ela:RL.CR.9-10.1",
  "njsls-ela:RL.CI.9-10.2",
  "njsls-ela:W.AW.9-10.1"
]
```

These standards are the standards Quillan should iterate through during review-unit observations and overall Focus Standard ratings.

## Review Unit

`review_unit` defines the assignment-specific unit of student evidence used during review.

For an English essay, the review unit will often be a paragraph. For other assignments, the review unit might be a stanza, page, section, scene, response, or whole submission.

Example:

```json
"review_unit": {
  "type": "paragraph",
  "singular_label": "paragraph",
  "plural_label": "paragraphs"
}
```

Required fields:

* `type`
* `singular_label`
* `plural_label`

### `review_unit.type`

`type` is the internal review-unit type.

Recommended values:

```text
paragraph
stanza
page
section
scene
response
whole_submission
custom
```

Rules:

* must be a non-empty lowercase snake-case string;
* should use one of the recommended values unless the assignment needs a custom unit;
* if `type` is `custom`, the teacher-facing labels become especially important.

### `review_unit.singular_label`

`singular_label` is the teacher-facing singular label.

Examples:

```text
paragraph
stanza
page
section
scene
response
submission
```

Rules:

* must be a non-empty string;
* should be lowercase unless the term conventionally requires capitalization;
* should be suitable for teacher-facing prompts.

### `review_unit.plural_label`

`plural_label` is the teacher-facing plural label.

Examples:

```text
paragraphs
stanzas
pages
sections
scenes
responses
submissions
```

Rules:

* must be a non-empty string;
* should be suitable for teacher-facing prompts.

### Teacher-Facing Label Use

The internal model may use the term `review_unit`, but teacher-facing workflows should use the configured labels.

If the assignment uses:

```json
"review_unit": {
  "type": "paragraph",
  "singular_label": "paragraph",
  "plural_label": "paragraphs"
}
```

then Quillan should ask:

```text
How many paragraphs did the student write?
```

not:

```text
How many review units did the student write?
```

If the assignment uses:

```json
"review_unit": {
  "type": "stanza",
  "singular_label": "stanza",
  "plural_label": "stanzas"
}
```

then Quillan should ask:

```text
How many stanzas did the student write?
```

## Rating Scale

`rating_scale` defines the performance levels used for review-unit Focus Standard observations and overall Focus Standard ratings.

Example:

```json
"rating_scale": {
  "scale_id": "standards_4_level",
  "levels": [
    {
      "value": 1,
      "label": "Developing",
      "description": "The work shows limited or emerging evidence of the standard."
    },
    {
      "value": 2,
      "label": "Approaching",
      "description": "The work shows partial evidence of the standard but is uneven, general, or incomplete."
    },
    {
      "value": 3,
      "label": "Meeting",
      "description": "The work shows clear and sufficient evidence of the standard."
    },
    {
      "value": 4,
      "label": "Exceeding",
      "description": "The work shows especially strong, precise, or sophisticated evidence of the standard."
    }
  ]
}
```

Required fields:

* `scale_id`
* `levels`

### `rating_scale.scale_id`

`scale_id` identifies the scale.

Rules:

* must be a non-empty string;
* should follow the shared `pds-core` identifier policy or a compatible lowercase snake-case pattern;
* identifies the assignment-local scale definition;
* does not imply a shared global scale unless later contracts define shared rating-scale records.

Example:

```json
"scale_id": "standards_4_level"
```

### `rating_scale.levels`

`levels` is an ordered array of rating levels.

Rules:

* must contain at least two levels;
* every level must contain `value`, `label`, and `description`;
* `value` must be a finite number;
* `label` must be a non-empty string;
* `description` must be a non-empty string;
* level values must be unique;
* level labels must be unique within the scale;
* higher numeric values should represent stronger performance;
* the array should be ordered from lowest performance to highest performance.

The default v0.8.6 scale is:

```text
1. Developing
2. Approaching
3. Meeting
4. Exceeding
```

### Relationship to Rubrics

The rating scale replaces generic rubric criteria as the primary scoring structure.

A rating scale may still provide rubric-like level descriptions, but the teacher’s scoring decision is attached to a Focus Standard, not to a generic rubric criterion.

Old model:

```text
Rubric criterion: Literary Concepts
Score: 3 / 4
```

New model:

```text
Focus Standard: njsls-ela:RL.CI.9-10.2
Overall rating: Meeting
```

## Basic Requirements

`basic_requirements` defines structural or compliance expectations for the assignment.

Example:

```json
"basic_requirements": {
  "paragraphs_min": 1,
  "required_elements": [
    "textual evidence",
    "explanation"
  ]
}
```

`basic_requirements` must be an object. It may be empty when an assignment has no configured basic requirements:

```json
"basic_requirements": {}
```

Supported fields:

* `paragraphs_min`
* `paragraphs_max`
* `word_count_min`
* `word_count_max`
* `required_elements`

### Numeric Requirement Fields

The following fields, when present, must be non-negative integers:

* `paragraphs_min`
* `paragraphs_max`
* `word_count_min`
* `word_count_max`

If both a minimum and maximum are present for the same measure, the minimum must be less than or equal to the maximum.

Example:

```json
"basic_requirements": {
  "paragraphs_min": 3,
  "paragraphs_max": 5,
  "word_count_min": 400,
  "word_count_max": 800
}
```

### `required_elements`

`required_elements` identifies required content or structural elements that the teacher will check.

Rules:

* when present, must be a non-empty array of strings;
* every element must be non-empty after trimming surrounding whitespace;
* duplicate required elements are invalid;
* values should be teacher-facing labels.

Example:

```json
"required_elements": [
  "claim",
  "textual evidence",
  "explanation"
]
```

### Teacher-Controlled Requirement Checks

Quillan does not automatically evaluate minimum requirements.

Quillan must not:

* count paragraphs automatically;
* count words automatically;
* parse student writing;
* run OCR to determine whether requirements are met;
* use AI to detect required elements;
* infer that a requirement is met or unmet from student writing.

The teacher records whether each requirement was met.

Requirement checks are not writing-quality scores. They are structural or compliance records used before full standards review.

### Relationship Between Review Unit and Requirements

The assignment’s review unit determines review structure, but existing requirement keys may still use known requirement names such as `paragraphs_min`.

Later implementation may generalize review-unit count requirements. For example, a poetry assignment might display “Minimum stanzas” in teacher-facing workflows even if the internal requirement system uses a generalized review-unit count.

This contract preserves the existing `paragraphs_min`, `paragraphs_max`, `word_count_min`, `word_count_max`, and `required_elements` fields for v0.8.6, while allowing later contracts to introduce more generalized requirement keys.

## Minimum Requirement Policy

`minimum_requirement_policy` defines what Quillan should allow when minimum requirements are not met.

Example:

```json
"minimum_requirement_policy": {
  "allow_return_without_full_review": true
}
```

Required fields:

* `allow_return_without_full_review`

### `allow_return_without_full_review`

`allow_return_without_full_review` is a boolean.

When `true`, Quillan may offer the teacher a workflow to return the submission without completing full standards review if minimum requirements are unmet.

When `false`, Quillan may still record unmet requirements, but the assignment does not explicitly permit an early return-without-full-review workflow.

Returning work without full review must not be treated as:

* a zero;
* a completed full review;
* a completed standards score;
* a normal scored submission;
* an automatic grade.

It is a separate teacher-controlled review outcome indicating that the submission was not ready for full standards scoring.

## Timestamps

### `created_at`

`created_at` records when the assignment record was created.

Rules:

* must be an ISO 8601 string with an explicit timezone offset;
* must not be a naive timestamp;
* should not change after assignment creation.

Example:

```json
"created_at": "2026-07-02T00:00:00+00:00"
```

### `updated_at`

`updated_at` records the most recent change to the assignment record.

Rules:

* must be an ISO 8601 string with an explicit timezone offset;
* must not be a naive timestamp;
* should update whenever assignment configuration changes.

Example:

```json
"updated_at": "2026-07-02T00:00:00+00:00"
```

## `module_details`

`module_details` is an object reserved for compatible Quillan extensions.

Rules:

* must be an object;
* may be empty;
* consumers must not require unknown keys inside `module_details`;
* future compatible additions may use this object when they do not change the core meaning of the assignment record.

Example:

```json
"module_details": {}
```

## Deprecated and Superseded Fields

The v0.8.6 assignment contract supersedes several old fields.

### `tagging_mode`

`tagging_mode` belongs to the old tag-centered workflow.

It is not part of the v0.8.6 target assignment contract.

Old purpose:

```text
Tell Quillan how to select or organize tags.
```

New model:

```text
Quillan reviews each assignment-defined review unit against each Focus Standard.
```

The review workflow no longer needs `tagging_mode` as a central assignment field.

### `rubric_id`

`rubric_id` belongs to the old generic rubric/scoring-profile workflow.

It is not part of the v0.8.6 target assignment contract as the primary scoring mechanism.

Old purpose:

```text
Resolve a shared rubric profile and score generic criteria.
```

New model:

```text
Use the assignment rating scale to rate each Focus Standard.
```

Rubric-like language may still exist inside rating-scale level descriptions, but overall scoring is attached to Focus Standards, not generic rubric criteria.

### `focus_standards`

The old assignment field `focus_standards` is superseded by `focus_standard_ids`.

The new name makes the field’s contents explicit: it stores durable standard IDs, not full standard records, display labels, or standards-profile data.

The v2 assignment loader does not accept old `focus_standards` fields as valid active assignment data. Use `focus_standard_ids` in schema version `2` records.

## Backward Compatibility and Migration

Schema version `2` is a breaking assignment-contract update.

The old pre-v0.8.6 assignment shape included fields such as:

```text
tagging_mode
focus_standards
rubric_id
```

Those fields are superseded by the standards-based assignment shape.

Quillan rejects older assignment records and schema-version-2 records missing
required contract fields. Ordinary load, show, discovery, and validation
operations do not normalize or mutate those files. No production-data
migration is provided by this contract.

## Assignment Creation

Assignment-creation workflows ask for or confirm:

1. class or classes using the assignment;
2. assignment title;
3. student-facing prompt;
4. writing type, with lowercase snake-case guidance;
5. standards profile;
6. Focus Standards from that profile;
7. review-unit type and teacher-facing labels;
8. rating scale;
9. minimum requirements; and
10. minimum-requirement return policy.

Assignment summaries should display:

* assignment ID;
* title;
* class ID or class IDs;
* writing type;
* student-facing prompt, possibly shortened for menus;
* standards profile;
* Focus Standards with readable standard descriptions where available;
* review-unit type and labels;
* rating scale;
* minimum requirements;
* minimum-requirement policy;
* assignment path.

Assignment creation should not require teachers to choose generic tag banks, comment banks, or rubrics as central assignment setup steps.

Menu and direct CLI creation automatically add `created_at`, `updated_at`, and
`module_details`. Both timestamps initially use one timezone-aware UTC ISO 8601
value, and `module_details` initially uses an empty object.

## Teacher-Facing Review Implications

The assignment contract should allow review workflows to produce prompts such as:

```text
How many paragraphs did the student write?
```

Then, for each paragraph and each Focus Standard:

```text
Paragraph 1

Focus Standard:
RL.CR.9-10.1 — Cite strong and thorough textual evidence to support analysis.

Standard applicable? Y/N
Evidence of standard? Y/N

Rating:
1. Developing
2. Approaching
3. Meeting
4. Exceeding

Rationale/comment, optional:
```

The assignment contract provides the Focus Standards, review-unit labels, and rating scale needed for this workflow.

## Complete English 10 Example

```json
{
  "schema_version": "2",
  "module": "quillan",
  "record_type": "assignment",
  "assignment_id": "coming-of-age_literary_analysis",
  "title": "Coming-of-Age Literary Analysis",
  "class_ids": ["english_10_simulation"],
  "writing_type": "literary_analysis",
  "student_prompt": "Using evidence from the story, explain how Nghi Vo turns ordinary objects into carriers of memory, grief, and power.",
  "standards_profile_id": "english10_2023_njsls_ela",
  "focus_standard_ids": [
    "njsls-ela:RL.CR.9-10.1",
    "njsls-ela:RL.CI.9-10.2",
    "njsls-ela:W.AW.9-10.1"
  ],
  "review_unit": {
    "type": "paragraph",
    "singular_label": "paragraph",
    "plural_label": "paragraphs"
  },
  "rating_scale": {
    "scale_id": "standards_4_level",
    "levels": [
      {
        "value": 1,
        "label": "Developing",
        "description": "The work shows limited or emerging evidence of the standard."
      },
      {
        "value": 2,
        "label": "Approaching",
        "description": "The work shows partial evidence of the standard but is uneven, general, or incomplete."
      },
      {
        "value": 3,
        "label": "Meeting",
        "description": "The work shows clear and sufficient evidence of the standard."
      },
      {
        "value": 4,
        "label": "Exceeding",
        "description": "The work shows especially strong, precise, or sophisticated evidence of the standard."
      }
    ]
  },
  "basic_requirements": {
    "paragraphs_min": 1,
    "required_elements": [
      "textual evidence",
      "explanation"
    ]
  },
  "minimum_requirement_policy": {
    "allow_return_without_full_review": true
  },
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

## Non-Goals

This contract does not define the new review record schema.

This contract does not define feedback export schemas.

This contract does not define standards-report schemas.

This contract does not migrate old assignment records, and runtime validation
does not repair them implicitly.

This contract does not authorize automatic scoring, OCR-based review, AI feedback, or automatic standards detection.

## Summary

The v0.8.6 assignment contract makes the assignment record the source of truth for standards-based review setup.

Old assignment model:

```text
assignment -> tagging mode -> tag banks / comment banks / rubric -> review artifacts
```

New assignment model:

```text
assignment -> Focus Standards + review unit + rating scale -> standards-based review
```

This contract ensures that later review records, feedback exports, and reports can all be built around the same assignment-defined standards-based structure.
