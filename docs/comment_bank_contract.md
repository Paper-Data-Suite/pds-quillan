# Quillan Shared Comment Bank Contract

Status: legacy/inactive compatibility documentation. Generic comment banks are
not the active v0.8.6 student-feedback composition workflow. Active feedback
composition uses `feedback.standard_feedback` and reusable Focus Standard
comments under `shared/focus_standard_comments/`.

## Purpose and Boundary

A comment bank is reusable, teacher-authored source data for selecting
feedback language across classes and assignments. The canonical shared
workspace-relative path is:

```text
shared/comment_banks/<bank_id>.json
```

For example:

```text
shared/comment_banks/general_writing.json
shared/comment_banks/argument_writing.json
shared/comment_banks/literary_analysis.json
```

Comment banks are local workspace artifacts. They are not student records,
submission evidence, review records, grades, or generated feedback. A bank
does not evaluate writing, imply standards mastery, or place a comment in a
student's review by itself.

This document defines comment bank schema version `1`. Runtime loading,
validation, direct student-facing selection, and teacher-facing creation and
editing through Review Student Work -> Manage Review Materials -> Comment
Banks are implemented. Assignment activation, automatic suggestions,
automatic feedback, and AI-generated comments are not.

Teachers can create, view, edit, extend, and validate shared banks from:

```text
Quillan -> Review Student Work -> Manage Review Materials -> Comment Banks
```

The authoring workflow writes only confirmed, valid banks under
`shared/comment_banks/<bank_id>.json`. It does not write invalid partial banks,
and it does not overwrite an existing bank unless the teacher explicitly types
`OVERWRITE`. Created banks are immediately available from Review Student Work
-> Select reusable comment because the menu uses the same schema and validation
as review-time loading.

Comment-bank authoring is subject-agnostic and writing-type-aware. Banks may
support essays, constructed responses, lab reports, reflections, research
papers, mathematical explanations, technical documentation, design rationale,
portfolio reflection, and other local written-work contexts.

For the full prepared-review workflow and the relationship among comment
banks, tag banks, rubrics, notes, requirement checks, review targets, exports,
and snapshots, see
[`prepared_review_workflow.md`](prepared_review_workflow.md).

Optional `standard_ids` are durable pds-core references only. Quillan stores
them as metadata but does not create, import, edit, retire, reactivate, or
authoritatively validate standards.

## Top-Level Structure

