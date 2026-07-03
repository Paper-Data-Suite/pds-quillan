# Standards-Based Review Redesign

## Purpose

This document defines the concept for Quillan’s v0.8.6 standards-based workflow redesign.

The first full Quillan simulation showed that many surrounding workflows are usable:

* roster creation
* assignment creation
* printable response packet generation
* QR scan intake and routing
* submission assembly
* student selection
* evidence viewing
* minimum-requirement checks

The major weakness is the student-review phase after minimum requirements. The current review workflow is organized around separate artifacts such as tags, comments, rubrics, scores, and review materials. Those artifacts are technically functional, but they make review feel disconnected from the teacher’s actual task: evaluating student writing against the assignment’s Focus Standards.

The redesigned model makes Focus Standards the center of review, scoring, feedback, export, and reporting.

Quillan should not be a generic tag/comment/rubric system.

Quillan should be a standards-based written-work review system.

The central relationship should be:

```text
student evidence -> review unit -> focus standard -> teacher judgment -> feedback/reporting
```

For English writing assignments, a review unit will often be a paragraph. For other assignment types, a review unit may be a stanza, page, section, scene, response, or whole submission. The assignment should define the review-unit type, and the review workflow should use the teacher-facing label for that type.

## Design Principles

### Focus Standards are the center of review

A Quillan assignment should identify the Focus Standards being assessed. Review should then revolve around those standards.

The teacher should not have to move through generic tag banks, comment banks, and rubric criteria in order to reach the standards. The review workflow should directly ask how the student’s evidence performs against each Focus Standard.

### Review moves from evidence to standards to feedback

The natural review sequence is:

```text
student work -> review-unit observations -> overall standard ratings -> student feedback
```

Quillan should guide the teacher through that sequence.

The teacher first looks at the student’s evidence. Then the teacher records observations about specific review units and Focus Standards. Then the teacher assigns overall ratings for each Focus Standard. Then the teacher decides what feedback should be shown to the student.

### Minimum requirements come before full review

Minimum requirements should be checked before full standards review.

If a submission does not meet basic assignment requirements, the teacher should be able to return the work with requirement-focused feedback instead of completing a full review.

For example, if an assignment requires textual evidence and explanation, but the student submitted a response with no textual evidence, Quillan should let the teacher stop the full review process and return the work for revision.

### Review-unit observations support overall ratings

A teacher’s overall rating for a Focus Standard should be grounded in review-unit-level evidence.

For example, a student’s overall rating for textual evidence should be informed by how that student used evidence in each paragraph or other configured review unit.

Quillan should help the teacher see that pattern before assigning the overall standard rating.

### Feedback is organized around Focus Standards

Student feedback should be organized around the Focus Standards assessed by the assignment.

The teacher should be able to decide whether to include:

* overall Focus Standard ratings
* overall Focus Standard rationales
* selected review-unit observations
* teacher-written comments
* reusable comments tied to the Focus Standard

Feedback should help the student understand how their work performed against the standards, not just present generic comments.

### Reporting aggregates standards performance

Quillan reports should help teachers understand standards performance across students and assignments.

Reports should answer questions such as:

* Which Focus Standards are students meeting?
* Which Focus Standards are students approaching or developing?
* Which students need support on a particular standard?
* Which assignments provide evidence for each standard?
* How does a student’s performance on a standard change over time?

Reporting should aggregate standards performance, not generic tag counts or generic rubric criteria.

### Reusable comments grow from real use

Reusable comments should not require a teacher to build a large comment bank before review begins.

Instead, reusable comments should be built from actual teacher use. When a teacher writes a useful student-facing comment for a Focus Standard, Quillan should allow the teacher to save that comment for later reuse.

Reusable comments should be organized by useful review context, such as:

* standard ID
* writing type
* rating level
* course or grade band, where useful

### Quillan remains teacher-controlled

Quillan should not infer standards performance, generate scores, or automatically produce feedback from student writing.

