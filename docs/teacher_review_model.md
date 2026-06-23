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

This document defines the review model and data boundaries. Quillan currently
validates relevant data contracts, can prepare printable writing-response
pages, and supports direct teacher-entered quick notes and structured tags.
It does not yet implement complete requirements-checking, scoring, feedback,
reporting, or terminal-menu review workflows. Its initial terminal menu is a
navigation skeleton rather than a review implementation. AI tagging, AI
scoring, AI feedback, and automatic grading are not implemented.

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

## Teacher-Review Artifacts

Teacher-review artifacts are records created by the teacher or confirmed
through teacher review:

* `requirements.json`
* `review.json`

`review.json` is the canonical active v0.7 record for teacher-entered notes,
tags, criterion scores, and teacher-selected comments. It is adjacent to and
references `submission.json`, but remains separate so teacher judgment does
not alter the student's original work. `requirements.json` remains a
separate, reserved structural-check support artifact.

Earlier designs named separate `tags.json` and `scores.json` files. Those are
historical concepts, not alternate active v0.7 records. Their content belongs
in `review.json`.

## Derived Exports and Reports

Derived outputs are generated from teacher-reviewed records:

* `feedback.md`
* `reports/standards_summary.csv`
* `reports/class_summary.csv`

`feedback.md` is a possible student-readable export. CSV reports are
aggregations. These outputs are not independent evidence or substitutes for
`review.json`; they should remain traceable to the teacher-confirmed records
from which they were derived.

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

Requirements results may be entered manually, confirmed by the teacher, or
eventually computed for low-risk structural facts. A computed result remains
distinct from scoring and feedback, and the teacher retains responsibility
for interpreting it in context.

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
accepted as explicit teacher input; rubric-profile lookup is not yet
implemented. The workflow does not calculate an overall score, percentage,
grade, weighted result, or mastery result.

## Feedback Philosophy

Feedback is student-readable teacher communication. It may draw on:

* teacher tags;
* teacher notes;
* score records;
* requirements checks; and
* teacher-approved standards profile or shared comment bank comments.

Feedback remains teacher-controlled. Future tooling may help select
teacher-approved language, draft text, or format a feedback file, but the
teacher must review and confirm the communication before it is treated as a
teacher export. Selected reusable or custom comments are stored in
`review.json`; a rendered `feedback.md` remains a derived artifact. Quillan
must not present authoritative AI-generated feedback.

Shared comment banks are reusable teacher-authored source data stored at
`shared/comment_banks/<bank_id>.json`. They are not student records and do
not grade, evaluate, or generate feedback by themselves. A future selection
workflow should copy a comment's teacher-approved language into
`review.json.comments` as a snapshot with `source: "comment_bank"`, the source
`bank_id`, and the source `comment_id`. Comment IDs are bank-local, so the pair
identifies the reusable source comment. The copied label and text remain
stable if the bank later changes; provenance does not create a live reference.
The source contract and future assignment-activation design are defined in
[`comment_bank_contract.md`](comment_bank_contract.md).

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

## Relationship to Existing Documentation

[`data_contracts.md`](data_contracts.md) defines the fields and formats of
individual Quillan records. This document defines the review philosophy and
the conceptual relationships among those records.

[`review_record_contract.md`](review_record_contract.md) defines the canonical
v0.7 `review.json` shape and its identity, state, timestamp, path, reference,
and mutation rules.

[`comment_bank_contract.md`](comment_bank_contract.md) defines reusable shared
comment source data and its boundary from selected review comments.

[`workspace_lifecycle.md`](workspace_lifecycle.md) defines where records live
in the shared PDS workspace and how active records relate over time. It does
not change the meaning of teacher review defined here.

