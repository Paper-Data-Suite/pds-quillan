# Quillan Teacher-Review Model

## Overview

Quillan's review model is teacher-controlled. Quillan preserves student
writing, organizes teacher-review artifacts, and reduces clerical friction,
but it does not replace the teacher's professional judgment.

The model keeps source evidence, teacher-review artifacts, and derived exports
distinct. Software may validate records, organize observations, format
teacher-approved language, and summarize confirmed records. It must not
present an unconfirmed software judgment as a teacher evaluation or encourage
review without reading the student's work.

Quillan is subject-agnostic. It can support teacher review of written
responses across disciplines, such as lab explanations, research responses,
reflection journals, technical explanations, design rationales, short
constructed responses, and ELA writing. ELA starter materials are one optional
starter pack, not the boundary of the review model.

This document defines the review model and data boundaries. Quillan currently
validates relevant data contracts, can prepare printable writing-response
pages, supports direct teacher-entered notes, tags, comments, and criterion
scores, provides guided selected-student review actions in the terminal menu,
supports teacher-entered minimum requirement checks from assignment
configuration, and can export student feedback and assignment summaries. AI
tagging, AI scoring, AI feedback, automatic requirements evaluation, and
automatic grading are not implemented.

For the teacher workflow before and during review, including reusable
materials, snapshot behavior, storage paths, and starter-material boundaries,
see [`prepared_review_workflow.md`](prepared_review_workflow.md).

## Source Evidence

Source evidence is the student-produced writing and the metadata needed to
identify and preserve it:

* `submission.txt`
* `submission.json`

The writing is the student's work. The metadata records its identity,
provenance, capture time, evidence-management state, and version. Source
evidence does not contain teacher notes, tags, scores, selected comments,
feedback exports, or reports.

Keeping source evidence separate allows a teacher to compare later review
artifacts with the writing that was actually submitted.

Teachers can manage page state from Selected Student Review without changing
teacher-review artifacts. Excluding a page removes it from active review while
preserving the manifest entry and routed evidence file. Restoring an excluded
page returns it to the active evidence set when safe; duplicate evidence is not
silently selected. Marking a page as needing rescan records evidence-management
status only. These actions update only the selected student's `submission.json`
and do not alter `review.json`, exports, rosters, assignments, review
materials, pds-core standards, or pds-core routes.

## Teacher-Review Artifacts

Teacher-review artifacts are records created by the teacher or confirmed
through teacher review:

* `review.json`

`review.json` is the canonical active v0.7 record for teacher-entered notes,
tags, criterion scores, teacher-selected comments, and teacher-entered
requirement checks. It is adjacent to and references `submission.json`, but
remains separate so teacher judgment does not alter the student's original
work. Current requirement checks are stored in
`review.json.requirement_checks`, not in a sibling `requirements.json`.

Tags and selected comments may include optional teacher-entered target
metadata such as page number, evidence ID, paragraph, multiple paragraphs, or
whole submission. Paragraph targets are not discovered from the student work:
Quillan does not parse writing, run OCR, use AI, count paragraphs, or infer
where a tag or comment applies.

Earlier designs named separate `tags.json` and `scores.json` files. Those are
historical concepts, not alternate active v0.7 records. Their content belongs
in `review.json`.

Prepared reusable materials, source evidence, teacher-review artifacts, and
exports serve different roles: source banks and rubrics live under `shared/`,
`submission.json` describes reviewable evidence, `review.json` stores teacher
review decisions, and exports are derived from those canonical records.

## Derived Exports and Reports

Derived outputs are generated from teacher-reviewed records:

* `submissions/<student_id>/exports/feedback.md`
* `assignments/<assignment_id>/exports/class_summary.csv`
* `assignments/<assignment_id>/exports/standards_summary.csv`

The student-level `exports/feedback.md` is a student-readable export. The
assignment-level CSV reports are
aggregations. These outputs are not independent evidence or substitutes for
`review.json`; they should remain traceable to the teacher-confirmed records
from which they were derived.

Selected Student Review also includes a terminal-only `View current review
details` view. It reads the current student's `review.json` and displays saved
requirement checks, tags, comments, scores, notes, target labels, and
include-in-feedback settings so a teacher can resume an interrupted review
without exporting a report. It is read-only and is not a replacement for full
reporting or student feedback export.

