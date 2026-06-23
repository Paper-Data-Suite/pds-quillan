# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It is designed to help teachers tag, score, and respond to student writing by connecting specific locations in written work to standards, comments, rubric scores, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Quillan is an early pre-1.0 foundation. The v0.7.0 milestone provides a
teacher-controlled review and export foundation through direct CLI commands
and Python APIs. The teacher-facing terminal menu currently covers assignment
management, roster management, printable response pages, workspace settings,
help, and exit; it does not yet guide the review and export workflow.

Quillan currently supports:

- assignment configuration validation;
- standards profile loading and validation;
- validation of the legacy text-oriented submission metadata shape;
- documented writing-evidence and teacher-review data contracts;
- a validated shared reusable comment bank contract with a synthetic example
  and direct teacher-controlled comment selection into `review.json`;
- loading and validation for the version `1` reviewable-evidence submission
  manifest through the distinct `quillan.submission_manifest` module;
- assembly of new version `1` submission manifests from caller-provided routed
  evidence metadata, including deterministic evidence IDs, missing and
  duplicate page representation, replacement, damaged, needs-rescan, and
  excluded evidence semantics, retained-source provenance, canonical paths,
  validation, and overwrite protection without choosing among ambiguous
  evidence;
- assignment-level discovery and assembly of already-routed response evidence
  through `quillan assemble-submissions`, with existing manifests skipped by
  default and explicit full regeneration through `--overwrite`;
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
  without assembling submissions;
- an internal routing failure preservation API that writes shared `pds-core`
  failure metadata under `scans/review/`, including retained-source provenance
  when available, without copying review artifacts;
- a direct `route-scan` command for already-decoded payloads, one supported
  QR-bearing image, or a QR-bearing PDF processed page by page. It
  orchestrates the existing parser, QR decoder, payload validator, route
  planner, evidence filer, and failure review helpers;
- read-only assignment submission status listing, workspace-safe local evidence
  opening, and student-aware selected-evidence opening; and
- explicit, teacher-controlled lightweight submission review-state updates
  that change only review metadata;
- direct teacher-controlled quick-note, structured-tag, reusable-comment, and
  criterion-score updates to canonical `review.json` records;
- derived student feedback, class summary, and standards summary exports; and
- synthetic examples and fixtures for safe testing and documentation.

Printable response generation is exposed through the teacher-facing menu and
the Python API in `quillan.printable_response`. It is not exposed as a
dedicated direct CLI command.