Every version `1` comment bank contains:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "comment_bank",
  "bank_id": "argument_writing",
  "title": "Argument Writing Comments",
  "description": "Reusable comments for claims, evidence, reasoning, organization, and style.",
  "scope": "shared",
  "writing_types": ["argument", "literary_analysis"],
  "categories": [
    {
      "category_id": "evidence",
      "label": "Evidence",
      "description": "Quotation choice, relevance, integration, and explanation.",
      "sort_order": 30,
      "module_details": {}
    }
  ],
  "comments": [
    {
      "comment_id": "evidence_needs_explanation",
      "label": "Evidence needs explanation",
      "text": "Your evidence is relevant, but explain more clearly how it supports your claim.",
      "category_id": "evidence",
      "subcategory": "analysis",
      "writing_types": ["argument", "literary_analysis"],
      "standard_ids": ["njsls-ela:W.AW.11-12.1"],
      "criterion_ids": ["evidence"],
      "polarity": "developing",
      "severity_default": 2,
      "include_in_feedback_default": true,
      "student_facing": true,
      "tags": ["evidence", "analysis", "quotation"],
      "hotwords": ["because", "shows", "suggests"],
      "teacher_note": "Use when the quotation is relevant but its explanation is thin.",
      "module_details": {}
    }
  ],
  "created_at": "2026-06-22T00:00:00+00:00",
  "updated_at": "2026-06-22T00:00:00+00:00",
  "module_details": {}
}
```

All top-level fields shown above are required.

* `schema_version` must be the string `"1"`.
* `module` must be the string `"quillan"`.
* `record_type` must be the string `"comment_bank"`.
* `bank_id` must be a valid shared `pds-core` identifier. It must match the
  filename stem at the canonical shared path.
* `title` must be a non-empty, teacher-readable string.
* `description` must be a string and may be empty.
* `scope` must be one of `shared`, `assignment_local`, `district`, or
  `system`. Schema version `1` defines all four values for forward
  compatibility, but `shared` is the supported MVP storage scope.
* `writing_types` must be an array of non-empty strings.
* `categories` must be an array of category records. Because every comment
  requires a category, a conforming non-empty bank will have categories.
* `comments` must be a non-empty array of comment records.
* `created_at` and `updated_at` must be timezone-aware ISO 8601 strings.
  `updated_at` must not precede `created_at`.
* `module_details` must be an object.

Fields not defined by this contract are not part of schema version `1`.
Compatible extensions belong in `module_details`; changes to required fields
or existing field meaning require a later schema version.

## Writing Types

Writing types are open, non-empty strings rather than a closed enum. This
allows Quillan to support new assignment forms without revising the schema.
Recommended values include:

* `argument`
* `literary_analysis`
* `informational`
* `narrative`
* `creative_writing`
* `journal`
* `reflection`
* `short_response`
* `research`
* `compare_contrast`
* `rhetorical_analysis`
* `poetry`
* `personal_narrative`
* `open_response`
* `general`

Lowercase snake case is recommended for stable filtering, but schema version
`1` validates only that each value is a non-empty string. Values are
case-sensitive. Duplicate exact values should be rejected.

Bank-level `writing_types` describes the bank's intended coverage. A
comment-level `writing_types` array narrows that coverage and therefore must
be a subset of the bank-level values. When the comment field is absent, the
comment inherits all bank-level writing types. The value `general` is an
ordinary writing-type label, not a wildcard.

Teacher-facing authoring menus call these values "writing assignment types."
Prompts explain comma-separated entry, lowercase values, and underscores
instead of spaces for multi-word values. The UI asks for labels first, suggests
stored IDs such as `bank_id`, `category_id`, and `comment_id`, and explains
that labels can use spaces while IDs are short JSON names.

## Category Records

Categories divide a bank into teacher-scannable sections and avoid one large
flat comment list. Each category requires:

* `category_id`;
* `label`.

Optional category fields are:

* `description`;
* `sort_order`; and
* `module_details`.

Example:

```json
{
  "category_id": "evidence",
  "label": "Evidence",
  "description": "Quotation choice, relevance, integration, and explanation.",
  "sort_order": 30,
  "module_details": {}
}
```

Category field rules are:

* `category_id` must be a valid shared identifier and unique within the bank.
* `label` must be a non-empty, teacher-readable string.
* `description`, when present, must be a string and may be empty.
* `sort_order`, when present, must be an integer. Consumers should sort by
  `sort_order` first and preserve file order as the stable tie-breaker.
* `module_details`, when present, must be an object.

Banks choose the categories useful to their own content; they are not
required to share one global category list. Useful starting values include
`claim`, `thesis`, `focus`, `evidence`, `analysis`, `organization`,
`development`, `style`, `voice`, `conventions`, `grammar`, `mechanics`,
`creativity`, `reflection`, `revision`, `process`, `strength`, `next_step`,
and `general`.

## Comment Records

Each comment is one stable, teacher-selectable unit of reusable language.
Required fields are:

* `comment_id`;
* `label`;
* `text`;
* `category_id`;
* `polarity`;
* `include_in_feedback_default`;
* `student_facing`; and
* `module_details`.

Optional fields are:

* `short_text`;
* `subcategory`;
* `writing_types`;
* `standard_ids`;
* `criterion_ids`;
* `severity_default`;
* `tags`;
* `hotwords`;
* `teacher_note`;
* `follow_up_prompt`;
* `revision_action`;
* `sort_order`;
* `created_at`; and
* `updated_at`.

Example:

```json
{
  "comment_id": "claim_is_clear",
  "label": "Clear claim",
  "short_text": "Clear claim.",
  "text": "Your central claim is clear and gives the response a strong direction.",
  "category_id": "claim",
  "subcategory": "strength",
  "writing_types": ["argument", "literary_analysis"],
  "standard_ids": ["njsls-ela:W.AW.11-12.1"],
  "criterion_ids": ["thesis"],
  "polarity": "positive",
  "severity_default": 0,
  "include_in_feedback_default": true,
  "student_facing": true,
  "tags": ["claim", "thesis", "focus"],
  "hotwords": ["claim", "argument", "position"],
  "teacher_note": "Use when the student has a clear controlling idea.",
  "module_details": {}
}
```

Comment field rules are:

* `comment_id` must be a valid shared identifier and unique within the bank.
  It is a stable source identifier and should not be renamed once selected
  into review records.
* `label` and `text` must be non-empty strings. `label` is concise,
  teacher-facing selection text; `text` is the full reusable language that
  the direct selection workflow can snapshot into a review.
* `short_text`, `subcategory`, `teacher_note`, `follow_up_prompt`, and
  `revision_action`, when present, must be non-empty strings.
* `category_id` must reference a category in the same bank.
* `writing_types`, when present, must be a non-empty array of non-empty
  strings, contain no duplicate exact values, and be a subset of the bank's
  `writing_types`.
* `standard_ids` and `criterion_ids`, when present, must be arrays of
  non-empty strings with no duplicate exact values. They are optional lookup
  metadata: the bank remains valid without an available standards or rubric
  profile, and their presence does not establish mastery or a score.
* `polarity` must be one of `positive`, `developing`, `negative`, or
  `neutral`.
* `severity_default`, when present, must be a non-negative integer. It is a
  triage and organization default, not a score.
  Teacher-facing authoring describes this as optional priority/severity for
  concerns; positive or neutral comments usually leave it blank.
* `include_in_feedback_default` must be a boolean. It is the initial
  preference used by the direct selection workflow, not an instruction to
  export the source comment automatically.
* `student_facing` must be a boolean. `false` marks language or guidance that
  is not appropriate to copy directly into student-facing feedback.
* `tags` and `hotwords`, when present, must be arrays of non-empty strings
  with no duplicate exact values. Tags support broad keyword filtering;
  hotwords support quick search terms and phrases.
* `sort_order`, when present, must be an integer. Consumers should sort by
  category order, then comment `sort_order`, and then preserve file order as
  a stable tie-breaker.
  Teacher-facing authoring describes this as display order.
* `created_at` and `updated_at`, when present, must be timezone-aware ISO 8601
  strings. When both are present, `updated_at` must not precede `created_at`.
* `module_details` must be an object.

## Assignment Activation

A future assignment contract may add an optional `comment_bank_ids` field:

```json
{
  "assignment_id": "villainy_essay",
  "writing_type": "argument",
  "comment_bank_ids": [
    "general_writing",
    "argument_writing",
    "literary_analysis"
  ]
}
```

Each item should be a valid, unique shared identifier resolving to
`shared/comment_banks/<bank_id>.json`.

For backward compatibility, `comment_bank_ids` should remain optional. A
future consumer may choose defaults based on `writing_type` when the field is
absent. When it is present, the assignment should activate only the listed
shared banks plus any future assignment-local supplemental bank.

This field is design guidance only in issue #109. The current assignment
validator does not accept or act on `comment_bank_ids`, and schema version
`1` does not define assignment-local merge or override behavior.

## Relationship to `review.json.comments`

The bank and the review record serve different purposes:

* a bank comment is reusable source data shared across reviews;
* a `review.json.comments` item is a teacher-selected snapshot associated
  with one student submission.

The direct selection operation copies the selected `label` and `text`,
set `source` to `"comment_bank"`, preserve the source `bank_id` and
`comment_id`, apply the teacher's `include_in_feedback` choice, and create a
new local `comment_record_id` and timestamp. A `comment_id` is unique only
within its bank, so `bank_id + comment_id` identifies the reusable source
comment. Copying display language is essential: provenance is not a live
reference, and later edits to a shared bank must not silently change an
existing student's review or exported feedback.

Source `standard_ids` and `criterion_ids` are filtering and alignment
metadata. Selection copies a sole standard automatically, stores an explicitly
requested source standard, and otherwise omits `standard_id`; it does not
treat either reference as a score or mastery decision.

The strict version `1` `review.json.comments` shape requires `bank_id` and
`comment_id` for `source: "comment_bank"`, along with snapshotted `label` and
`text`, `include_in_feedback`, `created_at`, and `module_details`. The
`bank_id` records provenance at `shared/comment_banks/<bank_id>.json`; review
validation does not load that file or perform selection.

Teacher-entered language uses `source: "custom"`. Reusable selected comments
come from Quillan comment banks with `source: "comment_bank"`; shared
standards definitions and profiles remain pds-core-owned.

## Selection and Search Expectations

Future tools should be able to filter or order bank comments by:

* active bank;
* assignment and comment writing type;
* category and subcategory;
* standard ID;
* criterion ID;
* polarity;
* default severity;
* tags and hotwords;
* student-facing status;
* feedback-inclusion default; and
* stable category and comment sort order.

These fields support fast teacher lookup. They do not authorize automatic
selection, automatic feedback, automatic standards detection, or scoring.

## Runtime Selection

```powershell
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
```

Optional `--standard`, `--include-in-feedback`, and
`--exclude-from-feedback` flags refine the selected snapshot. Include and
exclude are mutually exclusive. Only comments with `student_facing: true` are
selectable in this MVP; teacher-only language is rejected. The source bank,
submission manifest, routed evidence, and retained source scans are never
mutated. No feedback export is performed.

## Scope and Non-Goals

Schema version `1` and the first runtime workflow do not implement:

* comment bank editing, menus, search, or UI;
* mutation of comment-bank source files, `submission.json`, or evidence files;
* assignment-local merge or override behavior;
* guided feedback export from a comment-bank menu, email, LMS, or PDF export;
* reports or standard-mastery conclusions;
* automatic suggestions, standard detection, scoring, or grading;
* AI feedback or AI comment generation;
* district synchronization, cloud sharing, or system-bank distribution.

The repository example at
[`../examples/comment_banks/general_writing_synthetic.json`](../examples/comment_banks/general_writing_synthetic.json)
contains synthetic teacher language only and demonstrates the version `1`
shape.

Additional optional synthetic and NJ ELA starter comment banks live under
[`../examples/comment_banks/`](../examples/comment_banks/). They can be
installed from Review Student Work -> Manage Review Materials -> Starter Materials into
`shared/comment_banks/`; existing files are skipped unless exact overwrite
confirmation is provided. See [`starter_materials.md`](starter_materials.md)
and [`nj_ela_starter_materials.md`](nj_ela_starter_materials.md).
