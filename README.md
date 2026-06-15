# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It is designed to help teachers tag, score, and respond to student writing by connecting specific locations in written work to standards, comments, rubric scores, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Early planning and development.

Quillan currently supports:

- documented MVP data contracts;
- synthetic example files;
- standards profile loading and validation;
- an initial command-line interface;
- automated tests for standards validation and CLI behavior.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

Teacher judgment remains primary. Quillan may eventually help summarize tags or draft feedback, but final scoring and feedback decisions belong to the teacher.

## Planned MVP

The first useful version should support:

1. Creating or importing standards profiles.
2. Creating writing assignments.
3. Loading or entering plain-text submissions.
4. Checking basic assignment requirements.
5. Tagging subdivisions of writing by standard and comment.
6. Entering teacher-controlled rubric scores.
7. Exporting structured JSON, Markdown, and CSV outputs.

## Early Non-Goals

The MVP should not attempt:

- autonomous AI grading;
- handwriting OCR;
- precise word-level annotation;
- complex GUI development;
- hosted/cloud workflows;
- gradebook sync;
- parent/student emailing;
- district-level dashboards;
- multi-user collaboration.

These may be considered later, but they are outside the initial MVP.

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

Quillan uses `pds-core` route helpers for assignment-local storage beneath the
shared PDS workspace root:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/
```

Quillan also uses `pds-core` to build canonical PDS1 payload strings for
writing-response pages. QR image generation, workspace settings, scan routing,
and paper/PDF workflows are not yet implemented.

Quillan consumes class rosters through the shared `pds-core` roster contract.
Synthetic roster fixtures use the canonical columns `class_id`, `student_id`,
`last_name`, `first_name`, and `period`. Student IDs remain strings, including
leading zeros.

## Running Quillan

Show CLI help:

```powershell
quillan --help
```

Validate a standards profile:

```powershell
quillan validate-standards examples\standards\english_12_njsls_synthetic.json
```

Expected output:

```text
Valid standards profile: english_12_njsls_synthetic
```

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

Quillan's MVP data contracts are documented in [`docs/data_contracts.md`](docs/data_contracts.md).

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