## Tag Philosophy

A tag is a teacher-created or teacher-confirmed observation attached to
student writing evidence. A tag may connect:

* a location in the student writing;
* a standard;
* a reusable teacher-defined comment;
* a polarity;
* an optional severity; and
* an optional teacher note.

A tag is not an AI-detected issue, an automatic mark, a software-generated
judgment, a score, or proof that a standard was met or missed. Hotwords and
subskills may help a teacher find or organize possible areas for review, but
they do not establish a tag without teacher confirmation.

Tags can support review consistency and reporting, but they do not
mechanically determine scores.

The assignment-level `exports/standards_summary.csv` report groups only
standards-linked tags and selected comments from valid matching review
records. It reports tag polarity, feedback inclusion, and distinct-student
counts without reading evidence or source comment banks. It does not include
scores or notes, infer mastery, calculate grades, or
mutate canonical records. Student discovery is directory-based; roster-aware
missing-student reporting remains future work.

## Evidence Philosophy

In Quillan, evidence means preserved student work and teacher-confirmed
records about that work. Depending on the workflow, evidence may include:

* the student's submitted writing;
* submission metadata;
* teacher tags and notes;
* requirements-check records;
* teacher-entered scores; and
* teacher-confirmed feedback records.

Evidence should remain local-first, auditable, and traceable to the applicable
submission. It is not a conclusion produced by an AI evaluator. Source
evidence establishes what the student submitted; teacher-review artifacts
record how the teacher understood and evaluated it.

## Requirements Check Philosophy

A requirements check records structural or compliance information about a
submission. Examples include:

* word count;
* paragraph count;
* required elements;
* presence of a title;
* number of lines or stanzas; and
* required sections.

These checks help a teacher see whether basic assignment conditions were met.
They do not measure writing quality and must not be treated as a
writing-quality score.

Current Quillan requirement checks are manual teacher-entered booleans
generated from assignment `basic_requirements`. Quillan does not infer
paragraph counts, word counts, or required-element presence, and it does not
use OCR, AI, or automatic text parsing. Requirement checks remain distinct
from scoring and feedback, and the teacher retains responsibility for
interpreting them in context.

## Score Philosophy

A score record is a teacher-entered or teacher-confirmed scoring decision. A
teacher may consider:

* source evidence;
* teacher tags;
* rubric criteria;
* requirements checks; and
* teacher notes.

Tags and requirements results may inform a score, but they do not calculate
or compel one. Quillan must not automatically determine or generate scores. A
score record represents teacher judgment, not software judgment.

Quillan's direct `set-score` workflow records one criterion at a time in the
canonical `review.json`. It updates an existing record by `criterion_id` or
appends a new one without disturbing unrelated review data. Criterion IDs are
accepted as explicit teacher input.

The guided Review Student Work menu can also resolve an assignment's shared
rubric/scoring profile and let the teacher choose a criterion and score level
before saving. Custom criterion scoring remains available as an advanced
manual fallback. Neither path calculates an overall score, percentage, grade,
weighted result, or mastery result, and rubric level feedback does not
automatically create comments.

## Feedback Philosophy

Feedback is student-readable teacher communication. It may draw on:

* teacher tags;
* teacher notes;
* score records;
* requirements checks; and
* teacher-approved standards profile or shared comment bank comments.

Feedback remains teacher-controlled. The direct `export-feedback` workflow
formats already-selected teacher-authored comments and teacher-entered
criterion scores as Markdown; it does not draft, infer, select, or grade
anything. Selected reusable or custom comments are stored in `review.json`;
the rendered `submissions/<student_id>/exports/feedback.md` is derived.

The export preserves score and included-comment order. It includes only
comments marked `include_in_feedback: true` and uses their snapshotted text,
without reading source comment banks or standards profiles. Private notes,
score `teacher_note` values, structured tags, excluded comments, and comment
provenance are omitted.

Export does not change `review_state`, mark a review `exported`, update
timestamps, or mutate `review.json`, `submission.json`, evidence, retained
scans, or source banks. Existing feedback is protected unless the teacher
explicitly supplies `--overwrite`. Quillan must not present authoritative
AI-generated feedback.

