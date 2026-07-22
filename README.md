# Quillan

> **Storage contract:** Quillan assignment, submission, review, feedback, and
> assignment-report services use only
> `classes/<class_id>/modules/quillan/work/<assignment_id>/`. See
> [Module-qualified record services](docs/module_qualified_record_services.md)
> for the canonical contexts, plain-paper behavior, export paths, and scan-review
> ownership boundary. The former unqualified assignment tree is unsupported and
> is never inspected or written.

## Installed PDS2 module boundary

Quillan registers the `quillan` entry point in `paper_data_suite.modules` through
`quillan.pds_module:get_module_profile`. The profile supports Core routing contract
`1`, QR schema `PDS2`, route-registration schema `1`, and only Core route status
`active`.

An active route is only structurally dispatchable. The response-page handler also
requires the immutable issuance lifecycle to be exactly `issued`. Student and page
meaning come from immutable page context, never QR text, fallback text, filenames,
current roster data, or current assignment data. This boundary validates one
retained source page and returns a typed runtime result. After successful dispatch,
Quillan persists an immutable page observation, materializes page-specific evidence,
and assembles the exact issued response set into a submission manifest.

For a compact, read-only diagnostic of one student's submission and review
workflow, use `quillan review-status <class_id> <assignment_id> <student_id>`;
add `--format json` for the stable versioned structured contract.

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
* read-only submission status listing and assignment review dashboards;
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
classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
classes/<class_id>/modules/quillan/work/<assignment_id>/response_pages/issuances/<issuance_id>.json
classes/<class_id>/modules/quillan/work/<assignment_id>/response_pages/pages/<page_id>.json
classes/<class_id>/modules/quillan/work/<assignment_id>/templates/printable_response_pages.pdf
classes/<class_id>/modules/quillan/work/<assignment_id>/scans/
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/class_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/standards_summary.csv
shared/focus_standard_comments/<comment_set_id>.json
shared/standards/library.json
scans/source/YYYY-MM-DD/
scans/review/
```

An assignment ID is Quillan's `work_id`; its complete identity is the module,
class, and work ID. The class roster remains a shared Core-owned class record.
Within Quillan work, `scans/` stores Quillan-routed evidence rather than Core's
retained source scan, while `routes/` is reserved for Core-owned route
registrations. Quillan supports only the module-qualified tree above: there is
no unqualified assignment path, legacy migration, or fallback. Printable class
packets now use immutable v1 issuance/page records and one verified Core route
per physical page. Each QR contains only the canonical PDS2 locator; generation
renders to a same-directory temporary PDF and installs it atomically. Successful
scan dispatch now uses immutable observations and issuance membership for
submission assembly. Routed filenames are diagnostics, never identity.

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
Q. Quit
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
<workspace_root>/classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
```

Printable response packets can also be generated non-interactively:

```powershell
quillan printable-responses generate <class_id> <assignment_id> --dry-run
quillan printable-responses generate <class_id> <assignment_id> --pages-per-student 2 --yes
```

The CLI and menu share the same canonical assignment/roster planning and packet
transaction. Dry runs allocate no identities and write nothing. `--overwrite`
replaces only the canonical PDF; immutable records and Core routes are never
overwritten or reused. Direct CLI generation never opens the result; only the
menu offers an explicit open-file or open-folder choice after installation.
The CLI writes only the assignment-local
`templates/printable_response_pages.pdf` and protects existing packets unless
`--overwrite --yes` is supplied.

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
9. Update review workflow state
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
quillan route-scan <source>
```

It retains each supported image/PDF source exactly once, reads only the Core
retained copy, parses strict PDS2 locators, and dispatches physical pages through
the installed Core module registry. Actionable failures use Core review schema
version `2`. Successful Quillan pages create immutable observations and evidence,
then assemble affected submissions; post-dispatch failures remain distinct from
Core dispatch outcomes.

Opening evidence delegates to the local system viewer and is read-only. It
never marks work reviewed.

### Exports

Student feedback export reads a valid matching `submission.json` and
schema-version-2 `review.json` and can write:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

The three assignment-local CSV reports are:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/class_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/standards_summary.csv
```

