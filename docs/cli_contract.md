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
retained review-entry actions, guided export actions, workspace settings, help,
and exit.

As of the v0.8.6 standards-based review redesign gate, legacy generic
review-material workflows are no longer active CLI or menu workflows. The old
`add-tag`, `add-comment`, and `set-score` commands are intentionally removed
from argparse and must not write v1 tag, comment, or score review data.

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

## Direct Minimum-Requirement Review

The `requirements` namespace exposes the teacher-facing minimum-requirement
workflow as direct, non-interactive commands. Running `quillan requirements`
prints namespace help and exits successfully without resolving a workspace or
loading any records.

All three subcommands require a valid canonical assignment and an existing,
valid canonical `submission.json` for the requested class, assignment, and
student. Routed evidence alone is not review-ready; teachers must assemble the
submission first. Evidence-less plain-paper manifests are valid, and a valid
historical or unrostered submission does not require a current roster entry.

`requirements list` prints configured requirements, current checks, summary
counts, review state, and outcome in teacher-facing text. It is strictly
read-only. When `review.json` is absent it reports `not_started`, shows each
requirement as `not checked`, reports outcome `not_checked`, and creates
nothing. Stale checks whose keys are no longer configured are excluded from
configured completion counts.

`requirements set-check` accepts only a key currently derived from the
assignment's `basic_requirements`. Numeric keys are `paragraphs_min`,
`paragraphs_max`, `word_count_min`, and `word_count_max`; required-element keys
use `required_elements:<element>`. Labels and expected values come from the
assignment and cannot be supplied by the caller. `--met` becomes a boolean. A
supplied note is trimmed and stored; omission clears an earlier note. Updating
a key retains its check ID and does not infer or recalculate the outcome.

`requirements set-outcome` accepts exactly `met`, `unmet_continue_review`, or
`returned_without_full_review`. `met` requires every configured requirement to
be checked and met. `unmet_continue_review` requires at least one configured
unmet check; unchecked requirements may remain. Returning without full review
also requires a configured unmet check, an explicit nonblank note, and
`minimum_requirement_policy.allow_return_without_full_review: true` in the
assignment. No CLI flag overrides that policy.

These commands record teacher judgments only. They do not open evidence, count
words or paragraphs, detect required elements, run OCR or AI, infer outcomes,
grade, score, create observations or ratings, or compose feedback. The list
command writes nothing. The two set commands may create or replace only the
canonical
`classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json`,
through the validated atomic review-record writer. They do not modify the
assignment, submission manifest, roster, evidence, scans, exports, reports, or
other suite data.

## Current Command Surface

The implemented command surface currently exposed through argparse is:

```powershell
quillan
quillan --help
quillan assignment create <class_id> <assignment_id> --title <title> --writing-type <type> (--prompt <text> | --prompt-file <path>) --standards-profile-id <profile_id> --focus-standard-ids <id,...> (--yes | --dry-run)
quillan assignment show <class_id> <assignment_id>
quillan assignment validate <class_id> <assignment_id>
quillan requirements list <class_id> <assignment_id> <student_id>
quillan requirements set-check <class_id> <assignment_id> <student_id> --requirement-key <key> --met true|false [--note <text>]
quillan requirements set-outcome <class_id> <assignment_id> <student_id> --outcome met|unmet_continue_review|returned_without_full_review [--note <text>]
quillan review-units show <class_id> <assignment_id> <student_id>
quillan review-units set <class_id> <assignment_id> <student_id> --count <positive_integer>
quillan review-units set <class_id> <assignment_id> <student_id> --units <units.json>
quillan observations list <class_id> <assignment_id> <student_id>
quillan observations set <class_id> <assignment_id> <student_id> --unit-id <unit_id> --standard-id <standard_id> --applicable true|false [--evidence-present true|false] [--rating <integer>] [--rationale <text>] [--include-in-feedback true|false]
quillan roster create <class_id> --input <roster.csv> [--school-year YYYY-YYYY] [--overwrite] (--yes | --dry-run)
quillan roster show <class_id>
quillan roster validate <class_id>
quillan roster add-student <class_id> --student-id <student_id> --last-name <name> --first-name <name> --period <period> [--field <column=value> ...] (--yes | --dry-run)
quillan roster update-student <class_id> <student_id> [--last-name <name>] [--first-name <name>] [--period <period>] [--field <column=value> ...] (--yes | --dry-run)
quillan roster remove-student <class_id> <student_id> (--yes | --dry-run)
quillan validate-assignment <path>
quillan route-scan <source-file> --payload "<already-decoded PDS1 payload>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
quillan list-scan-review [--include-resolved] [--limit N]
quillan resolve-scan-review <failure_id> --action <action> [--message "..."] [--evidence-path <workspace-relative-path>]
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
quillan workspace --help
quillan menu
```

