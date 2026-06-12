# Quillan Printable Writing-Response Template Contract

## Overview

This document defines the MVP contract for one generic printable Quillan
writing-response page. It describes the information and page structure that a
future PDF generator must produce so teachers can distribute identifiable
paper writing surfaces and later connect captured pages to local Quillan
records.

The page is a paper-writing and routing artifact. It does not evaluate student
work, provide feedback, assign a score, or represent a software-made judgment.
Teacher review remains governed by
[`teacher_review_model.md`](teacher_review_model.md).

## Template Purpose

The template supports paper-first and restricted-technology writing workflows
by providing:

* a usable surface for student handwriting;
* human-readable identity information for distribution and handling;
* machine-readable identity for future scan-routing work; and
* durable links to one class, assignment, student, and response-page number.

This is a response-page contract, not a complete assignment-packet contract.
Assignment prompts, directions, requirements, rubrics, standards summaries,
and other packet materials are separate concerns.

## Core Page Unit

One physical response page represents exactly:

* one `class_id`;
* one `assignment_id`;
* one `student_id`;
* one positive integer `page_number`; and
* one lined student writing surface.

A future generator may produce `N` response pages for a student by repeating
this contract with a different `page_number` on each page. The human-readable
identity and PDS1 payload must describe the same class, assignment, student,
and page number.

## Page Format

The MVP page format is:

* US Letter;
* 8.5 by 11 inches; and
* portrait orientation.

Content must stay within printer-safe margins suitable for ordinary school
printers. The identity area, QR code, writing area, and footer must not overlap
or depend on edge-to-edge printing.

Future contracts may add other paper sizes or orientations. Such options do
not change the MVP default and are not layout modes defined here.

## Required Page Elements

Each response page must contain:

* one QR code encoding the canonical Quillan PDS1 response payload;
* the student's human-readable display name;
* the human-readable `student_id`;
* a human-readable class label or `class_id`;
* a human-readable assignment title or `assignment_id`;
* the human-readable `page_number`;
* a large, simple lined writing area; and
* a basic header and/or footer that organizes page identity without
  interfering with writing.

The header is the natural location for student, class, and assignment
information. The QR code and page number may be placed in the header or
footer. This contract does not prescribe typography, exact dimensions, or a
final visual design, but all required elements must remain legible on the
printed page.

## Student Identity

Every page must display both:

* the student display name, for practical teacher distribution and student
  use; and
* `student_id`, for durable routing and record linkage.

The display name is presentation data and must not replace `student_id`.
Teachers should not need to memorize student IDs to distribute pages, while
future processing must not rely on names as stable identifiers.

The page's QR payload must contain `student_id`. It must not contain the
student display name.

For class and assignment information, a friendly class label and assignment
title are preferred for usability. If those display values are unavailable,
the page must display `class_id` and `assignment_id` instead. The underlying
PDS1 payload always uses the identifiers.

## QR / PDS1 Payload

Each page must include a QR code encoding the existing canonical response
payload:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

The payload fields have these meanings:

* `module=quillan` identifies the Paper Data Suite module;
* `class` carries `class_id`;
* `aid` carries `assignment_id`;
* `sid` carries `student_id`;
* `page` carries the positive integer response-page number; and
* `doc=response` identifies the document as a writing-response page.

The PDS1 payload is the machine-readable source of routing identity. Human-
readable labels support people handling the paper, but they do not override
the payload. All displayed identifiers and the displayed page number must
match their corresponding payload values.

The QR code must be visually separate from the writing lines, printed with
sufficient contrast, and given unobstructed whitespace so the page remains
usable for future scanning. Exact QR sizing, rendering, error-correction
settings, image generation, decoding, and scan routing belong to later
implementation work.

Synthetic example:

```text
PDS1|module=quillan|class=english12_period3_synthetic|aid=villainy_final_essay_synthetic|sid=stu_0001|page=1|doc=response
```

## Writing Area

The MVP writing surface is one simple lined area occupying most of the usable
page. It must:

* provide practical spacing for handwriting;
* leave enough uninterrupted room for a student response;
* remain clear of the QR code and identity fields; and
* avoid header, footer, or decorative elements that obscure writing lines.

This contract does not require an exact line count, line spacing, margin
width, or header height. Those measurements should be established and tested
when PDF generation is implemented.

The MVP has one writing-area layout. Cornell notes, graphic organizers,
short-answer boxes, rubric grids, teacher scoring areas, and other specialized
layouts are not variants of this contract.

## Page Numbering

`page_number` is required for every response page and must be a positive
integer.

For `N` pages generated for one student, class, and assignment, pages should
be numbered in response order from `1` through `N`. The number must appear:

* in human-readable form on the printed page; and
* as the `page` value in that page's PDS1 payload.

The displayed form may be `Page 1` or `Page 1 of N`. A total page count is
optional and is not part of the current PDS1 response payload. Page order is
scoped to the combination of class, assignment, and student; it is not a
global page identifier.

## Output Location

Future generated printable response PDFs belong under the assignment-local
template directory:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/templates/
```

This location keeps teacher-distributed materials with the applicable local
assignment. This contract does not define a filename, create the directory,
generate a PDF, or move any files.

## Privacy and Synthetic Data

Generated production pages are local, teacher-controlled artifacts. They may
contain real student display names and IDs when a teacher creates them for
actual classroom use. Those local artifacts must be handled according to the
school's privacy and records practices and must not be committed to this
repository.

Documentation, examples, tests, and fixtures committed to the repository must
use synthetic data only. Do not commit:

* real student names or IDs;
* real rosters;
* real student writing;
* real grades;
* real scanned student work; or
* real parent or guardian information.

Synthetic display names should be obviously fictional, and synthetic
identifiers should follow the same validation rules as production identifiers.

## Relationship to Future Fixtures

This contract is the source of page-template expectations for the synthetic
paper-workflow fixtures planned in issue `#22`. Those fixtures should provide
enough synthetic data to construct and verify a response page, including:

* a valid `class_id`;
* a class display label when the scenario exercises friendly labels;
* a valid `assignment_id`;
* an assignment title;
* a valid `student_id`;
* a synthetic student display name;
* a positive integer page number; and
* a standards profile reference if required by the assignment fixture.

Fixtures should make it possible to verify that human-readable fields agree
with the PDS1 identity fields without introducing real student information.
This document does not create or prescribe the storage schema for those
fixtures.

## Out of Scope

This contract does not implement or define:

* PDF or QR image generation;
* scan decoding, routing, filing, or OCR;
* complete printable assignment packets;
* prompt, rubric, standards-summary, or graphic-organizer pages;
* multiple response-layout modes;
* teacher scoring areas;
* synthetic fixture files;
* assignment, submission, or standards model redesign;
* requirements checking, tagging, scoring, feedback, or reporting;
* AI tagging, scoring, feedback, or automatic grading; or
* CLI, menu, or workspace-settings workflows.

The field-level PDS1 contract remains documented in
[`data_contracts.md`](data_contracts.md), and the intended assignment-local
directory remains documented in
[`workspace_lifecycle.md`](workspace_lifecycle.md).
