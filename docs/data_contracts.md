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

A standards profile defines the standards and comments available for tagging.

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

Each comment requires:

* `comment_id`
* `label`
* `polarity`

Allowed polarity values:

* `positive`
* `developing`
* `negative`

Optional comment fields:

* `severity_default`
* `feedback_template`
* `subskills`

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
          "polarity": "positive"
        },
        {
          "comment_id": "evidence_needs_explanation",
          "label": "Evidence needs more explanation",
          "polarity": "developing"
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

An assignment defines what students wrote, which class or classes are connected, which standards are active, and what basic requirements apply.

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

A submission stores or references a student's written work.

MVP submissions are plain-text files.

Suggested path:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.txt
```

A future metadata file may describe source type, import time, OCR status, or original file references.

Example path:

```text
<PDS workspace root>/classes/english12_period3_synthetic/assignments/villainy_final_essay_synthetic/submissions/stu_0001/submission.txt
```

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
