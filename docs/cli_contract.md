# Quillan CLI Contract

## Purpose and Status

This document defines Quillan's command-line contract during pre-1.0
development. It records:

* the command surface that is implemented now;
* the boundary between direct commands and the interactive menu;
* conventions for help, errors, paths, output, and exit status; and
* the compatibility expectations contributors should use when changing the
  CLI.

The CLI includes a developer-oriented, scriptable command layer and a
teacher-facing terminal menu. The menu now covers assignment management, roster
management, printable response pages, QR-aware scan intake, review navigation,
guided review-entry actions, guided export actions, Manage Review Materials guidance,
workspace settings, help, and exit.

This contract describes implemented behavior separately from future design. A
command or workflow documented elsewhere as planned is not part of the current
CLI until it is implemented, tested, and added here.

Quillan is pre-1.0. Command names, output, and conventions may evolve, but
changes should be intentional, documented, and covered by tests.

## Invocation

Installing the project exposes the `quillan` console command through the
entry point in `pyproject.toml`:

```text
quillan = "quillan.cli:main"
```

The supported user-facing invocation is therefore:

```powershell
quillan [command] [arguments]
```

Calling `quillan.cli.main()` from Python is useful for tests, but it is not a
separate public Python API contract.

## Current Command Surface

The implemented command surface currently exposed through argparse is:

```powershell
quillan
quillan --help
quillan validate-assignment <path>
quillan route-scan <source-file> --payload "<already-decoded PDS1 payload>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
quillan open-evidence <workspace-relative-evidence-path>
quillan open-submission <class_id> <assignment_id> <student_id>
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity <polarity> [--standard-id <standard_id>]
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id> [--standard-id <standard_id>]
quillan set-score <class_id> <assignment_id> <student_id> --criterion <criterion_id> --label "..." --score <number> --max-score <number>
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan workspace --help
quillan menu
```

Running `quillan` without a command launches the teacher-facing terminal menu.
Running `quillan workspace` without a subcommand prints top-level help and
exits successfully; it does not inspect or modify the workspace.

The teacher-facing menu may also be launched explicitly:

```powershell
quillan menu
```

Bare `quillan` and the explicit `menu` command launch the same interactive
menu. The other commands remain direct and non-interactive.

### `validate-assignment`

```powershell
quillan validate-assignment <path>
```

Loads a UTF-8 JSON assignment configuration and applies Quillan's current
structural assignment validation rules. Cross-file validation against the
shared `pds-core` workspace standards library is available through Quillan's
assignment standards-selection helper, but this CLI command does not currently
load the workspace standards library.

On success, it writes this form to standard output:

```text
Valid assignment config: <assignment_id>
```

It is read-only. It does not create an assignment directory, copy the
configuration into the workspace, or validate referenced files as a complete
cross-file workflow.

### `workspace show`

```powershell
quillan workspace show
```

Uses the shared `pds-core` workspace status API to report:

* the resolved Paper Data Suite workspace root;
* the source used to resolve it;
* whether the root exists;
* whether it is a directory;
* whether it is writable;
* the shared configuration-file path; and
* the default workspace root.

This command reports status only. It does not create, select, repair, or
change a workspace. A reported `no` value is status information and does not
by itself make the command fail.

### `workspace set`

```powershell
quillan workspace set <path>
```

Uses shared `pds-core` behavior to validate/create the supplied workspace root
and save it as the Paper Data Suite workspace preference. This operation does
not move, copy, migrate, delete, archive, or reorganize existing Quillan or
Paper Data Suite files. If `PDS_WORKSPACE_ROOT` is set, the environment value
still takes precedence over the saved preference.

### `workspace validate`

```powershell
quillan workspace validate
```

Resolves the active root using the shared precedence rules, creates the
workspace and shared metadata if needed, and verifies that it is writable. It
does not prompt for a different root or change the saved preference.

### `workspace reset`

```powershell
quillan workspace reset
```

Clears only the saved Paper Data Suite workspace-root preference. It does not
delete workspace directories or files. The command reports the newly resolved
root after reset; `PDS_WORKSPACE_ROOT`, when set, still takes precedence.

All workspace commands use shared `pds-core` APIs and configuration. Quillan
does not maintain a separate workspace config. Expected workspace errors are
reported as `Error: ...` without a traceback and return a nonzero status.

## Direct CLI and Menu Boundary

Direct CLI commands and the interactive menu serve different use cases.
They may call the same application services, but neither should implement
business rules independently.