Running `quillan` without a command launches the teacher-facing terminal menu.
Running `quillan workspace` without a subcommand prints top-level help and
exits successfully; it does not inspect or modify the workspace.

Running `quillan roster` without a subcommand prints roster help and exits
successfully without resolving or inspecting the workspace.

Running `quillan review-units` without a subcommand prints review-unit help
and exits successfully without resolving or inspecting the workspace.

Running `quillan observations` without a subcommand prints observation help
and exits successfully without resolving or inspecting the workspace.

### `review-units` commands

`review-units show` loads the canonical assignment and assembled submission
manifest, plus `review.json` when it exists. It reports assignment-derived
unit labels, canonical paths, review state, units, and observation counts. If
there is no review record it reports `not_started`, zero units, and zero
observations without creating a file or directory.

`review-units set` is an immediate, non-interactive replacement operation.
Exactly one of `--count` and `--units` is required. Count mode generates
sequences `1..N`. JSON mode reads a non-empty UTF-8 JSON array whose objects
may contain only `sequence`, `label`, `page_number`, and `evidence_id`.
`sequence` is explicit, unique, positive, non-boolean, and sorted ascending
before writing; it need not be contiguous. Labels must be nonblank. Page and
evidence references are validated only against submission-manifest metadata,
including page/evidence membership. Unknown fields and raw record fields such
as `unit_id`, `unit_type`, `standard_observations`, and `module_details` are
rejected.

The assignment supplies `review_unit.type` and its singular and plural labels.
Canonical IDs are `<type>_<sequence>` and omitted labels become the title-cased
singular label plus the sequence, such as `paragraph_2` / `Paragraph 2`.
Stable canonical IDs preserve their observations when labels or evidence
metadata change. Removed IDs remove their observations, and stale feedback
observation references are cleaned while feedback records, ratings, minimum
requirements, exports, private notes, metadata, and surviving observations
remain intact.

### `observations` commands

The `observations` namespace exposes review-unit Focus Standard observations
as direct, non-interactive commands. Both commands validate the canonical
assignment, require an existing valid canonical `submission.json`, and validate
an existing `review.json` rather than treating a malformed or mismatched record
as empty. Routed evidence is not assembled automatically. A valid plain-paper
manual submission and a valid unrostered historical submission are accepted.

`observations list` is strictly read-only. It reports canonical paths, review
state, review-unit and Focus Standard totals, expected/recorded/unrecorded pair
counts, applicability, evidence, unit-rating and feedback-inclusion counts, and
the assignment rating scale. It then displays every active unit-standard pair,
with units ordered by `sequence` and standards ordered by the assignment's
`focus_standard_ids`. Recorded rows include the observation ID, applicability,
evidence presence, optional unit-level rating and assignment label, rationale,
feedback eligibility, and timestamp. Unit-level ratings are clearly separate
from overall Focus Standard ratings. When no review or no units exist, list
reports zero units and explains that units must be defined first; it returns
success and creates nothing. A `returned_without_full_review` record remains
readable.

`observations set` requires an existing review with defined units. `--unit-id`
must match an active unit and `--standard-id` must match an assignment Focus
Standard. The command completely replaces the editable values for that pair;
it is not a sparse patch. A new pair receives the next globally unique
`observation_NNNN` ID. Updating a pair preserves its observation ID and clears
an earlier rating or rationale when the corresponding optional argument is
omitted.

`--applicable` accepts exactly `true` or `false`. Applicable observations
require an explicit `--evidence-present true|false`; this records only whether
the teacher found related evidence and does not imply mastery. `--rating` is
optional for applicable observations. When present it must be an integer value
from the current assignment's `rating_scale.levels`; when omitted the stored
rating is `null`. Not-applicable observations reject `--evidence-present` and
`--rating`, and store both fields as `null`. Rationale text is trimmed; omission
or blank text stores `null`. Omitted `--include-in-feedback` defaults to `true`
for applicable observations and `false` for not-applicable observations, while
either default may be explicitly overridden.

