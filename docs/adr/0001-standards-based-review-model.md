# ADR 0001: Adopt Standards-Based Review Model

## Status

Accepted

## Date

2026-07-02

## Issue

#214

## Milestone

v0.8.6 — Standards-Based Workflow Redesign

## Context

Quillan is a local-first Paper Data Suite module for reviewing written student work. Its existing review model is teacher-controlled: Quillan preserves student evidence, organizes teacher-entered review artifacts, and produces derived exports and reports. It must not read student work automatically, infer standards mastery, generate scores, generate feedback, or replace the teacher’s professional judgment.

The current v0.7 review model is organized around generic review artifacts:

```text
tags
comments
rubrics / criterion scores
notes
requirement checks
exports
```

The current assignment contract includes fields such as `standards_profile_id`, `focus_standards`, `tagging_mode`, `basic_requirements`, and `rubric_id`. The current review record contract stores teacher-entered data in arrays such as `notes`, `tags`, `scores`, `comments`, and `requirement_checks`. Current prepared-review documentation describes a workflow in which teachers prepare reusable comment banks, tag banks, and rubrics before review, then select or snapshot those artifacts while reviewing student evidence.

This model is technically functional, but the first full Quillan simulation showed that the student-review phase feels disconnected from classroom practice. The teacher has to move through artifact-centered workflows such as:

```text
choose tag bank -> choose tag category -> choose tag
choose comment bank -> choose comment category -> choose comment
choose rubric -> choose criterion -> choose score level
```

Those workflows place generic tags, comments, rubrics, and review materials between the teacher and the central question:

```text
How does this student’s writing perform against the assignment’s Focus Standards?
```

The v0.8.6 redesign concept document, `docs/standards_based_review_redesign.md`, defines a new target model:

```text
student evidence -> review unit -> focus standard -> teacher judgment -> feedback/reporting
```

In this model, Focus Standards are the organizing structure for review, scoring, feedback, export, and reporting. Review units are assignment-defined units of student evidence, such as paragraphs, stanzas, pages, sections, scenes, responses, or whole submissions. For an English essay, the review unit will often be a paragraph. For another discipline or assignment type, a different unit may be more appropriate.

This ADR records the architectural decision to adopt that standards-based model as Quillan’s target review architecture.

## Decision

Quillan will replace the generic tags/comments/rubrics-centered review model with a standards-based review model centered on Focus Standards and assignment-defined review units.

The primary review relationship will be:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

The redesigned review workflow will be organized around:

1. opening student evidence;
2. recording minimum requirement checks;
3. optionally returning work without full scoring when minimum requirements are not met;
4. entering the number of assignment-defined review units in the student submission;
5. evaluating each review unit against each Focus Standard;
6. summarizing evidence by Focus Standard;
7. assigning an overall rating for each Focus Standard;
8. composing student feedback organized by Focus Standard;
9. exporting student-facing feedback, with PDF as a first-class output; and
10. generating standards-based class and student reports.

The old generic artifacts are not the target architecture for v0.8.6:

* Generic tags are replaced by review-unit Focus Standard observations.
* Generic rubric criteria and criterion scores are replaced by Focus Standard rating scales and overall Focus Standard ratings.
* Generic prebuilt comment banks are replaced by reusable Focus Standard comments that grow from actual teacher use.
* Standards profiles remain essential because assignments choose Focus Standards from standards profiles.
* Minimum requirement checks remain early in the workflow and stay separate from standards ratings.

The redesigned model remains teacher-controlled. Quillan will organize teacher judgments, validate records, format exports, and summarize confirmed review data. Quillan will not infer scores, assign standards mastery, parse student writing, run OCR to evaluate writing, generate feedback automatically, or grade student work.

## Consequences

### Assignment records

Assignment records will need to change.

The current assignment shape includes `tagging_mode` and `rubric_id`, both of which belong to the old tag/rubric-centered model. The redesigned assignment record should instead make the standards-based review path explicit.

Future assignment contracts should support:

* assignment identity;
* class identity, eventually including multiple classes where supported;
* assignment title;
* student-facing prompt;
* writing type;
* standards profile ID;
* Focus Standard IDs;
* review-unit type;
* review-unit singular and plural teacher-facing labels;
* rating scale;
* minimum requirements; and
* minimum-requirement return policy, if supported.

Conceptually, an assignment should be able to express:

```json
{
  "assignment_id": "coming-of-age_literary_analysis",
  "title": "Coming-of-Age Literary Analysis",
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
      { "value": 1, "label": "Developing" },
      { "value": 2, "label": "Approaching" },
      { "value": 3, "label": "Meeting" },
      { "value": 4, "label": "Exceeding" }
    ]
  },
  "basic_requirements": {
    "paragraphs_min": 1,
    "required_elements": [
      "textual evidence",
      "explanation"
    ]
  }
}
```

This ADR does not finalize that schema. The binding assignment contract belongs in the later assignment-contract issue.

### Review records

Review records will need to change substantially.

The current `review.json` stores independent arrays for notes, tags, scores, comments, and requirement checks. In the standards-based model, the review record should instead make review-unit observations and Focus Standard ratings the central data.

Future review records should support:

* identity and submission reference;
* minimum requirement checks;
* minimum-requirement return outcome, if used;
* review units;
* review-unit Focus Standard observations;
* standard applicability;
* evidence presence;
* review-unit rating;
* optional rationale/comment;
* overall Focus Standard ratings;
* overall Focus Standard rationales;
* feedback inclusion choices;
* student feedback comments by Focus Standard; and
* export status or export metadata.

Conceptually, the review record should be able to express:

```json
{
  "student_id": "10001",
  "assignment_id": "coming-of-age_literary_analysis",
  "requirement_checks": [],
  "review_units": [
    {
      "unit_id": "paragraph_1",
      "label": "Paragraph 1",
      "sequence": 1,
      "standard_observations": [
        {
          "standard_id": "njsls-ela:RL.CR.9-10.1",
          "applicable": true,
          "evidence_present": true,
          "rating": 2,
          "rationale": "The paragraph uses evidence from the story, but the explanation is still general.",
          "include_in_feedback": false
        }
      ]
    }
  ],
  "overall_standard_ratings": [
    {
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "rating": 3,
      "rationale": "Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.",
      "include_in_feedback": true
    }
  ],
  "feedback": {
    "include_review_unit_observations": false,
    "include_overall_standard_ratings": true,
    "standard_comments": [
      {
        "standard_id": "njsls-ela:RL.CR.9-10.1",
        "text": "Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.",
        "include_in_feedback": true
      }
    ]
  }
}
```

This ADR does not finalize the new review schema. The binding review-record contract belongs in the later review-record contract issue.

### Submission manifests

The existing `submission.json` evidence manifest should remain conceptually separate from teacher review.

The submission manifest answers:

```text
What evidence exists?
Where did it come from?
Which evidence is selected?
What is the evidence-management state?
```

The review record answers:

```text
What did the teacher record about the evidence?
How did the teacher evaluate the evidence against Focus Standards?
What feedback and reporting data should be derived from that review?
```

The standards-based redesign should preserve this boundary. Scan routing, retained-source provenance, evidence selection, page state, and rescan state should not be mixed with standards ratings or feedback decisions.

### Minimum requirements

Minimum requirement checks remain part of the review model.

They should stay early in the workflow and remain teacher-controlled. Quillan should not infer paragraph counts, word counts, or required-element presence from student writing.

The redesign adds a clearer workflow gate: when minimum requirements are not met, the teacher should be able to return the work without completing full Focus Standard review.

A submission returned for unmet minimum requirements should not be treated as a zero, a completed standards review, or a normal scored submission. It should be represented explicitly as a review outcome.

### Feedback exports

Student feedback export must be redesigned.

The current export is Markdown-only and renders class ID, assignment ID, student ID, criterion scores, and included comments. The standards-based model requires feedback organized around Focus Standards.

Future feedback exports should support:

* polished PDF output as a first-class deliverable;
* optional Markdown as a companion artifact;
* student name, with student ID only where useful;
* assignment title;
* class information;
* generated date;
* selected overall Focus Standard ratings;
* selected overall rationales;
* selected review-unit observations, when the teacher chooses to include them;
* teacher-written or reusable comments organized by Focus Standard; and
* clear omission of teacher-only internal metadata.

The export should not include unselected rationales, private notes, internal JSON fields, hidden workflow metadata, or obsolete tag/comment/rubric provenance.

### Reports

Reports must become standards-based.

The current standards summary is derived from standards referenced by tags and selected comments. The current class summary includes score counts and arithmetic score totals from criterion-score records. Those summaries reflect the old review model.

Future reports should aggregate teacher-confirmed standards-based review records.

Reports should help teachers answer questions such as:

* Which Focus Standards are students meeting?
* Which Focus Standards are students approaching or developing?
* Which students need support on a particular Focus Standard?
* Which assignments provide evidence for each Focus Standard?
* How does a student’s performance on a Focus Standard change over time?

Reports should not be based on generic tag counts or generic rubric criteria. They should be based primarily on overall Focus Standard ratings and, where useful, review-unit observations.

Reports remain derived artifacts. They must not replace review records or present unconfirmed software judgments.

### Reusable comments

Reusable comments remain useful, but the old prebuilt generic comment-bank model is no longer the target architecture.

The redesigned model should let reusable comments grow from real teacher use. During feedback composition, a teacher should be able to:

1. write a new comment for a Focus Standard;
2. use an existing reusable comment for that Focus Standard; or
3. write a new comment and save it for future reuse.

Reusable comments should be associated with useful context such as:

* standard ID;
* writing type;
* rating level; and
* grade band, course, or local scope where useful.

This approach preserves the benefit of reusable language without forcing teachers to build large generic comment banks before review.

### Old review-material workflows

The existing generic review-material workflows are not the target architecture for v0.8.6.

This includes old generic workflows for:

* tag banks;
* comment banks;
* rubrics / scoring profiles;
* review-material browsing;
* tag-centered review;
* comment-bank-centered review; and
* rubric-criterion scoring.

These workflows should be removed, replaced, or explicitly deprecated as the standards-based redesign is implemented.

The codebase should not preserve both complete systems indefinitely. Keeping the old generic review-material system alongside the new standards-based system would increase code bloat, menu confusion, stale tests, obsolete examples, and unclear teacher workflows.

Temporary compatibility shims may be acceptable during implementation, but the target architecture is standards-based review.

### Tests and examples

Tests and examples that assume the old tag/comment/rubric-centered model will need to be removed, rewritten, or moved to legacy coverage.

New tests and examples should cover:

* assignment creation with Focus Standards and review-unit configuration;
* minimum requirement checks and return-without-full-review behavior;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* feedback composition by Focus Standard;
* reusable Focus Standard comments;
* student-facing PDF export;
* standards-based class and student reports; and
* preservation of the source evidence / review record boundary.

Examples must remain synthetic or explicitly marked starter-material content. Real student names, writing, scans, scores, grades, feedback, or personally identifiable information must not be committed.

## Rejected Alternatives

### Alternative 1: Keep the old tag/comment/rubric model and polish the UX

This was rejected.

The simulation exposed many UX issues: teachers are dumped back to menus too often, score selection is numerically ambiguous, standard requirement checks and return-without-full-review behavior;

* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* feedback composition by Focus Standard;
* reusable Focus Standard comments;
* student-facing PDF export;
* standards-based class and student reports; and
* preservation of the source evidence / review record boundary.

Examples must remain synthetic or explicitly marked starter-material content. Real student names, writing, scans, scores, grades, feedback, or personally identifiable information must metadata is hidden in some places, student names are missing in key screens, and starter rubric language needs editorial review.

Those issues are real, but fixing them would not solve the deeper problem. The old model still asks teachers to manipulate generic artifacts rather than directly evaluate student evidence against Focus Standards.

Polishing the old workflow would improve the surface while preserving the wrong center of gravity.

### Alternative 2: Keep tags, comments, and rubrics as first-class concepts but rename them

This was rejected.

Renaming old artifacts would not remove the underlying indirection. If a “tag” is really a review-unit Focus Standard observation, it should be modeled as a review-unit Focus Standard observation. If a rubric score is really an overall rating for a Focus Standard, it should be modeled as an overall Focus Standard rating.

The redesign should not merely relabel old concepts. It should change the data model and workflow so the standards-based relationship is explicit.

### Alternative 3: Treat standards as optional metadata attached to old artifacts

This was rejected.

The current model lets tags and selected comments carry optional `standard_id` values, and assignments already store `focus_standards`. However, standards are still secondary to artifact workflows. The teacher first chooses a tag, comment, or rubric criterion, and standards may or may not be attached.

In the redesigned model, standards are not optional metadata layered on top of tags, comments, and rubric criteria. Standards are the organizing structure for review, scoring, feedback, export, and reporting.

### Alternative 4: Build better starter tag/comment/rubric banks

This was rejected as the main solution.

Starter materials can be useful, but simulation showed that prebuilt generic materials can be awkward, overbroad, or misaligned with a specific assignment. A broad rubric may include criteria that do not apply to a particular writing task. Prebuilt feedback language may not match the teacher’s purpose.