Current classroom-data workflows are local-first: they read and write the
teacher-selected Paper Data Suite workspace and do not upload student work,
review records, comment banks, or exports to a hosted service. Canonical v0.7
records and exports live at:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
shared/comment_banks/<bank_id>.json
```

Opening evidence delegates only to the local system viewer. Exports are
derived files and never replace the canonical manifest or review record.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

Teacher judgment remains primary. Quillan may eventually help summarize tags or draft feedback, but final scoring and feedback decisions belong to the teacher.

## Designed but Not Yet Implemented

The data contracts and design documents describe additional teacher-review
and paper-ingest workflows that are not yet implemented end to end. In
particular, Quillan does not currently provide:

- end-to-end production scan intake and routing beyond one already-selected
  source file;
- OCR or handwriting interpretation;
- automatic conversion of scans into reviewed submissions;
- batch-ingesting raw scan folders;
- merging newly routed evidence into existing teacher review state;
- complete requirements-checking workflows;
- AI tagging, AI scoring, or AI feedback;
- AI suggestions or PDF text extraction;
- automatic grading;
- automatic mastery calculation, review-state decisions, or evidence
  selection among duplicates;
- guided teacher-facing submission review, notes, tags, comment selection,
  scoring, feedback export, or summary export workflows;
- teacher-facing scan intake or QR recognition;
- complete teacher-facing assignment editing workflows; or
- a dedicated printable-response command.

The intended scan-routing rules and failure behavior are documented in
[`docs/scan_routing_design.md`](docs/scan_routing_design.md). The implemented
route planner, successful filing helper, and failure preservation helper follow
the shared `pds-core` active scan contract: canonical retained sources belong
in `scans/source/YYYY-MM-DD/`, canonical routing review records belong in
`scans/review/`, and assignment-level `scans/` contains routed evidence rather
than canonical source retention. OCR and review-state updates remain outside
the direct routing and assembly commands.

## Reviewable Evidence Workflow

Quillan's v0.6 workflow separates retained source scans, routed evidence, and
student submission manifests.

A **retained source scan** is the canonical active source copy Quillan keeps in
the source scan store during active scan intake. **Routed evidence** is a file
copied or derived from retained source material and filed under an assignment's
`scans/` directory for student/assignment review. A **student submission
manifest** is the structured record connecting one student and assignment to
pages, page states, one or more evidence records, selected evidence, and
provenance.

A routed evidence file by itself is not a complete student submission. Routing
does not mean that work is complete, reviewed, scored, or ready for feedback.

The supported teacher/developer sequence is:

1. The teacher obtains or selects a local source file.
2. Quillan receives an already-decoded Quillan PDS1 payload.
3. `route-scan` retains the source scan and files routed assignment evidence.
4. If routing cannot safely complete, Quillan preserves failure metadata under
   `scans/review/` rather than silently discarding the failure.
5. `assemble-submissions` creates missing student submission manifests from
   routed evidence.
6. `list-submissions` reports assignment status without writing files.
7. `open-submission` opens the selected evidence for a specific student.
8. The teacher reads and evaluates the evidence in the local system viewer.
9. `add-note` appends a teacher-entered observation to the student's canonical
   `review.json`.
10. `add-tag` appends a teacher-entered structured observation to that review
    record.
11. `add-comment` selects student-facing teacher-authored language from a
    shared comment bank into that review record as a stable snapshot.
12. `set-score` sets or updates one explicitly teacher-entered criterion score.
13. `export-feedback` writes selected comments and criterion scores to a
    student-facing Markdown file.
14. `export-class-summary` writes an assignment-level teacher review CSV.
15. `export-standards-summary` writes an assignment-level standards-linked
    tag and selected-comment CSV.
16. `set-review-state` records lightweight submission-manifest progress when
    the teacher chooses.

Opening evidence and updating review state are separate teacher-controlled
actions. Opening a file never marks a submission reviewed.

The commands in this workflow are:

```powershell
quillan route-scan <source-file> --payload "<PDS1 payload>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
quillan open-evidence <workspace-relative-evidence-path>
quillan open-submission <class_id> <assignment_id> <student_id>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity developing
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
quillan set-score <class_id> <assignment_id> <student_id> --criterion evidence --label "Evidence" --score 3 --max-score 4
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

- `route-scan` retains one selected source scan and files routed evidence from
  either an already-decoded payload, one supported QR-bearing image, or one
  QR-bearing PDF. PDF intake processes pages independently, files page evidence
  as PNG files, and preserves handled failures under `scans/review/`; it does
  not batch-ingest folders, run OCR, use the menu, or assemble a submission.
- `assemble-submissions` creates missing manifests from routed filenames, or
  fully regenerates them with `--overwrite`; it does not inspect file contents
  or choose among ambiguous duplicate evidence.
- `list-submissions` gives a read-only overview of manifests, routed evidence,
  missing, duplicate, needs-rescan, and excluded pages, present-but-unselected
  evidence, and students needing assembly; it does not create or modify files.
- `open-evidence` opens one workspace-relative local evidence file as a
  low-level helper; it does not determine which student submission to review.
- `open-submission` opens one student's selected evidence and requires exactly
  one selected evidence item; it does not update review metadata.
- `add-note` appends teacher-entered text to `review.json`, creating that
  record only when the adjacent `submission.json` exists, validates, and
  matches the requested student submission. It does not mutate evidence or
  the submission manifest.
- `add-tag` appends a teacher-entered structured tag to `review.json`. Tags
  may reference a validated standard, reusable profile comment, page,
  evidence ID, or writing location, but they do not score work, prove mastery,
  or generate feedback.
- `add-comment` validates a shared bank and appends one student-facing source
  comment to `review.json.comments`. The selected record stores
  `bank_id + comment_id` provenance and copies label and text, so later bank
  edits do not change an existing review. Feedback inclusion uses the bank
  default unless explicitly included or excluded; this command does not
  export feedback.
- `set-score` sets one teacher-entered criterion score in `review.json`.
  Existing criteria update by `criterion_id`; unrelated review data is
  preserved. Criterion IDs are not yet validated against rubric profiles, and
  no overall score is calculated.
- `export-feedback` reads a valid matching `submission.json` and `review.json`,
  then writes
  `submissions/<student_id>/exports/feedback.md`. It includes criterion scores
  and only snapshotted comments marked `include_in_feedback: true`, without
  reading source comment banks. Private notes, score notes, tags, and comment
  provenance are excluded. Existing feedback is protected unless
  `--overwrite` is supplied, and export does not mutate canonical records,
  evidence, timestamps, or review state.
