# Quillan Assignment Reporting Contract

## Purpose and Boundary

This document defines Quillan's v0.8.6 assignment-level reporting contract.

Quillan should provide enough reporting to stand alone for a single writing assignment. It should not become the broader Paper Data Suite reporting engine.

The reporting boundary is:

```text
Quillan may summarize one Quillan assignment.
A future Paper Data Suite reporting module should summarize across assignments, modules, courses, terms, and time.
```

Quillan assignment-level reports may help a teacher answer questions such as:

```text
Which students have completed review for this assignment?
Which students were returned without full review?
Which Focus Standards were students meeting, approaching, or still developing on this assignment?
Which feedback exports exist for this assignment?
Which assignment-local records may need attention before I rely on these results?
```

Quillan assignment-level reports must not answer broader questions such as:

```text
How is this student progressing across the marking period?
What is this student's overall standards mastery?
How should Quillan evidence combine with ScoreForm evidence?
What grade should this student receive?
How has the class grown across multiple assignments?
```

Those broader questions belong to a future Paper Data Suite reporting module.

## Status

This is the active assignment-level reporting contract for the v0.8.6
standards-based workflow redesign. Runtime exports support compact student
performance, comprehensive class, and Focus Standard summary CSVs from schema version `2`
review records. Some optional future formats, such as PDFs or assignment
results manifests, may remain contract guidance, but the active reporting
workflow is no longer the legacy schema version `1` tag/comment/score summary
path.

## Design Context

This contract follows the standards-based redesign direction established in:

* [`standards_based_review_redesign.md`](standards_based_review_redesign.md)
* [`adr/0001-standards-based-review-model.md`](adr/0001-standards-based-review-model.md)
* [`assignment_contract.md`](assignment_contract.md)
* [`review_record_contract.md`](review_record_contract.md)
* [`focus_standard_comment_contract.md`](focus_standard_comment_contract.md)
* [`feedback_export_contract.md`](feedback_export_contract.md)

The central review relationship remains:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Assignment-level reports are derived artifacts generated from canonical Quillan records. They are not the canonical source of teacher judgment.

## Quillan-Owned Assignment Reports

Quillan owns three target assignment-local reporting artifacts.

### Student Performance Summary

The ordinary teacher-facing student-by-standard report. It answers which
rating each student received on each assignment Focus Standard without
including internal record paths or routine workflow diagnostics.

```text
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
```

It contains student identity, review status, minimum-requirement status,
actionable flags, and one compact rating cell per Focus Standard in assignment
order. Missing and returned ratings remain missing; they are never converted
to zero or the lowest rating.

### Comprehensive Class Summary

An audit/troubleshooting summary of record validity and paths, review progress,
requirement status, feedback export status, and detailed Focus Standard fields.
`class_summary.csv` remains its backward-compatible path.

Suggested paths:

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.pdf
```

### Standards Summary

A teacher-facing summary of Focus Standard performance for one class and one assignment.

Suggested paths:

```text
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.pdf
```

### Assignment Results Manifest

A machine-readable, assignment-local handoff artifact that records what Quillan exported for one assignment and where those files are located.

Suggested path:

```text
classes/<class_id>/assignments/<assignment_id>/exports/assignment_results_manifest.json
```

The assignment results manifest is forward-looking. It should make future Paper Data Suite reporting integration easier without making Quillan responsible for cross-assignment or cross-module reporting.

## Out-of-Scope Reporting

Quillan must not produce:

* cross-assignment reports;
* cross-module reports;
* marking-period reports;
* school-year reports;
* longitudinal standards-growth reports;
* student portfolio reports across assignments;
* parent or administrator dashboards;
* gradebook averages;
* grades;
* percentages;
* automatic mastery determinations;
* weighted scores;
* module-combined reporting, such as Quillan plus ScoreForm;
* intervention reports;
* attendance reports;
* discipline reports; or
* any report requiring data from multiple Paper Data Suite modules.

Those concerns belong to a future Paper Data Suite reporting module.

## Reporting Principles

Quillan assignment-level reports should be:

* assignment-local;
* teacher-facing;
* derived from canonical records;
* reproducible from local files;
* structured enough for later reporting handoff;
* clear about missing or invalid records;
* clear about returned-without-full-review cases;
* clear about missing ratings;
* careful with student privacy;
* free of grade calculations; and
* compatible with future Paper Data Suite reporting.

Quillan reports must not:

* inspect student writing;
* parse student writing;
* quote student writing;
* read routed evidence contents to calculate results;
* run OCR;
* run handwriting recognition;
* use AI;
* infer ratings;
* infer standards mastery;
* calculate grades;
* convert missing ratings into zeros;
* convert missing ratings into the lowest rating level;
* mutate canonical review data;
* mutate assignment data;
* mutate submission manifests;
* mutate reusable comments; or
* replace teacher judgment.

## Canonical Input Records

Assignment-level reports may read the following records.

### Roster

```text
classes/<class_id>/roster.csv
```

Roster data may be used for:

* student display names;
* expected student lists;
* row ordering;
* missing-submission detection; and
* distinguishing rostered students from discovered unrostered submission folders.

Rules:

* Prefer shared `pds-core` roster display helpers when available.
* Fall back to `student_id` when display data is unavailable.
* Do not duplicate full roster records into report outputs.
* Do not expose unnecessary roster fields.
* If no roster is available, reports may summarize discovered submission folders only.

### Assignment Record

```text
classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Reports use assignment data for:

* assignment identity;
* title;
* class IDs;
* writing type;
* standards profile ID;
* ordered Focus Standard IDs;
* review-unit labels;
* rating scale values and labels;
* minimum requirements; and
* minimum-requirement policy.

Reports should use the assignment's Focus Standard order:

```text
assignment.json.focus_standard_ids
```

as the default order for standards columns, standards rows, and manifest standards arrays.

### Submission Manifests

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

Reports may use submission manifests for:

* submission presence;
* submission state;
* selected evidence availability;
* missing page status;
* duplicate evidence status;
* needs-rescan status;
* selected/candidate evidence management state;
* submission updated timestamp; and
* warning generation.

Reports must not expose detailed routed evidence paths or retained-source provenance in ordinary teacher-facing summary outputs unless a later debugging contract explicitly allows it.

### Review Records

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

Target reports use schema version `2` review records.

Reports may use review records for:

* review state;
* minimum requirement checks;
* minimum-requirement outcome;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* feedback inclusion choices;
* feedback export metadata;
* review updated timestamp; and
* warning generation.

Reports must not include:

* private notes;
* unselected student-facing feedback text;
* reusable comment provenance;
* internal review IDs unless needed in a non-student-facing debugging report;
* full feedback text unless a later contract explicitly defines that report; or
* any field that would make the report a replacement for reading the underlying review record.

### Student Feedback Exports

Reports may check for student feedback exports at:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

Reports may use feedback export metadata stored in:

```text
review.json.exports.feedback_pdf
review.json.exports.feedback_markdown
```

Reports may summarize:

* whether feedback PDF exists;
* whether feedback Markdown exists;
* whether feedback export metadata exists;
* whether an export appears stale;
* generated timestamps; and
* safe workspace-relative export paths.

Reports should not read feedback export contents to calculate results.

### Standards Library

When available, reports may read pds-core standards metadata from the workspace standards library.

Reports may use standards metadata for:

* standard display code;
* standard short name;
* standard description;
* subject;
* course;
* source;
* grade band; and
* domain/category display.

Rules:

* Durable references remain `standard_id` values.
* Quillan must not create, redefine, retire, reactivate, or mutate standards while generating reports.
* Missing standards display metadata should produce warnings, not invented labels.
* Missing standards display metadata should not block a report when durable `standard_id` values are available.

## Output Formats

The target assignment-level reports may be generated in CSV, PDF, and JSON.

### CSV

CSV is the preferred machine-readable and spreadsheet-friendly format for assignment summaries.

CSV reports should:

* use stable headers;
* use one row per expected reporting entity;
* use workspace-relative paths;
* avoid embedded private notes;
* avoid student writing;
* distinguish missing data from low performance; and
* include warnings where useful.

### PDF

PDF is the preferred printable teacher-facing format for human review.

PDF reports should:

* be derived from the same canonical data as CSV reports;
* preserve the same privacy and teacher-control rules;
* avoid implying grades or percentages;
* show clear titles, timestamps, and assignment identity; and
* avoid including raw JSON or internal IDs except where useful for teacher troubleshooting.

PDF layout, typography, pagination, and visual design belong to later implementation work.

### JSON

JSON is the preferred machine-readable handoff format for future Paper Data Suite reporting.

The assignment results manifest should:

* summarize assignment-local outputs;
* identify source records and exported artifacts;
* provide enough structured data for future reporting ingestion;
* avoid broad reporting calculations;
* avoid student writing;
* avoid private notes; and
* remain scoped to one assignment.

## Workspace-Relative Path Policy

All report paths stored in generated artifacts must be workspace-relative strings.

Report paths must not contain:

* absolute paths;
* Windows drive-letter paths;
* rooted paths;
* `.` or `..` path components;
* null bytes; or
* paths that resolve outside the workspace root.

This rule applies to:

* report output paths;
* assignment paths;
* submission manifest paths;
* review record paths;
* feedback export paths; and
* any report manifest path fields.

## Timestamp Policy

Generated report metadata should use timezone-aware ISO 8601 timestamps.

Example:

```text
2026-07-02T00:00:00+00:00
```

Naive timestamps are not part of this target contract.

Generated reports should record:

* generation timestamp;
* source assignment updated timestamp;
* source roster updated timestamp, when available;
* source submission timestamp summary;
* source review timestamp summary; and
* source feedback export timestamp summary, when useful.

When a source record has no internal timestamp, runtime implementation may use file metadata if available, but that behavior should be documented clearly when implemented.

## Rating Scale Resolution

Ratings are assignment-local values.

Reports must resolve rating values through:

```text
assignment.json.rating_scale.levels[]
```

Rules:

* Reports must not assume a universal four-point scale.
* Reports must not hardcode labels such as `Developing`, `Approaching`, `Meeting`, or `Exceeding` except in synthetic examples where the assignment uses those labels.
* Reports must preserve missing ratings as missing.
* Reports must not convert missing ratings into `0`.
* Reports must not convert missing ratings into the lowest rating level.
* Reports must not calculate averages unless a later contract explicitly allows assignment-local descriptive statistics.
* Reports must not convert ratings into percentages or grades.

Example rating-scale level:

```json
{
  "value": 3,
  "label": "Meeting",
  "description": "The work shows clear and sufficient evidence of the standard."
}
```

If a review record stores:

```json
{
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "rating": 3
}
```

the report may display:

```text
Meeting
```

because `3` resolves to that label in the assignment's rating scale.

## Standard Column Key Policy

CSV exports may need stable column suffixes for Focus Standards.

Durable `standard_id` values may contain punctuation such as `:`, `.`, and `/`. Those values are valid standards references, but they may be awkward as raw CSV column suffixes.

For CSV column names, Quillan should use a deterministic non-durable `standard_column_key`.

Recommended transformation:

```text
standard_id -> replace every character outside A-Z, a-z, 0-9, underscore, and hyphen with underscore
```

Example:

```text
njsls-ela:RL.CR.9-10.1 -> njsls-ela_RL_CR_9-10_1
```

Rules:

* `standard_column_key` is for report column names only.
* `standard_column_key` must not replace the durable `standard_id`.
* Reports should include the durable `standard_id` wherever the report has one row per standard.
* If two standards would produce the same `standard_column_key`, the runtime must disambiguate safely and warn rather than silently merging columns.
* Future implementation may move this transformation into a shared helper if other modules need similar reporting behavior.

## Assignment-Level Class Summary

### Purpose

The class summary is a teacher-facing assignment-management and instructional-planning report.

It summarizes one class and one assignment.

It is not:

* a grade report;
* a gradebook export;
* a mastery report;
* a longitudinal report;
* a parent report;
* an administrator dashboard; or
* a replacement for reading student work.

