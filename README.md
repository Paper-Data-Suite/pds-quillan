# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It is designed to help teachers tag, score, and respond to student writing by connecting specific locations in written work to standards, comments, rubric scores, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Quillan is an early pre-1.0 foundation. It is developer- and CLI-oriented
rather than a complete teacher-facing application.

Quillan currently supports:

- assignment configuration validation;
- standards profile loading and validation;
- submission metadata validation;
- documented writing-evidence and teacher-review data contracts;
- printable writing-response PDF generation with student, class, assignment,
  and page identity;
- QR codes containing canonical PDS1 Quillan response payloads on printable
  response pages;
- roster-aware printable response generation using shared `pds-core` roster
  records and display-name helpers;
- shared Paper Data Suite workspace status reporting;
- assignment-local storage paths based on shared `pds-core` route helpers; and
- synthetic examples and fixtures for safe testing and documentation.

Printable response generation is implemented as a Python API in
`quillan.printable_response`; it is not yet exposed as a complete teacher
menu or dedicated CLI command.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

Teacher judgment remains primary. Quillan may eventually help summarize tags or draft feedback, but final scoring and feedback decisions belong to the teacher.

## Designed but Not Yet Implemented

The data contracts and design documents describe additional teacher-review
and paper-ingest workflows that are not yet implemented end to end. In
particular, Quillan does not currently provide:

- production scan routing, copying, or filing;
- QR extraction from scanned PDFs or images;
- OCR or handwriting interpretation;
- automatic conversion of scans into reviewed submissions;
- assignment creation and roster management workflows;
- implemented requirements-checking, tagging, scoring, feedback, or
  production reporting workflows;
- AI tagging, AI scoring, or AI feedback;
- automatic grading; or
- full teacher-facing terminal menu workflows or a dedicated
  printable-response command.

The intended scan-routing rules and failure behavior are documented in
[`docs/scan_routing_design.md`](docs/scan_routing_design.md), but that document
is a design contract rather than an implemented router.

## Current Non-Goals

- precise word-level annotation;
- complex GUI development;
- hosted/cloud workflows;
- gradebook sync;
- parent/student emailing;
- district-level dashboards;
- multi-user collaboration.

These remain outside the current foundation. Quillan's implemented printable
pages are identity-bearing writing surfaces; they do not evaluate student
work or imply that scan ingestion and automated review exist.

## Development

Quillan is written in Python.

Development priorities:

- clear data models;
- local-first file storage;
- structured JSON/CSV outputs;
- CLI-first workflow;
- tests around validation, tagging, scoring, and reporting;
- separated command-line logic and core business logic.

## Local Setup

`pds-core` is required for local Paper Data Suite development. Check out
`pds-core` and `pds-quillan` as sibling repositories; the parent directory name
and location can vary:

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

From inside `pds-quillan`, install the project, development tools, and the
editable sibling checkout of `pds-core`:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Installing only Quillan's ordinary third-party dependencies is not sufficient
for Paper Data Suite development because Quillan depends on shared
infrastructure from `pds-core`.

Quillan uses `pds-core` workspace and route contracts. Assignment-local files
follow this convention beneath the resolved shared workspace root:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/
```

Printable response PDFs are written to:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
```

Quillan consumes class rosters through the shared `pds-core` roster contract,
including `pds_core.rosters.load_roster()` and shared student display-name
helpers. Canonical roster columns are `class_id`, `student_id`, `last_name`,
`first_name`, and `period`; student IDs remain strings so leading zeros are
preserved.

Quillan also consumes the shared PDS1 payload conventions and helpers from
`pds-core`. Each generated response page embeds a QR code containing a
canonical payload such as:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

Generating this QR code is implemented. Extracting it from a later scan,
routing the scan, and performing OCR are not.

## Running Quillan

Show CLI help:

```powershell
quillan --help
```

Inspect the shared Paper Data Suite workspace root:

```powershell
quillan workspace show
```

This read-only command reports the resolved root, resolution source, config
path, default root, and basic filesystem status using the shared `pds-core`
workspace status API.

Validate a standards profile:

```powershell
quillan validate-standards <standards-profile.json>
```

Expected output:

```text
Valid standards profile: english_12_njsls_synthetic
```

Validate an assignment configuration:

```powershell
quillan validate-assignment <assignment.json>
```

The current command surface is:

```powershell
quillan --help
quillan validate-standards <standards-profile.json>
quillan validate-assignment <assignment.json>
quillan workspace show
```

Submission metadata validation and printable response generation currently
use Python APIs rather than dedicated CLI commands.

## Quality Checks

Run tests:

```powershell
pytest
```

Run lint checks:

```powershell
ruff check .
```

Run type checks:

```powershell
mypy .
```

Before opening a pull request, all three should pass:

```powershell
pytest
ruff check .
mypy .
```

Run the complete validation sequence, including the diff whitespace check:

```powershell
.\run_tests.ps1
```

## Data Contracts

Quillan's data contracts are documented in
[`docs/data_contracts.md`](docs/data_contracts.md).

The printable response contract and implemented generator are described in
[`docs/printable_response_template.md`](docs/printable_response_template.md).

The shared workspace layout and the distinction between active and reserved
paths are documented in
[`docs/workspace_lifecycle.md`](docs/workspace_lifecycle.md).

Synthetic example files are available in [`examples/`](examples/).

## Synthetic Data Policy

The repository should not include real student data.

Committed examples and tests should use:

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
2. Run `pytest`, `ruff check .`, and `mypy .`.
3. Commit and push the branch.
4. Open a pull request into `main`.
5. Link the relevant issue using `Closes #<issue-number>`.
6. Use squash merge for most feature branches.
7. Delete the remote branch after merging.
8. Pull the updated `main` branch locally.

## License

MIT