The redesign should let reusable comments grow from actual teacher use and attach those comments to standards, writing types, and rating levels.

### Alternative 5: Keep the old model and add the new model alongside it permanently

This was rejected as the target architecture.

Maintaining two complete review systems would increase code complexity and teacher confusion. It would also make contracts, examples, exports, reports, and tests harder to reason about.

A temporary transition period may be necessary while v0.8.6 is implemented, but the long-term target is one standards-based review model.

### Alternative 6: Make Quillan a generic grading/rubric engine

This was rejected.

Quillan’s purpose is not to become a generic gradebook or rubric engine. Its purpose is to support teacher-controlled review of written student evidence in a Paper Data Suite workflow.

The redesigned model should support standards-based ratings and reports, but it should not automatically calculate grades, percentages, weighted results, mastery conclusions, or gradebook-ready scores unless a later decision explicitly adds that behavior.

### Alternative 7: Use AI, OCR, or automatic parsing to detect standards performance

This was rejected for the v0.8.6 model.

Quillan should remain teacher-controlled. It may preserve evidence, route scans, organize records, validate data, format feedback, and summarize teacher-confirmed review data. It should not automatically read student work, infer paragraph counts, identify textual evidence, score standards, or generate student feedback.

Later tools may assist with transcription or accessibility, but this ADR does not authorize automatic standards evaluation.

## Follow-Up Work

This ADR guides later v0.8.6 issues. Follow-up work includes:

1. redesigning the assignment contract for Focus Standards and review units;
2. redesigning the review record contract for standards-based observations;
3. designing reusable Focus Standard comments;
4. redesigning student feedback export;
5. designing standards-based class and standards reports;
6. triaging existing issues against the redesign;
7. auditing the current codebase against the new concept and contracts;
8. removing obsolete generic review-material workflows;
9. implementing assignment creation updates;
10. implementing review-unit Focus Standard observations;
11. implementing overall Focus Standard ratings;
12. implementing the minimum-requirements return workflow;
13. implementing the Focus Standard feedback composer;
14. implementing student-facing PDF export;
15. implementing standards-based class and standards summaries;
16. replacing obsolete tests and examples; and
17. running a second full end-to-end simulation.

The concept document `docs/standards_based_review_redesign.md` is the guiding narrative document for these issues. This ADR records the architectural decision.

## Non-Goals

This ADR does not implement the new workflow.

This ADR does not define final JSON schemas.

This ADR does not rewrite the assignment contract, review record contract, feedback export contract, or report contracts.

This ADR does not delete old tag, comment, rubric, or review-material code.

This ADR does not migrate old review records.

This ADR does not decide whether old pre-v0.8.6 review records will be migrated, left readable as legacy records, or treated as incompatible test artifacts.

This ADR does not define gradebook behavior or automatic grade calculation.

This ADR does not authorize AI scoring, AI feedback, OCR-based evaluation, automatic standards detection, or automatic paragraph detection.

## Acceptance Criteria for Later Implementation

The decision recorded here is fully realized when:

* assignments store Focus Standards and review-unit configuration;
* minimum requirement checks remain early in review and can gate full scoring;
* review records store review-unit Focus Standard observations;
* review records store overall Focus Standard ratings;
* generic tags are no longer the primary observation mechanism;
* generic rubric criteria are no longer the primary scoring mechanism;
* generic prebuilt comment banks are replaced by reusable Focus Standard comments;
* student feedback is composed around Focus Standards;
* student feedback can be exported as a polished PDF;
* reports aggregate standards-based ratings and observations;
* obsolete tag/comment/rubric-centered menus, examples, tests, and docs are removed or clearly deprecated; and
* a second end-to-end simulation confirms that the new workflow is coherent for a real teacher review task.

## Summary

Quillan’s v0.7 review model organizes teacher review around reusable materials and generic artifacts:

```text
tags -> comments -> rubrics -> scores -> exports
```

The v0.8.6 target model organizes teacher review around standards-based evidence evaluation:

```text
minimum requirements -> review-unit observations -> overall Focus Standard ratings -> student feedback -> standards reporting
```

This decision makes Focus Standards and review units the center of Quillan’s review architecture. It preserves the teacher-controlled, local-first, auditable nature of Quillan while replacing the disconnected tag/comment/rubric-centered workflow with a clearer standards-based model.
