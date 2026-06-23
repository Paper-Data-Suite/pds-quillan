# Quillan Data Contracts

Quillan stores structured evidence about student writing using local files.

These contracts describe the expected file formats for standards profiles,
shared comment banks, assignments, submissions, teacher review, requirements
checks, feedback exports, and reports.

Standards profiles, assignment configurations, the legacy text-oriented
submission metadata shape, and the reviewable-evidence submission manifest
have implemented Python validation support. New-manifest writing and assembly
from caller-provided evidence metadata are implemented; evidence discovery,
merging, and state-changing review workflows are not. The writing-response
payload contract is implemented and used by printable PDF generation.
Requirements, teacher-review records, feedback exports, and reporting records
remain contracts for teacher-controlled workflows that are not yet
implemented end to end.

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

## Standards Profile

A standards profile is a teacher- or department-defined collection of
instructional targets and reusable review language. Profiles can be reused
across assignments to make teacher review, evidence organization, and
reporting more consistent.

A profile describes the review vocabulary available to a teacher. It does not
discover standards, inspect writing automatically, determine whether a
standard was met, generate authoritative feedback, or calculate a score.

Suggested Paper Data Suite path:

```text
shared/standards/<profile_id>.json
```

Standalone Quillan MVP path:

```text
quillan_data/standards/<profile_id>.json
```

Required top-level fields:

* `profile_id`
* `subject`
* `course`
* `standards`

Each standard requires:

* `code`
* `short_name`
* `description`
* `comments`

A standard is an instructional target or teacher-defined evaluation category.
It may represent a published standard, a course skill, a local performance
expectation, or a writing criterion used in another subject. Standard `code`
values must be unique within a standards profile.

The `comments` field is a list and may be empty when a teacher has not defined
reusable comments for that standard. A standard with no comments is available
for alignment and reporting only until teacher-review comments are added.

Each comment requires:

* `comment_id`
* `label`
* `polarity`

A comment is reusable teacher-approved language connected to a standard. It
supports consistent teacher tagging and feedback, but its presence in a
profile is not a judgment about any student work. Each `comment_id` must be
unique within its standard. The same `comment_id` may be reused under a
different standard; records that refer to a comment use both `standard_code`
and `comment_id` to identify it.

Allowed polarity values:

* `positive`
* `developing`
* `negative`

Polarity organizes teacher observations as strengths, developing skills, or
problems. It has no numeric scoring semantics and does not determine a grade.

Optional comment fields:

* `severity_default`
* `feedback_template`
* `subskills`
* `hotwords`

`severity_default`, when present, is a non-negative integer. It is a suggested
organizational default for a teacher-entered observation, not a score.
`feedback_template` is optional teacher-approved wording.

Subskills are smaller teacher-defined components of a standard or comment,
such as `claim`, `reasoning`, `evidence_integration`, `imagery`, or
`line_breaks`. Hotwords are teacher-defined text cues, such as `because`,
`however`, or `this shows`, that may help a teacher search for or organize
evidence. Both fields are optional lists of non-empty strings, and either list
may be empty.

Hotwords and subskills are support metadata only. A hotword match is not proof
that a standard was met or missed, and neither field defines an automated
detection, feedback, grading, or scoring rule. Scores and final judgments
remain teacher decisions based on teacher-reviewed evidence.

Example:

```json
{
  "profile_id": "english_12_njsls_synthetic",
  "subject": "English Language Arts",
  "course": "English 12",
  "standards": [
    {
      "code": "W.AW.11-12.1",
      "short_name": "Argument Writing",
      "description": "Write arguments to support claims using valid reasoning and relevant and sufficient evidence.",
      "comments": [
        {
          "comment_id": "clear_claim",
          "label": "Clear claim",
          "polarity": "positive",
          "subskills": ["claim"],
          "hotwords": ["claim", "thesis", "argues"]
        },
        {
          "comment_id": "evidence_needs_explanation",
          "label": "Evidence needs more explanation",
          "polarity": "developing",
          "severity_default": 2,
          "feedback_template": "The evidence is relevant, but the explanation needs to show more clearly how it supports the claim.",
          "subskills": ["reasoning", "evidence_explanation"],
          "hotwords": ["quote", "example", "this shows"]
        },
        {
          "comment_id": "unsupported_claim",
          "label": "Unsupported claim",
          "polarity": "negative"
        }
      ]
    }
  ]
}
```

## Shared Comment Bank

A shared comment bank is reusable teacher-authored source data stored at:

```text
shared/comment_banks/<bank_id>.json
```

It organizes comments with writing types, categories, subcategories,
standards and criterion references, polarity, severity defaults, search
metadata, and student-facing controls. Banks are not student records, do not
grade work, and do not generate feedback by themselves.

