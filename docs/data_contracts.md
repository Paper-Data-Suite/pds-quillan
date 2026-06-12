# Quillan MVP Data Contracts

Quillan stores structured evidence about student writing using local files.

These contracts describe the expected MVP file formats for standards profiles, assignments, submissions, requirements checks, tags, scores, feedback, and reports.

All examples must use synthetic data only. No real student names, writing, rosters, scores, or personally identifiable student information should be committed to the repository.

## Design Principles

Quillan data should be:

* local-first;
* human-readable where practical;
* structured enough for validation and reporting;
* subject-agnostic;
* compatible with future Paper Data Suite shared data structures;
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

## Submission

A submission preserves student-produced writing as evidence and records how
that writing entered the teacher's review workflow. The writing and its
metadata are stored separately:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.txt
```

`submission.txt` contains the student writing. `submission.json` organizes the
artifact and its provenance without adding scores, feedback, or software-made
judgments.

Required submission metadata fields:

* `submission_id`
* `assignment_id`
* `class_id`
* `student_id`
* `source_type`
* `text_file`
* `captured_at`
* `status`
* `version`

Allowed MVP `source_type` values:

* `manual_entry`
* `typed_text`
* `pasted_text`
* `file_import`
* `paper_scan`
* `ocr_scan`
* `google_doc_export`

Allowed MVP `status` values:

* `captured`
* `needs_review`
* `reviewed`
* `superseded`
* `invalid`

Example `submission.json`:

```json
{
  "submission_id": "sub_stu_0001_v1",
  "assignment_id": "villainy_final_essay_synthetic",
  "class_id": "english12_period3_synthetic",
  "student_id": "stu_0001",
  "source_type": "manual_entry",
  "text_file": "submission.txt",
  "captured_at": "2026-06-07T12:00:00",
  "status": "captured",
  "version": 1
}
```

The metadata identifiers follow shared `pds-core` identifier validation.
`text_file` must be a relative path contained within the submission record;
absolute paths and parent-directory traversal are not allowed. `version` is a
positive integer.

Requirements checks, teacher tags, teacher notes, rubric scores entered or
confirmed by the teacher, and feedback records remain separate artifacts.
Software may organize and validate these records, but the student text remains
the evidence and teacher review remains central.

## Writing-Response Payload

Each Quillan writing-response page can be identified by a canonical PDS1
payload built through `pds-core`:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

The page number is a positive integer. Class, assignment, and student
identifiers follow shared `pds-core` identifier validation.

Example:

```text
PDS1|module=quillan|class=english12_p4|aid=personal_narrative|sid=1001|page=1|doc=response
```

This contract identifies response documents only; QR image generation, paper
forms, and scan routing are outside the current implementation.

## Requirements Check

A requirements check records whether the submission met basic assignment requirements.

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

## Tag Record

A tag record connects a specific observation to a location in the writing, a standard, and a structured comment.

Suggested path:

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

## Score Record

A score record stores the teacher's final scoring decision.

Scores are informed by tags but are not automatically determined by tags.

Suggested path:

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

## Feedback File

A feedback file stores student-readable feedback.

Suggested path:

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

A standards summary aggregates tag data by standard.

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

A class summary aggregates submission-level results.

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
