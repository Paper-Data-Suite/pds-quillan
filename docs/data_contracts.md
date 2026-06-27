# Quillan Data Contracts

Quillan stores structured evidence about student writing using local files.

These contracts describe the expected file formats for standards profiles,
shared comment banks, shared tag banks, assignments, submissions, teacher
review, requirements checks, feedback exports, and reports.

Standards profiles, assignment configurations, the legacy text-oriented
submission metadata shape, comment banks, tag banks, review records, and the
reviewable-evidence submission manifest have implemented Python validation
support. Routed-evidence discovery and manifest assembly, explicit
teacher-controlled review updates, reusable-comment selection, reusable-tag
selection, and student, class, and standards exports are implemented through
direct CLI commands, guided menus, and Python APIs. The writing-response payload
contract is implemented and used by printable PDF generation.

For the expected workspace layout and file lifecycle of these records, see
[`workspace_lifecycle.md`](workspace_lifecycle.md).

For the teacher-controlled relationship among evidence, review artifacts,
scores, feedback, and reports, see
[`teacher_review_model.md`](teacher_review_model.md).

For the canonical v0.7 `review.json` schema, including notes, tags, scores,
comments, state, paths, timestamps, and mutation policy, see
[`review_record_contract.md`](review_record_contract.md).

For reusable teacher-authored feedback language stored at
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

For the required structure and human-readable elements of a printable
writing-response page, see
[`printable_response_template.md`](printable_response_template.md).

All examples must use synthetic data only. No real student names, writing, rosters, scores, or personally identifiable student information should be committed to the repository.

## Design Principles

Quillan data should be:

* local-first;
* human-readable where practical;
* structured enough for validation and reporting;
* subject-agnostic;
* compatible with shared Paper Data Suite data structures;
* auditable by a teacher.

## Standards References

Shared standards definitions, durable `standard_id` values, reusable standards profiles, and profile validation are owned by `pds-core` and stored in the workspace standards library.

Quillan stores only durable pds-core references:

* assignment `standards_profile_id` stores a pds-core `profile_id`;
* assignment `focus_standards` stores pds-core `standard_id` values;
* review tags and selected reusable comments may store optional pds-core `standard_id` provenance;
* reusable tag templates may store optional pds-core `standard_ids` as source metadata.

Quillan does not store or validate an independent standards-profile JSON shape. Legacy Quillan standards-profile files were removed before production use as a pre-1.0 breaking cleanup, with no production-data migration.

## Shared Comment Bank

A shared comment bank is reusable teacher-authored source data stored at:

```text
shared/comment_banks/<bank_id>.json
```

It organizes comments with writing types, categories, subcategories,
standards and criterion references, polarity, severity defaults, search
metadata, and student-facing controls. Banks are not student records, do not
grade work, and do not generate feedback by themselves.

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
a stable snapshot rather than a live reference. The complete version `1`
shape and validation rules are defined in
[`comment_bank_contract.md`](comment_bank_contract.md). Runtime validation and
direct selection are implemented; assignment activation remains future work.

Comment banks are subject-agnostic and writing-type-aware teacher-authored
review materials. Optional `standard_ids` are pds-core durable references only;
Quillan does not create, import, edit, retire, reactivate, or authoritatively
validate standards through comment-bank workflows.

## Shared Tag Bank

A shared tag bank is reusable teacher-authored source data stored at:

```text
shared/tag_banks/<tag_bank_id>.json
```

It organizes short teacher observations with writing types, categories,
polarity, optional standard references, optional rubric/scoring criterion
metadata, optional severity defaults, and optional teacher-note prompts. Tag
banks are not student records, grades, scores, mastery determinations,
generated feedback, automatic judgments, or automatic suggestions.

Teachers can create, view, edit, extend, and validate shared tag banks from
Review Materials -> Tag Banks. The workflows write only confirmed, valid
version `1` bank files under `shared/tag_banks/`, never invalid partial files.
Existing banks are not overwritten unless the teacher explicitly confirms with
`OVERWRITE`.

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

## Assignment

An assignment defines what the teacher asked students to write, which class or
classes are connected, which standards are active, and what basic requirements
apply.

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Required fields:

* `assignment_id`
* `title`
* `class_ids`
* `writing_type`
* `standards_profile_id`
* `tagging_mode`
* `focus_standards`
* `basic_requirements`
* `rubric_id`

Allowed MVP tagging modes:

* `focus`
* `focus_plus_past`
* `benchmark`
* `custom`

Example:

```json
{
  "assignment_id": "villainy_final_essay_synthetic",
  "title": "Villainy Final Essay",
  "class_ids": ["english12_period3_synthetic"],
  "writing_type": "literary argument essay",
  "standards_profile_id": "english12_2023_njsls",
  "tagging_mode": "focus",
  "focus_standards": [
    "nj_ela_2023_rl_cr_11_12_1",
    "nj_ela_2023_w_aw_11_12_1"
  ],
  "basic_requirements": {
    "paragraphs_min": 4,
    "paragraphs_max": 6,
    "word_count_min": 500,
    "required_elements": [
      "thesis",
      "textual evidence",
      "comparative reasoning"
    ]
  },
  "rubric_id": "argument_essay_4pt_synthetic"
}
```

Assignment configs store shared `pds-core` standards references. The
`standards_profile_id` should identify a profile in the workspace standards
library, and `focus_standards` should contain shared `standard_id` values
rather than teacher-facing display codes. Quillan-specific comments, hotwords,
feedback templates, review tags, and writing-review scaffolding remain
module-owned; Quillan does not maintain an independent standards universe.

