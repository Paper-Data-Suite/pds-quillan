# Quillan

Quillan is a local-first, teacher-controlled review tool for written student
work. It helps a teacher move from student evidence to review units, Focus
Standards, teacher judgment, feedback, and assignment-local reporting.

Quillan is not an AI essay grader, OCR evaluator, gradebook, LMS, or
cross-assignment reporting engine. It does not read writing, infer scores,
calculate grades, generate feedback, or replace teacher judgment.

Quillan is subject-agnostic. It can support written response review in English
/ ELA, history / social studies, science, computer science, technical writing,
world languages, arts/humanities, and interdisciplinary writing tasks.

## Current Status

Quillan is an early pre-1.0 foundation. The active v0.8.6 workflow is
standards-based:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

Quillan currently supports:

* v2 assignment configuration validation and guided creation;
* pds-core standards profile selection;
* Focus Standard selection through `focus_standard_ids`;
* review-unit configuration;
* rating-scale configuration;
* basic requirements and minimum-requirement return policy;
* printable QR paper response packets;
* QR/paper routing and submission assembly;
* read-only submission status listing;
* workspace-safe evidence opening and selected-evidence opening;
* minimum-requirements review with explicit teacher-entered outcomes;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* Focus Standard feedback composition;
* reusable Focus Standard comments in `shared/focus_standard_comments/`;
* student feedback export to Markdown, PDF, or both;
* assignment-local Student Performance Summary export;
* assignment-local Comprehensive Class Summary export; and
* assignment-local Focus Standard summary export.

The old generic tag, comment-bank, rubric, and criterion-score workflow has
been removed. Quillan has no runtime compatibility path for that model.

Canonical active records and exports live at:

```text
classes/<class_id>/roster.csv
classes/<class_id>/assignments/<assignment_id>/assignment.json
classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
classes/<class_id>/assignments/<assignment_id>/scans/
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
shared/focus_standard_comments/<comment_set_id>.json
shared/standards/library.json
scans/source/YYYY-MM-DD/
scans/review/
```

## Teacher-Facing Menu

Launch the menu with either:

```powershell
quillan
quillan menu
```

The top-level menu is:

```text
1. Assignment Management
2. Review Student Work
3. Roster Management
4. Workspace Settings
5. Help
6. Exit
```

### Assignment Management

Assignment Management supports:

```text
1. Create writing assignment
2. View/validate assignment
3. Printable Response Pages
4. Back
```

Assignment creation requires an existing roster and writes:

```text
<workspace_root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The v0.8.6 creation workflow prompts for class, title, assignment ID, writing
type, student prompt, pds-core standards profile, Focus Standards, review-unit
settings, rating scale, basic requirements, and minimum-requirement policy.
New active assignments use schema version `2` fields such as
`student_prompt`, `focus_standard_ids`, `review_unit`, `rating_scale`,
`basic_requirements`, and `minimum_requirement_policy`.

### Review Student Work

The first Review Student Work menu is:

```text
1. Assignment Review Actions
2. Scan Intake / Route Paper Responses
3. Back
```

After selecting a class and assignment, the assignment-level menu is:

```text
1. Select student/submission
2. Assemble routed submissions
3. Export Comprehensive Class Summary
4. Export Standards Summary
5. Export Student Performance Summary
6. Back
```

The selected-student review menu is:

```text
1. Open submission evidence
2. View current review details
3. Review minimum requirements
4. Review units and Focus Standard observations
5. Overall Focus Standard ratings
6. Compose Focus Standard feedback
7. Manage submission pages
8. Add teacher note
9. Update submission review state
10. Export student feedback
11. Refresh summary
12. Back
```

Minimum-requirement checks are generated from assignment `basic_requirements`
and stored as teacher-entered data in `minimum_requirement_checks` and
`minimum_requirement_outcome`. Missing checks are not treated as unmet
automatically.

Review-unit observations record teacher-entered applicability, evidence
presence, optional ratings, rationales, and feedback-inclusion choices for a
specific review unit and Focus Standard. Overall Focus Standard ratings are
teacher-entered from the assignment `rating_scale`; Quillan does not infer
them from observations.

Feedback composition stores per-standard rating/rationale inclusion choices,
selected observation IDs, custom comments, and reusable Focus Standard comment
snapshots under `feedback.standard_feedback`.

### Scan Intake And Evidence

Scan intake uses the same QR-aware behavior as:

```powershell
quillan route-scan <source> --decode-qr
```

It routes supported QR-bearing images, PDFs, or non-recursive folders, preserves
handled failures under `scans/review/`, and prints explicit
`assemble-submissions` guidance. It does not OCR writing, inspect evidence
content, grade work, create review records, or generate feedback.

Opening evidence delegates to the local system viewer and is read-only. It
never marks work reviewed.

### Exports

Student feedback export reads a valid matching `submission.json` and
schema-version-2 `review.json` and can write:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

The three assignment-local CSV reports are:

```text
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