Feedback eligibility belongs to the observation. Setting it does not compose
feedback or add/remove IDs in `feedback.standard_feedback`. Observation writes
do not create or alter `overall_standard_ratings`. They preserve unrelated
units, observations, minimum-requirement data, feedback records and comments,
exports, notes, top-level metadata, and the original creation timestamp. The
shared observation service performs review-state transitions and refuses to
modify `returned_without_full_review` records until the minimum-requirements
outcome changes.

List writes nothing. Set may modify only
`classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json`
through the shared validated atomic writer. Neither command opens evidence,
parses PDFs or images, runs OCR, handwriting recognition, or AI, infers any
teacher judgment, calculates overall ratings, grades, or scores, marks review
complete, composes feedback, or modifies assignments, submissions, rosters,
evidence, exports, reports, Core data, or ScoreForm data.

Both commands require a valid canonical `submission.json`, including for
plain-paper submissions without digital evidence. They do not require current
roster membership and never assemble a submission automatically. `show` is
read-only and remains available for returned submissions. `set` may create or
atomically update only the canonical `review.json` and rejects a
`returned_without_full_review` record. Neither command opens evidence files,
parses PDFs or images, runs OCR or AI, counts or segments writing, or creates
observations, ratings, feedback, or grades.

The teacher-facing menu may also be launched explicitly:

```powershell
quillan menu
```

Bare `quillan` and the explicit `menu` command launch the same interactive
menu. The other commands remain direct and non-interactive.

### `roster` commands

The `roster` namespace manages canonical shared roster artifacts under
`classes/<class_id>/`. All commands resolve the active Paper Data Suite
workspace through PDS Core; Quillan has no separate roster workspace setting.
Direct roster commands never enter the menu or prompt with `input()`.

`roster create` loads `--input` through the shared roster CSV loader. The CSV
must contain `class_id`, `student_id`, `last_name`, `first_name`, and `period`,
with at least one valid row. Its class ID must exactly match the positional
class ID. The validated roster is written through the shared canonical writer,
not copied byte-for-byte. Student IDs remain strings, so leading zeros are
preserved. Optional columns, their order, blank values, and row order are also
preserved.

Creation uses an explicit valid `--school-year` when supplied, otherwise the
workspace's active school year. If neither exists, creation fails with guidance
and writes nothing. A confirmed creation writes exactly the paired canonical
artifacts `classes/<class_id>/roster.csv` and
`classes/<class_id>/class.json`. If either target already exists, replacement
requires both `--overwrite` and `--yes`; the paired plan is fully validated
before writing. A failed new paired write removes artifacts newly created by
that operation.

`roster show` and `roster validate` are read-only. Both load the canonical CSV
through PDS Core. Show displays every required and optional column, the student
count, paths, and the class school year when valid metadata exists. Missing
metadata is reported as `not set`; malformed metadata is reported without a
traceback. Validate also checks canonical folder identity and any existing
metadata. Missing metadata remains valid for older class folders, while invalid
existing metadata makes validation fail.

`add-student`, `update-student`, and `remove-student` construct a new immutable
roster through shared PDS Core mutation functions and replace only
`classes/<class_id>/roster.csv` after `--yes`. They never modify `class.json`.
Add appends a student; update preserves both row position and the positional
student ID as stable identity; remove affects only the active roster and cannot
remove its final student.

Optional values use repeatable `--field column=value` arguments. Only columns
already present in the roster's optional schema are allowed. Required columns,
unknown columns, and duplicate keys fail. Add fills omitted optional values
with blank strings. Update retains omitted values, while `--field name=` clears
that value. These commands cannot add CSV columns.

Every roster write requires exactly one of `--yes` or `--dry-run`. Omitting
both fails without prompting or writing. Dry runs perform normal validation,
show the target and resulting count, and create no directories or files.
Active-roster removal does not traverse or delete class metadata, assignments,
submission manifests, reviews, scans, printable PDFs, evidence, notes,
observations, ratings, feedback, exports, reports, historical results, or other
module data.