The teacher makes review decisions. Quillan organizes those decisions, stores them consistently, and turns them into useful feedback and reports.

## Retained Workflow Areas

The redesign should preserve the parts of Quillan that worked well in simulation.

### Roster creation

Roster creation should remain mostly intact.

The known improvement is school-year metadata. Classes should be tied to an academic year so that similar class names or periods can be reused across years without ambiguity.

### Assignment creation

Assignment creation should remain, but it needs to become more standards-based.

Assignment creation should collect or confirm:

* class or classes using the assignment
* assignment title
* student-facing prompt
* writing type
* standards profile
* Focus Standards
* review-unit type and teacher-facing labels
* minimum requirements
* rating scale
* whether unmet minimum requirements may be returned without full review

Assignment creation should make the standards-based review path clear before student work is reviewed.

### Printable response packets

Printable response packet generation should remain.

The packet workflow already supports paper-based writing and QR-assisted routing. Future improvements may include better direct file-opening behavior after packet generation, but the core workflow is retained.

### QR scan intake and routing

QR scan intake and routing should remain.

The simulation showed that QR-based routing is one of Quillan’s strongest pieces. The redesign should not disturb this unless required by downstream review-record changes.

### Submission assembly

Submission assembly should remain.

The assembled submission remains the teacher’s evidence source for review. Review-record redesign should not require changes to the basic idea that routed pages are assembled into a student submission.

### Student selection

Choosing a student for review should remain.

The known improvement is that screens should show student names, not only student IDs, when roster metadata is available.

### Evidence viewing

Evidence viewing should remain.

Multi-page evidence opening is necessary. A future improvement may be to provide a single scrollable document or PDF rather than multiple PNG windows, but the core need is the same: the teacher must be able to inspect the student’s actual submitted work while reviewing.

### Minimum requirement checks

Minimum requirement checks should remain and become the first decision point in full review.

The simulation showed that this workflow is clear and useful. The redesign should keep it, then add a clear gate for submissions that do not meet minimum requirements.

## New Review Flow

The redesigned student-review workflow should follow this sequence:

```text
1. Open student evidence
2. Record minimum requirement checks
3. If requirements are unmet, optionally return the work without full scoring
4. Enter the number of review units the student wrote
5. Review each review unit against each Focus Standard
6. View a Focus Standard evidence summary
7. Assign an overall rating for each Focus Standard
8. Compose student feedback organized by Focus Standard
9. Export student feedback, including PDF output
10. Mark review/export status clearly
```

This order matters.

The teacher should not be asked to choose among generic review artifacts. The workflow should guide the teacher through the actual review process.

## Minimum Requirement Gate

Minimum requirements are basic assignment conditions that must be checked before full standards review.

Examples include:

* minimum number of paragraphs
* required textual evidence
* required explanation
* required claim
* required citation
* required source use
* required submission pages

If minimum requirements are not met, Quillan should present a clear gate.

Example:

```text
Minimum requirements were not met.

Unmet requirements:
- Required element: textual evidence
- Minimum paragraphs: expected 3, found 1

Choose an action:

1. Return to student without full scoring
2. Continue full review anyway
3. Add requirement feedback
4. Export minimum-requirements feedback
B. Back
```

Returning work without full scoring should not be treated as a zero or a completed full review. It is a separate review outcome indicating that the submission was not ready for full standards scoring.

This supports realistic classroom practice. Teachers often do not want to complete detailed standards scoring on a submission that is incomplete, missing required evidence, or not reviewable.

## Review Units

A review unit is the assignment-defined unit of student evidence that the teacher reviews against the Focus Standards.

Examples of review units include:

* paragraph
* stanza
* page
* section
* scene
* response
* whole submission
* custom unit

For an English essay, the review unit will often be `paragraph`.

For a poetry assignment, the review unit might be `stanza`.

For a drama assignment, the review unit might be `scene`.

For a short constructed response, the review unit might be `whole response`.

The internal model may use the term `review_unit`, but teacher-facing screens should use the configured label.