### Direct CLI commands

A direct command should be preferred when the operation:

* has an explicit name and a bounded set of arguments;
* can run without a sequence of interactive prompts;
* is useful in development, diagnostics, scripts, or repeatable workflows;
* can report a clear success or failure status; and
* does not require the user to navigate a teacher-facing session.

Validation, status inspection, import/export, and other discrete operations
are natural direct-command candidates. Direct commands should remain usable
without the menu.

### Interactive menu

Bare `quillan` launches the current menu. `quillan menu` is an explicit alias
for the same behavior.

The top-level menu provides:

```text
1. Assignment Management
2. Review Student Work
3. Roster Management
4. Workspace Settings
5. Help
6. Exit
```

Menu workflows should orchestrate reusable application functions. They should
not become the only route to core operations, and they should not duplicate
business rules that already live in CLI handlers or domain modules.

#### Assignment Management

Assignment Management provides:

```text
1. Create writing assignment
2. View/validate assignment
3. Printable Response Pages
4. Back
```

Creation selects one class with an existing canonical roster, prompts for the
fields in the existing assignment config contract, and writes:

```text
<workspace_root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Assignment creation prompts for:

* assignment title;
* assignment ID;
* writing type;
* pds-core standards profile selection;
* tagging mode;
* pds-core focus-standard selection;
* basic requirements; and
* rubric ID.

`writing_type` is currently a typed teacher-entered value, not a discovered or
selectable list.

`standards_profile_id` is selected from the active pds-core standards library
and stored as a durable pds-core `profile_id`. Focus standards are selected
from that profile and stored as durable pds-core `standard_id` values.

An existing config is replaced only after exact `OVERWRITE` confirmation.

View/validate accepts an explicit JSON path, uses the existing assignment
loader and validator, prints a concise summary, and does not rewrite the file.

These workflows do not add assignment editing, deletion, import, scoring,
feedback, tagging execution, requirements checking, reports, scan routing,
OCR, or AI.

#### Roster Management

Roster Management provides:

```text
1. Create class roster
2. View class roster
3. Edit class roster
4. Validate class roster
5. Back
```

These menu-only workflows use shared `pds-core` class and roster APIs.
Canonical rosters are stored at:

```text
<workspace_root>/classes/<class_id>/roster.csv
```

Student IDs remain strings, including leading zeros, and existing optional
columns remain in their original order. Viewing and validation are read-only.

Editing stages shared immutable roster mutations in memory. Add, edit, and
active-roster removal do not write immediately. Saving requires typing `SAVE`;
canceling staged changes requires typing `DISCARD`.

Active-roster removal never deletes assignments, submissions, printable PDFs,
scans, reports, tags, scores, feedback, or historical evidence.

#### Printable Response Pages

Printable Response Pages is reached through Assignment Management and provides:

```text
1. Generate class packet
2. Back
```

Generation selects a class with an existing canonical roster, then selects a
canonical assignment config for that class. Invalid configs are identified and
cannot be selected; the assignment must include the selected class in
`class_ids`.

Blank pages-per-student input defaults to `1`, and nonblank input must be a
positive integer.

The current output mode is one combined class packet PDF:

```text
<workspace_root>/classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
```

An existing packet is replaced only after exact `OVERWRITE` confirmation.

The workflow uses the existing roster-aware printable generator and does not
alter roster or assignment data. It does not add individual PDFs, scan
routing, OCR, review, scoring, feedback, reports, AI, or a direct printable
CLI command.

#### Scan Intake / Route Paper Responses

Scan Intake / Route Paper Responses is reached through Review Student Work and
prompts for a local scan source path:

```text
Scan file or folder path (leave blank to cancel):
```

Blank input cancels without routing files.

Nonblank input trims surrounding whitespace and removes one matching pair of
surrounding quotes, so pasted Windows paths such as
`"C:\Users\Teacher\Desktop\scan folder"` work as a single path.

The source may be a supported image file, a PDF, or a non-recursive folder
containing supported image/PDF scan files.

The workflow uses the same QR-aware implementation path as:

```powershell
quillan route-scan <source> --decode-qr
```

It does not expose payload mode.

It prints the structured scan intake summary, including processed sources,
attempted pages, routed, preserved, failed, skipped unsupported,
review-required, and failure-category counts.

If routed evidence exists, it prints the same explicit
`assemble-submissions` next-step guidance as the direct command.

If review is required, the preserved-failure caution is printed.

The workflow does not automatically assemble submissions, move or archive the
teacher's original source files, create `submission.json` or `review.json`,
run OCR, score, tag, generate feedback, or perform AI work.

#### Review Student Work

Review Student Work provides guided scan intake, review-material management,
class, assignment, and student/submission navigation plus review-entry and
export actions.

The first Review Student Work menu provides:

```text
1. Assignment Review Actions
2. Scan Intake / Route Paper Responses
3. Manage Review Materials
4. Back
```

The workflow lists available classes from the active workspace, lists
assignments for the selected class, and prints the current assignment
submission status through the existing status formatting path.

Roster students remain visible even when they do not yet have an assembled
submission.

After a class and assignment are selected, the assignment-level review actions
menu provides:

```text
1. Select student/submission
2. Assemble routed submissions
3. Export class review summary
4. Export standards summary
5. Refresh submission status
6. Back
```

Selecting a student/submission lets the teacher pick a student by number. The
selected-student view shows a compact current review summary with class,
assignment, student, submission/evidence status, review state, and existing
`review.json` counts when a valid review record is already present. Long file
paths are reserved for detail/output actions.

Assignment-level student selection clears the prior assignment-status summary
before showing the student list. Nested review selections such as reusable
tags, reusable comments, and rubric scoring also clear between levels so each
screen stands on its own. `B. Back` returns to the immediate previous
selection screen.

The selected-student review menu provides:

```text
1. Open submission evidence
2. Record minimum requirement checks
3. Manage submission pages
4. Add teacher note
5. Add structured tag
6. Select reusable comment
7. Set criterion score
8. Update submission review state
9. Export student feedback
10. Refresh summary
11. Back
```

Opening submission evidence delegates to the same existing safe selected
evidence-opening path as:

```powershell
quillan open-submission <class_id> <assignment_id> <student_id>
```

Missing manifests or missing selected evidence are reported clearly.

`Record minimum requirement checks` lists checks generated from the selected
assignment's `basic_requirements`: minimum/maximum paragraph count,
minimum/maximum word count, and each configured required element. The teacher
records each check as `1` for met/yes or `2` for not met/no. Quillan stores
the teacher-entered boolean in `review.json.requirement_checks`; it does not
count words or paragraphs, parse writing, run OCR, use AI, infer a result, or
change rubric scores.

Guided review-entry actions reuse the same underlying review services as the
direct commands:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity <polarity>
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
quillan set-score <class_id> <assignment_id> <student_id> --criterion <criterion_id> --label "..." --score <number> --max-score <number>
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

`Add structured tag` opens an Add Tag chooser. Teachers can select a reusable
tag from `shared/tag_banks/<tag_bank_id>.json` by bank, category, and tag
template, or choose Custom tag for a one-off/manual observation. Reusable tag
screens show bank titles, category labels, tag labels, optional
severity/polarity, and durable IDs as secondary detail. Custom tag polarity is
selected from enumerated choices, and optional details are grouped behind an
explicit prompt. Reusable tag selections snapshot template values into
`review.json.tags` with
`source: "tag_bank"`, `tag_bank_id`, and `tag_template_id`; custom tags and the
direct `add-tag` command remain compatible.

`Select reusable comment` is selection-first: the teacher chooses a comment
bank, category, and student-facing comment, sees a feedback preview, then
confirms the write or changes the include-in-feedback setting. Comment labels
are primary; bank and comment IDs are displayed as secondary durable details.
Missing comment banks point teachers to Review Student Work ->
Manage Review Materials -> Comment Banks.

`Set criterion score` opens a score chooser. Teachers can score from a valid
shared rubric resolved through `assignment.rubric_id`, or choose Custom
criterion score when the rubric is missing or does not contain the needed
criterion. Rubric scoring shows rubric metadata, criteria, levels, and a
confirmation screen before writing. Custom scoring is label-first and suggests
a `criterion_id`; the direct `set-score` command remains manual and
compatible. Rubric level feedback metadata is informational only and is not
converted into comments.

When reusable comments or tags include pds-core `standard_id` references,
review-time menus may resolve readable metadata through pds-core read-only
selection helpers. Unresolved standards fall back to durable IDs with metadata
unavailable. Quillan does not create, import, edit, retire, reactivate, or
authoritatively validate pds-core standards from review mode.

`Update submission review state` displays the allowed states with
teacher-facing descriptions and requires confirmation before saving. This is
an explicit workflow status change, not a grade, and is not inferred from
notes, tags, comments, scores, or exports.

Guided export actions reuse the same underlying export services as the direct
commands:

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

Menu export actions preserve overwrite protection. Student feedback export
explains that it formats the current review record and does not rescore work
or generate AI feedback. Existing export files are not replaced unless the
teacher explicitly chooses overwrite.

Major selected-student actions clear and reframe the action screen before
prompting. `B`/Back cancels safely; blank input means Back only where the
screen says so. Cancellation does not write review records, submission
manifests, exports, scans, rosters, assignments, review materials, pds-core
workspace preferences, or pds-core route/standards files.

The Review Student Work menu does not automatically assemble submissions,
route scans, run OCR, parse evidence contents, score work automatically, infer
mastery, generate AI feedback, or perform AI work.

#### Manage Review Materials

Manage Review Materials is reached through Review Student Work and provides a
preparation area for reusable teacher-authored review aids:

```text
1. Comment Banks
2. Tag Banks
3. Rubrics / Scoring Profiles
4. Starter Materials
5. Back
```

The menu is subject-agnostic and is intended for teachers reviewing written
student work such as essays, constructed responses, lab reports, journals,
reflections, research papers, mathematical explanations, technical writing, and
other local writing tasks.

Comment Banks opens a submenu:

```text
1. Create comment bank
2. View comment banks
3. Edit comment bank
4. Add category
5. Add comment
6. Validate comment bank
7. Back
```

Comment-bank authoring writes confirmed, valid version `1` banks only under
`shared/comment_banks/<bank_id>.json`. New banks are immediately available to
Review Student Work -> Select reusable comment because they use the same
schema, loading logic, and validation as review-time selection.

Comment banks are teacher-authored reusable feedback language. They do not
grade work, imply mastery, generate automatic feedback, or mutate student
records by themselves. Review selection snapshots the chosen label and text
into `review.json.comments`; later bank edits do not silently rewrite previous
review records.

Tag Banks opens a submenu:

```text
1. Create tag bank
2. View tag banks
3. Edit tag bank
4. Add category
5. Add reusable tag
6. Validate tag bank
7. Back
```

Tag-bank authoring writes confirmed, valid version `1` banks only under
`shared/tag_banks/<tag_bank_id>.json`. It builds complete banks in memory,
validates before writing, refuses accidental overwrites unless the teacher types
exactly `OVERWRITE`, and does not write invalid partial files.

Tag banks are teacher-authored reusable observations for quick tagging. They do
not grade work, imply mastery, generate automatic feedback, or mutate student
records by themselves.

Review-material authoring prompts use teacher-facing labels while preserving
the JSON contracts. The UI calls `writing_types` "writing assignment types,"
explains comma-separated values and underscores for multi-word values, suggests
stored IDs from labels, and distinguishes labels from system IDs such as
`bank_id`, `tag_bank_id`, `rubric_id`, `category_id`, `comment_id`,
`tag_template_id`, and `criterion_id`. Optional tag details are explained as
description, writing assignment type limits, linked standards, linked rubric
criteria, priority/severity, private note question, and display order.
`student_facing_default` is not prompted for until it has visible runtime
behavior.

Rubrics / Scoring Profiles opens a submenu for teacher-authored reusable
scoring profiles. It writes confirmed, valid version `1` rubrics only under
`shared/rubrics/<rubric_id>.json`; assignment creation and review-time rubric
scoring can immediately resolve valid shared rubrics.

Starter Materials opens a submenu:

```text
1. Preview starter materials
2. Validate starter materials
3. Install all starter materials
4. Install selected starter materials
5. Back
```

Starter materials are optional synthetic examples for onboarding and local
testing. The workflow validates source JSON files with the same comment-bank,
tag-bank, and rubric validators used at runtime. Installation copies validated
JSON files only into `shared/comment_banks/`, `shared/tag_banks/`, and
`shared/rubrics/`. Existing files are skipped by default, and bulk overwrite
requires the exact confirmation text `OVERWRITE`.

Selected Student Review presents the assembled student's review workspace as:

```text
1. Open submission evidence
2. View current review details
3. Record minimum requirement checks
4. Manage submission pages
5. Add teacher note
6. Add structured tag
7. Select reusable comment
8. Set criterion score
9. Update submission review state
10. Export student feedback
11. Refresh summary
12. Back
```

View current review details is terminal-only and read-only. It displays the
current `review.json` contents for the selected student, including requirement
checks, notes, tags, comments, scores, comment feedback-inclusion settings,
and tag/comment targets. It does not generate an export file and does not
modify `review.json`, `submission.json`, or evidence files.

Selected Student Review includes Manage Submission Pages. Teachers can exclude
a page from active review, restore an excluded page, or mark a page as needing
rescan after confirmation. These actions update only the selected student's
`submission.json`, validate before writing, preserve evidence records and
routed files, and do not modify review notes, tags, comments, scores, feedback
exports, rosters, assignments, review materials, pds-core standards, or
pds-core routes.

Starter installation does not create assignments, rosters, scans, submissions,
review records, exports, pds-core standards, pds-core standards profiles, or
pds-core route helpers.

Review materials are Quillan-owned teaching and review aids. They may later
reference durable pds-core `profile_id` and `standard_id` values. Optional
comment-bank and tag-bank `standard_ids` are pds-core references only; optional
tag-bank `criterion_ids` are rubric/scoring metadata only. Quillan does not
create, import, edit, retire, reactivate, or authoritatively validate standards.
The menu does not duplicate or replace pds-core ownership of standards,
workspace resolution, shared class routes, roster routes, scan routes, or route
helpers.

#### Workspace Settings

Workspace Settings provides:

```text
1. Show current workspace
2. Set workspace folder
3. Validate/create current workspace
4. Reset saved workspace preference
5. Back
```

Showing the workspace calls the same status behavior as:

```powershell
quillan workspace show
```

and remains read-only.

Setting prompts for a folder; blank input cancels without changing the saved
preference. Nonblank input validates/creates the folder and saves it through
shared `pds-core` configuration.

Validate/create operates on the currently resolved root.

Reset clears only the saved preference and then reports the current resolved
root.

The menu warns that setting does not migrate files, resetting does not delete
files, and `PDS_WORKSPACE_ROOT` still takes precedence.

The workspace submenu does not include school-year settings.

#### Help, Exit, and Shared Menu Behavior

Menu help describes Quillan as a local-first, teacher-controlled
writing-evidence tool; keeps teacher judgment primary; states that Quillan is
not automated grading software; identifies unsupported AI and OCR workflows;
notes that guided scan intake routes QR-coded response pages only; and
summarizes repository safe-data expectations and current direct commands.

The menu clears the screen only when both standard input and standard output
are interactive terminals.

A normal exit or `KeyboardInterrupt` returns status `0`.

CLI parser construction lives in `quillan/cli_app/parser.py`; argument
conversion, output helpers, top-level dispatch, and command handlers live
under `quillan/cli_app`. `quillan/cli.py` remains the public compatibility
facade and `quillan.cli:main` console-script entrypoint. Validation, storage,
workspace resolution, and other domain behavior belong in their relevant
modules or in shared `pds-core` services.

## Help and Discoverability

`--help` is the canonical discovery mechanism at each parser level:

```powershell
quillan --help
quillan workspace --help
```

Help output should:

* identify Quillan and its purpose;
* list implemented commands only;
* show required positional arguments and available options;
* use the command names and argument forms documented here; and
* exit with status `0`.

Command summaries should describe effects accurately, especially whether an
operation reads, writes, or modifies workspace data. Planned commands belong
in design or roadmap documentation, not active help output.

During the current pre-1.0 period, a command-specific parser level without a
selected operation may continue to print help and return `0`. The top-level
parser is different: bare `quillan` launches the teacher-facing menu.

## Paths and Filesystem Behavior

Path arguments use the platform's normal path syntax and Python's `pathlib`
semantics.

* Relative paths are interpreted from the process's current working
  directory.
* Absolute paths are accepted.
* Paths containing spaces should be quoted by the invoking shell.
* File-validation commands require a readable file; they do not search the
  PDS workspace or example directories for a missing path.
* JSON inputs are read as UTF-8.
* Commands should not expand `~`, environment variables, or shell wildcards
  themselves. Any expansion performed by a shell occurs before Quillan sees
  the argument.
* User-facing path errors should include the relevant path when doing so is
  safe and useful.

Commands that operate on managed Paper Data Suite records should use shared
`pds-core` workspace and route contracts rather than constructing competing
workspace layouts. The active layout is documented in
[`workspace_lifecycle.md`](workspace_lifecycle.md).

Commands that write files document their destination, overwrite policy, and
handled-failure behavior in their command sections and help output.

## Scan Routing

```powershell
quillan route-scan <source-file> --payload "<already-decoded PDS1 payload>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
```

This command routes selected scan sources using exactly one payload source:
caller-supplied canonical PDS1 text through `--payload`, or QR payloads
decoded from a supported local image, each page of a PDF, or every supported
scan file directly inside a folder through `--decode-qr`.

Folder intake is QR-aware only; `--payload` requires a file and rejects
folders.

Supported scan extensions are:

```text
.jpeg
.jpg
.pdf
.png
.tif
.tiff
```

PDF intake uses `pdf2image`, which requires Poppler installed on the user's
machine.

Folder intake is non-recursive. It processes only direct child files in
deterministic order by case-insensitive filename with a stable filename
tie-breaker. Unsupported files such as `.txt`, `.csv`, `.DS_Store`, or
`Thumbs.db` are skipped, counted in the structured summary, and are not
failures.

An empty folder, or a folder with no supported scan files, prints a clear
error and exits `1`.

On success, route-scan retains the source under:

```text
scans/source/YYYY-MM-DD/
```

and files routed evidence under the target assignment's `scans/` directory.

PDF pages route independently and successful PDF page evidence is filed as PNG
files. `source_page_number` records the physical PDF page separately from the
decoded `payload_page_number`.

Decode, payload, planning, filing, or PDF conversion failures are preserved
under:

```text
scans/review/
```

when they can be handled safely.

QR-aware image and PDF intake prints a structured scan intake summary with
source, page, routed, preserved, failed, skipped unsupported, and
review-required counts. Folder intake produces one aggregate summary across
all processed sources.

Partial success is explicit: exit `0` can mean all pages routed or that
expected failures were safely preserved for review, including when later files
continued after a preserved failure. Preserved failures require review before
intake is treated as complete. Exit `1` means an unexpected failure occurred
or a failure could not be preserved safely.

After QR-aware intake, the command derives assembly targets from routed
`ScanIntakePageResult` entries in the current `ScanIntakeSummary`. Routed
pages with both `class_id` and `assignment_id` are grouped by class/assignment
and reported in deterministic order as explicit next-step commands:

```powershell
quillan assemble-submissions <class_id> <assignment_id>
```

Preserved, failed, skipped, and malformed routed pages without complete
class/assignment identity do not create assembly targets.

The command does not scan assignment `scans/` directories to find targets, so
the guidance only reflects evidence routed by the current intake run.

When review is required, the next-step message warns that preserved failures
should be reviewed before the batch is treated as complete.

The command does not move, delete, or archive source files after folder
intake. The Scan Intake / Route Paper Responses menu invokes this same
QR-aware intake path.

QR-aware scan intake does not assemble submissions, create review records, run
OCR, or identify a student from raw scan content without a valid payload.

## Submission Assembly and Status

```powershell
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
```

`assemble-submissions` discovers already-routed PDF and image evidence by the
assignment filename convention and creates canonical student `submission.json`
manifests.

Existing manifests are skipped unless `--overwrite` requests full
regeneration. Assembly does not inspect evidence contents, recover provenance
absent from filenames, or choose among ambiguous duplicate evidence.

`list-submissions` is read-only. It reports manifest and page states,
present-but-unselected evidence, students needing assembly, unassembled routed
files, and skipped filenames without creating or modifying records.

These commands do not open evidence, update review state, create review
records, score work, tag work, generate feedback, run OCR, or perform AI work.

## Evidence and Submission Opening

```powershell
quillan open-evidence <workspace-relative-evidence-path>
quillan open-submission <class_id> <assignment_id> <student_id>
```

`open-evidence` opens one existing file that resolves inside the active
workspace.

`open-submission` validates one canonical manifest and opens its single
selected evidence item.

Both commands are read-only. They do not inspect content, select evidence,
score work, tag work, create review records, generate feedback, or update
review state.

## Submission Review State

```powershell
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

