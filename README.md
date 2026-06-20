# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It is designed to help teachers tag, score, and respond to student writing by connecting specific locations in written work to standards, comments, rubric scores, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Quillan is an early pre-1.0 foundation. It provides direct CLI commands and
an initial teacher-facing terminal menu skeleton, but it is not yet a complete
teacher-facing application.

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
- teacher-facing class roster creation, viewing, staged editing, and validation
  through the Roster Management menu;
- teacher-facing writing assignment config creation and read-only validation
  through the Assignment Management menu;
- teacher-facing generation of one combined printable response class packet
  from an existing canonical roster and assignment config;
- shared Paper Data Suite workspace status reporting;
- assignment-local storage paths based on shared `pds-core` route helpers;
- an internal, read-only decoded response-page route planner that validates
  class, assignment, roster, and student relationships without writing files;
- an internal successful-route evidence filing helper that retains selected
  source scans under `scans/source/YYYY-MM-DD/`, files routed copies under the
  assignment `scans/` directory, and returns source and route provenance
  without assembling submissions; and
- synthetic examples and fixtures for safe testing and documentation.

Printable response generation is exposed through the teacher-facing menu and
the Python API in `quillan.printable_response`. It is not exposed as a
dedicated direct CLI command.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

Teacher judgment remains primary. Quillan may eventually help summarize tags or draft feedback, but final scoring and feedback decisions belong to the teacher.

## Designed but Not Yet Implemented

The data contracts and design documents describe additional teacher-review
and paper-ingest workflows that are not yet implemented end to end. In
particular, Quillan does not currently provide:

- end-to-end production scan intake and routing (the internal APIs require an
  already-selected readable source file and an already-successful route plan);
- routing failure preservation under `scans/review/`;
- QR extraction from scanned PDFs or images;
- OCR or handwriting interpretation;
- automatic conversion of scans into reviewed submissions;
- assignment creation workflows;
- implemented requirements-checking, tagging, scoring, feedback, or
  production reporting workflows;
- AI tagging, AI scoring, or AI feedback;
- automatic grading; or
- complete teacher-facing assignment editing or review workflows; or
- a dedicated printable-response command.

The intended scan-routing rules and failure behavior are documented in
[`docs/scan_routing_design.md`](docs/scan_routing_design.md), but that document
is a design contract rather than an implemented router. Future routing must use
the shared `pds-core` active scan contract: canonical retained sources belong
in `scans/source/YYYY-MM-DD/`, canonical routing review records belong in
`scans/review/`, and assignment-level `scans/` contains routed evidence rather
than canonical source retention.

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

The Roster Management menu creates and reads canonical shared rosters at:

```text
<PDS workspace root>/classes/<class_id>/roster.csv
```

Existing optional columns are displayed and preserved when students are
added, edited, or removed. Edits remain in memory until the teacher types
`SAVE`; canceling changed data requires `DISCARD`. Removing a student changes
only the active roster and does not delete assignments, submissions,
printable PDFs, scans, reports, tags, scores, feedback, or historical
evidence.

The Assignment Management menu creates validated writing assignment configs
from prompts and can view/validate an explicit existing assignment JSON file.
Creation requires an existing canonical class roster and saves to:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Generated configs use Quillan's existing assignment validation contract. This
menu does not edit, delete, import, score, tag, check requirements, generate
feedback or reports, route scans, or perform OCR or AI work.

The Printable Response Pages menu selects an existing canonical class roster
and assignment config, prompts for a positive number of pages per student, and
generates one combined class packet at:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
```

Replacing an existing packet requires exact `OVERWRITE` confirmation.
Generation does not alter the roster or assignment config. Generated PDFs are
local workspace artifacts and should not be committed.

Quillan also consumes the shared PDS1 payload conventions and helpers from
`pds-core`. Each generated response page embeds a QR code containing a
canonical payload such as:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

Generating this QR code is implemented. Extracting it from a later scan,
routing the scan, and performing OCR are not.

## Running Quillan

Launch the initial teacher-facing menu skeleton:

```powershell
quillan
```

`quillan menu` launches the same menu as an explicit alias.

The menu provides writing assignment config creation and validation through
Assignment Management, class roster creation, viewing, staged editing, and
validation through Roster Management, and combined class-packet generation
through Printable Response Pages. Workspace Settings can show, set,
validate/create, and reset the shared Paper Data Suite workspace root. Help
summarizes Quillan's teacher-controlled purpose and safe-data expectations.

Show direct CLI help:

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

The same shared workspace operations are also available directly:

```powershell
quillan workspace set <folder>
quillan workspace validate
quillan workspace reset
```

Quillan uses the shared `pds-core` workspace configuration; it does not create
a Quillan-specific workspace config. Setting a root validates/creates it and
saves the shared preference, but does not move or migrate existing files.
Resetting clears only the saved preference and does not delete workspace
files. In both cases, `PDS_WORKSPACE_ROOT` still takes precedence over the
saved preference when it is set.

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
quillan
quillan --help
quillan validate-standards <standards-profile.json>
quillan validate-assignment <assignment.json>
quillan workspace show
quillan menu
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
