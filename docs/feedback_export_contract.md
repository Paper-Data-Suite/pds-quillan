# Quillan Student Feedback Export Contract

## Purpose and Boundary

This document defines the target v0.8.6 Quillan student feedback export contract.

A student feedback export is a derived student-facing artifact generated from canonical Quillan workspace records. It communicates teacher-entered review decisions to a student in a clear, standards-based format.

The export is organized around the assignment's **Focus Standards**.

The central review relationship remains:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Student feedback should answer:

```text
How did this student perform on the Focus Standards selected for this assignment, and what teacher-selected feedback should the student see next?
```

It should not answer:

```text
Which generic tags, generic comments, or generic rubric scores were attached to this student?
```

The feedback export is not the canonical review record. The canonical teacher review record remains:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

A generated feedback export must not replace, rewrite, or become the source of truth for:

* `assignment.json`;
* `submission.json`;
* `review.json`;
* roster records;
* standards library records;
* reusable Focus Standard comment sets; or
* routed evidence files.

## Status

This is the target student feedback export contract for the v0.8.6 standards-based workflow redesign.

Implementation, runtime validators, CLI commands, menu workflows, PDF generation, Markdown generation, tests, and migration helpers may not yet match this contract until later v0.8.6 implementation issues are completed.

At the time this contract is introduced, the current runtime may still export legacy schema version `1` Markdown feedback based on:

```text
review.json.scores
review.json.comments
```

That legacy export behavior is implementation history. It is not the target architecture for new standards-based review work.

## Design Context

This contract follows the standards-based redesign direction established in:

* [`standards_based_review_redesign.md`](standards_based_review_redesign.md)
* [`adr/0001-standards-based-review-model.md`](adr/0001-standards-based-review-model.md)
* [`assignment_contract.md`](assignment_contract.md)
* [`review_record_contract.md`](review_record_contract.md)
* [`focus_standard_comment_contract.md`](focus_standard_comment_contract.md)

The relevant target contracts define the following responsibilities:

* `assignment.json` defines the student-facing prompt, writing type, standards profile, Focus Standards, review-unit labels, rating scale, minimum requirements, and minimum-requirement policy.
* `submission.json` defines selected evidence, candidate evidence, duplicate evidence, missing evidence, source provenance, and submission-management state.
* `review.json` defines teacher-entered minimum requirement checks, minimum-requirement outcome, review units, review-unit Focus Standard observations, overall Focus Standard ratings, feedback composition choices, student-facing comments, private notes, and export metadata.
* reusable Focus Standard comment sets define reusable teacher-authored source language. When a reusable comment is selected for a student review, its text is copied into `review.json` as a stable snapshot.

The feedback export contract defines how those teacher-confirmed records are presented to the student.

## Primary Output Format

PDF is the primary student-facing feedback export format.

The canonical PDF output path is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
```

Markdown may be retained as an optional plain-text companion artifact.

The optional Markdown output path is:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

Rules:

* PDF is the first-class student-facing deliverable.
* Markdown, if generated, must derive from the same canonical records and follow the same inclusion, privacy, and teacher-control rules.
* Markdown must not contain additional student-facing judgments that are absent from the PDF unless a later contract explicitly defines a different companion-output policy.
* Export generation must not mutate teacher judgments, selected evidence, reusable comment source files, rating scales, standards profiles, rosters, or routed evidence.
* Export generation may update export metadata in `review.json.exports` only when the later runtime implementation explicitly supports that mutation safely.

## Canonical Input Records

A student feedback export is generated from the following records.

### Assignment Record

Canonical path:

```text
classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Required target schema:

```json
{
  "schema_version": "2",
  "record_type": "assignment"
}
```

The export uses assignment data for:

* assignment title;
* class identity;
* student-facing prompt;
* writing type;
* standards profile ID;
* ordered Focus Standard IDs;
* review-unit labels;
* rating scale labels and descriptions;
* minimum requirements; and
* minimum-requirement return policy.

The export must use the assignment's Focus Standard order:

```text
assignment.json.focus_standard_ids
```

as the default order for student-facing standards sections.

### Submission Manifest

Canonical path:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

The export may use the submission manifest for:

* student identity;
* assignment identity;
* selected evidence references;
* submission-management state;
* evidence availability;
* selected page count; and
* stale-export detection when selected evidence changes.

The export should not expose detailed evidence-management metadata to students unless a later contract defines a student-facing reason.

