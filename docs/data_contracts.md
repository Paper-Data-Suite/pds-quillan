# Quillan Data Contracts

Quillan stores structured evidence about student writing using local files.

These contracts describe the expected file formats for standards profiles,
legacy shared comment banks, shared tag banks, assignments, submissions,
teacher review, reusable Focus Standard comments, requirements checks,
feedback exports, assignment-level reports, and reports.

Some contracts describe currently implemented runtime behavior. Others define
target v0.8.6 standards-based contract shapes that may precede full runtime
implementation. When a contract is a target contract, the relevant document
states that status explicitly.

Standards profiles, assignment configurations, the legacy text-oriented
submission metadata shape, legacy comment banks, tag banks, review records, and
the reviewable-evidence submission manifest have implemented Python validation
support. Routed-evidence discovery and manifest assembly, explicit
teacher-controlled review updates, reusable-comment selection, reusable-tag
selection, and student, class, and standards exports are implemented through
direct CLI commands, guided menus, and Python APIs. The writing-response payload
contract is implemented and used by printable PDF generation. Target v0.8.6
standards-based contracts for assignments, review records, reusable Focus
Standard comments, student feedback exports, and assignment-level reporting may
not yet have matching runtime validators or workflows.

For the expected workspace layout and file lifecycle of these records, see
[`workspace_lifecycle.md`](workspace_lifecycle.md).

For the subject-agnostic prepared-review workflow, including the differences
among reusable materials, source evidence, review artifacts, exports, snapshot
behavior, and starter-material boundaries, see
[`prepared_review_workflow.md`](prepared_review_workflow.md).

For the teacher-controlled relationship among evidence, review artifacts,
scores, feedback, and reports, see
[`teacher_review_model.md`](teacher_review_model.md).

For the target v0.8.6 standards-based `assignment.json` schema, including
Focus Standards, review-unit configuration, rating scales, student-facing
prompts, minimum requirements, and minimum-requirement policy, see
[`assignment_contract.md`](assignment_contract.md).

For the target v0.8.6 standards-based `review.json` schema, including minimum
requirement checks, review units, review-unit Focus Standard observations,
overall Focus Standard ratings, feedback choices, export metadata, paths,
timestamps, and mutation policy, see
[`review_record_contract.md`](review_record_contract.md).

For the target v0.8.6 reusable Focus Standard comment contract stored at
`shared/focus_standard_comments/<comment_set_id>.json`, including lookup by
standard, writing type, rating value, purpose, active status, student-facing
status, source provenance, usage metadata, privacy rules, and snapshot behavior,
see [`focus_standard_comment_contract.md`](focus_standard_comment_contract.md).

For the target v0.8.6 student feedback export contract, including PDF-first
student-facing feedback, optional Markdown companion output, Focus
Standard-organized ratings, optional review-unit observations, optional
rationales, teacher-selected comments, minimum-requirement return feedback,
export metadata, stale-export detection, privacy rules, and runtime-status
boundaries, see [`feedback_export_contract.md`](feedback_export_contract.md).

For the target v0.8.6 assignment-level reporting contract, including
assignment-local class summaries, assignment-local Focus Standard summaries,
assignment results manifests, report metadata, stale-report detection,
assignment-local reporting boundaries, and future Paper Data Suite reporting
handoff boundaries, see
[`assignment_reporting_contract.md`](assignment_reporting_contract.md).

For legacy reusable teacher-authored feedback language stored at
`shared/comment_banks/<bank_id>.json`, including categories, writing-type
filters, standards and criterion links, and future assignment activation, see
[`comment_bank_contract.md`](comment_bank_contract.md).

For reusable teacher-authored tag observations stored at
`shared/tag_banks/<tag_bank_id>.json`, including categories, writing-type
filters, optional standards references, optional criterion metadata, and
review-time snapshot behavior, see
[`tag_bank_contract.md`](tag_bank_contract.md).

For reusable teacher-authored rubric / scoring profile records stored at
`shared/rubrics/<rubric_id>.json`, including criteria, score levels,
assignment linkage, and review-time score snapshots, see
[`rubric_contract.md`](rubric_contract.md).

For optional synthetic starter review materials that can be previewed,
validated, and installed into `shared/comment_banks/`, `shared/tag_banks/`, and
`shared/rubrics/`, see [`starter_materials.md`](starter_materials.md). Starter
installation is limited to those review-material folders and does not create
assignments, rosters, scans, submissions, review records, exports, reusable
Focus Standard comment sets, or pds-core standards.