- `export-class-summary` discovers immediate student directories under the
  assignment `submissions/` directory and writes
  `assignments/<assignment_id>/exports/class_summary.csv`. Each student gets
  one deterministic row, including status rows for missing, invalid, or
  identity-mismatched records. Ready rows summarize states, teacher-entered
  score totals, selected comments, tags, notes, and feedback-file existence.
  The totals are transparent arithmetic, not grades. The export does not read
  evidence or comment banks and does not mutate canonical records.
- `export-standards-summary` reads valid matching `submission.json` and
  `review.json` records and writes
  `assignments/<assignment_id>/exports/standards_summary.csv`. It creates one
  sorted row per `standard_code` referenced by a structured tag or selected
  comment, including tag polarity, feedback-inclusion, and distinct-student
  counts. It does not include scores or notes, load standards profiles, infer
  mastery or grades, read evidence or comment banks, use a roster, or mutate
  canonical records. Existing output requires `--overwrite`.
- `set-review-state` updates only the manifest's `submission_state` and
  `updated_at`; it does not inspect evidence or make a review decision.

Allowed review states are `unreviewed`, `in_progress`, `needs_rescan`, and
`reviewed`. The review-state update is metadata-only and occurs only when the
teacher explicitly requests it.

Quillan does not perform OCR, handwriting recognition, PDF text
extraction, AI scoring, AI feedback, AI suggestions, automatic grading,
automatic review-state updates, automatic evidence selection among duplicates,
rubric scoring, automatic feedback generation, standards mastery reporting, or
roster-aware missing-student reporting. Quick
notes and structured tags are teacher-entered
records; they do not score or generate feedback by themselves.
The teacher remains responsible for reading and evaluating student work.

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

Reusable teacher-authored comment banks live at
`shared/comment_banks/<bank_id>.json`. The version `1` source-data contract,
category and comment shapes, future assignment activation, and snapshot
boundary with `review.json.comments` are documented in
[`docs/comment_bank_contract.md`](docs/comment_bank_contract.md). The direct
`add-comment` workflow validates a bank and copies selected teacher-authored
language into the canonical review record.

Quillan also consumes the shared PDS1 payload conventions and helpers from
`pds-core`. Each generated response page embeds a QR code containing a
canonical payload such as:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

Generating this QR code is implemented. A caller can route a selected scan
after separately decoding its payload, but Quillan does not extract QR codes,
split PDFs, or perform OCR.

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
The menu does not currently select submissions for review, add notes or tags,
select comment-bank comments, enter scores, export feedback or summaries,
ingest scans, or recognize QR codes. Those operations are direct CLI/API
workflows or future teacher-facing usability work.

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

Open one local evidence file with the system default application:

```powershell
quillan open-evidence classes/<class_id>/assignments/<assignment_id>/scans/<file>
```

The path must be relative to and remain inside the active PDS workspace.
Quillan validates that it identifies an existing file, then delegates the
platform-specific opening behavior to `pds-core`. This command does not
inspect, parse, modify, select, score, tag, review, or generate feedback from
the evidence.

Open the selected routed evidence for one student's canonical submission:

```powershell
quillan open-submission <class_id> <assignment_id> <student_id>
```

Quillan loads and validates the student's manifest, verifies its identity, and
uses the same local evidence-opening support as `open-evidence`. Exactly one
selected evidence item is currently required. Use `list-submissions` first for
missing, duplicate, needs-rescan, or unselected submissions. Opening is
read-only: it does not change review state or select, score, tag, evaluate,
inspect, OCR, or generate feedback from evidence.

Explicitly update one submission's lightweight teacher review state:

```powershell
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

Allowed states are `unreviewed`, `in_progress`, `needs_rescan`, and `reviewed`.
The command changes only `submission_state` and `updated_at` in the validated
manifest. Opening a submission does not update its state. This command does
not open or inspect evidence, score, tag, evaluate, run OCR, or generate
feedback.

Append a quick teacher note to one student's canonical review record:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "Strong claim, but evidence explanation needs work."
```

Notes are stored in `review.json` with stable local IDs and timezone-aware
timestamps. If `review.json` does not exist, Quillan creates it only after the
adjacent `submission.json` validates and matches the requested class,
assignment, and student. Adding a note never mutates `submission.json`, routed
evidence, or retained source scans, and it does not score, tag, or generate
feedback.