Student Performance Summary is the compact ordinary teacher-facing table.
Comprehensive Class Summary (`class_summary.csv`) is audit/troubleshooting
oriented. Standards Summary aggregates assignment Focus Standards.

Exports are derived artifacts. Markdown compatibility export writes only the
Markdown artifact and does not add review export metadata. PDF export, including
PDF with a Markdown companion, updates only the selected canonical `review.json`:
it records export metadata, advances ordinary reviewed work to
`review_state: exported`, and updates `updated_at`. Work returned without a full
review keeps that distinct terminal state. Export does not change teacher
judgments, ratings, rationales, comments, or observations, and it does not mutate
assignment records, submission manifests, routed evidence, rosters, standards,
reusable comments, or sibling review records.

## Direct CLI Commands

The assignment-level review dashboard is available in concise teacher text or
stable schema-version-1 JSON. Both forms are non-interactive and strictly
read-only:

```powershell
quillan review-dashboard <class_id> <assignment_id> [--format text|json]
```

It combines roster coverage, submissions, routed evidence, page states, review
workflow, minimum-requirement outcomes, feedback freshness, and assignment-
filtered scan-review attention. It does not inspect evidence, infer judgments,
assemble submissions, or write exports or reports.

Common direct CLI entry points include:

```powershell
quillan
quillan --help
quillan review-dashboard <class_id> <assignment_id>
quillan review-status <class_id> <assignment_id> <student_id> --format json
quillan assignment --help
quillan roster --help
quillan printable-responses --help
quillan requirements --help
quillan review-units --help
quillan observations --help
quillan ratings --help
quillan feedback --help
quillan review-workflow --help
quillan workspace --help
```

See [`docs/cli_contract.md`](docs/cli_contract.md) for the authoritative,
exhaustive implemented command surface and current option syntax.

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

Create and activate a virtual environment, then install Quillan with its
development extras:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "C:\path\to\pds_core-0.5.x-py3-none-any.whl"
python -m pip install -e ".[dev]"
python -m pip check
```

The configured package index did not provide a compatible PDS Core distribution
during the Core 0.5 baseline validation, so install a verified compatible wheel
first. Pip then confirms that wheel satisfies Quillan's declared
`pds-core>=0.5,<0.6` runtime dependency. A sibling Core checkout is not required,
and no neighboring Core source path is used. `requirements-dev.txt` is a
convenience wrapper around `.[dev]` and may be used instead of the direct
editable-install command.

To validate clean editable and noneditable installations, run:

```powershell
powershell -ExecutionPolicy Bypass `
    -File .\scripts\validate_development_install.ps1 `
    -Python .\.venv\Scripts\python.exe `
    -PdsCoreWheel "C:\path\to\pds_core-0.5.x-py3-none-any.whl"
```

The equivalent `PDS_CORE_WHEEL` environment variable may be used instead of
`-PdsCoreWheel`; an explicit parameter takes precedence. The isolated validation checks package metadata, editable and noneditable installation, installed import origins, CLI availability, and workspace side effects. During the v0.8.9 migration, all active Quillan runtime surfaces are being converted to PDS2 and module-qualified storage.


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

### Plain-paper manual submissions

When a student writes on paper outside Quillan, select that roster student in
Review Student Work and choose **Create plain-paper submission for this
student**. Quillan creates a review-ready `submission.json` and `review.json`
without routing a scan, running OCR, or fabricating digital evidence. The
physical paper remains under the teacher's control, and the normal
standards-based review and export actions apply after setup. This plain-paper
workflow does not create QR, route, page, scan, or digital-evidence records.
Never commit real student data or workspace artifacts.