The allowed states are:

```text
unreviewed
in_progress
needs_rescan
reviewed
```

This command updates only `submission_state` and `updated_at` in the validated
manifest. It does not open or inspect evidence or make an automatic review
decision.

## Quick Teacher Notes

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
```

This direct command appends one teacher-entered note to canonical
`review.json`, creating the record only when the adjacent `submission.json`
exists, validates, and matches the requested identity.

It preserves the manifest, evidence, and unrelated review content.

## Structured Review Tags

```powershell
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity developing
```

This direct command appends one teacher-entered tag to the canonical
`review.json`, creating that record only when the adjacent `submission.json`
exists, validates, and matches the requested identity.

Optional flags are:

```text
--standard-id
--comment-id
--severity
--note
--page
--evidence-id
--location-type
--location-value
```

Handled workspace, record, and tag-validation failures return `1`.

Success returns `0` and reports the class, assignment, student, tag ID,
polarity, review state, and workspace-relative review-record path.

The command never mutates the submission manifest, routed evidence, or
retained source scans, and it does not score, analyze, or generate feedback.

The guided Selected Student Review tag flow uses teacher-facing target prompts
instead of raw JSON. Teachers may choose whole submission, specific
paragraph(s), a specific page, page plus paragraph(s), skip location, or Back.
Paragraph input accepts values such as `2`, `2-4`, `2,4,6`, and `2, 4-6`.
Targets are teacher-entered metadata; Quillan does not parse writing, run OCR,
use AI, count paragraphs, or infer where a tag belongs.

## Reusable Comment Selection

```powershell
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
```

This direct command validates a shared comment bank and appends one
teacher-selected student-facing comment to canonical `review.json`.

In the guided Selected Student Review reusable-comment flow, the teacher is
also prompted for the same optional target choices used by tags. The
confirmation screen shows the selected comment text, target, and
include-in-feedback setting before writing. Comment targets are stored in
`review.json.comments` as optional `page_number`, `evidence_id`, and
`location` fields.

Optional flags are:

```text
--standard-id
--include-in-feedback
--exclude-from-feedback
```

The command copies label and text and preserves `bank_id + comment_id`
provenance, so later bank edits do not change the review.

It does not export feedback or mutate the source bank, manifest, or evidence.

## Criterion Scores

```powershell
quillan set-score <class_id> <assignment_id> <student_id> --criterion <criterion_id> --label "..." --score <number> --max-score <number>
```

This direct command sets or updates one explicitly teacher-entered criterion
score in canonical `review.json`.

Optional flags are `--scale` and `--note`.

The command creates a missing review record only when the adjacent
`submission.json` validates and matches the requested identity.

Success returns `0` and reports the class, assignment, student, criterion,
score and maximum, score ID, created-or-updated action, review state, and
workspace-relative review-record path.

Handled workspace, score, and record failures return `1`.

Updating by `criterion_id` preserves the existing score ID and unrelated
review sections.

The command does not validate criteria against a rubric profile, calculate an
overall score, infer scores, or mutate the submission manifest or evidence.

## Student Feedback Export

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
```