### Suggested Paths

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.pdf
```

### Row Population

Preferred row policy:

* If a roster is available, include one row per rostered student.
* If a submission exists for a student not found in the roster, include that student with a warning.
* If no roster is available, include one row per discovered submission folder.
* Missing submissions for rostered students should appear as missing, not disappear from the report.

This policy helps the teacher distinguish:

* students who did not submit;
* students whose submissions were routed but not reviewed;
* students whose review records are missing or invalid;
* students returned without full review; and
* students with completed standards review.

### Stable Columns

The class summary CSV should include these stable columns:

```text
class_id
assignment_id
student_id
student_display_name
roster_status
submission_manifest_path
submission_state
submission_valid
review_record_path
review_state
review_valid
minimum_requirement_status
returned_without_full_review
feedback_pdf_path
feedback_pdf_status
feedback_pdf_stale
feedback_markdown_path
feedback_markdown_status
feedback_markdown_stale
warnings
```

Field meanings:

* `class_id`: assignment class ID.
* `assignment_id`: assignment ID.
* `student_id`: student identifier.
* `student_display_name`: roster-resolved display name when available.
* `roster_status`: one of `rostered`, `unrostered_submission`, or `roster_unavailable`.
* `submission_manifest_path`: workspace-relative path to `submission.json`, when available.
* `submission_state`: submission-management state from `submission.json`, when available.
* `submission_valid`: boolean or status value indicating whether the submission manifest validated.
* `review_record_path`: workspace-relative path to `review.json`, when available.
* `review_state`: review state from `review.json`, when available.
* `review_valid`: boolean or status value indicating whether the review record validated.
* `minimum_requirement_status`: status from `review.json.minimum_requirement_outcome.status`, when available.
* `returned_without_full_review`: true when the review outcome returned work without full standards review.
* `feedback_pdf_path`: workspace-relative path to generated PDF feedback, when available.
* `feedback_pdf_status`: expected values include `present`, `missing`, `stale`, or `unknown`.
* `feedback_pdf_stale`: boolean stale flag when determinable.
* `feedback_markdown_path`: workspace-relative path to generated Markdown feedback, when available.
* `feedback_markdown_status`: expected values include `present`, `missing`, `stale`, or `unknown`.
* `feedback_markdown_stale`: boolean stale flag when determinable.
* `warnings`: semicolon-separated or JSON-encoded warning list.

### Focus Standard Rating Columns

For each assignment Focus Standard, the class summary should include rating columns.

Recommended column pattern:

```text
rating__<standard_column_key>
rating_label__<standard_column_key>
rating_included_in_feedback__<standard_column_key>
rating_missing__<standard_column_key>
```

Example:

```text
rating__njsls-ela_RL_CR_9-10_1
rating_label__njsls-ela_RL_CR_9-10_1
rating_included_in_feedback__njsls-ela_RL_CR_9-10_1
rating_missing__njsls-ela_RL_CR_9-10_1
```

Rules:

* Rating values must come from `review.json.overall_standard_ratings[]`.
* Rating labels must resolve through `assignment.json.rating_scale.levels[]`.
* Missing ratings must remain blank or explicitly missing.
* Missing ratings must not become `0`.
* Missing ratings must not become the lowest rating label.
* Returned-without-full-review students should not be treated as fully reviewed students with missing low ratings.
* Invalid review records should produce warnings.
* Ratings for standards outside the assignment's `focus_standard_ids` should produce warnings rather than silently expanding the report's standard set.

### Class Summary PDF

The class summary PDF should be a readable teacher-facing rendering of the CSV content.

It may include:

* assignment title;
* class ID or display name;
* generated timestamp;
* review progress counts;
* returned-without-full-review counts;
* feedback export counts;
* a student table;
* Focus Standard rating columns or compact indicators; and
* warnings.

The PDF must not include:

* student writing;
* private notes;
* full feedback text;
* routed evidence contents;
* raw JSON records;
* grade calculations; or
* percentages presented as grades.

## Assignment-Level Focus Standard Summary

### Purpose

The Focus Standard summary is a teacher-facing assignment-level standards snapshot.

It summarizes how students performed on the assignment's selected Focus Standards, based on teacher-entered overall Focus Standard ratings.

It supports teacher reflection for one assignment only.

It is not:

* a standards mastery report;
* a longitudinal progress report;
* a cross-assignment report;
* a cross-module report;
* a gradebook report; or
* a replacement for broader Paper Data Suite reporting.

### Suggested Paths

```text
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.pdf
```

### Row Population

The standards summary should include one row per assignment Focus Standard.

Rows should follow the order of:

```text
assignment.json.focus_standard_ids
```

If a review record includes a rating for a standard outside `focus_standard_ids`, the report should warn rather than add an extra ordinary row.

### Stable Columns

The standards summary CSV should include these stable columns:

```text
class_id
assignment_id
standards_profile_id
focus_standard_order
standard_id
standard_column_key
standard_display_code
standard_display_name
students_expected
students_with_submissions
students_with_valid_reviews
students_reviewed_for_standard
students_returned_without_full_review
students_missing_rating
students_with_rating_included_in_feedback
feedback_pdf_present_count
feedback_pdf_stale_count
rating_counts_json
warnings
```

Field meanings:

* `class_id`: assignment class ID.
* `assignment_id`: assignment ID.
* `standards_profile_id`: assignment standards profile ID.
* `focus_standard_order`: one-based position in `assignment.json.focus_standard_ids`.
* `standard_id`: durable pds-core standard ID.
* `standard_column_key`: deterministic CSV-safe report key.
* `standard_display_code`: pds-core display code when available.
* `standard_display_name`: pds-core short name or display name when available.
* `students_expected`: roster count when roster is available, otherwise discovered submission count.
* `students_with_submissions`: count of students with submission manifests or submission folders.
* `students_with_valid_reviews`: count of valid schema version `2` review records.
* `students_reviewed_for_standard`: count of students with an overall rating for this Focus Standard.
* `students_returned_without_full_review`: count of students returned before full standards review.
* `students_missing_rating`: count of expected students without an overall rating for this Focus Standard.
* `students_with_rating_included_in_feedback`: count of students whose rating for this standard was selected for student feedback.
* `feedback_pdf_present_count`: count of students with PDF feedback present.
* `feedback_pdf_stale_count`: count of students with stale PDF feedback.
* `rating_counts_json`: JSON object mapping assignment rating values to counts.
* `warnings`: semicolon-separated or JSON-encoded warning list.

### Rating Count Columns

Because rating scales are assignment-local, the contract should not require a universal set of rating count columns.

The stable required representation is:

```text
rating_counts_json
```

Example:

```json
{
  "1": 2,
  "2": 6,
  "3": 14,
  "4": 3
}
```

Implementations may also add human-friendly dynamic columns based on the assignment rating scale.

Example dynamic columns for a four-level synthetic scale:

```text
rating_count__1
rating_label__1
rating_count__2
rating_label__2
rating_count__3
rating_label__3
rating_count__4
rating_label__4
```

Rules:

* Dynamic rating columns must be generated from `assignment.json.rating_scale.levels[]`.
* Dynamic rating columns must not assume four levels.
* `rating_counts_json` should remain available as the stable machine-readable representation.
* Missing ratings should be counted separately in `students_missing_rating`.
* Returned-without-full-review students should be counted separately and not treated as low ratings.

### Focus Standard Summary PDF

The Focus Standard summary PDF should be a readable teacher-facing rendering of standards performance for the assignment.

It may include:

* assignment title;
* class ID or display name;
* generated timestamp;
* Focus Standard table;
* rating distribution per Focus Standard;
* missing rating counts;
* returned-without-full-review counts;
* feedback export coverage; and
* warnings.

The PDF must not include:

* student writing;
* private notes;
* full feedback comments;
* grade calculations;
* percentages presented as grades;
* automatic mastery labels; or
* cross-assignment claims.

## Optional Review-Unit Observation Summary

Reports may include limited summaries of review-unit Focus Standard observations when the structure is useful and safe.

Source:

```text
review.json.review_units[].standard_observations[]
```

Acceptable assignment-level observation summaries include:

* count of observations by Focus Standard;
* count of applicable observations by Focus Standard;
* count of evidence-present observations by Focus Standard;
* count of observation ratings by Focus Standard and assignment rating value;
* count of observations selected for student feedback; and
* count of review units observed per student.

Observation summaries must be clearly labeled as observation summaries.

Rules:

* Observation summaries must not replace overall Focus Standard ratings.
* Observation summaries must not create automatic overall ratings.
* Observation summaries must not be averaged into ratings.
* Observation summaries must not infer mastery.
* Observation summaries must not quote student writing.
* Observation summaries must not include private notes.
* Observation summaries must not expose internal IDs in ordinary reports.
* Observation summaries should be optional.

If observation summaries are included in CSV, they should use clearly named columns or JSON fields rather than ambiguous score-like labels.

Example stable column:

```text
observation_counts_json
```

Example value:

```json
{
  "applicable": 24,
  "evidence_present": 19,
  "selected_for_feedback": 8
}
```

## Assignment Results Manifest

### Purpose

The assignment results manifest is a machine-readable handoff artifact for one Quillan assignment.

It records:

* which assignment was summarized;
* which reports were generated;
* which student feedback exports exist;
* which source timestamps were used;
* which Focus Standards were included; and
* which assignment-local warnings were detected.

It is designed to support future Paper Data Suite reporting ingestion.

It is not:

* a gradebook export;
* a full report database;
* a cross-assignment report;
* a cross-module report;
* a student portfolio;
* a parent/admin dashboard; or
* a replacement for canonical Quillan records.

### Suggested Path

```text
classes/<class_id>/assignments/<assignment_id>/exports/assignment_results_manifest.json
```

### Top-Level Shape

Target top-level shape:

```json
{
  "schema_version": "1",
  "module": "quillan",
  "record_type": "assignment_results_manifest",
  "class_id": "english_10_simulation",
  "assignment_id": "coming-of-age_literary_analysis",
  "assignment_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/assignment.json",
  "standards_profile_id": "english10_2023_njsls_ela",
  "focus_standard_ids": [
    "njsls-ela:RL.CR.9-10.1",
    "njsls-ela:RL.CI.9-10.2",
    "njsls-ela:W.AW.9-10.1"
  ],
  "exports": {
    "class_summary_csv": null,
    "class_summary_pdf": null,
    "standards_summary_csv": null,
    "standards_summary_pdf": null
  },
  "source_timestamps": {
    "generated_at": "2026-07-02T00:00:00+00:00",
    "source_assignment_updated_at": "2026-07-02T00:00:00+00:00",
    "source_roster_updated_at": null,
    "source_submission_records_max_updated_at": "2026-07-02T00:00:00+00:00",
    "source_review_records_max_updated_at": "2026-07-02T00:00:00+00:00"
  },
  "student_results": [],
  "warnings": [],
  "module_details": {}
}
```

Required top-level fields:

* `schema_version`;
* `module`;
* `record_type`;
* `class_id`;
* `assignment_id`;
* `assignment_path`;
* `standards_profile_id`;
* `focus_standard_ids`;
* `exports`;
* `source_timestamps`;
* `student_results`;
* `warnings`;
* `module_details`.

### Export Metadata Entries

Each entry in `exports` should be either `null` or an object.

Example:

```json
{
  "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/exports/class_summary.csv",
  "format": "csv",
  "generated_at": "2026-07-02T00:00:00+00:00",
  "stale": false,
  "module_details": {}
}
```

Expected export keys:

```text
class_summary_csv
class_summary_pdf
standards_summary_csv
standards_summary_pdf
```

Rules:

* Missing exports should be represented as `null`.
* Paths must be workspace-relative.
* `format` should be `csv`, `pdf`, or another explicitly documented format.
* `generated_at` should be timezone-aware.
* `stale` should reflect known stale status when determinable.
* `module_details` must be an object.

### Student Results

Each `student_results[]` item summarizes assignment-local status for one student.

Target shape:

```json
{
  "student_id": "10001",
  "student_display_name": "Sample Student",
  "roster_status": "rostered",
  "submission_manifest_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/submission.json",
  "submission_state": "reviewed",
  "submission_valid": true,
  "review_record_path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/review.json",
  "review_state": "ready_for_export",
  "review_valid": true,
  "minimum_requirement_status": "met",
  "returned_without_full_review": false,
  "overall_standard_ratings": [
    {
      "standard_id": "njsls-ela:RL.CR.9-10.1",
      "rating": 3,
      "rating_label": "Meeting",
      "include_in_feedback": true
    }
  ],
  "feedback_exports": {
    "feedback_pdf": {
      "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/exports/feedback.pdf",
      "status": "present",
      "stale": false
    },
    "feedback_markdown": {
      "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/exports/feedback.md",
      "status": "present",
      "stale": false
    }
  },
  "warnings": [],
  "module_details": {}
}
```

Required student-result fields:

* `student_id`;
* `student_display_name`;
* `roster_status`;
* `submission_manifest_path`;
* `submission_state`;
* `submission_valid`;
* `review_record_path`;
* `review_state`;
* `review_valid`;
* `minimum_requirement_status`;
* `returned_without_full_review`;
* `overall_standard_ratings`;
* `feedback_exports`;
* `warnings`;
* `module_details`.

Rules:

* Student results summarize assignment-local review status.
* Student results should not include student writing.
* Student results should not include private notes.
* Student results should not include full feedback text.
* Student results should not include routed evidence contents.
* Student results should not include retained-source scan details.
* Missing paths should be `null`.
* Missing ratings should be omitted from `overall_standard_ratings` or represented with an explicit missing status in a later schema version.
* Missing ratings must not be represented as low ratings.

### Overall Standard Rating Items

Each `overall_standard_ratings[]` item in the manifest should use this target shape:

```json
{
  "standard_id": "njsls-ela:RL.CR.9-10.1",
  "rating": 3,
  "rating_label": "Meeting",
  "include_in_feedback": true
}
```

Rules:

* `standard_id` must be a durable pds-core standard ID.
* `rating` must come from `review.json.overall_standard_ratings[]`.
* `rating_label` must resolve from `assignment.json.rating_scale.levels[]`.
* `include_in_feedback` must come from the review record.
* Ratings must not be calculated during manifest generation.
* Ratings must not be inferred from review-unit observations.
* Ratings must not be inferred from comments.
* Ratings must not be converted into grades.

## Report Metadata and Stale Detection

Assignment-level reports should include enough metadata to detect stale outputs.

A report should be considered stale or potentially stale when any source record used to generate it changed after report generation.

### Stale Conditions

A report should be considered stale when:

```text
assignment.json updated_at is later than the report's source_assignment_updated_at
```

A report should be considered stale or potentially stale when:

```text
any included review.json updated_at is later than the report's recorded review timestamp summary
```

A report may be considered stale or potentially stale when:

```text
any included submission.json updated_at is later than the report's recorded submission timestamp summary
```

A report may be considered stale or potentially stale when:

```text
roster.csv changes after report generation
```

because display names, expected student lists, or roster membership may have changed.

### Stale Detection Rules

* Stale detection should warn the teacher.
* Stale detection should not silently rewrite reports.
* Stale detection should not silently delete reports.
* Stale detection should not mutate review records.
* Stale detection should not mutate submission manifests.
* Stale detection should not mutate assignments.
* If the report cannot determine stale status, it should report `unknown` rather than assuming `fresh`.

## Validation and Warning Policy

Assignment-level reports should make missing and invalid records visible.

Warnings may include:

* missing roster;
* missing assignment;
* invalid assignment;
* missing standards profile;
* unresolved standard display metadata;
* missing submission manifest;
* invalid submission manifest;
* missing review record;
* invalid review record;
* schema version mismatch;
* review record references a different assignment;
* review record references a different student;
* rating uses a value not found in assignment rating scale;
* rating references a standard outside assignment Focus Standards;
* missing overall Focus Standard rating;
* returned without full review;
* feedback PDF missing;
* feedback PDF stale;
* feedback Markdown stale;
* duplicate submission folders;
* unrostered submission found; and
* report stale status unknown.

Warnings should be included in:

* `student_performance_summary.csv`, where relevant;
* `class_summary.csv`;
* `standards_summary.csv`, where relevant;
* `assignment_results_manifest.json`; and
* teacher-facing PDF reports, where practical.

Warnings should not become grades, penalties, or automatic judgments.

## Returned Without Full Review

Reports must distinguish returned-without-full-review submissions from completed standards reviews.

Relevant fields:

```text
review.json.review_state
review.json.minimum_requirement_outcome.status
review.json.minimum_requirement_outcome.returned_without_full_review
```

Rules:

* Returned-without-full-review students should be counted separately.
* Returned-without-full-review students should not be treated as missing because the teacher forgot to review them.
* Returned-without-full-review students should not receive low inferred Focus Standard ratings.
* Returned-without-full-review students should not be counted as fully reviewed for standards-performance summaries.
* Returned-without-full-review counts should appear in class and standards summaries.
* Returned-without-full-review status should appear in the assignment results manifest.

## Missing Ratings

Reports must distinguish missing ratings from low ratings.

A missing rating may occur because:

* the review is not started;
* the review is in progress;
* the review was returned without full review;
* the teacher has not rated that Focus Standard yet;
* the review record is invalid;
* the review record is missing; or
* the assignment/review contract changed.

Rules:

* Missing ratings must not become `0`.
* Missing ratings must not become the lowest level on the assignment scale.
* Missing ratings must not become `Developing` unless the teacher actually selected that rating.
* Missing ratings should be counted in `students_missing_rating`.
* Missing ratings should generate warnings or status fields where useful.
* Missing ratings should remain distinct from returned-without-full-review cases.

## Privacy and Data Hygiene

Assignment-level reports must not include real student data in committed examples.

Committed examples must use:

* fake class IDs;
* fake assignment IDs;
* fake student IDs;
* fake student names;
* fake teacher comments;
* fake review data;
* fake timestamps; and
* synthetic standards-alignment examples.

Do not commit:

* real student names;
* real student IDs;
* real rosters;
* real student writing;
* real scanned work;
* real feedback for actual students;
* real grades;
* parent or guardian information;
* accommodations;
* disability information;
* health information;
* discipline information;
* attendance information;
* private family information; or
* personally identifiable student information.

Generated assignment-level reports must not include:

* private teacher notes;
* student writing contents;
* scanned work contents;
* routed evidence contents;
* retained-source scan contents;
* parent or guardian information;
* accommodations;
* disability information;
* health information;
* discipline information;
* attendance information;
* private family information;
* gradebook records;
* cross-module records; or
* cross-assignment calculations.

## Relationship to Student Feedback Exports

Student feedback exports are individual student-facing artifacts defined in:

```text
docs/feedback_export_contract.md
```

Assignment-level reports may summarize whether those artifacts exist and whether they appear stale.

Assignment-level reports should not copy full student feedback text into class summaries or standards summaries.

The assignment results manifest may include paths and status for feedback exports.

Example:

```json
{
  "feedback_pdf": {
    "path": "classes/english_10_simulation/assignments/coming-of-age_literary_analysis/submissions/10001/exports/feedback.pdf",
    "status": "present",
    "stale": false
  }
}
```

Rules:

* Reports may summarize feedback export status.
* Reports may summarize feedback export coverage.
* Reports may warn about stale feedback.
* Reports must not expose private notes.
* Reports must not become a substitute for reading individual feedback.

## Relationship to Future Paper Data Suite Reporting

The assignment results manifest is intentionally designed as a handoff artifact.

A future Paper Data Suite reporting module may consume:

* Quillan assignment results manifests;
* ScoreForm assignment results;
* future scanned-essay module results;
* other module-specific outputs; and
* shared pds-core standards metadata.

That future module may produce:

* cross-assignment reports;
* cross-module reports;
* longitudinal standards summaries;
* student portfolio reports;
* marking-period summaries;
* dashboards;
* export packages; and
* other broader analytics.

Quillan should not implement those broader reports.

Quillan's responsibility ends at assignment-local summaries and assignment-local handoff metadata.

## Relationship to Legacy Runtime

Legacy runtime exports produced:

```text
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