Example assignment configuration, conceptually:

```text
Review-unit type: paragraph
Singular label: paragraph
Plural label: paragraphs
```

Teacher-facing prompt:

```text
How many paragraphs did the student write?
```

Not:

```text
How many review units did the student write?
```

The review-unit type belongs in assignment creation because it determines how review will proceed. A teacher should not have to reconfigure the review structure for every student unless a particular student’s submission requires an exception.

## Review-Unit Focus Standard Observations

After minimum requirements are checked, Quillan should ask how many review units the student wrote.

Then Quillan should iterate through each review unit and each Focus Standard.

Example:

```text
Paragraph 1

Focus Standard:
RL.CR.9-10.1 — Cite strong and thorough textual evidence to support analysis.

Standard applicable? Y/N
Evidence of standard? Y/N

Rating:
1. Developing
2. Approaching
3. Meeting
4. Exceeding

Rationale/comment, optional:
```

Each review-unit Focus Standard observation should capture:

* student ID
* assignment ID
* review unit
* Focus Standard ID
* whether the standard is applicable to that unit
* whether evidence of the standard is present
* rating, when applicable
* optional rationale/comment
* optional feedback-inclusion choice, if appropriate

### Applicability

Not every Focus Standard applies to every review unit.

For example, in a multi-paragraph literary analysis essay, the interpretive claim standard may apply most directly to the introduction or thesis paragraph. Textual evidence may apply more strongly to body paragraphs. Conventions may apply across the whole response rather than to one paragraph in isolation.

Quillan should let the teacher mark a standard as not applicable for a particular review unit.

Not applicable is not the same as no evidence.

### Evidence present

Evidence present means that the review unit contains some evidence related to the standard.

A paragraph may contain evidence of a standard but still receive a low rating. For example, a paragraph might include textual evidence but explain it weakly.

Evidence present is not the same as meeting the standard.

### Rating

The default standards rating scale should be:

```text
1. Developing
2. Approaching
3. Meeting
4. Exceeding
```

This is not a percentage, grade, or generic rubric score. It is the teacher’s judgment of performance against a Focus Standard in a review unit.

Future versions may allow assignment-specific or district-specific scales, but the concept remains the same: the rating is tied directly to a Focus Standard.

### Rationale

The rationale is an optional teacher-entered explanation of the observation.

Examples:

```text
The paragraph includes a relevant quotation, but the explanation is general.
```

```text
The paragraph clearly explains how the object carries memory and grief.
```

```text
The standard is not applicable to this paragraph because this paragraph only introduces the topic.
```

Rationales may later help the teacher compose student feedback, but they should not automatically become student-facing unless the teacher chooses to include them.

## Overall Focus Standard Ratings

After review-unit observations are complete, Quillan should summarize the evidence for each Focus Standard.

The teacher should then assign an overall rating for that Focus Standard.

Example:

```text
Focus Standard: RL.CR.9-10.1
Cite strong and thorough textual evidence to support analysis.

Paragraph 1
Applicable: yes
Evidence: yes
Rating: Approaching
Rationale: The paragraph uses evidence, but explanation is general.

Paragraph 2
Applicable: yes
Evidence: yes
Rating: Meeting
Rationale: The quotation is relevant and clearly explained.

Paragraph 3
Applicable: yes
Evidence: yes
Rating: Meeting
Rationale: Evidence is integrated smoothly and supports the interpretation.

Overall Focus Standard Rating:
1. Developing
2. Approaching
3. Meeting
4. Exceeding

Overall rationale/comment, optional:
```

The overall Focus Standard rating is the primary scoring object in the redesigned model.

It replaces generic rubric scoring as the main way Quillan records performance.

This does not mean rubrics are impossible. A rating scale may still define what Developing, Approaching, Meeting, and Exceeding mean. But the teacher’s score should be attached to the Focus Standard, not to a generic criterion that may or may not apply to the assignment.

## Student Feedback

Student feedback should come after review-unit observations and overall Focus Standard ratings.