This direct command requires valid matching canonical `submission.json` and
`review.json` records, then writes the derived artifact:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

It includes ordered criterion scores and snapshotted comments marked
`include_in_feedback: true`.

It excludes private notes, score notes, structured tags, excluded comments,
and comment source/provenance fields, and it does not read source comment
banks.

Success returns `0` and reports the identity, included-comment count, score
count, overwrite status, and workspace-relative feedback path.

Handled workspace, validation, missing-record, and overwrite failures return
`1`.

Without `--overwrite`, an existing feedback file is preserved.

The command does not mutate review state, timestamps, canonical records, or
evidence.

## Class Review Summary Export

```powershell
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
```

This direct command discovers immediate student directories under the
assignment's canonical `submissions/` directory and writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
```

Rows are sorted by `student_id`.

Valid matching records produce `ready` rows with submission and review states,
score counts and simple score/max-score totals, selected and included comment
counts, tag and note counts, feedback-export existence, and
workspace-relative paths.

Missing, invalid, and identity-mismatched student records produce
`missing_submission`, `invalid_submission`, `missing_review`,
`invalid_review`, or `identity_mismatch` rows rather than aborting the whole
export.

A missing assignment submissions directory is a handled failure.

Success returns `0` and prints row/status counts, overwrite status, and the
summary path. Handled failures return `1`.

The export is read-only with respect to canonical records. It does not read
evidence files or comment banks, use a roster, infer missing students,
calculate percentages, grades, mastery, or weighted results, or generate a
standards summary.

Existing CSV files require `--overwrite`.

## Standards Summary Export

```powershell
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

