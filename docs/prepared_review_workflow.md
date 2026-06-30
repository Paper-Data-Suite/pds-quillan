# Prepared Review Workflow

## Purpose

Quillan is a local-first prepared-review system for written student work.
Teachers prepare reusable review materials before grading, then select and
snapshot the relevant comments, tags, rubric scores, notes, targets, and
requirement checks while reviewing actual student evidence.

This workflow is teacher-controlled. Quillan helps organize review decisions;
it does not read student work, generate feedback, score automatically, infer
mastery, run OCR, or use AI.

## Subject-Agnostic Design

Quillan is subject-agnostic. It is designed for teacher review of written
responses across disciplines. ELA starter materials are included as one
optional starter pack, but the underlying comment-bank, tag-bank, rubric,
assignment, submission, and review-record structures are not ELA-specific.

Useful local contexts include English / ELA, history / social studies,
science, computer science, technical writing, world languages,
arts/humanities, and interdisciplinary writing tasks. Subject-neutral review
materials can support claim/evidence/reasoning responses, lab explanations,
research responses, reflection journals, technical explanations, design
rationales, and short constructed responses.

## Review Materials

Reusable review materials live under `shared/`. They are prepared before or
between reviews and selected during review. Selected values are copied into
`review.json` so old reviews stay stable when source materials change later.

### Comment Banks

Comment banks are reusable student-facing feedback language stored at:

```text
shared/comment_banks/<bank_id>.json
```

They are selected into `review.json.comments` and copied at selection time.
They may include `include_in_feedback_default`, standards metadata, criterion
metadata, and writing-type metadata. They can be used across assignments and
subjects.

Comment banks are not automatic feedback, AI feedback, grades, or student
records.

### Tag Banks

Tag banks are reusable teacher observations stored at:

```text
shared/tag_banks/<tag_bank_id>.json
```

They support fast review, grouping, and reporting. A tag template may include
polarity, severity, standards metadata, criterion IDs, and a private note
prompt. Selected tags are copied into `review.json.tags`.

Tag banks are not scores, automatic suggestions, proof of mastery, or
student-facing feedback by default.

### Rubrics / Scoring Profiles

Rubrics and scoring profiles are reusable criteria and levels stored at:

```text
shared/rubrics/<rubric_id>.json
```

They help teachers select criterion scores during review. Selected scores are
snapshotted into `review.json.scores`.

Rubrics do not automatically grade, calculate percentages, calculate final
grades, infer mastery, or turn level feedback metadata into comments.

### Notes

Notes are private, freeform teacher observations stored in:

```text
review.json.notes
```

They support teacher memory, review process notes, private context, and
conference reminders. Notes are not student-facing feedback exports,
structured reporting data, or scores.

### Requirement Checks

Requirement checks are teacher-entered booleans generated from assignment
`basic_requirements` and stored in:

```text
review.json.requirement_checks
```

They document whether basic assignment conditions were met and help teachers
review consistently. They are not automatic counting, OCR, AI, quality
scoring, or grade calculation.

### Review Targets

Tags and comments may include teacher-entered target metadata:

```text
review.json.tags[].page_number
review.json.tags[].evidence_id
review.json.tags[].location
review.json.comments[].page_number
review.json.comments[].evidence_id
review.json.comments[].location
```

Targets point feedback to a paragraph, page, evidence item, whole submission,
or another controlled location. They are not automatic paragraph detection,
OCR, AI, or text parsing.

## Before Review

1. Create or select standards/profile data in pds-core if standards are being used.
2. Create or select a Quillan assignment.
3. Prepare or install comment banks.
4. Prepare or install tag banks.
5. Prepare or install rubrics/scoring profiles.
6. Print response pages when using the paper workflow.
7. Scan, route, and assemble student submissions.
8. Confirm each selected student has reviewable evidence.

Standards are optional metadata references. Quillan does not own or mutate
pds-core standards definitions, standards profiles, or route helpers.

## During Review

1. Select class, assignment, and student.
2. Open submission evidence.
3. View current review details if resuming work.
4. Record minimum requirement checks when applicable.
5. Add reusable or custom tags.
6. Add reusable comments.
7. Add page, paragraph, or evidence targets when helpful.
8. Score rubric criteria or use custom scoring.
9. Add private notes only when needed.
10. Update review state.
11. Export student feedback.
12. Export assignment summaries when needed.

These are teacher workflow actions. Opening evidence does not mark a
submission reviewed, and exporting feedback does not rescore work.

## Snapshot Behavior

When a teacher selects a reusable comment, Quillan stores provenance such as
`bank_id` and `comment_id`, copies the selected label and text into
`review.json.comments`, and stores the teacher's feedback-inclusion choice.
Later edits to the source comment bank do not rewrite previous review records.

When a teacher selects a reusable tag, Quillan stores provenance such as
`tag_bank_id` and `tag_template_id`, then copies the selected label, polarity,
severity, and optional metadata into `review.json.tags`. Later edits to the
source tag bank do not rewrite previous review records.

When a teacher scores from a rubric, Quillan stores the chosen criterion,
score, max score, scale, and optional teacher note in `review.json.scores`.
Later edits to the rubric do not rewrite previous review scores.

Student feedback exports and summary exports are derived from `review.json`,
not live source banks.

## Storage Map

```text
shared/comment_banks/<bank_id>.json          reusable student-facing comments
shared/tag_banks/<tag_bank_id>.json          reusable teacher observations
shared/rubrics/<rubric_id>.json              reusable scoring profiles
classes/<class_id>/assignments/<assignment_id>/assignment.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

`submission.json` is source evidence metadata. `review.json` is teacher
review. Exports are derived artifacts. Reusable review materials live under
`shared/`.

## Starter Materials

Starter materials are optional, teacher-editable review materials. They are
not official curriculum, not district grading policy, and not automatic
evaluation.

Synthetic starter materials are small, portable examples for testing and
onboarding. NJ ELA starter materials are larger teacher-editable classroom
starter packs. Both install through the same Starter Materials workflow and
copy only shared review materials into:

```text
shared/comment_banks/
shared/tag_banks/
shared/rubrics/
```

Starter installation does not create or modify standards, assignments,
rosters, scans, submissions, review records, exports, pds-core standards
files, pds-core standards profiles, or pds-core route helpers.

## Safety Boundaries

Quillan preserves the teacher-controlled model:

* reusable materials do not act until the teacher selects them;
* source evidence, review artifacts, reusable materials, and exports stay
  distinct;
* exports are derived from teacher-confirmed `review.json` records;
* standards references are optional pds-core metadata;
* examples and tests must use synthetic data unless they are explicitly
  labeled starter-material content.

Do not commit real student names, rosters, writing, grades, scans, review
notes, feedback, exports, or personally identifiable information.

## Related Docs

* [`data_contracts.md`](data_contracts.md)
* [`comment_bank_contract.md`](comment_bank_contract.md)
* [`tag_bank_contract.md`](tag_bank_contract.md)
* [`rubric_contract.md`](rubric_contract.md)
* [`review_record_contract.md`](review_record_contract.md)
* [`teacher_review_model.md`](teacher_review_model.md)
* [`starter_materials.md`](starter_materials.md)
* [`nj_ela_starter_materials.md`](nj_ela_starter_materials.md)
* [`workspace_lifecycle.md`](workspace_lifecycle.md)