Feedback should be organized around Focus Standards.

For each Focus Standard, the teacher should be able to decide whether to include:

* the overall rating
* the overall rationale
* selected review-unit observations
* selected review-unit rationales
* a new teacher-written comment
* a reusable comment

Example:

```text
Focus Standard: RL.CR.9-10.1
Overall rating: Meeting
Overall rationale: Across the response, the evidence is relevant and usually well explained.

Include this rating in student feedback? Y/N
Include this rationale in student feedback? Y/N
Include paragraph-level observations? Y/N
Add student feedback comment? Y/N
```

If the teacher chooses to add a comment:

```text
Add student feedback comment?

1. Use reusable comment
2. Write new comment
3. Write new comment and save for future reuse
B. Back
```

A reusable comment should be tied to useful context, such as:

* standard ID
* writing type
* rating level
* grade band or course, where useful

Example reusable comment:

```text
Standard: RL.CR.9-10.1
Writing type: literary_analysis
Rating: Approaching

Comment:
Your evidence is relevant, but your explanation needs to show more clearly how the quotation supports your interpretation.
```

This approach lets the comment library grow from authentic teacher use.

The teacher does not need to create a large prebuilt comment bank before review. The teacher writes real comments during real review and saves the ones worth reusing.

## Export

Student-facing export should produce a polished PDF as a first-class output.

Markdown may remain as an optional companion artifact, but PDF is the practical teacher/student/parent deliverable.

The PDF should include:

* student name
* student ID, if useful
* class information
* assignment title
* generated date
* Focus Standard ratings selected for feedback
* selected rationales
* selected comments
* optional review-unit observations, if the teacher chooses to include them

The PDF should not include:

* teacher-only internal notes
* internal JSON metadata
* hidden workflow fields
* unselected rationales
* private review artifacts
* implementation details

Example student-facing feedback structure:

```text
Feedback Report

Student: Ava Martinez (10001)
Class: English 10 Simulation
Assignment: Coming-of-Age Literary Analysis
Generated: July 2, 2026

Focus Standard: RL.CR.9-10.1
Cite strong and thorough textual evidence to support analysis.

Rating: Meeting

Feedback:
Your evidence is relevant and usually well explained. To improve, make sure each quotation is followed by analysis that explains how it supports your interpretation.

Focus Standard: RL.CI.9-10.2
Determine a theme or central idea and analyze its development.

Rating: Approaching

Feedback:
You identify an important idea in the story, but your explanation should more clearly show how that idea develops across the response.
```

A teacher should be able to decide how much detail to include. Some situations call for brief feedback. Others call for paragraph-level detail.

## Reporting

Quillan reports should be standards-based.

Reports should help teachers answer questions such as:

* Which Focus Standards are students meeting?
* Which Focus Standards are students approaching or developing?
* Which students need support on a particular standard?
* Which review units show the strongest evidence?
* Which assignments provide evidence for each standard?
* How does performance on a standard change over time?

Possible report types:

### Student standard summary

Shows one student’s performance across Focus Standards for one assignment.

Example:

```text
Student: Ava Martinez
Assignment: Coming-of-Age Literary Analysis

RL.CR.9-10.1: Meeting
RL.CI.9-10.2: Approaching
W.AW.9-10.1: Approaching
```

### Class standard summary

Shows class performance by Focus Standard.

Example:

```text
Standard: RL.CR.9-10.1

Developing: 4 students
Approaching: 8 students
Meeting: 12 students
Exceeding: 3 students
```

### Assignment evidence summary

Shows which assignments generated evidence for which standards.

Example:

```text
Assignment: Coming-of-Age Literary Analysis
Focus Standards:
- RL.CR.9-10.1
- RL.CI.9-10.2
- W.AW.9-10.1
```

### Longitudinal standard summary

Shows performance on a standard over multiple assignments.

Example:

```text
Student: Ava Martinez
Standard: RL.CR.9-10.1

Assignment 1: Approaching
Assignment 2: Meeting
Assignment 3: Meeting
Assignment 4: Exceeding
```

Reporting should be built from teacher-confirmed review records. Quillan should not infer standards mastery from student writing automatically.

## Relationship to Old Tags, Comments, and Rubrics

The v0.8.6 redesign replaces the old tag/comment/rubric-centered review model.

### Old generic tags

Old generic tags are replaced by review-unit Focus Standard observations.

The useful idea inside old tags was that a teacher could mark something about the student’s work. In the redesigned model, that marking happens directly against a Focus Standard and review unit.

Old model:

```text
Add structured tag -> choose tag bank -> choose category -> choose tag -> maybe choose standard
```

New model:

```text
Paragraph 2 -> RL.CR.9-10.1 -> applicable -> evidence present -> rating -> rationale
```

The new model is more direct and more standards-based.

### Old generic rubrics

Old generic rubrics are replaced by Focus Standard rating scales and overall Focus Standard ratings.

The useful idea inside old rubrics was that a teacher could choose a performance level. In the redesigned model, performance levels are attached directly to the Focus Standards.

Old model:

```text
Rubric criterion: Literary Concepts
Score: 3 / 4
```

New model:

```text
Focus Standard: RL.CI.9-10.2
Rating: Meeting
Rationale: The response identifies a central idea and explains how it develops through the story’s objects.
```

This avoids generic criteria that may not apply to the assignment.

### Old generic comment banks

Old generic prebuilt comment banks are replaced by reusable Focus Standard comments.

The useful idea inside old comment banks was that teachers should not have to rewrite the same feedback repeatedly. That idea remains.

The difference is that reusable comments should be created and reused in direct connection with Focus Standards, writing types, and rating levels.

Old model:

```text
Select reusable comment -> choose comment bank -> choose category -> choose comment
```

New model:

```text
Focus Standard: W.AW.9-10.1
Rating: Approaching
Add feedback comment:
1. Use reusable comment for this standard
2. Write new comment
3. Write new comment and save for future reuse
```

### Standards profiles remain essential

Standards profiles remain necessary.

The assignment’s Focus Standards should be selected from a standards profile. Standards profiles provide the durable standard IDs and descriptions that organize review, scoring, feedback, and reporting.

## Worked English 10 Example

### Assignment setup

```text
Class: English 10 Simulation
Assignment: Coming-of-Age Literary Analysis
Writing type: literary_analysis
Review-unit type: paragraph
Singular label: paragraph
Plural label: paragraphs
```

Student-facing prompt:

```text
Using evidence from the story, explain how Nghi Vo turns ordinary objects into carriers of memory, grief, and power.
```

Focus Standards:

```text
njsls-ela:RL.CR.9-10.1
Cite strong and thorough textual evidence and make relevant connections to support analysis.

njsls-ela:RL.CI.9-10.2
Determine a theme or central idea and analyze how it is developed over the course of the text.

njsls-ela:W.AW.9-10.1
Write arguments to support claims with clear reasons and relevant evidence.
```

Minimum requirements:

```text
Minimum paragraphs: 1
Required element: textual evidence
Required element: explanation
```

Rating scale:

```text
1. Developing
2. Approaching
3. Meeting
4. Exceeding
```

### Minimum requirements

For student `10001`, the teacher opens the evidence and records:

```text
Minimum paragraphs: met
Required element: textual evidence: met
Required element: explanation: met
```

Because minimum requirements are met, Quillan continues to full standards review.

### Review-unit count

Quillan asks:

```text
How many paragraphs did the student write?
```

Teacher enters:

```text
4
```

Quillan creates four paragraph review units:

```text
Paragraph 1
Paragraph 2
Paragraph 3
Paragraph 4
```

### Paragraph 1 observation

Quillan begins with Paragraph 1 and the first Focus Standard.

```text
Paragraph 1

Focus Standard:
RL.CR.9-10.1 — Cite strong and thorough textual evidence and make relevant connections to support analysis.

Standard applicable? Y/N
```