For the required structure and human-readable elements of a printable
writing-response page, see
[`printable_response_template.md`](printable_response_template.md).

All examples must use synthetic data only. No real student names, writing,
rosters, scores, or personally identifiable student information should be
committed to the repository. ELA starter files are examples of one
subject-specific starter pack. They do not make Quillan's data contracts
ELA-specific, and ordinary examples should remain synthetic unless they are
explicitly starter-material content.

## Design Principles

Quillan data should be:

* local-first;
* human-readable where practical;
* structured enough for validation and reporting;
* subject-agnostic;
* compatible with shared Paper Data Suite data structures;
* auditable by a teacher.

## Standards References

Shared standards definitions, durable `standard_id` values, reusable standards
profiles, and profile validation are owned by `pds-core` and stored in the
workspace standards library.

Quillan stores only durable pds-core references:

* assignment `standards_profile_id` stores a pds-core `profile_id`;
* target v0.8.6 assignment `focus_standard_ids` stores pds-core `standard_id`
  values;
* target v0.8.6 review-unit Focus Standard observations store pds-core
  `standard_id` values;
* target v0.8.6 overall Focus Standard ratings store pds-core `standard_id`
  values;
* target v0.8.6 Focus Standard feedback records store pds-core `standard_id`
  values;
* target v0.8.6 reusable Focus Standard comments store pds-core `standard_id`
  values;
* target v0.8.6 student feedback exports derive standards display from
  assignment Focus Standards, review-record Focus Standard feedback, and
  pds-core standards definitions when available;
* target v0.8.6 assignment-level reports derive standards display from
  assignment Focus Standards, review-record overall Focus Standard ratings,
  optional review-unit Focus Standard observations, and pds-core standards
  definitions when available;
* legacy pre-v0.8.6 assignment `focus_standards` stores pds-core
  `standard_id` values;
* legacy review tags and selected reusable comments may store optional
  pds-core `standard_id` provenance; and
* reusable tag templates may store optional pds-core `standard_ids` as source
  metadata.

Quillan does not store or validate an independent standards-profile JSON shape.
Legacy Quillan standards-profile files were removed before production use as a
pre-1.0 breaking cleanup, with no production-data migration.

## Shared Comment Bank

A legacy shared comment bank is subject-agnostic, reusable teacher-authored
feedback language stored at:

```text
shared/comment_banks/<bank_id>.json
```

It organizes comments with writing types, categories, subcategories, standards
and criterion references, polarity, severity defaults, search metadata, and
student-facing controls. Banks are not student records, do not grade work, and
do not generate feedback by themselves.

Teachers can create, view, edit, extend, and validate shared banks from Review
Materials -> Comment Banks. The workflows write only confirmed, valid version
`1` bank files under `shared/comment_banks/`, never invalid partial files.
Existing banks are not overwritten unless the teacher explicitly confirms with
`OVERWRITE`.

Future assignments may optionally activate banks through `comment_bank_ids`.
The implemented direct shared-bank selection copies chosen language into
`review.json.comments` with `source: "comment_bank"`, `bank_id`, and
`comment_id`. Because comment IDs are unique only within a bank, the pair
preserves source provenance. The copied label and text make the student review
a stable snapshot rather than a live reference. The complete version `1` shape
and validation rules are defined in
[`comment_bank_contract.md`](comment_bank_contract.md). Runtime validation and
direct selection are implemented; assignment activation remains future work.

Comment banks are subject-agnostic and writing-type-aware teacher-authored
review materials. Optional `standard_ids` are pds-core durable references only;
Quillan does not create, import, edit, retire, reactivate, or authoritatively
validate standards through comment-bank workflows.

Under the target v0.8.6 standards-based review model, legacy generic comment
banks are superseded by reusable Focus Standard comments. Legacy comment-bank
workflows remain implementation history until the reusable Focus Standard
comment workflow is implemented and old generic review-material workflows are
removed, migrated, or preserved as compatibility tooling.

## Reusable Focus Standard Comments

A reusable Focus Standard comment set is target v0.8.6 teacher-authored
feedback source material stored at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

The complete target contract is defined in
[`focus_standard_comment_contract.md`](focus_standard_comment_contract.md).