The guided feedback export screen explains that export formats the current
review record. It does not rescore work, generate AI feedback, or modify
notes, tags, comments, scores, review state, submissions, scans, review
materials, or pds-core records. If an export already exists, the teacher must
explicitly choose overwrite before Quillan replaces it.

Shared comment banks are reusable teacher-authored source data stored at
`shared/comment_banks/<bank_id>.json`. They are not student records and do
not grade, evaluate, or generate feedback by themselves. The direct
`add-comment` workflow copies a student-facing comment's teacher-approved
language into
`review.json.comments` as a snapshot with `source: "comment_bank"`, the source
`bank_id`, and the source `comment_id`. Comment IDs are bank-local, so the pair
identifies the reusable source comment. The copied label and text remain
stable if the bank later changes; provenance does not create a live reference.
The bank feedback default may be overridden by the teacher at selection time.
Teacher-only bank comments are rejected, and selection does not itself export
feedback.
The guided Review Student Work menu presents comment banks by title, then
category, then comment label and feedback preview. Source IDs remain visible
as secondary detail. Missing comment banks point teachers to Review Student
Work -> Manage Review Materials -> Comment Banks.
The source contract and future assignment-activation design are defined in
[`comment_bank_contract.md`](comment_bank_contract.md).

Optional synthetic starter comment banks, tag banks, and rubrics can be
installed from Review Student Work -> Manage Review Materials -> Starter
Materials for onboarding and testing. They are subject-agnostic examples only,
install into shared
review-material folders, and do not create assignments, rosters, submissions,
review records, exports, or pds-core standards.

Reusable tag banks are also selected in a bank, category, and tag-template
flow. Custom tags are framed as one-off/manual observations with enumerated
polarity and optional details grouped behind an explicit prompt. Missing tag
banks point teachers to Review Student Work -> Manage Review Materials ->
Tag Banks while preserving the custom fallback.

When reusable comments or tags include pds-core `standard_id` references,
Quillan may resolve display metadata through pds-core read-only helpers. This
display does not mutate the standards library or turn Quillan into the
authoritative standards owner. Unresolved standards fall back to durable IDs
with metadata unavailable.

## Report Philosophy

Reports summarize teacher-reviewed records. They may help teachers identify:

* common strengths;
* common areas for growth;
* standards-level patterns;
* class-level needs; and
* individual student review summaries.

Reports must be derived from teacher-confirmed artifacts rather than
unconfirmed software judgments. They support instructional planning and
clerical organization, but they do not replace reading student work or
reviewing the underlying records.

The implemented class review summary reads existing assignment submission and
review records and emits one status row per discovered student directory.
Ready rows include transparent totals of teacher-entered scores and maximums,
but those sums are not grades, percentages, mastery judgments, or weighted
results. Missing or invalid records remain visible as status rows. The export
does not inspect evidence or source comment banks, use a roster, or mutate
canonical records. Standards aggregation is available through the implemented
standards summary export; roster-aware missing-student reporting remains
future work.

## Relationship to Existing Documentation

[`data_contracts.md`](data_contracts.md) defines the fields and formats of
individual Quillan records. This document defines the review philosophy and
the conceptual relationships among those records.

[`review_record_contract.md`](review_record_contract.md) defines the canonical
v0.7 `review.json` shape and its identity, state, timestamp, path, reference,
and mutation rules.

## Review Readiness

Routed scan evidence and a review-ready submission are distinct. Before a
teacher adds notes, tags, comments, scores, review state, or feedback exports,
Quillan requires an assembled submission record. When routed evidence exists
but that record is missing, the review menu offers assignment-level assembly
instead of actions that would fail. Assembly neither evaluates evidence nor
changes review state, notes, tags, comments, scores, or exports.

Selected-student review actions clear and reframe major action screens, use
`B`/Back cancellation consistently, and avoid writing until the teacher has
made the specific action decision. Updating submission review state is an
explicit workflow status change; Quillan does not infer it from review
artifacts or exports.

[`comment_bank_contract.md`](comment_bank_contract.md) defines reusable shared
comment source data and its boundary from selected review comments.

[`workspace_lifecycle.md`](workspace_lifecycle.md) defines where records live
in the shared PDS workspace and how active records relate over time. It does
not change the meaning of teacher review defined here.