The `rubric_id` field may resolve to a shared Quillan rubric profile at
`shared/rubrics/<rubric_id>.json`. Unresolved custom rubric IDs remain
structurally valid assignment data; they simply cannot power rubric-based menu
scoring until a matching valid shared rubric exists.

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
separate from the evidence manifest. Teacher-entered notes, tags, scores,
selected comments, and their distinct `review_state` belong in the adjacent
`review.json` defined by
[`review_record_contract.md`](review_record_contract.md). This manifest
contract also does not implement evidence discovery, manifest merging, file
opening, review commands, or state updates.

## Submission Review Record

The canonical active v0.7 teacher-review artifact is:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

It stores teacher-entered notes, tags, criterion scores, selected comments,
and a `review_state` that is independent of the evidence manifest's
`submission_state`. All required fields, nested record shapes, identifier and
reference rules, controlled vocabularies, timestamp policy,
workspace-relative path policy, and append-versus-update behavior are defined
in [`review_record_contract.md`](review_record_contract.md).

The adjacent `submission.json` remains the canonical evidence manifest.
`review.json` references that manifest and its evidence IDs without copying
routed evidence paths.

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
assignment conditions. It may be manually entered, teacher-confirmed, or
eventually computed for low-risk facts such as word count or paragraph count.
It remains separate from writing-quality scoring and does not determine a
score or feedback decision.

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/requirements.json
```

Requirement status values:

* `met`
* `partially_met`
* `not_met`
* `not_checked`

Example:

```json
{
  "submission_id": "sub_0001_villainy_final_essay_synthetic",
  "student_id": "stu_0001",
  "assignment_id": "villainy_final_essay_synthetic",
  "requirements_check": {
    "paragraph_count": {
      "expected_min": 4,
      "expected_max": 6,
      "actual": 5,
      "status": "met"
    },
    "word_count": {
      "expected_min": 500,
      "actual": 487,
      "status": "partially_met"
    },
    "required_elements": {
      "thesis": "met",
      "textual evidence": "met",
      "comparative reasoning": "partially_met"
    }
  }
}
```

## Review Tags and Scores

Active tag and criterion-score records are stored only in the `tags` and
`scores` arrays of canonical `review.json`. Their current shapes and validation
rules are defined in
[`review_record_contract.md`](review_record_contract.md). Quillan does not
create or mirror standalone review-artifact files for either record type.

## Feedback File (Derived Export)

The feedback file stores student-readable teacher communication derived from a
valid matching canonical `review.json`. It is not a canonical review record
and must not replace `review.json`.

Canonical export path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

The Markdown contains class, assignment, student, generation timestamp,
teacher-entered criterion scores, and snapshotted text for comments marked
`include_in_feedback: true`. Score and included-comment order follow
`review.json`.

The export excludes private notes, score `teacher_note` values, structured
tags, excluded comments, and comment source/provenance metadata. It does not
read source comment banks, mutate canonical records or evidence, change
`review_state`, or mark a review exported. Replacing an existing feedback file
requires explicit overwrite approval.

## Standards Summary Report

The standards summary is an implemented assignment-level derived export from
valid matching `submission.json` and `review.json` records. It remains
traceable to teacher-entered review artifacts and is not independent evidence.

Canonical path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

Stable columns:

```text
class_id,assignment_id,standard_id,student_count,tag_student_count,comment_student_count,tag_count,positive_tag_count,developing_tag_count,negative_tag_count,neutral_tag_count,selected_comment_count,included_comment_count,excluded_comment_count,review_count,missing_review_count,invalid_review_count,missing_submission_count,invalid_submission_count,identity_mismatch_count,source
```

Each row represents one `standard_id` referenced by a tag or selected
comment in a valid matching review, sorted by code. Tag counts use the four
validated polarities. Comment counts distinguish included and excluded
selected comments. Student counts are distinct per standard and source type.
Assignment-level record-status counts repeat on each row; a report with no
standards-linked artifacts contains only the header.

The export ignores tags and comments without `standard_id`, scores, and
notes. It map criteria to standards, infer
mastery, calculate grades, inspect evidence, read comment banks, use a roster,
or mutate canonical records.

## Class Summary Report

A class review summary is an implemented assignment-level derived export for
review management and instructional planning. It is not a replacement for
reading student work or consulting the underlying records.

Canonical path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
```

Stable columns:

```text
class_id,assignment_id,student_id,row_status,review_state,submission_state,score_count,total_score,total_max_score,included_comment_count,selected_comment_count,tag_count,note_count,feedback_export_exists,submission_manifest_path,review_record_path,feedback_export_path,error
```

Each immediate child directory under the assignment `submissions/` directory
produces one row, sorted by `student_id`. `row_status` is one of `ready`,
`missing_submission`, `invalid_submission`, `missing_review`, `invalid_review`,
or `identity_mismatch`. Individual bad records remain visible as status rows.
Ready rows contain counts and the arithmetic sums of teacher-entered `score`
and `max_score` values. These totals are not percentages, grades, weighted
scores, mastery results, or rubric levels.

The export reads only expected `submission.json` and `review.json` records and
checks whether each `exports/feedback.md` path exists. It does not read
feedback contents, evidence files, retained scans, standards profiles, or
comment banks, and it does not mutate canonical records. Roster-aware missing
student reporting remains future work.

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

## Submission Readiness

`submission.json` is the canonical review-ready submission record. Routed scan
files alone are evidence, not a submission record. Menu workflows present this
as an "assembled submission" or "submission record" to teachers, while the
filename remains available as technical detail. Existing submission files are
not overwritten by normal assembly; review records remain separate and are not
rewritten by scan routing or assembly.