This command discovers immediate student directories under the assignment
`submissions/` directory and writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

It validates each available `submission.json` and `review.json`, counts
missing, invalid, and identity-mismatched records without aborting the
assignment export, and emits one row per referenced standard sorted by
`standard_id`.

Rows aggregate standards-linked structured tags by polarity and selected
comments by feedback inclusion, plus distinct student counts.

Artifacts without `standard_id` are ignored.

If no valid linked artifacts exist, the command writes a header-only CSV.

Success returns `0`. Handled workspace, validation, missing-directory, and
overwrite failures return `1`.

The export does not include notes or scores, map criteria to standards, inspect
student writing or evidence, read comment banks,
use AI, calculate grades or mastery, use a roster, or mutate canonical
records.

Existing CSV files require `--overwrite`.

## Export and Menu Overwrite Behavior

Direct export commands require `--overwrite` to replace existing export
artifacts.

Guided menu export actions prompt before replacing an existing export file.

Invalid overwrite responses cancel safely.

Exports do not mutate:

* `submission.json`;
* `review.json`;
* routed evidence files;
* retained source scans;
* rosters;
* assignment configs;
* comment banks; or
* pds-core standards libraries.

The menu delegates to the same export services and output formatters as the
direct CLI handlers. It does not implement a parallel export system.