### `assignment create`, `show`, and `validate`

```powershell
quillan assignment create <class_id> <assignment_id> ...
quillan assignment show <class_id> <assignment_id>
quillan assignment validate <class_id> <assignment_id>
```

`assignment create` builds the same schema-version-2 shape and uses the same
defaults and structural validation as menu assignment creation. It requires an
existing canonical class roster and validates the selected profile and Focus
Standards against the active workspace's PDS Core standards library. New writes
require `--yes`; replacing an existing config requires both `--overwrite` and
`--yes`. `--dry-run` validates and reports the canonical path without creating
an assignment directory or writing files.

New menu and CLI assignments include equal initial `created_at` and `updated_at`
values as timezone-aware UTC ISO 8601 strings and include an empty
`module_details` object.

The prompt may be supplied inline with `--prompt` or read as UTF-8 text with
`--prompt-file`. Basic paragraph, word-count, and required-element options are
optional. Review-unit labels and the four-level standards rating scale default
to the same values used by the menu.

`assignment show` loads the canonical workspace config, validates its structure
and path identity, and prints the shared assignment summary. `assignment
validate` additionally validates the standards profile and every Focus Standard
against the active workspace library. Both commands are read-only. They reject
older records missing required schema-version-2 fields and do not normalize or
rewrite them.

These commands write or inspect only
`classes/<class_id>/assignments/<assignment_id>/assignment.json`; they do not
create submission, review, evidence, scan, export, Core, or ScoreForm data.

### `validate-assignment`

```powershell
quillan validate-assignment <path>
```

Loads a UTF-8 JSON assignment configuration and applies Quillan's current
structural assignment validation rules. Cross-file validation against the
shared `pds-core` workspace standards library is available through Quillan's
assignment standards-selection helper, but this CLI command does not currently
load the workspace standards library. The structural rules require
timezone-aware ISO 8601 `created_at` and `updated_at` strings and an object-valued
`module_details` field. Missing legacy fields are rejected without changing the
input file.

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
fields in the active schema version `2` assignment config contract, and writes:

```text
<workspace_root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

Assignment creation prompts for:

* assignment title;
* assignment ID;
* writing type;
* student prompt;
* pds-core standards profile selection;
* pds-core Focus Standard selection stored as `focus_standard_ids`;
* review-unit configuration;
* rating-scale configuration;
* basic requirements; and
* minimum-requirement return policy.

`writing_type` is currently a typed teacher-entered value, not a discovered or
selectable list.

`standards_profile_id` is selected from the active pds-core standards library
and stored as a durable pds-core `profile_id`. Focus standards are selected
from that profile and stored as durable pds-core `standard_id` values.

An existing config is replaced only after exact `OVERWRITE` confirmation.

View/validate accepts an explicit JSON path, uses the existing assignment
loader and validator, prints a concise summary, and does not rewrite the file.

These workflows do not add assignment editing, deletion, import, scoring,
feedback, generic tagging, reports, scan routing, OCR, or AI.

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

Review Student Work provides guided scan intake, class, assignment, and
student/submission navigation plus retained review-entry and export actions.

The first Review Student Work menu provides:

```text
1. Assignment Review Actions
2. Scan Intake / Route Paper Responses
3. Back
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
3. Export Comprehensive Class Summary
4. Export Standards Summary
5. Export Student Performance Summary
6. Back
```

Selecting a student/submission lets the teacher pick a student by number. The
selected-student view shows a compact current review summary with class,
assignment, student, submission/evidence status, review state, and existing
`review.json` counts when a valid review record is already present. Long file
paths are reserved for detail/output actions.

Assignment-level student selection clears the prior assignment-status summary
before showing the student list. Nested review selections clear between levels
so each screen stands on its own. `B. Back` returns to the immediate previous
selection screen.

Terminal review screens should clear and redraw after a teacher selects an
option by default. Retaining prior output is intentional only when that
information provides necessary context for the current action. Parent
dashboards may show broader status, but focused action screens should show
only the current task, selected student, selected review unit/requirement/Focus
Standard when relevant, and immediately useful status. Confirmation screens
should be concise, and `Back` should return to the previous menu with its
fuller context restored. Prior menu options, parent dashboard blocks, and
debug-style details should not remain on screen merely because the terminal
transcript stacked them there.

The selected-student review menu provides:

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

Opening submission evidence delegates to the same existing safe selected
evidence-opening path as:

```powershell
quillan open-submission <class_id> <assignment_id> <student_id>
```

Missing manifests or missing selected evidence are reported clearly.

`Review minimum requirements` lists checks generated from the selected
assignment's `basic_requirements`: minimum/maximum paragraph count,
minimum/maximum word count, and each configured required element. The teacher
records each check as `1` for met/yes or `2` for not met/no. Quillan stores
the teacher-entered boolean in `minimum_requirement_checks` and stores the
teacher-selected result in `minimum_requirement_outcome`. It does not count
words or paragraphs, parse writing, run OCR, use AI, infer a result, or change
standards ratings.

`Review units and Focus Standard observations` lets the teacher define or
replace review units and record teacher-entered observations for assignment
Focus Standards. Observations may be applicable or not applicable, may record
teacher-entered evidence presence, may omit a rating, and may be included or
excluded from feedback consideration.

`Overall Focus Standard ratings` summarizes observations by Focus Standard and
lets the teacher enter overall ratings from the assignment `rating_scale`.
Ratings are not inferred from observations. Marking ratings complete is an
explicit teacher action.

`Compose Focus Standard feedback` stores per-standard rating/rationale
inclusion choices, selected observation IDs, custom comments, reusable Focus
Standard comment snapshots, and save-for-reuse choices under
`feedback.standard_feedback`. Marking feedback composed is explicit.

Retained guided review-entry actions reuse the same underlying review services
as the direct commands:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

The generic structured-tag, comment-bank, rubric, and criterion-score runtime
workflows have been removed. Quillan does not create, import, edit, retire,
reactivate, or authoritatively validate pds-core standards from review mode.

`Update submission review state` displays the allowed states with
teacher-facing descriptions and requires confirmation before saving. This is
an explicit workflow status change, not a grade, and is not inferred from
notes, tags, comments, scores, or exports.

Guided export actions reuse the same underlying export services as the direct
commands:

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-student-performance-summary <class_id> <assignment_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-comprehensive-class-summary <class_id> <assignment_id> [--overwrite]
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

Selected Student Review includes Manage Submission Pages. Teachers can exclude
a page from active review, restore an excluded page, or mark a page as needing
rescan after confirmation. These actions update only the selected student's
`submission.json`, validate before writing, preserve evidence records and
routed files, and do not modify review notes, tags, comments, scores, feedback
exports, rosters, assignments, review materials, pds-core standards, or
pds-core routes.

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

## Scan Review Resolution

`quillan list-scan-review` lists valid unresolved and deferred Quillan routing
review records from the active workspace. `--include-resolved` also shows items
whose latest valid resolution is resolved; `--limit`, `--class-id`,
`--assignment-id`, and `--failure-category` narrow the display. Malformed or
unreadable metadata is skipped with a warning count instead of making the
entire listing fail.

`quillan resolve-scan-review <failure_id> --action <action>` accepts
`rescan_needed`, `cannot_route`, `mixed_assignment`, `evidence_filed`,
`dismissed_duplicate`, `other`, or `defer`. Common actions have safe default
messages; `other` requires `--message`. `--evidence-path` is accepted only with
`evidence_filed` and must be workspace-relative.

The command writes a new exclusive-create Core resolution record under
`scans/review/resolutions/`. It does not change the referenced failure record,
retained scan, submission manifest, submission review state, or teacher review
record. The interactive **Review Student Work > Resolve Scan Review Items**
path provides the same decisions with compact list, detail, action, note, and
result screens.

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

## Plain-Paper Manual Submission

```powershell
quillan create-plain-paper-submission <class_id> <assignment_id> <student_id> --yes
quillan create-plain-paper-submission <class_id> <assignment_id> <student_id> --dry-run
```

This command is for student work completed on physical plain paper when no
digital, QR, or scanned evidence exists. It creates only the canonical
evidence-less `submission.json` and paired empty `review.json`; it does not
create scans, routed evidence, OCR output, PDFs, images, or feedback.

`--yes` is required to write without an interactive prompt. `--dry-run` runs
the same identity, assignment, roster, and existing-record validation and
reports the workspace-relative target paths without writing files. The flags
are mutually exclusive.

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

## Removed Legacy Review Writes

The legacy direct review-write commands `add-tag`, `add-comment`, and
`set-score` are no longer part of the active CLI surface. They were removed as
part of the v0.8.6 standards-based review redesign gate and must not write v1
`review.json.tags`, `review.json.comments`, or `review.json.scores` data.

The matching selected-student menu actions for structured tags, reusable
comments, and criterion scores are also removed. Replacement Focus Standard
observation, rating, feedback, and reporting workflows now live in the guided
selected-student menu and schema version `2` review record.

## Student Feedback Export

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--format markdown|pdf|both] [--overwrite]
```

