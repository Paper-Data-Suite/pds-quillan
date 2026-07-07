# Quillan Rubric / Scoring Profile Contract

Status: legacy/inactive compatibility documentation. Generic rubrics and
criterion-score workflows are not the active v0.8.6 scoring workflow. Active
ratings are overall Focus Standard ratings using the assignment `rating_scale`.

Rubrics and scoring profiles are teacher-authored reusable review materials.
They let a teacher score prepared criteria by selecting a criterion and level
during review instead of typing raw score fields.

Rubrics are subject-agnostic scoring profiles. They define criteria and
levels; they do not automatically grade, calculate final grades or
percentages, infer mastery, or generate feedback. For the full
prepared-review workflow and the relationship among rubrics, comment banks,
tag banks, notes, requirement checks, review targets, exports, and snapshots,
see [`prepared_review_workflow.md`](prepared_review_workflow.md).

Quillan stores shared rubric profiles at:

```text
shared/rubrics/<rubric_id>.json
```

Rubrics are Quillan-owned review materials under the active pds-core workspace.
They may contain optional `standard_ids` as durable pds-core references, but
Quillan does not create, import, edit, retire, reactivate, or otherwise manage
pds-core standards through rubric workflows.

Optional synthetic and NJ ELA starter rubrics live under
[`../examples/rubrics/`](../examples/rubrics/). They can be installed from
Review Student Work -> Manage Review Materials -> Starter Materials into `shared/rubrics/`; existing files are
skipped unless exact overwrite confirmation is provided. Starter rubrics are
examples or teacher-editable starting points only and are not official
curriculum or recommended grading policy. See
[`starter_materials.md`](starter_materials.md) and
[`nj_ela_starter_materials.md`](nj_ela_starter_materials.md).

## Version 1

Required top-level fields:

* `schema_version`: string, currently `"1"`;
* `module`: string, `"quillan"`;
* `record_type`: string, `"rubric"`;
* `rubric_id`: shared identifier, matching the filename stem;
* `title`: non-empty teacher-facing title;
* `description`: string;
* `scope`: `"shared"` for the MVP;
* `writing_types`: non-empty list of open strings;
* `criteria`: non-empty list of criterion records;
* `created_at`: timezone-aware ISO 8601 timestamp;
* `updated_at`: timezone-aware ISO 8601 timestamp;
* `module_details`: object.

Teacher-facing authoring menus call `writing_types` "writing assignment
types." Prompts explain comma-separated entry, lowercase values, and
underscores instead of spaces for multi-word values. The UI asks for labels
first, suggests stored IDs such as `rubric_id` and `criterion_id`, and explains
that labels can use spaces while IDs are short JSON names.

Example:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "rubric",
  "rubric_id": "general_constructed_response_4pt",
  "title": "General Constructed Response 4-Point Rubric",
  "description": "Reusable scoring profile for written constructed responses.",
  "scope": "shared",
  "writing_types": ["general", "constructed_response"],
  "criteria": [
    {
      "criterion_id": "reasoning_explanation",
      "label": "Reasoning / Explanation",
      "description": "Score how clearly the response explains its thinking.",
      "max_score": 4,
      "scale": "4_point",
      "standard_ids": [],
      "sort_order": 20,
      "levels": [
        {
          "score": 3,
          "label": "Clear explanation",
          "description": "The response explains its reasoning clearly.",
          "student_facing_feedback": "Your explanation is clear.",
          "teacher_note": "Use when reasoning is clear but not fully developed.",
          "sort_order": 30,
          "module_details": {}
        }
      ],
      "module_details": {}
    }
  ],
  "created_at": "2026-06-26T00:00:00+00:00",
  "updated_at": "2026-06-26T00:00:00+00:00",
  "module_details": {}
}
```

## Criteria

Required criterion fields:

* `criterion_id`: shared identifier, unique within the rubric;
* `label`: non-empty teacher-facing label;
* `max_score`: positive finite number;
* `scale`: non-empty string;
* `levels`: non-empty list of level records;
* `module_details`: object.

Optional criterion fields are `description`, `standard_ids`, and `sort_order`.
`standard_ids` are metadata references only; rubric workflows never mutate
pds-core standards files.
Teacher-facing authoring explains linked standards as optional pds-core
references and describes `sort_order` as display order.

## Levels

Required level fields:

* `score`: finite number greater than or equal to zero and no greater than the
  criterion `max_score`;
* `label`: non-empty teacher-facing label;
* `module_details`: object.

Optional level fields are `description`, `student_facing_feedback`,
`teacher_note`, and `sort_order`. Level feedback is metadata in this version.
Selecting a level does not automatically create a comment or feedback export
entry.

Duplicate level score values within one criterion are invalid.

## Assignment Linkage

Assignment configs store `rubric_id`. A valid rubric resolves at:

```text
shared/rubrics/<rubric_id>.json
```

Unresolved rubric IDs remain structurally valid assignment data. They cannot
power rubric-based review scoring until a matching valid shared rubric exists,
but teachers may still use custom criterion scoring.

## Review Scoring

Review-time rubric scoring snapshots selected values into the existing
`review.json` score record shape:

* `criterion_id`;
* `label`;
* `score`;
* `max_score`;
* `scale`;
* optional `teacher_note`;
* `updated_at`;
* `module_details`.

The score record is not a live rubric reference. Later edits to a rubric do not
retroactively change previously recorded review scores.