Teacher enters:

```text
Y
```

Quillan asks:

```text
Evidence of standard? Y/N
```

Teacher enters:

```text
Y
```

Quillan asks:

```text
Rating:
1. Developing
2. Approaching
3. Meeting
4. Exceeding
```

Teacher enters:

```text
2
```

Quillan asks:

```text
Rationale/comment, optional:
```

Teacher enters:

```text
The paragraph uses evidence from the story, but the explanation is still general.
```

Stored conceptually:

```text
Review unit: Paragraph 1
Standard: RL.CR.9-10.1
Applicable: yes
Evidence present: yes
Rating: Approaching
Rationale: The paragraph uses evidence from the story, but the explanation is still general.
```

### Paragraph 1 second Focus Standard

Quillan moves to the next Focus Standard.

```text
Paragraph 1

Focus Standard:
RL.CI.9-10.2 — Determine a theme or central idea and analyze how it is developed over the course of the text.

Standard applicable? Y/N
```

Teacher enters:

```text
Y
```

Quillan asks:

```text
Evidence of standard? Y/N
```

Teacher enters:

```text
Y
```

Teacher rates the paragraph:

```text
3. Meeting
```

Rationale:

```text
The paragraph identifies memory as a central idea and begins to explain how ordinary objects carry that idea.
```

Stored conceptually:

```text
Review unit: Paragraph 1
Standard: RL.CI.9-10.2
Applicable: yes
Evidence present: yes
Rating: Meeting
Rationale: The paragraph identifies memory as a central idea and begins to explain how ordinary objects carry that idea.
```

### Paragraph 1 third Focus Standard

Quillan moves to the writing standard.

```text
Paragraph 1

Focus Standard:
W.AW.9-10.1 — Write arguments to support claims with clear reasons and relevant evidence.

Standard applicable? Y/N
```

Teacher enters:

```text
Y
```

Evidence present:

```text
Y
```

Rating:

```text
2. Approaching
```

Rationale:

```text
The claim is present, but it should be more clearly stated as an interpretation.
```

### Focus Standard summary

After all paragraph observations are complete, Quillan summarizes by Focus Standard.

Example:

```text
Focus Standard: RL.CR.9-10.1
Cite strong and thorough textual evidence and make relevant connections to support analysis.

Paragraph 1
Applicable: yes
Evidence: yes
Rating: Approaching
Rationale: The paragraph uses evidence from the story, but the explanation is still general.

Paragraph 2
Applicable: yes
Evidence: yes
Rating: Meeting
Rationale: The paragraph uses a relevant example and explains how it connects to memory.

Paragraph 3
Applicable: yes
Evidence: yes
Rating: Meeting
Rationale: The paragraph explains how Yongjun’s clothing reveals grief and power.

Paragraph 4
Applicable: yes
Evidence: yes
Rating: Meeting
Rationale: The ending is connected to evidence about family garments and memory.
```

Quillan asks:

```text
Overall Focus Standard Rating:
1. Developing
2. Approaching
3. Meeting
4. Exceeding
```

Teacher enters:

```text
3
```

Quillan asks:

```text
Overall rationale/comment, optional:
```

Teacher enters:

```text
Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.
```

Stored conceptually:

```text
Standard: RL.CR.9-10.1
Overall rating: Meeting
Overall rationale: Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.
```

### Student feedback composition

After overall ratings are entered, Quillan moves to student feedback.

Example:

```text
Focus Standard: RL.CR.9-10.1
Overall rating: Meeting
Overall rationale: Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.

Include rating in student feedback? Y/N
```

Teacher enters:

```text
Y
```

Quillan asks:

```text
Include overall rationale in student feedback? Y/N
```

Teacher enters:

```text
Y
```

Quillan asks:

```text
Add student feedback comment? Y/N
```

Teacher enters:

```text
Y
```

Quillan offers:

```text
1. Use reusable comment
2. Write new comment
3. Write new comment and save for future reuse
```