This direct command requires valid matching canonical `submission.json` and
`review.json` records, then writes the selected derived artifact or artifacts:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

`--format` accepts `markdown`, `pdf`, or `both`. The default is `markdown` for
pre-1.0 compatibility with earlier scripts.

The export is standards-based. It uses the review record's
`minimum_requirement_outcome`, `overall_standard_ratings`, selected review-unit
observations, and `feedback.standard_feedback` content. It excludes private
notes, unselected observations, unselected comments, reusable-comment
provenance, routed evidence paths, and internal review IDs.

Success returns `0` and reports the identity, selected format, overwrite
status, and workspace-relative feedback path or paths.

Handled workspace, validation, missing-record, and overwrite failures return
`1`.

Without `--overwrite`, an existing feedback file is preserved.

The command does not mutate review state, timestamps, canonical records, or
evidence.

## Assignment-Local Class Summary Export

```powershell
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
```

This direct command reads the assignment config, roster when available,
submission manifests, review records, and feedback export metadata, then
writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
```

Rows follow roster order when a roster is available, then discovered
unrostered submission folders by `student_id`. Without a roster, rows are
sorted by discovered `student_id`.

Rows include submission and review states, minimum-requirement outcomes,
returned-without-full-review status, assignment Focus Standard ratings,
rating labels from the assignment rating scale, feedback PDF/Markdown status,
warnings, and workspace-relative paths.

Missing, invalid, and identity-mismatched student records produce
stable warnings such as `missing_submission`, `invalid_submission`,
`missing_review`, `invalid_review`, or `identity_mismatch` rather than
aborting the whole export.

A missing assignment config is a handled failure.

Success returns `0` and prints row/status counts, overwrite status, and the
summary path. Handled failures return `1`.

The export is read-only with respect to canonical records. It does not read
evidence files, source comment banks, student writing, private notes, or full
feedback text. It does not calculate percentages, grades, mastery, or
weighted results, or generate a standards summary.

Existing CSV files require `--overwrite`.

## Assignment-Local Focus Standard Summary Export

```powershell
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

This command reads the assignment's configured Focus Standards, discovered
or rostered student records, and feedback export metadata, then writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

It validates each available `submission.json` and `review.json`, counts
missing, invalid, returned-without-full-review, and identity-mismatched
records without aborting the assignment export, and emits one row per
assignment Focus Standard in assignment order.

Rows aggregate teacher-entered overall Focus Standard ratings from
`overall_standard_ratings`, missing-rating counts, feedback-inclusion counts,
and feedback PDF coverage.

Ratings outside the assignment Focus Standards produce warnings rather than
ordinary rows.

If no valid reviews exist, the command still writes one row per assignment
Focus Standard with zero counts.

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
* reusable Focus Standard comments; or
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
* a direct CLI command for review-unit observations, overall Focus Standard
  ratings, or feedback composition;
* AI grading, scoring, tagging, or feedback;
* automatic grading, mastery calculation, review-state decisions, or
  duplicate-evidence selection;
* LMS integration;
* cloud sync;
* email delivery; and
* dashboard/reporting automation.

Their presence in design documents or Python modules does not add them to the
CLI contract.

## Selected-student plain-paper action

When a roster student has no routed evidence and no submission manifest, the
interactive selected-student review menu offers creation of a plain-paper
manual submission. It requires `y` or `yes` confirmation. Existing manifests,
existing orphan review records, and routed-evidence-only students are not
converted. Opening evidence for a manual submission reports that no digital
evidence is attached instead of invoking an evidence opener.