Student-facing feedback must not include:

* retained source scan paths;
* duplicate evidence details;
* candidate evidence details;
* excluded evidence details;
* routing failure metadata;
* internal file provenance;
* scan intake summaries; or
* source file paths.

### Review Record

Canonical path:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

Required target schema:

```json
{
  "schema_version": "2",
  "record_type": "submission_review"
}
```

The export uses review data for:

* review state;
* minimum requirement checks;
* minimum-requirement outcome;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* feedback inclusion choices;
* Focus Standard feedback comments;
* export metadata; and
* timestamps.

The export must not include private notes.

### Roster Record

Canonical path:

```text
classes/<class_id>/roster.csv
```

When available, roster data may be used to show a student display name.

Rules:

* Prefer shared `pds-core` roster display helpers when available.
* Fall back to `student_id` when roster data is unavailable.
* Do not duplicate roster records into `review.json`.
* Do not require student names inside the review record.
* Do not expose unnecessary roster fields in student-facing feedback.

### Standards Library

Canonical pds-core workspace path:

```text
standards/library.json
```

When available, the standards library may be used to resolve student-facing display labels for Focus Standards.

The export may use:

* standard code;
* short name;
* source;
* subject;
* course;
* domain; and
* description, if appropriate for student-facing display.

Durable references remain the pds-core `standard_id` values stored in Quillan records.

Rules:

* Quillan does not own, mutate, import, retire, reactivate, or authoritatively redefine standards during feedback export.
* If a standard definition cannot be resolved, the export may fall back to the durable `standard_id`.
* Missing display metadata must not block export when the teacher has already completed review data.
* Missing display metadata must not cause Quillan to invent standard labels.

## Teacher-Controlled Source Rules

Feedback export is formatting and presentation. It is not grading.

The export must not:

* infer standards performance;
* calculate overall Focus Standard ratings;
* average review-unit observations;
* convert ratings into percentages;
* convert missing ratings into zeros;
* select comments automatically;
* generate feedback automatically;
* run OCR;
* run handwriting recognition;
* parse student writing;
* use AI to score student work;
* use AI to generate feedback;
* include unselected review data;
* include private notes; or
* use live reusable comment text to alter old reviews.

Teacher judgment remains primary.

The export may organize and display teacher-entered review data, but it must not create new judgments.

## Snapshot Rule for Reusable Comments

Reusable Focus Standard comments are source material.

When a reusable Focus Standard comment is selected for a student review, its text is copied into:

```text
review.json.feedback.standard_feedback[].comments[]
```

The feedback export must use the copied review-record text.

The export must not perform live lookup into:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

during export in order to rewrite, refresh, or replace student feedback.

Later edits to reusable comment source files must not silently change prior:

* review records;
* PDF exports;
* Markdown exports; or
* historical feedback artifacts.

## Student-Facing Output Structure

The primary PDF export should use a clear, student-facing structure.

Recommended top-level sections:

```text
Feedback
Assignment
Overall Feedback by Focus Standard
Optional Review-Unit Feedback
Minimum Requirement Notice, when applicable
Next Steps, when recorded
```

The exact visual layout belongs to the later PDF implementation issue, but the data contract should preserve the following content model.

## Header Section

The feedback header should identify the student and assignment.

Recommended fields:

* student display name, when available;
* student ID, when needed or when no display name is available;
* assignment title;
* class display context;
* generated timestamp;
* optional writing type;
* optional standards profile display label, when available;
* optional student-facing prompt.

Example:

```text
Feedback

Student: Sample Student
Class: English 10 Simulation
Assignment: Coming-of-Age Literary Analysis
Generated: 2026-07-02T00:00:00+00:00
```

Rules:

* Use the assignment title from `assignment.json.title`.
* Use the student display name from roster data when available.
* Fall back to `student_id` when roster data is unavailable.
* Do not require real student names in examples.
* Do not expose private roster metadata.
* Do not expose internal workspace paths in the student-facing header.

## Assignment Prompt

The export may include the student-facing prompt.

Source:

```text
assignment.json.student_prompt
```

Rules:

* The prompt should be included when it helps the student understand the feedback context.
* Long prompts may be abbreviated in the visual PDF layout if the full prompt is available elsewhere.
* Prompt inclusion should not change the canonical assignment record.
* Prompt text should come from `assignment.json`; export generation must not invent or rewrite the assignment prompt.