Reusable Focus Standard comments are organized around pds-core `standard_id`
values and are intended for standards-based feedback composition. They are
designed to grow from actual teacher feedback work. A teacher may write a
custom comment while composing feedback under a Focus Standard and optionally
save that comment for reuse after removing student-specific details.

Reusable Focus Standard comments support lookup by:

* `standard_id`;
* `writing_type`;
* `rating_value`;
* `active`;
* `student_facing`;
* optional `grade_band`;
* optional `purpose`;
* optional `comment_set_id`; and
* optional usage metadata.

Reusable Focus Standard comments are source material, not canonical student
review data. When a teacher selects one for a student review, Quillan should
copy the text into schema version `2` `review.json` as a stable snapshot under:

```text
review.json.feedback.standard_feedback[].comments[]
```

Later edits to the reusable comment source must not silently alter prior
student review records or previously generated feedback exports.

The target v0.8.6 reusable Focus Standard comment model must not:

* select comments automatically;
* generate feedback automatically;
* score student work;
* infer standards performance;
* inspect student writing;
* use OCR;
* use AI to write comments; or
* replace teacher judgment.

At the time this target contract is introduced, runtime workflows may still
use legacy comment banks and schema version `1` `review.json.comments`. The
new reusable Focus Standard comment contract does not itself implement storage,
validation, lookup, menu workflows, export behavior, tests, or migration.

## Shared Tag Bank

A shared tag bank is subject-agnostic, reusable teacher-authored observation
source data stored at:

```text
shared/tag_banks/<tag_bank_id>.json
```

It organizes short teacher observations with writing types, categories,
polarity, optional standard references, optional rubric/scoring criterion
metadata, optional severity defaults, and optional teacher-note prompts. Tag
banks are not student records, grades, scores, mastery determinations,
generated feedback, automatic judgments, or automatic suggestions.

Teachers can create, view, edit, extend, and validate shared tag banks from
Review Student Work -> Manage Review Materials -> Tag Banks. The workflows
write only confirmed, valid version `1` bank files under `shared/tag_banks/`,
never invalid partial files. Existing banks are not overwritten unless the
teacher explicitly confirms with `OVERWRITE`.

Review Student Work -> Add structured tag can select a reusable tag by bank,
category, and tag template. The selected values are copied into
`review.json.tags` with `source: "tag_bank"`, `tag_bank_id`, and
`tag_template_id`, plus snapshotted label, polarity, optional severity,
optional `standard_id`, optional `criterion_id`, and optional teacher note.
Custom one-off tags remain available, and existing direct CLI add-tag behavior
remains compatible.

Tag banks are Quillan-owned review materials. Optional `standard_ids` are
pds-core durable references only; Quillan does not create, import, edit,
retire, reactivate, or authoritatively validate standards through tag-bank
workflows. Optional `criterion_ids` are rubric/scoring metadata only.

Under the target v0.8.6 standards-based review model, generic review tags are
superseded by review-unit Focus Standard observations. Legacy tag-bank
workflows remain implementation history until obsolete generic review-material
workflows are removed or replaced.

## Assignment

A Quillan assignment defines what the teacher asked students to write, which
class or classes are connected, which Focus Standards are active, what review
unit should structure teacher review, which rating scale should be used, and
what basic requirements apply.

The target v0.8.6 standards-based assignment contract is defined in
[`assignment_contract.md`](assignment_contract.md).

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The v0.8.6 assignment contract makes the assignment record the source of truth
for standards-based review setup. It supports:

* assignment identity;
* class identity;
* writing type;
* student-facing prompt;
* standards profile reference;
* Focus Standard IDs selected from that standards profile;
* assignment-defined review-unit type and teacher-facing labels;
* standards rating scale;
* basic requirements; and
* minimum-requirement return policy.

A v0.8.6 assignment record should use schema version `2` and include fields such
as:

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

Assignment configs store shared `pds-core` standards references. The
`standards_profile_id` should identify a profile in the workspace standards
library, and `focus_standard_ids` should contain shared `standard_id` values
rather than teacher-facing display codes. Quillan-specific review workflows,
feedback comments, rating scales, and writing-review scaffolding remain
module-owned; Quillan does not maintain an independent standards universe.