## Output and Error Handling

Human-readable command results are the current output contract. Quillan does
not yet provide a machine-readable `--json` mode, and scripts should not
assume that prose, whitespace, or field ordering will remain stable before
1.0.

The intended convention is:

* successful results and requested help go to standard output;
* usage and argument-parsing errors go to standard error;
* operational or validation failures produce a concise, actionable message;
* expected user errors do not display a Python traceback; and
* diagnostics should distinguish invalid input from an internal programming
  failure.

Current validation failures are reported with these prefixes:

```text
Invalid assignment config: ...
```

Current workspace-resolution failures use:

```text
Error: ...
```

At present, validation failures are emitted to standard error by the console
entry point, while `workspace show` operational failures are printed to
standard output. This is an existing pre-1.0 inconsistency, not a requirement
for new commands. New and revised handlers should converge on standard error
for failures, with tests updated alongside the behavior.

Unexpected exceptions indicate defects and are not converted into a success
status. Sensitive classroom data must not be added to routine diagnostics,
examples, or trace output.

## Exit Codes

The process exit status is part of the CLI contract:

| Status        | Meaning                                                                                                                                            |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0`           | The requested operation or menu session completed successfully, or help was requested or printed for a no-operation command-specific parser level. |
| `1`           | The command was understood, but validation or an operational action failed.                                                                        |
| `2`           | Command-line usage was invalid, as reported by `argparse`.                                                                                         |
| Other nonzero | An unexpected failure or a future explicitly documented category.                                                                                  |

Examples of status `1` include a missing or invalid JSON input and failure to
resolve workspace status. Examples of status `2` include an unknown command,
a missing required path argument, and an unexpected extra argument.

Callers should generally treat `0` as success and any nonzero value as
failure. They should not depend on additional nonzero distinctions unless a
command documents them.

## Pre-1.0 Compatibility Expectations

Until Quillan reaches 1.0:

* the CLI may add, rename, reorganize, or remove commands;
* human-readable wording and formatting may change;
* exit-code conventions should remain coherent even when command details
  change;
* existing commands should not change meaning casually or silently;
* behavior changes should update this document, user-facing README examples,
  CLI help, and tests as applicable; and
* deprecation is preferred when a widely used command can reasonably be
  migrated, but pre-1.0 changes do not promise a fixed deprecation period.

The source of truth for the current surface is the combination of
`quillan.cli_app`, the public `quillan/cli.py` facade, CLI tests, menu tests,
and this document. If they disagree, the implementation and tests describe
executable behavior, and the mismatch should be corrected rather than treated
as an undocumented feature.

## Not Currently Part of the CLI

The following capabilities are implemented only as Python APIs, planned, or
explicitly outside the current end-to-end foundation:

* printable response generation as a dedicated command;
* submission validation as a dedicated command;
* recursive scan folder intake, source-file archiving, inbox draining, or
  automatic production scan routing;
* OCR or handwriting interpretation;
* PDF text extraction;
* complete requirements-checking workflows;
* AI grading, scoring, tagging, or feedback;
* automatic grading, mastery calculation, review-state decisions, or
  duplicate-evidence selection;
* LMS integration;
* cloud sync;
* email delivery; and
* dashboard/reporting automation.

Their presence in design documents or Python modules does not add them to the
CLI contract.
