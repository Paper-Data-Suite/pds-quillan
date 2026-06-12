# Quillan Teacher-Review Model

## Overview

Quillan's review model is teacher-controlled. Quillan preserves student
writing, organizes teacher-review artifacts, and reduces clerical friction,
but it does not replace the teacher's professional judgment.

The model keeps source evidence, teacher-review artifacts, and derived reports
distinct. Software may validate records, organize observations, format
teacher-approved language, and summarize confirmed records. It must not
present an unconfirmed software judgment as a teacher evaluation or encourage
review without reading the student's work.

## Source Evidence

Source evidence is the student-produced writing and the metadata needed to
identify and preserve it:

* `submission.txt`
* `submission.json`

The writing is the student's work. The metadata records its identity,
provenance, capture time, lifecycle status, and version. Source evidence does
not contain teacher tags, scores, feedback, or reports.

Keeping source evidence separate allows a teacher to compare later review
artifacts with the writing that was actually submitted.

## Teacher-Review Artifacts

Teacher-review artifacts are records created by the teacher or confirmed
through teacher review:

* `requirements.json`
* `tags.json`
* `scores.json`
* `feedback.md`

These records describe structural checks, observations, decisions, and
communication associated with a submission. They remain connected to, but
separate from, the source evidence so teacher judgment does not alter the
student's original work.

## Derived Reports

Derived reports are aggregations generated from teacher-reviewed records:

* `reports/standards_summary.csv`
* `reports/class_summary.csv`

Reports are not independent evidence. They summarize existing
teacher-confirmed observations and decisions and should remain traceable to
the records from which they were derived.

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

## Feedback Philosophy

Feedback is student-readable teacher communication. It may draw on:

* teacher tags;
* teacher notes;
* score records;
* requirements checks; and
* standards profile comments.

Feedback remains teacher-controlled. Future tooling may help select
teacher-approved language, draft text, or format a feedback file, but the
teacher must review and confirm the communication before it is treated as a
teacher-review artifact. Quillan must not present authoritative AI-generated
feedback.

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

[`workspace_lifecycle.md`](workspace_lifecycle.md) defines where records live
in the shared PDS workspace and how active records relate over time. It does
not change the meaning of teacher review defined here.