The old pre-v0.8.6 assignment fields `tagging_mode`, `focus_standards`, and
`rubric_id` are superseded by the standards-based assignment shape. The old
`tagging_mode` field belongs to the tag-centered workflow. The old `rubric_id`
field belongs to the generic rubric/scoring-profile workflow. The old
`focus_standards` field is superseded by the clearer canonical field name
`focus_standard_ids`.

Because Quillan is still pre-pilot and no production classroom data is expected
to depend on the old assignment contract, v0.8.6 may treat the schema version
`2` assignment shape as a breaking cleanup with no production-data migration.
Runtime assignment loading and discovery reject old assignment records as
legacy configs rather than listing them as valid active assignments.
Later implementation work must decide whether old assignment records are
rejected with clear guidance, read as legacy records, migrated by a helper, or
temporarily supported by compatibility code.

## Submission Manifest

A Quillan submission manifest is a local, teacher-controlled evidence record
for one student and one assignment. It connects class, assignment, and student
identity to routed evidence, retained-source provenance, and explicit
submission-management state. Routed evidence alone does not establish that a
submission is complete, reviewed, scored, tagged, or ready for feedback.

The canonical location is:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

This section defines draft schema version `1`. The distinct
`quillan.submission_manifest` module loads and validates this contract, and
`quillan.submission_manifest_paths` computes its canonical active path and
safely writes a caller-provided manifest. Writes validate before filesystem
changes, create missing parent directories, and refuse overwrites by default.
`quillan.submission_assembly` can build and write a new manifest from
caller-provided routed evidence metadata. It automatically selects only
unambiguous pages, leaves duplicate pages unselected, represents expected
missing pages, and preserves complete retained-source provenance.
The existing `quillan.submissions` loader remains responsible for an earlier
text-oriented metadata shape. The assembly API does not discover scan-folder
evidence, merge with an existing manifest, or update submission-management
state.

The active path is currently a Quillan-owned artifact contract rather than a
`pds-core` route. Inactive-preservation tooling such as `pds-sunset` may later
consume or preserve it without owning Quillan's active layout.

### Top-Level Structure