Student Performance Summary is the compact ordinary teacher-facing table.
Comprehensive Class Summary (`class_summary.csv`) is audit/troubleshooting
oriented. Standards Summary aggregates assignment Focus Standards.

Exports are derived artifacts. They do not mutate assignment records,
submission manifests, review records, routed evidence, rosters, standards, or
reusable comments.

## Direct CLI Commands

The direct command surface exposed through argparse is:

```powershell
quillan
quillan --help
quillan validate-assignment <path>
quillan route-scan <source-file> --payload "<already-decoded PDS1 payload>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
quillan decode-scan <source-file> [--hide-payload]
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
quillan open-evidence <workspace-relative-evidence-path>
quillan open-submission <class_id> <assignment_id> <student_id> [--page N]
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan export-feedback <class_id> <assignment_id> <student_id> [--format markdown|pdf|both] [--overwrite]
quillan export-student-performance-summary <class_id> <assignment_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-comprehensive-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan menu
```

The removed legacy commands `add-tag`, `add-comment`, and `set-score` are not
part of the active command surface.

## Data Contracts

Primary contracts:

```text
docs/data_contracts.md
docs/assignment_contract.md
docs/review_record_contract.md
docs/focus_standard_comment_contract.md
docs/feedback_export_contract.md
docs/assignment_reporting_contract.md
docs/cli_contract.md
docs/prepared_review_workflow.md
docs/teacher_review_model.md
docs/workspace_lifecycle.md
```

Legacy comment-bank, tag-bank, and rubric contract docs remain as historical
or compatibility documentation when explicitly labeled that way.

## Local Setup

`pds-core` is required for local Paper Data Suite development. Check out
`pds-core` and `pds-quillan` as sibling repositories:

```text
Paper-Data-Suite/
  pds-core/
  pds-quillan/
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install development dependencies from inside `pds-quillan`:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

PDF scan intake uses `pdf2image` and requires Poppler installed on the user's
machine.

## Quality Checks

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run Ruff:

```powershell
.\.venv\Scripts\ruff.exe check .
```

Run the project validation script:

```powershell
.\run_tests.ps1
```

## Synthetic Data Policy

The repository must not include real student data.

Committed examples and tests should use fake student IDs, fake class IDs,
synthetic writing samples, synthetic teacher comments, synthetic rosters,
synthetic standards libraries, and synthetic scan-like fixtures.

Do not commit real student names, rosters, student writing, grades,
accommodations, attendance or discipline context, scanned student work, review
notes, feedback, exports, screenshots, or workspace artifacts.

## Non-Goals

Quillan does not currently provide OCR, handwriting recognition, PDF text
extraction, AI tagging, AI scoring, AI feedback, automatic grading, automatic
mastery calculation, automatic evidence selection, automatic review-state
decisions, automatic requirements evaluation, recursive raw scan intake,
gradebook export, LMS integration, parent/admin reporting, dashboards, cloud
sync, or hosted collaboration.

Quillan's review tools record teacher decisions. They do not replace teacher
judgment.

## Development Workflow

Use issue branches for changes:

```powershell
git checkout main
git pull
git checkout -b issue-number-short-description
git push -u origin issue-number-short-description
```

Recommended pull request workflow:

1. Make a focused change.
2. Run tests and lint checks.
3. Commit and push the branch.
4. Open a pull request into `main`.
5. Link the relevant issue using `Closes #<issue-number>`.

## License

MIT