## Focus Standard Sections

Student feedback should be organized primarily by Focus Standard.

The default Focus Standard order is:

```text
assignment.json.focus_standard_ids
```

Each Focus Standard section may include:

* standard display code or title, when resolved from pds-core;
* durable `standard_id`, when useful;
* overall Focus Standard rating, when selected for feedback;
* rating label from the assignment rating scale;
* overall rationale, when selected for feedback;
* selected review-unit observations, when selected for feedback;
* selected teacher comments;
* selected reusable Focus Standard comment snapshots; and
* next-step or revision language recorded by the teacher.

Example section:

```text
Focus Standard: RL.CR.9-10.1 — Cite textual evidence

Rating: Meeting

Teacher Feedback:
Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.
```

Rules:

* Focus Standard sections should be student-readable.
* Internal IDs such as `observation_id`, `unit_id`, `feedback_comment_id`, and `requirement_check_id` should not appear in ordinary student-facing output.
* Durable `standard_id` may appear if needed for clarity, but teacher-facing display fields should be preferred when available.
* A section should not imply that missing feedback equals failure.
* A section should not imply that omitted standards were not assessed unless the review record explicitly supports that statement.

## Overall Focus Standard Ratings

Overall Focus Standard ratings are the primary standards-based scoring object in the v0.8.6 review model.

Source:

```text
review.json.overall_standard_ratings[]
```

Relevant fields:

```text
overall_standard_ratings[].standard_id
overall_standard_ratings[].rating
overall_standard_ratings[].rationale
overall_standard_ratings[].include_in_feedback
```

Rules:

* Only ratings with `include_in_feedback: true` should appear by default.
* `standard_id` must match one of the assignment's `focus_standard_ids`.
* `rating` must be resolved against `assignment.json.rating_scale.levels`.
* Student-facing output should show the rating label.
* Numeric rating values may be shown if useful, but they must not be presented as percentages or grades.
* Missing ratings must not be displayed as zeros.
* Missing ratings must not be inferred from observations.
* Missing ratings must not be automatically created during export.
* Overall Focus Standard ratings are teacher judgments, not calculated averages.

Example rating source:

```json
{
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "rating": 3,
  "rationale": "Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.",
  "include_in_feedback": true,
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Example student-facing display:

```text
RL.CR.9-10.1 — Cite textual evidence
Rating: Meeting
```

## Rating Label Resolution

Rating values are assignment-local values.

The export resolves a rating value through:

```text
assignment.json.rating_scale.levels[]
```

Example assignment rating scale entry:

```json
{
  "value": 3,
  "label": "Meeting",
  "description": "The work shows clear and sufficient evidence of the standard."
}
```

If the review stores:

```json
"rating": 3
```

the student-facing export should display:

```text
Meeting
```

Rules:

* Rating labels come from the assignment record.
* Rating values must not be interpreted without the assignment rating scale.
* The export must not assume a universal four-point scale unless the assignment uses one.
* If a rating value cannot be resolved, the export should fail safely or show a clear teacher-facing warning rather than inventing a label.
* Runtime implementation should avoid generating polished student output from unresolved rating values unless a clear fallback policy is defined.

## Overall Rationales

Overall rationales explain the teacher's overall Focus Standard rating.

Source:

```text
review.json.overall_standard_ratings[].rationale
```

Inclusion control:

```text
review.json.overall_standard_ratings[].include_in_feedback
review.json.feedback.standard_feedback[].include_overall_rationale
```

Rules:

* Rationales should appear only when selected for student feedback.
* A `null` rationale should not produce placeholder text such as "No rationale."
* Rationale text should be displayed under the relevant Focus Standard.
* Rationales are teacher-entered text. Export generation must not generate or rewrite them.
* Rationales should not appear if the relevant overall rating is excluded unless a later workflow explicitly allows rationale-only feedback.

Example student-facing display:

```text
Why this rating:
Your paragraph uses relevant evidence, but the explanation needs to connect the quotation more directly to your claim.
```

## Review-Unit Observations

Review-unit observations are teacher-entered judgments about one Focus Standard in one review unit.

Source:

```text
review.json.review_units[].standard_observations[]
```

Relevant observation fields:

```text
observation_id
standard_id
applicable
evidence_present
rating
rationale
include_in_feedback
```

Relevant review-unit fields:

```text
unit_id
sequence
label
unit_type
page_number
evidence_id
```

Global inclusion setting:

```text
review.json.feedback.include_review_unit_observations
```

Focus Standard-specific selected observations:

```text
review.json.feedback.standard_feedback[].included_observation_ids
```

Rules:

* Review-unit observations are optional in student feedback.
* Only selected observations should appear.
* Selected observations should be grouped under the relevant Focus Standard.
* Review-unit labels should use the assignment-defined review-unit labels.
* The export should use teacher-facing labels such as "Paragraph 2," not internal wording such as "review unit sequence 2."
* Review-unit observations must not be averaged into overall Focus Standard ratings.
* Review-unit observations must not be inferred from student writing.
* Review-unit observations must not expose internal IDs in ordinary student-facing output.

For an assignment whose review unit is `paragraph`, student-facing feedback may say:

```text
Paragraph 2:
Your evidence is relevant, but your explanation needs to connect more clearly to the claim.
```

It should not say:

```text
unit_id paragraph_2 observation_id observation_0007
```

## Review-Unit Rating Display

A selected review-unit observation may include a rating.

Rules:

* Observation ratings use the same assignment rating scale as overall ratings.
* Observation ratings should be resolved to labels before display.
* Observation ratings are local evidence-level judgments, not final scores.
* The export should avoid visual designs that make review-unit observations look like separate grades unless a later contract explicitly supports that behavior.

Example:

```text
Paragraph 1 — RL.CR.9-10.1
Observation: Approaching
The paragraph includes evidence, but the explanation is still general.
```

## Feedback Composition Source

Student-facing comments are stored in:

```text
review.json.feedback.standard_feedback[].comments[]
```

A Focus Standard feedback record may include:

```json
{
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "include_overall_rating": true,
  "include_overall_rationale": true,
  "included_observation_ids": [],
  "comments": [],
  "module_details": {}
}
```

Rules:

* Each `standard_feedback[].standard_id` should match one assignment Focus Standard.
* Comments are grouped by Focus Standard.
* Only comments with `include_in_feedback: true` should appear.
* Comments with `include_in_feedback: false` must not appear in ordinary student-facing output.
* Custom comments and reusable comment snapshots are both allowed.
* The export should not show source/provenance details unless a later contract explicitly defines a student-facing reason.
* Feedback comments must use the text stored in the review record.

## Feedback Comment Structure

A feedback comment snapshot in a review record uses this general target shape:

```json
{
  "feedback_comment_id": "feedback_comment_0001",
  "source": "custom",
  "text": "Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.",
  "reusable_comment_id": null,
  "save_for_reuse": false,
  "include_in_feedback": true,
  "created_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

A reusable Focus Standard comment selected into feedback uses a stable copied snapshot:

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

Student-facing output should display only the teacher-approved feedback text.

It should not display:

* `feedback_comment_id`;
* `source`;
* `reusable_comment_id`;
* `comment_set_id`;
* `save_for_reuse`;
* `created_at`;
* `module_details`; or
* reusable-comment provenance.

## Comment Sources

Allowed comment sources are defined by the review-record contract.

Expected source values include:

```text
custom
reusable_focus_standard_comment
```

Rules:

* `custom` means the teacher wrote the feedback directly for this review.
* `reusable_focus_standard_comment` means the teacher selected reusable source language and Quillan copied it into the review record.
* Both source types should be treated as teacher-selected feedback once stored in `review.json`.
* Source type is internal provenance and should normally be hidden from students.

## Minimum-Requirement Return Feedback

The feedback export must support submissions returned without full standards review.

Relevant fields:

```text
review.json.minimum_requirement_checks[]
review.json.minimum_requirement_outcome
review.json.review_state
```

A minimum-requirements return applies when:

```json
"review_state": "returned_without_full_review"
```

or when:

```json
"minimum_requirement_outcome": {
  "status": "returned_without_full_review",
  "returned_without_full_review": true
}
```

In this case, the student-facing export may use a different structure from full standards feedback.

Recommended sections:

```text
Feedback
Assignment
Minimum Requirements
What Needs Revision
Next Step
```

The output may include:

* assignment title;
* student display name or student ID;
* a clear statement that the submission was returned without full standards review;
* unmet minimum requirements;
* teacher note, if student-facing and selected;
* revision or resubmission guidance, if recorded;
* generated timestamp.

The output must not present:

* a zero;
* a grade;
* completed Focus Standard ratings;
* missing Focus Standard ratings as failing ratings;
* a completed standards review;
* a normal reviewed submission; or
* automatic grade language.

Example student-facing language:

```text
This submission was returned before full standards review because one or more minimum requirements were not met.

Please revise the items below before the work is reviewed for the assignment's Focus Standards.
```

## Minimum Requirement Checks

Minimum requirement checks come from:

```text
review.json.minimum_requirement_checks[]
```

Example:

```json
{
  "requirement_check_id": "requirement_check_0002",
  "requirement_key": "required_elements:textual_evidence",
  "label": "Required element: textual evidence",
  "expected": "textual evidence",
  "met": false,
  "teacher_note": "Add at least one relevant quotation from the story.",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Student-facing output should show:

```text
Required element: textual evidence
Status: Needs revision
Teacher note: Add at least one relevant quotation from the story.
```

Rules:

* Requirement checks are teacher-entered.
* Quillan must not count paragraphs automatically.
* Quillan must not count words automatically.
* Quillan must not parse student writing.
* Quillan must not run OCR to determine requirement completion.
* Quillan must not use AI to detect required elements.
* Requirement checks are not writing-quality scores.

## Full Review Feedback Versus Return Feedback

A full standards-based feedback export and a minimum-requirements return export are different student-facing cases.

### Full Standards-Based Feedback

Use when the teacher has completed enough review to provide Focus Standard feedback.

Relevant states may include:

```text
ratings_complete
feedback_composed
ready_for_export
exported
```

Typical content:

* assignment identity;
* student identity;
* Focus Standard ratings;
* selected rationales;
* selected review-unit observations;
* selected comments;
* next steps.

### Returned Without Full Review

Use when the teacher returns work before full standards review.

Relevant state:

```text
returned_without_full_review
```

Typical content:

* assignment identity;
* student identity;
* unmet minimum requirements;
* requirement-focused teacher note;
* revision or resubmission guidance.

Rules:

* Return feedback should not pretend that full standards review occurred.
* Full standards feedback should not be generated automatically when the review state indicates return without full review.
* The teacher should control which export is generated when states are ambiguous.

## Export Metadata in `review.json`

The target review record includes export metadata under:

```text
review.json.exports
```

Target structure:

```json
{
  "feedback_pdf": null,
  "feedback_markdown": null
}
```

After export, a metadata entry should use this general shape:

```json
{
  "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/exports/feedback.pdf",
  "format": "pdf",
  "generated_at": "2026-07-02T00:00:00+00:00",
  "source_review_updated_at": "2026-07-02T00:00:00+00:00",
  "source_assignment_updated_at": "2026-07-02T00:00:00+00:00",
  "source_submission_updated_at": "2026-07-02T00:00:00+00:00",
  "module_details": {}
}
```

Required export metadata fields:

* `path`;
* `format`;
* `generated_at`;
* `source_review_updated_at`;
* `source_assignment_updated_at`;
* `source_submission_updated_at`;
* `module_details`.

Field rules:

* `path` must be a safe workspace-relative path.
* `format` must identify the generated format, such as `pdf` or `markdown`.
* `generated_at` must be a timezone-aware ISO 8601 timestamp.
* `source_review_updated_at` records the review record timestamp used for export.
* `source_assignment_updated_at` records the assignment timestamp used for export.
* `source_submission_updated_at` records the submission manifest timestamp used for export.
* `module_details` must be an object.
* Unknown fields are not part of the target export metadata contract unless a later schema version defines them.

## Stale Export Detection

Export metadata supports stale-export detection.

A feedback export should be considered stale when:

```text
review.json.updated_at > exports.feedback_pdf.source_review_updated_at
```

A feedback export may be considered stale or potentially stale when:

```text
assignment.json.updated_at > exports.feedback_pdf.source_assignment_updated_at
```

or:

```text
submission.json.updated_at > exports.feedback_pdf.source_submission_updated_at
```

The same logic applies to `feedback_markdown` metadata.

Rules:

* Stale export detection should warn the teacher.
* Stale export detection should not silently rewrite exports.
* Stale export detection should not silently delete exports.
* Stale export detection should not alter teacher judgments.
* If selected evidence changed after export, the teacher should be warned before relying on the old feedback artifact.
* If assignment rating labels or Focus Standards changed after export, the teacher should be warned before relying on the old feedback artifact.

## Export Overwrite Policy

Generated feedback exports are derived artifacts, but overwriting them still requires care.

Rules:

* Export generation should refuse to overwrite an existing `feedback.pdf` unless the teacher explicitly confirms or passes an overwrite option.
* Export generation should refuse to overwrite an existing `feedback.md` unless the teacher explicitly confirms or passes an overwrite option.
* Overwrite behavior should be atomic where practical.
* Failed export writes must not leave partial visible output when avoidable.
* Updating export metadata should happen only after successful export creation.
* If metadata update fails after export creation, the runtime should report that mismatch clearly.

The precise CLI/menu overwrite mechanics belong to later implementation work.

## Student-Facing Privacy Rules

Student-facing feedback exports must exclude private teacher-only data.

The export must not include:

* `review.json.private_notes`;
* internal review IDs;
* internal observation IDs;
* internal comment IDs;
* reusable comment IDs;
* comment set IDs;
* retained-source scan paths;
* routed evidence filesystem paths;
* duplicate evidence metadata;
* candidate evidence metadata;
* excluded evidence metadata;
* scan failure metadata;
* source file paths;
* local workspace root paths;
* raw JSON records;
* debug metadata;
* hidden workflow metadata;
* unselected observations;
* unselected rationales;
* unselected comments;
* inactive reusable comments;
* live reusable comment source text that was not selected; or
* teacher-only provenance.

The export should include only the data the teacher selected or confirmed for student-facing feedback.

## Repository Privacy and Data Hygiene

Committed examples must use synthetic data only.

Do not commit:

* real student names;
* real student IDs;
* real rosters;
* real student writing;
* real scanned work;
* real feedback for actual students;
* real grades;
* real parent or guardian information;
* accommodation information;
* disability information;
* health information;
* discipline information;
* attendance information;
* private family information; or
* personally identifiable student information.

Synthetic examples should use clearly artificial class IDs, assignment IDs, student IDs, comments, and review data.

## Recommended Student-Facing PDF Content Model

A full standards-based feedback PDF should follow this content model.

```text
Feedback

Student
Assignment
Generated

Assignment Prompt, optional

Focus Standard 1
- Rating, if selected
- Rationale, if selected
- Selected review-unit observations, if selected
- Teacher-selected comments

Focus Standard 2
- Rating, if selected
- Rationale, if selected
- Selected review-unit observations, if selected
- Teacher-selected comments

Focus Standard 3
- Rating, if selected
- Rationale, if selected
- Selected review-unit observations, if selected
- Teacher-selected comments

Next Steps, if recorded
```

A minimum-requirements return PDF should follow this content model.

```text
Feedback

Student
Assignment
Generated

Returned Before Full Standards Review

Minimum Requirements
- Requirement
- Status
- Teacher note, if selected

Next Step
```

The exact typography, pagination, headers, footers, table styling, and visual design belong to the later PDF implementation issue.

## Recommended Markdown Companion Model

If Markdown is generated, it should use the same content model as the PDF.

Recommended path:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

Rules:

* Markdown is optional.
* Markdown is a companion artifact, not the primary target.
* Markdown should be useful for plain-text review, copying, or debugging.
* Markdown must follow the same inclusion and privacy rules as PDF.
* Markdown should not expose internal metadata that is hidden from the PDF.
* Markdown should not become the canonical review record.

## Complete Synthetic Full-Review Example

This example is illustrative. It is not a required runtime export JSON schema.

Source assignment:

```json
{
  "schema_version": "2",
  "module": "quillan",
  "record_type": "assignment",
  "assignment_id": "coming-of-age_literary_analysis",
  "title": "Coming-of-Age Literary Analysis",
  "class_ids": ["english_10_simulation"],
  "writing_type": "literary_analysis",
  "student_prompt": "Using evidence from the story, explain how ordinary objects become connected to memory, grief, and power.",
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

Selected review feedback source:

```json
{
  "overall_standard_ratings": [
    {
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "rating": 3,
      "rationale": "Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.",
      "include_in_feedback": true,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    }
  ],
  "feedback": {
    "include_review_unit_observations": false,
    "include_overall_standard_ratings": true,
    "standard_feedback": [
      {
        "standard_id": "njsls-ela:RL.CR.9-10.1",
        "include_overall_rating": true,
        "include_overall_rationale": true,
        "included_observation_ids": [],
        "comments": [
          {
            "feedback_comment_id": "feedback_comment_0001",
            "source": "custom",
            "text": "Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.",
            "reusable_comment_id": null,
            "save_for_reuse": false,
            "include_in_feedback": true,
            "created_at": "2026-07-02T00:00:00+00:00",
            "module_details": {}
          }
        ],
        "module_details": {}
      }
    ]
  }
}
```

Possible student-facing Markdown companion output:

```markdown
# Feedback

Student: Sample Student  
Class: English 10 Simulation  
Assignment: Coming-of-Age Literary Analysis  
Generated: 2026-07-02T00:00:00+00:00  

## Assignment

Using evidence from the story, explain how ordinary objects become connected to memory, grief, and power.

## Focus Standard Feedback

### RL.CR.9-10.1 — Cite textual evidence

Rating: Meeting

Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.

Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.
```

## Complete Synthetic Minimum-Requirement Return Example

Selected review source:

```json
{
  "review_state": "returned_without_full_review",
  "minimum_requirement_checks": [
    {
      "requirement_check_id": "requirement_check_0001",
      "requirement_key": "paragraphs_min",
      "label": "Minimum paragraphs",
      "expected": 1,
      "met": true,
      "teacher_note": null,
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    },
    {
      "requirement_check_id": "requirement_check_0002",
      "requirement_key": "required_elements:textual_evidence",
      "label": "Required element: textual evidence",
      "expected": "textual evidence",
      "met": false,
      "teacher_note": "Add at least one relevant quotation from the story.",
      "updated_at": "2026-07-02T00:00:00+00:00",
      "module_details": {}
    }
  ],
  "minimum_requirement_outcome": {
    "status": "returned_without_full_review",
    "returned_without_full_review": true,
    "teacher_note": "Please revise and resubmit with textual evidence before full standards review.",
    "updated_at": "2026-07-02T00:00:00+00:00"
  }
}
```

Possible student-facing Markdown companion output:

```markdown
# Feedback

Student: Sample Student  
Class: English 10 Simulation  
Assignment: Coming-of-Age Literary Analysis  
Generated: 2026-07-02T00:00:00+00:00  

## Returned Before Full Standards Review

This submission was returned before full standards review because one or more minimum requirements were not met.

Please revise and resubmit with textual evidence before full standards review.

## Minimum Requirements

- Minimum paragraphs: Met
- Required element: textual evidence: Needs revision
  - Add at least one relevant quotation from the story.
```

## Relationship to Legacy Feedback Export

Legacy feedback export may currently use:

```text
review.json.scores
review.json.comments
```

and generate:

```text
exports/feedback.md
```

That behavior belongs to the older schema version `1` review model.

The target v0.8.6 model supersedes that approach:

* old generic criterion scores are superseded by overall Focus Standard ratings;
* old generic selected comments are superseded by Focus Standard feedback comments;
* old generic tag counts are not student-facing feedback structure;
* old Markdown-first export is superseded by PDF-first export.

Compatibility code may temporarily support legacy exports until the implementation issues replace runtime behavior.

## Relationship to Later Issues

This contract prepares later work, especially:

```text
#224 Remove obsolete generic review-material workflows
#229 Implement Focus Standard feedback composer
#230 Implement student feedback PDF export
#231 Implement standards-based class and standards summaries
#232 Replace tests and examples for the old review model
```

This contract does not require those implementation changes by itself.

## Out of Scope

This contract does not implement:

* PDF generation;
* Markdown export rewrite;
* CLI command changes;
* menu changes;
* runtime validation for schema version `2`;
* review-record migration;
* deletion of legacy feedback export code;
* reusable Focus Standard comment lookup;
* feedback composition workflow;
* export overwrite prompts;
* export metadata mutation;
* standards-based class reports;
* standards-based standards reports;
* AI feedback generation;
* OCR-based feedback generation;
* automatic scoring;
* automatic mastery calculation; or
* automatic review-state transitions.

## Runtime Status

At the time this target contract is introduced, current runtime workflows may still:

* validate schema version `1` review records;
* export Markdown feedback from legacy scores and comments;
* use legacy comment banks;
* use legacy tag banks;
* use legacy rubric/scoring profiles; and
* rely on tests and examples from the old review model.

This document defines the target student feedback export contract for the v0.8.6 standards-based redesign. It does not by itself update runtime validators, export services, menu workflows, CLI commands, tests, examples, or migration behavior.

You’ll also want to add a short link entry for this file in `docs/data_contracts.md` after the review-record / Focus Standard comments entries.