from legacy schema version `1` review fields such as:

```text
review.json.tags
review.json.scores
review.json.comments
```

That behavior is legacy implementation history and is not the active v0.8.6
reporting path.

The active v0.8.6 reporting model uses:

```text
assignment.json.focus_standard_ids
assignment.json.rating_scale
submission.json.submission_state
review.json.review_state
review.json.minimum_requirement_outcome
review.json.overall_standard_ratings
review.json.review_units[].standard_observations, where useful
review.json.exports
```

## Synthetic Example Policy

Synthetic examples may be stored under:

```text
examples/exports/
```

Suggested examples:

```text
examples/exports/class_summary_v2_synthetic.csv
examples/exports/standards_summary_v2_synthetic.csv
examples/exports/assignment_results_manifest_v2_synthetic.json
```

Example files must be clearly synthetic.

They should not include:

* real student names;
* real student IDs;
* real rosters;
* real writing;
* real scans;
* real grades;
* real feedback;
* real parent contact information; or
* identifiable classroom records.

## Out of Scope

This contract does not implement:

* class summary runtime rewrite;
* standards summary runtime rewrite;
* PDF report generation;
* CSV report generation;
* assignment results manifest generation;
* CLI command changes;
* menu changes;
* runtime validation for schema version `2`;
* migration from schema version `1` reports;
* deletion of legacy report code;
* tests;
* cross-assignment reporting;
* cross-module reporting;
* grade calculations;
* percentages;
* mastery calculations;
* student portfolio reports;
* parent/admin dashboards;
* longitudinal standards reports;
* ScoreForm plus Quillan combined reporting;
* AI analysis;
* OCR analysis;
* automatic scoring; or
* automatic feedback generation.

## Summary

Quillan assignment-level reporting should make one writing assignment easier to manage and reflect on.

The target model is:

```text
Quillan can summarize the results of this writing assignment.
Paper Data Suite reporting can later summarize learning across assignments, modules, and time.
```

Assignment-level reports should derive from teacher-entered records, preserve Focus Standard structure, distinguish missing data from low ratings, respect privacy, and prepare clean handoff data for future suite-wide reporting.
