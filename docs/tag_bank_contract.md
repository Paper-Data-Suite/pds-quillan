# Quillan Tag Bank Contract

Status: legacy/inactive compatibility documentation. Generic tag banks are not
the active v0.8.6 observation workflow. Active observations are review-unit
Focus Standard observations stored in schema version `2` `review.json`.

A tag bank is reusable, teacher-authored source data for selecting short
structured review observations during student-work review.

Tag banks are stored under the active pds-core workspace root:

```text
shared/tag_banks/<tag_bank_id>.json
```

Tags are review aids. They are not grades, scores, mastery determinations,
generated feedback, student-facing feedback by default, automatic judgments,
or automatic tag suggestions.

Tag banks are subject-agnostic and can support teacher observations for
written work across disciplines. For the full prepared-review workflow and
the relationship among tag banks, comment banks, rubrics, notes, requirement
checks, review targets, exports, and snapshots, see
[`prepared_review_workflow.md`](prepared_review_workflow.md).

Quillan owns tag-bank review-material files. Optional `standard_ids` are
pds-core durable standard references only; Quillan does not create, import,
edit, retire, reactivate, or otherwise manage standards through tag banks.
Optional `criterion_ids` are rubric/scoring metadata only.

## Schema Version 1

Every version `1` tag bank contains:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "tag_bank",
  "tag_bank_id": "general_written_response_tags",
  "title": "General Written Response Tags",
  "description": "Reusable teacher observations for written responses.",
  "scope": "shared",
  "writing_types": ["general", "constructed_response"],
  "categories": [],
  "tags": [],
  "created_at": "2026-06-26T00:00:00+00:00",
  "updated_at": "2026-06-26T00:00:00+00:00",
  "module_details": {}
}
```

For the MVP, `scope` is `shared`. `writing_types` are open strings and must be
non-empty. `tag_bank_id` must pass shared identifier validation and match the
filename stem.

`categories` and `tags` must both be non-empty before a bank is written.

## Categories

Each category requires `category_id` and `label`. Optional fields are
`description`, `sort_order`, and `module_details`.

`category_id` must pass shared identifier validation and be unique within the
bank. `label` must be non-empty. `sort_order`, when present, is an integer.

## Tag Templates

Each tag template requires `tag_template_id`, `label`, `category_id`,
`polarity`, and `module_details`.

Optional fields are `description`, `writing_types`, `standard_ids`,
`criterion_ids`, `severity_default`, `teacher_note_prompt`,
`student_facing_default`, `sort_order`, `created_at`, and `updated_at`.

Teacher-facing authoring menus describe these as optional tag details rather
than metadata. The UI asks for a tag label first, suggests `tag_template_id`
from that label, and explains that stored IDs use lowercase letters, numbers,
underscores, or hyphens with underscores for multi-word values. The UI uses
"writing assignment types" for `writing_types`.

`severity_default` is presented as optional priority/severity for concerns; it
is not a grade and does not affect scoring. `teacher_note_prompt` is presented
as a private note question shown during review, and the teacher's response is
stored as a private tag note. `student_facing_default` remains valid schema but
is not prompted for in teacher authoring until a visible student-facing runtime
workflow exists. `sort_order` is presented as optional display order.

`polarity` is one of `positive`, `developing`, `negative`, or `neutral`.
`category_id` must reference a category in the same bank. Template
`writing_types`, when present, must be a subset of the bank-level
`writing_types`.

## Runtime Behavior

Tag banks are created and edited from:

```text
Quillan -> Review Student Work -> Manage Review Materials -> Tag Banks
```

The workflow builds banks in memory, validates the complete bank before
writing, writes only valid files, atomically replaces existing files, and
requires exact `OVERWRITE` confirmation before replacing an existing bank.
Canceling creation does not create `shared/tag_banks/` or partial files.

Optional synthetic and NJ ELA starter tag banks live under
[`../examples/tag_banks/`](../examples/tag_banks/). They can be installed from
Review Student Work -> Manage Review Materials -> Starter Materials into `shared/tag_banks/`; existing files
are skipped unless exact overwrite confirmation is provided. See
[`starter_materials.md`](starter_materials.md) and
[`nj_ela_starter_materials.md`](nj_ela_starter_materials.md).

Review mode can select reusable tags by bank, category, and template. Selected
values are snapshotted into `review.json.tags` with `source: "tag_bank"`,
`tag_bank_id`, and `tag_template_id`, plus copied label, polarity, optional
severity, and optional metadata. Later edits to the source tag bank do not
rewrite prior review records.

Custom one-off tags remain available and existing direct CLI add-tag behavior
remains compatible.