Future assignments may optionally activate banks through
`comment_bank_ids`. Direct shared-bank selection copies the chosen language into
`review.json.comments` with `source: "comment_bank"`, `bank_id`, and
`comment_id`. Because comment IDs are unique only within a bank, the pair
preserves source provenance. The copied label and text make the student review
a stable snapshot rather than a live reference. The complete version `1`
shape and validation rules are defined in
[`comment_bank_contract.md`](comment_bank_contract.md). Runtime validation,
assignment activation, and selection are not implemented.

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
  "standards_profile_id": "english_12_njsls_synthetic",
  "tagging_mode": "focus",
  "focus_standards": [
    "W.AW.11-12.1",
    "W.WP.11-12.4"
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
names are printed for handling but are not included in the payload. QR
extraction from later scans, scan routing, and OCR remain unimplemented. The
printable page structure, identity fields, writing area, and output location
are defined in
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

## Tag Record (Historical Design)

This section preserves the earlier separate-file design for historical
context. It is not an active v0.7 contract. Canonical tag records are items in
the `tags` array of `review.json`, with their current shape defined in
[`review_record_contract.md`](review_record_contract.md). Implementations must
not create or mirror active tag data in `tags.json`.

Historical suggested path (not active in v0.7):

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/tags.json
```

Required fields:

* `tag_id`
* `submission_id`
* `student_id`
* `class_id`
* `assignment_id`
* `location`
* `standard_code`
* `comment_id`
* `label`
* `polarity`
* `created_at`

Optional fields:

* `severity`
* `teacher_note`

Allowed MVP polarity values:

* `positive`
* `developing`
* `negative`

Allowed MVP location keys:

* `paragraph`
* `sentence`
* `page`
* `stanza`
* `line`
* `section`
* `scene`
* `whole_submission`

Example:

```json
[
  {
    "tag_id": "tag_0001",
    "submission_id": "sub_0001_villainy_final_essay_synthetic",
    "student_id": "stu_0001",
    "class_id": "english12_period3_synthetic",
    "assignment_id": "villainy_final_essay_synthetic",
    "location": {
      "paragraph": 2
    },
    "standard_code": "W.AW.11-12.1",
    "comment_id": "evidence_needs_explanation",
    "label": "Evidence needs more explanation",
    "polarity": "developing",
    "severity": 2,
    "teacher_note": "The example is relevant, but the student does not explain how it proves the claim.",
    "created_at": "2026-06-07T12:00:00"
  }
]
```

## Score Record (Historical Design)

This section preserves the earlier aggregate score-file design for historical
context. It is not an active v0.7 contract. Canonical criterion score records
are items in the `scores` array of `review.json`. Scores remain
teacher-entered or teacher-confirmed decisions and are never automatically
generated or determined by tags or other records.

Historical suggested path (not active in v0.7):

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/scores.json
```

Example:

```json
{
  "submission_id": "sub_0001_villainy_final_essay_synthetic",
  "student_id": "stu_0001",
  "assignment_id": "villainy_final_essay_synthetic",
  "rubric_id": "argument_essay_4pt_synthetic",
  "rubric_scores": {
    "claim": 3,
    "evidence": 2,
    "reasoning": 2,
    "organization": 3,
    "language": 3
  },
  "overall_score": 13,
  "max_score": 20,
  "teacher_summary": "The essay has a clear central claim and relevant evidence, but several body paragraphs need stronger explanation."
}
```

## Feedback File (Derived Export)

A future feedback file may store exported student-readable teacher
communication. It may draw on
teacher-reviewed tags, notes, score records, requirements checks, and
teacher-approved standards profile comments. Any future drafting or formatting
support must remain teacher-reviewed and teacher-controlled.

Unlike the historical `tags.json` and `scores.json` concepts, `feedback.md`
may remain a derived export path. It is not the canonical review record and
must not replace `review.json`.

Reserved export path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/feedback.md
```

Example:

```markdown
# Feedback — Villainy Final Essay

## Strengths

- Your essay has a clear central claim.
- You chose relevant evidence from the texts and films.

## Areas for Growth

- Some evidence needs more explanation.
- Several comparisons would be stronger if you explained the moral significance of each example.

## Teacher Summary

The essay has a clear central claim and relevant evidence, but several body paragraphs need stronger explanation.
```

## Standards Summary Report

A standards summary aggregates teacher-reviewed tag data by standard. It is a
derived report rather than independent evidence and should remain traceable to
its underlying review records.

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/reports/standards_summary.csv
```

Required MVP columns:

```text
assignment_id,class_id,standard_code,positive_tags,developing_tags,negative_tags,most_common_positive,most_common_developing,most_common_negative
```

Example row:

```csv
assignment_id,class_id,standard_code,positive_tags,developing_tags,negative_tags,most_common_positive,most_common_developing,most_common_negative
villainy_final_essay_synthetic,english12_period3_synthetic,W.AW.11-12.1,12,18,6,clear_claim,evidence_needs_explanation,unsupported_claim
```

## Class Summary Report

A class summary aggregates teacher-reviewed submission-level results. It is a
derived report for review and instructional planning, not a replacement for
reading student work or consulting the underlying records.

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/reports/class_summary.csv
```

Required MVP columns:

```text
assignment_id,class_id,student_id,requirements_status,overall_score,max_score,positive_tags,developing_tags,negative_tags
```

Example row:

```csv
assignment_id,class_id,student_id,requirements_status,overall_score,max_score,positive_tags,developing_tags,negative_tags
villainy_final_essay_synthetic,english12_period3_synthetic,stu_0001,partially_met,13,20,4,5,1
```

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