Every version `1` manifest contains:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "submission_manifest",
  "class_id": "english12_p3_synthetic",
  "assignment_id": "essay_01_synthetic",
  "student_id": "00107",
  "expected_pages": null,
  "submission_state": "unreviewed",
  "pages": [],
  "created_at": "2026-06-20T00:00:00+00:00",
  "updated_at": "2026-06-20T00:00:00+00:00",
  "module_details": {}
}
```

Field requirements are:

* `schema_version`: the string `"1"`;
* `module`: the string `"quillan"`;
* `record_type`: the string `"submission_manifest"`;
* `class_id`, `assignment_id`, and `student_id`: the routed identity;
* `expected_pages`: `null` when unknown, otherwise a positive integer;
* `submission_state`: one of the values below;
* `pages`: an array of structured page entries;
* `created_at` and `updated_at`: timezone-aware ISO 8601 strings; and
* `module_details`: an object reserved for compatible Quillan extensions.

Initial `submission_state` values are:

* `unreviewed`: evidence exists or may exist, but teacher review has not begun;
* `in_progress`: the teacher has started reviewing the submission;
* `needs_rescan`: the teacher has decided that the submission or at least one
  page requires correction or another scan; and
* `reviewed`: the teacher has completed review at the submission-management
  level.

Submission state is an explicit workflow record. It must not be inferred from
the number of evidence files and is not a grade, rubric result, feedback
status, tag status, or automatic judgment.

### Page Entries

Each item in `pages` contains:

```json
{
  "page_number": 1,
  "page_state": "present",
  "selected_evidence_id": null,
  "evidence": []
}
```

`page_number` is a positive integer and is unique within the manifest.
`selected_evidence_id` is either `null` or the ID of an evidence candidate in
the same page entry. It remains nullable so ambiguous duplicate evidence can
wait for a teacher decision. A non-null selection does not delete or replace
the other candidates. When it is non-null, the referenced candidate has the
`selected` role and no other candidate on that page does. When it is `null`,
no candidate on that page has the `selected` role.

Initial `page_state` values are:

* `present`: at least one evidence candidate exists and no special problem is
  marked;
* `missing`: an expected page currently has no routed evidence;
* `duplicate`: multiple candidates represent the same logical page;
* `needs_rescan`: the teacher has marked the page for correction or rescan;
  and
* `excluded`: the teacher has intentionally removed the page from the active
  review set while preserving its evidence.

Page state records evidence-management status only. Known pages may be listed
with an empty `evidence` array, including missing pages.

Teacher-facing page management may change a selected student's page state to
`excluded`, restore an excluded page to `present`, `missing`, or `duplicate`
based on preserved evidence, or mark a page `needs_rescan`. These updates are
manifest-only: routed evidence files and review records are preserved. Restore
selects a single evidence candidate only when there is exactly one candidate;
multiple candidates remain duplicate/unselected to avoid choosing the wrong
evidence.

When excluding a page, Quillan records each evidence candidate's prior
`evidence_role` and `evidence_state` in that candidate's `module_details`
before setting the active fields to `excluded`. Restoring an excluded page uses
that preserved state when available, so prior candidate, replacement, damaged,
or needs-rescan evidence-management information is not silently erased.

### Evidence Candidates

A page may have zero, one, or many evidence candidates. Every candidate
contains:

* `evidence_id`: a stable string unique within the manifest;
* `routed_evidence_path`: a workspace-relative path to the routed artifact;
* `evidence_role`: one of the role values below;
* `evidence_state`: one of the state values below;
* `duplicate_number`: `null` when not assigned, otherwise a positive integer;
* `created_at`: a timezone-aware ISO 8601 association timestamp;
* `retained_source`: retained-source provenance, or `null` when unavailable;
  and
* `module_details`: an object reserved for compatible Quillan extensions.

Initial `evidence_role` values are:

* `candidate`: available but not explicitly selected;
* `selected`: currently selected as the review copy for its page;
* `replacement`: a rescan or replacement candidate; and
* `excluded`: preserved but intentionally outside the active review set.

Initial `evidence_state` values are:

* `active`: usable unless the teacher later records otherwise;
* `needs_rescan`: should be replaced or supplemented;
* `damaged`: preserved but visibly or technically flawed; and
* `excluded`: preserved but outside active review.

When `retained_source` is present, it contains:

* `source_scan_id`: the retained source scan identifier;
* `source_filename`: the original source filename;
* `source_sha256`: the source SHA-256 digest;
* `retained_source_path`: the workspace-relative retained source path; and
* `source_page_number`: `null` when unavailable, otherwise a positive integer.

Evidence candidates are append-and-preserve records. Duplicate, replacement,
damaged, selected, or excluded candidates remain represented rather than
being silently overwritten or deleted.

The focused new-manifest assembly API accepts caller-provided `candidate`,
`replacement`, and `excluded` roles. Callers cannot provide `selected`;
assembly reserves that role for the single ordinary active evidence item on an
otherwise unambiguous page. An explicit candidate remains unselected, a lone
replacement or damaged/needs-rescan item produces a `needs_rescan` page, and a
page containing only excluded evidence produces an `excluded` page. Multiple
items remain a `duplicate` page unless all are excluded. No timestamp,
duplicate number, replacement role, or ordering is treated as teacher intent.
All evidence remains represented for a later teacher-selection workflow.

### Path and Timestamp Policy

Every stored artifact path is a workspace-relative string interpreted from
the resolved PDS workspace root. Manifest paths must not contain:

* an absolute or rooted path;
* a Windows drive-letter path;
* `.` or `..` path components;
* null bytes; or
* any resolution outside the workspace root.

These requirements apply to routed evidence and retained-source paths and are
enforced by `quillan.submission_manifest`.

All timestamps use ISO 8601 strings with a timezone offset, such as
`2026-06-20T00:00:00+00:00`. Naive timestamps are not part of this contract.

### Synthetic Example

A complete fake example with one present page, one missing page, one duplicate
page, and retained-source provenance is stored in
[`submission_manifest_synthetic.json`](../examples/submissions/submission_manifest_synthetic.json).

This contract does not define or implement scoring, tagging, requirements
checking, feedback, reports, OCR, handwriting recognition, AI suggestions, AI
scoring, AI feedback drafting, or automatic grading. Those concerns remain
separate from the evidence manifest.

Target v0.8.6 teacher-entered standards-based review data belongs in the
adjacent `review.json` defined by
[`review_record_contract.md`](review_record_contract.md). That target review
record stores minimum requirement checks, review units, review-unit Focus
Standard observations, overall Focus Standard ratings, feedback choices, export
metadata, and private notes.

Current runtime implementation may still support legacy schema version `1`
review records containing notes, tags, criterion scores, selected comments, and
requirement checks until the v0.8.6 implementation issues update validators and
workflows.

This manifest contract also does not implement evidence discovery, manifest
merging, file opening, review commands, or state updates.

## Submission Review Record

The target v0.8.6 standards-based teacher-review artifact is:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

The target schema version `2` review record stores teacher-entered or
teacher-confirmed standards-based review data for one student submission. It is
defined in [`review_record_contract.md`](review_record_contract.md).

A schema version `2` review record includes:

* identity fields;
* a reference to the adjacent `submission.json`;
* a reference to the associated `assignment.json`;
* explicit `review_state`;
* minimum requirement checks;
* minimum-requirement outcome;
* review units;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* Focus Standard feedback choices and comments;
* export metadata; and
* private teacher notes.

The adjacent `submission.json` remains the canonical evidence manifest.
`review.json` references that manifest and its evidence IDs without copying
routed evidence paths.

The associated `assignment.json` remains the source of truth for the
student-facing prompt, writing type, standards profile, Focus Standards,
review-unit labels, rating scale, basic requirements, and minimum-requirement
policy.

The old schema version `1` review shape centered on `notes`, `tags`, `scores`,
`comments`, and `requirement_checks` is legacy development history. Those
fields are superseded by the standards-based schema version `2` model. Current
runtime validators and tests may still use schema version `1` until later
implementation work updates them.

## Writing-Response Payload

Each Quillan writing-response page can be identified by a canonical PDS1
payload built through `pds-core`:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

The page number is a positive integer. Class, assignment, and student
identifiers follow shared `pds-core` identifier validation.

Printable response generation consumes validated `pds-core` roster records.
The shared roster fields are `class_id`, `student_id`, `last_name`,
`first_name`, and `period`. Roster student IDs remain strings, including
leading zeros, and visible names use the shared student display helper.
Quillan consumes these records for generation and provides teacher-facing
creation, viewing, staged editing, and validation through the Roster
Management menu.

Example:

```text
PDS1|module=quillan|class=english12_p4|aid=personal_narrative|sid=1001|page=1|doc=response
```

This contract identifies response documents only. The implemented printable
generator embeds the payload in a QR code on each response page and writes the
batch PDF to the assignment-local `templates/` directory. Student display
names are printed for handling but are not included in the payload. A direct
`route-scan` command can retain and route a selected source file when the
caller supplies an already-decoded canonical PDS1 payload. QR extraction from
raw scans, PDF splitting, batch scan intake, automatic raw-scan routing, and
OCR remain unimplemented. The printable page structure, identity fields,
writing area, and output location are defined in
[`printable_response_template.md`](printable_response_template.md).

## Requirements Check

A requirements check records structural or compliance information about basic
assignment conditions. Quillan requirement checks are teacher-entered booleans
generated from assignment `basic_requirements`. They remain separate from
writing-quality ratings and do not determine a score or feedback decision.

Target v0.8.6 storage location:

```text
review.json.minimum_requirement_checks
```

Legacy schema version `1` storage location:

```text
review.json.requirement_checks
```

Quillan does not count words, count paragraphs, parse writing, run OCR, use
AI, or infer whether a required element is present. The teacher records
whether each requirement was met.

Example item:

```json
{
  "requirement_check_id": "requirement_check_0001",
  "requirement_key": "required_elements:claim",
  "label": "Required element: claim",
  "expected": "claim",
  "met": true,
  "teacher_note": null,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

The target v0.8.6 shape is defined in
[`review_record_contract.md`](review_record_contract.md#minimum-requirement-checks).

## Review-Unit Observations and Overall Ratings

Target v0.8.6 review-unit Focus Standard observations and overall Focus
Standard ratings are stored in canonical `review.json`.

Target storage locations:

```text
review.json.review_units[].standard_observations
review.json.overall_standard_ratings
```

Review-unit observations record teacher judgments about a specific review unit
and a specific Focus Standard. Overall Focus Standard ratings record the
teacher's overall standards-performance judgment for the whole submission.

Both record types use Focus Standard IDs from the associated assignment's
`focus_standard_ids` and rating values from the assignment's `rating_scale`.

Quillan must not infer observations or ratings from student writing, OCR,
handwriting recognition, tags, comments, or AI.

The complete target shape is defined in
[`review_record_contract.md`](review_record_contract.md).

## Legacy Review Tags and Scores

Legacy schema version `1` tag and criterion-score records are stored only in
the `tags` and `scores` arrays of canonical `review.json`.

Target v0.8.6 review records do not use generic tags and criterion scores as
the central review model.

Legacy `tags` are superseded by review-unit Focus Standard observations.

Legacy `scores` are superseded by overall Focus Standard ratings.

Current runtime validators and tests may still support legacy `tags` and
`scores` until later v0.8.6 implementation work updates the review workflow.

## Feedback File (Derived Export)

A feedback file stores student-readable teacher communication derived from
matching canonical assignment, submission, and review records. It is not a
canonical review record and must not replace `review.json`.

The complete target v0.8.6 student feedback export contract is defined in
[`feedback_export_contract.md`](feedback_export_contract.md).

Target v0.8.6 feedback is organized around Focus Standards and generated from
schema version `2` feedback composition data.

Expected target export paths include:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

The v0.8.6 target model treats PDF feedback as the first-class student-facing
export. Markdown may remain available as an optional plain-text companion
artifact.

Target feedback exports may include:

* assignment identity;
* student display name or student ID;
* assignment prompt, when useful;
* teacher-selected overall Focus Standard ratings;
* teacher-selected overall rationales;
* teacher-selected review-unit observations;
* teacher-selected feedback comments;
* minimum-requirement return feedback, when work is returned without full
  review; and
* export timestamps and derived-artifact metadata.

Student-facing feedback comments may include teacher-written custom comments
and comments snapshotted from reusable Focus Standard comment sets. Exports must
use the copied text stored in `review.json`, not live reusable-comment lookups.

Feedback exports must exclude private notes and any review-unit observations,
rationales, ratings, or comments the teacher did not choose to include in
student-facing feedback.

Export files are derived artifacts. They must not replace `review.json`.
Replacing an existing feedback file requires explicit overwrite approval.

Export metadata should be stored under target schema version `2` review records
at:

```text
review.json.exports.feedback_pdf
review.json.exports.feedback_markdown
```

That metadata should record the generated path, format, generation timestamp,
and source `updated_at` timestamps used for stale-export detection.

Current runtime feedback export may still produce only Markdown from legacy
schema version `1` criterion scores and selected comments until later v0.8.6
implementation work updates export behavior.

## Assignment-Level Reporting

Quillan assignment-level reports are teacher-facing derived exports for one
class and one assignment. They help a teacher review assignment completion,
review progress, requirement outcomes, Focus Standard ratings, feedback export
status, and assignment-local warnings.

The complete target v0.8.6 assignment reporting contract is defined in
[`assignment_reporting_contract.md`](assignment_reporting_contract.md).

Quillan assignment-level reports may summarize:

* one Quillan class;
* one Quillan assignment;
* that assignment's roster, when available;
* that assignment's submission manifests;
* that assignment's schema version `2` review records;
* that assignment's feedback export status;
* that assignment's overall Focus Standard ratings; and
* that assignment's optional review-unit Focus Standard observation summaries.

Quillan assignment-level reports must not summarize:

* multiple assignments;
* multiple modules;
* marking periods;
* school years;
* longitudinal growth;
* gradebook averages;
* percentages;
* final grades;
* mastery determinations;
* cross-module evidence;
* student portfolios; or
* parent/admin dashboards.

Those broader reporting concerns belong to a future Paper Data Suite reporting
module.

Target assignment-level report paths include:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/class_summary.pdf
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.pdf
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/assignment_results_manifest.json
```

Assignment-level reports are derived artifacts. They must not replace
`assignment.json`, `submission.json`, `review.json`, student feedback exports,
roster records, or pds-core standards records.

Current runtime class and standards summary exports may still use legacy schema
version `1` review data until later v0.8.6 implementation work updates
reporting behavior.

## Class Summary Report

A class review summary is an assignment-level derived export for review
management and instructional planning. It is not a replacement for reading
student work or consulting the underlying records.

Canonical target paths:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/class_summary.pdf
```

Target v0.8.6 class summaries should use schema version `2` review records to
summarize review progress, requirement status, returned-without-full-review
outcomes, overall Focus Standard ratings, feedback/export status, and record
validity for one assignment.

Target class summaries may include:

* one row per rostered student, when a roster is available;
* unrostered submission warnings;
* missing submission indicators;
* submission state;
* review state;
* minimum-requirement status;
* returned-without-full-review status;
* feedback PDF status;
* feedback Markdown status;
* stale feedback indicators;
* review validity status;
* warning summaries; and
* overall Focus Standard ratings for the assignment.

Target class summaries must not calculate percentages, grades, weighted scores,
automatic mastery results, rubric levels, cross-assignment summaries, or
cross-module summaries.

The export reads canonical assignment, submission, and review records. It does
not read student writing, feedback contents, evidence files, retained scans,
standards profiles, or reusable comment sources except where the assignment
reporting contract explicitly defines a safe read-only reference. It must not
mutate canonical records.

Current runtime class summary export may still report legacy schema version `1`
counts, criterion-score totals, comment counts, tag counts, note counts, and
feedback Markdown existence until later v0.8.6 implementation work updates
reporting behavior.

## Standards Summary Report

The standards summary is an assignment-level derived export from valid matching
`assignment.json`, `submission.json`, and `review.json` records. It remains
traceable to teacher-entered review artifacts and is not independent evidence.

Canonical target paths:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.pdf
```

Target v0.8.6 standards summaries should aggregate standards-based review data
from schema version `2` review records for one assignment, including overall
Focus Standard ratings and, where useful, optional review-unit Focus Standard
observation summaries.

The target standards summary should support assignment-local instructional
questions such as:

* which Focus Standards students are meeting, approaching, or still developing
  on this assignment;
* which Focus Standards have the most missing ratings on this assignment;
* which Focus Standards have many students returned without full review;
* which Focus Standards have student feedback exported; and
* which assignment-local review records need teacher attention.

Target standards summaries must not answer broader reporting questions such as:

* which assignments provide evidence for a standard across the course;
* how a student's standards performance changes over time;
* how Quillan evidence combines with ScoreForm evidence;
* what grade a student should receive;
* what mastery level a student has reached across assignments; or
* how a class is progressing across a marking period.

Those broader reports belong to a future Paper Data Suite reporting module.

Target reports must not infer mastery, calculate grades, inspect evidence, read
student writing, use AI, or mutate canonical records.

Current runtime standards summary export may still aggregate legacy schema
version `1` tags and selected comments with `standard_id` values until later
v0.8.6 implementation work updates reporting behavior.

## Assignment Results Manifest

An assignment results manifest is a machine-readable, assignment-local handoff
artifact for one Quillan assignment.

Suggested target path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/assignment_results_manifest.json
```

The complete target shape is defined in
[`assignment_reporting_contract.md`](assignment_reporting_contract.md#assignment-results-manifest).

The manifest may include:

* class ID;
* assignment ID;
* assignment path;
* standards profile ID;
* Focus Standard IDs;
* generated report paths;
* report generation timestamps;
* source timestamp summaries;
* student result summaries;
* feedback export paths and status;
* overall Focus Standard ratings and labels;
* returned-without-full-review status;
* validation or warning summaries; and
* module details.

The assignment results manifest is intended to support future Paper Data Suite
reporting ingestion without making Quillan responsible for broader reporting.

The manifest must not include:

* full student writing;
* scanned work contents;
* routed evidence contents;
* retained-source scan contents;
* private teacher notes;
* full feedback text;
* parent or guardian data;
* accommodations;
* health or disability information;
* discipline information;
* attendance information;
* grades;
* percentages;
* mastery calculations;
* cross-assignment calculations; or
* cross-module calculations.

The manifest is a derived artifact. It must not replace `assignment.json`,
`submission.json`, `review.json`, student feedback exports, rosters, or
pds-core standards records.

## Synthetic Data Policy

The repository must not include real student data.

Committed examples should use:

* fake student IDs;
* fake class IDs;
* synthetic writing samples;
* synthetic scores;
* synthetic teacher comments.

Do not commit:

* real student names;
* real rosters;
* real student writing;
* real grades;
* real parent contact information;
* real scanned student work.

Reusable comments and reporting examples must not include student-identifying
details, private family information, accommodations, health information,
disability information, discipline information, attendance information, or
exact copied student writing unless the content is explicitly synthetic example
material.

## Submission Readiness

`submission.json` is the canonical review-ready submission record. Routed scan
files alone are evidence, not a submission record. Menu workflows present this
as an "assembled submission" or "submission record" to teachers, while the
filename remains available as technical detail. Existing submission files are
not overwritten by normal assembly; review records remain separate and are not
rewritten by scan routing or assembly.
