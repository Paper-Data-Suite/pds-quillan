# NJ ELA Starter Review Materials

Quillan includes optional New Jersey ELA starter review materials for high
school writing review. They cover:

* English 10 / grades 9-10 standards references;
* English 12 / grades 11-12 standards references.

These materials are teacher-editable starter review materials aligned to
common high school ELA writing tasks and 2023 NJSLS-ELA references. They are
not official state curriculum, not district grading policy, and not automatic
evaluation.

Status: these files are legacy/inactive v1 review-material examples for
comment-bank, tag-bank, and rubric compatibility work. They are not the active
v0.8.6 standards-based review workflow, which uses assignment Focus Standards,
review units, overall Focus Standard ratings, Focus Standard feedback
composition, and reusable Focus Standard comments.

Quillan is not an ELA-only grader. These files are one optional historical
starter pack for ELA classrooms; Quillan's active assignment, submission, and
review-record structures remain subject-agnostic. For the active
standards-based review model, see
[`prepared_review_workflow.md`](prepared_review_workflow.md).

## What Is Included

Each grade band includes comment banks, tag banks, and rubrics for:

* argument and persuasive writing;
* informational, expository, and explanatory writing;
* literary analysis and comparative analysis;
* research writing;
* narrative, memoir, short story, poetry, and creative writing;
* reflection, journal, open response, short response, and response to
  literature.

The source files live under:

```text
examples/comment_banks/
examples/tag_banks/
examples/rubrics/
```

## Files

English 10 comment banks:

```text
ela10_argument_writing.json
ela10_informational_writing.json
ela10_literary_analysis.json
ela10_research_writing.json
ela10_narrative_creative_writing.json
ela10_reflection_short_response.json
```

English 12 comment banks:

```text
ela12_argument_writing.json
ela12_informational_writing.json
ela12_literary_analysis.json
ela12_research_writing.json
ela12_narrative_creative_writing.json
ela12_reflection_short_response.json
```

Matching tag banks use the same stems with `_tags.json`. Matching rubrics use
the same stems with `_rubric.json`.

## Standards Metadata

The files use durable `njsls-ela:` standard IDs selected from the local
`2023_NJSLS_ELA.md` reference. English 10 materials use `9-10` IDs. English 12
materials use `11-12` IDs.

Standards references are metadata only. They do not import standards, create
standards profiles, record standards usage, infer mastery, calculate grades,
or validate student writing.

## Installation

Use:

```text
Quillan -> Review Student Work -> Manage Review Materials -> Starter Materials
```

The starter-material workflow can preview, validate, install all, or install
selected materials. Installation copies validated JSON files into:

```text
shared/comment_banks/
shared/tag_banks/
shared/rubrics/
```

Existing files are skipped by default. Replacement requires the exact
confirmation text `OVERWRITE`.

## Safety Boundaries

Installing NJ ELA starter materials does not create assignments, rosters,
scans, submissions, review records, exports, pds-core standards files,
pds-core standards profiles, or pds-core route helpers.

The materials contain reusable teacher-facing review language, tags, rubric
criteria, and standards metadata. They do not run OCR, parse student writing,
generate AI feedback, recommend comments automatically, score work, or change
student data.