Append a structured teacher tag:

```powershell
quillan add-tag <class_id> <assignment_id> <student_id> --label "Evidence needs more explanation" --polarity developing
```

Tags are stored in the `tags` array of the student's canonical `review.json`.
Optional flags can reference a standard (`--standard`), profile comment
(`--comment-id`), severity, teacher note, page, evidence ID, and controlled
location. Standard and comment references use the assignment config and
`shared/standards/<profile_id>.json`; standards in the profile are allowed
even when they are not assignment focus standards. A missing review record is
created only for a valid matching `submission.json`.

Tags remain teacher-entered review artifacts. Adding one does not mutate the
submission manifest or evidence, calculate a score, establish standard
mastery, analyze writing, or generate feedback.

Set or update one teacher-entered criterion score:

```powershell
quillan set-score <class_id> <assignment_id> <student_id> --criterion evidence --label "Evidence" --score 3 --max-score 4
```

Scores are stored in the `scores` array of the student's canonical
`review.json`. A missing review record is created only when the adjacent
`submission.json` validates and matches the requested identity. Repeating the
command for the same `criterion_id` preserves its score ID, updates that
criterion, and preserves unrelated notes, tags, scores, comments, and
metadata. Optional `--scale` and `--note` values describe the latest explicit
teacher input; omitting them during an update removes stale prior values.

Quillan does not derive scores from student writing, tags, notes, comments,
requirements, standards references, or evidence metadata. This command does
not calculate totals, weighted scores, percentages, grades, mastery, or any
other overall score. Rubric-profile criterion validation is future work.

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

Route one selected scan using an already-decoded Quillan PDS1 payload:

```powershell
quillan route-scan <source-file> --payload "PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page>|doc=response"
```

Or route one supported local image or PDF by decoding Quillan response-page QR
payloads:

```powershell
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
```

Successful routing retains the selected source under
`scans/source/YYYY-MM-DD/` and files response evidence under the assignment
`scans/` directory. PDF intake converts pages independently and files routed
page evidence as PNG files, preserving the physical `source_page_number`
separately from the decoded `payload_page_number`. Decode, payload, planning,
filing, and PDF conversion failures are preserved under `scans/review/` when
possible. Exit code `0` means the input was routed or safely preserved for
review; exit code `1` means it could not be handled safely.

This direct developer/teacher primitive is single-scan only. QR-aware intake
supports `.png`, `.jpg`, `.jpeg`, `.tif`, and `.tiff` images plus `.pdf`
files. PDF conversion uses `pdf2image` and requires Poppler installed on the
user's machine. The command does not batch-ingest folders, run OCR, score, tag,
generate feedback, assemble submissions, create review records, create reports,
or expose menu scan intake.

Assemble all student manifests discoverable from routed filenames in an
assignment's `scans/` directory:

```powershell
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
```

Discovery recognizes routed PDF and image filenames such as
`response_00107_pg_003.pdf` and
`response_00107_pg_003__dup_001.png`. It does not inspect evidence file
contents or reconstruct retained-source provenance. Existing manifests are
skipped by default; `--overwrite` fully regenerates them without preserving
prior review state or teacher selections.

List current manifest and routed-evidence status without changing any files:

```powershell
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
```

The status includes submission and page states, present-but-unselected pages,
students with routed evidence but no manifest, unassembled routed files, and
skipped malformed or unrelated scan filenames. Existing manifests are loaded
and validated; an invalid manifest is an error. The command does not open
evidence, assemble or update manifests, select evidence, score, tag, run OCR,
or generate feedback.

The current command surface is:

```powershell
quillan
quillan --help
quillan validate-standards <standards-profile.json>
quillan validate-assignment <assignment.json>
quillan route-scan <source-file> --payload "<PDS1|...>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
quillan open-evidence <workspace-relative-path>
quillan open-submission <class_id> <assignment_id> <student_id>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity developing
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
quillan set-score <class_id> <assignment_id> <student_id> --criterion <criterion_id> --label "..." --score <number> --max-score <number>
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan menu
```

Legacy text-oriented submission metadata validation and printable response
generation currently use Python APIs rather than dedicated CLI commands.

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

The canonical v0.7 teacher-review `review.json` contract is documented in
[`docs/review_record_contract.md`](docs/review_record_contract.md).

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