Teacher chooses:

```text
2
```

Teacher writes:

```text
Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.
```

### Simplified exported feedback preview

Quillan generates a student-facing PDF.

Conceptual preview:

```text
Feedback Report

Student: Ava Martinez (10001)
Class: English 10 Simulation
Assignment: Coming-of-Age Literary Analysis
Generated: July 2, 2026

Focus Standard: RL.CR.9-10.1
Cite strong and thorough textual evidence and make relevant connections to support analysis.

Rating: Meeting

Teacher Feedback:
Across the response, the evidence is relevant and usually connected to the interpretation, though some explanation could be more precise.

Your evidence is relevant and usually well chosen. To improve, make sure each quotation is followed by analysis that explains exactly how it supports your interpretation.

Focus Standard: RL.CI.9-10.2
Determine a theme or central idea and analyze how it is developed over the course of the text.

Rating: Meeting

Teacher Feedback:
Your response identifies an important central idea about memory and explains how ordinary objects carry that meaning across the story.

Focus Standard: W.AW.9-10.1
Write arguments to support claims with clear reasons and relevant evidence.

Rating: Approaching

Teacher Feedback:
Your claim is on the right track, but it should be stated more clearly as an interpretation. Try to name not only what the story shows, but what the story suggests about memory, grief, or power.
```

The export does not show internal review metadata unless the teacher explicitly chooses to include it.

## Conceptual Data Shape

This document is not a binding schema contract. The schema details belong in later contract tickets.

However, the conceptual data shape should look roughly like this.

### Assignment

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

### Review record

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

Again, this is only conceptual. Binding field names, validation rules, migration decisions, and compatibility policy belong in later contract work.

## Non-Goals of This Redesign Document

This document does not implement the new workflow.

This document does not delete old tag, comment, rubric, or review-material code.

This document does not define final JSON schemas.

This document does not define all menu behavior in implementation detail.

This document does not decide migration policy for old review records.

This document establishes the target concept so that ADRs, contracts, code audits, deletion work, and implementation tickets can be aligned.

## Open Design Questions

The redesign still needs later decisions on several questions.

### Should review-unit observations always require ratings?

Some observations may only need applicability and evidence presence. Later contracts should decide whether rating is required whenever a standard is applicable, or whether the teacher may skip rating at the review-unit level.

### How should whole-submission standards be handled?

Some standards may not fit neatly into paragraph-by-paragraph review. Conventions, organization, or overall argument quality may be better evaluated across the whole submission.

Possible approaches:

* allow a `whole_submission` review unit
* allow standards to be marked as whole-submission-only
* allow assignment configuration to choose which standards are reviewed by unit and which are reviewed overall only

### How much paragraph-level detail should be included in feedback?

Including every paragraph-level observation may overwhelm students. Quillan should let the teacher choose what to include.

The default student-facing feedback may only include overall Focus Standard ratings and selected comments.

### Should reusable comments be global, course-specific, or teacher-specific?

Reusable comments should likely be local workspace artifacts at first. Later versions may support course, department, district, or system-level reusable comments.

### How should standards-based ratings interact with grades?

This redesign defines standards ratings, not gradebook grades. Future work may decide whether and how standards ratings can be converted into grades, summaries, or reports.

### How should old records be handled?

Because this redesign replaces the old review model, later work must decide whether to migrate old review records, leave them readable but deprecated, or treat pre-redesign records as incompatible test artifacts.

## Summary

The v0.8.6 redesign should make Quillan simpler and more coherent by centering review on Focus Standards.

The old review workflow asked teachers to manage separate artifacts:

```text
tags -> comments -> rubrics -> scores -> exports
```

The new workflow should follow the logic of standards-based writing review:

```text
minimum requirements -> review-unit observations -> overall standard ratings -> student feedback -> standards reporting
```

This model better matches classroom practice. It directly connects student evidence to standards, turns those judgments into feedback, and produces reports that help teachers understand standards performance.
