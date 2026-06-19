# Quillan CLI Contract

## Purpose and Status

This document defines Quillan's command-line contract during pre-1.0
development. It records:

* the command surface that is implemented now;
* the boundary between direct commands and the initial interactive menu;
* conventions for help, errors, paths, output, and exit status; and
* the compatibility expectations contributors should use when changing the
  CLI.

The CLI includes a developer-oriented, scriptable command layer and an initial
teacher-facing menu with shared-roster management. It is not a complete
teacher-facing application.
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
quillan validate-standards <path>
quillan validate-assignment <path>
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan workspace --help
quillan menu
```

Running `quillan` without a command launches the initial teacher-facing
terminal menu. Running `quillan workspace` without a subcommand prints
top-level help and exits successfully; it does not inspect or modify the
workspace.

The teacher-facing menu may also be launched explicitly:

```powershell
quillan menu
```

Bare `quillan` and the explicit `menu` command launch the same interactive
menu skeleton. Direct validation and workspace-status commands remain
non-interactive.

### `validate-standards`

```powershell
quillan validate-standards <path>
```

Loads a UTF-8 JSON standards profile and applies Quillan's current standards
profile validation rules.

On success, it writes this form to standard output:

```text
Valid standards profile: <profile_id>
```

It is read-only. It does not rewrite, normalize, copy, or install the profile.

### `validate-assignment`

```powershell
quillan validate-assignment <path>
```

Loads a UTF-8 JSON assignment configuration and applies Quillan's current
assignment validation rules.

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

Bare `quillan` launches the current menu, which is a small discovery and
navigation shell. `quillan menu` is an explicit alias for the same behavior.
The menu provides:

```text
1. Assignment Management
2. Roster Management
3. Printable Response Pages
4. Workspace Settings
5. Help
6. Exit
```

Roster Management provides:

```text
1. Create class roster
2. View class roster
3. Edit class roster
4. Validate class roster
5. Back
```

These menu-only workflows use shared `pds-core` class and roster APIs.
Canonical rosters are stored at
`<workspace_root>/classes/<class_id>/roster.csv`. Student IDs remain strings,
including leading zeros, and existing optional columns remain in their
original order. Viewing and validation are read-only.

Editing stages shared immutable roster mutations in memory. Add, edit, and
active-roster removal do not write immediately. Saving requires typing
`SAVE`; canceling staged changes requires typing `DISCARD`. Active-roster
removal never deletes assignments, submissions, printable PDFs, scans,
reports, tags, scores, feedback, or historical evidence.

Assignment Management provides:

```text
1. Create writing assignment
2. View/validate assignment
3. Back
```

Creation selects one class with an existing canonical roster, prompts for the
fields in the existing assignment config contract, and writes
`<workspace_root>/classes/<class_id>/assignments/<assignment_id>/assignment.json`.
An existing config is replaced only after exact `OVERWRITE` confirmation.
View/validate accepts an explicit JSON path, uses the existing assignment
loader and validator, prints a concise summary, and does not rewrite the file.
These workflows do not add assignment editing, deletion, import, scoring,
feedback, tagging execution, requirements checking, reports, scan routing,
OCR, AI, or printable packet generation.

Printable Response Pages states that PDF generation exists as a Python API but
has no teacher-facing menu workflow yet.

Workspace Settings provides:

```text
1. Show current workspace
2. Set workspace folder
3. Validate/create current workspace
4. Reset saved workspace preference
5. Back
```

Showing the workspace calls the same status behavior as
`quillan workspace show` and remains read-only. Setting prompts for a folder;
blank input cancels without changing the saved preference. Nonblank input
validates/creates the folder and saves it through shared `pds-core`
configuration. Validate/create operates on the currently resolved root.
Reset clears only the saved preference and then reports the current resolved
root. The menu warns that setting does not migrate files, resetting does not
delete files, and `PDS_WORKSPACE_ROOT` still takes precedence.

The workspace submenu does not include school-year settings. The overall menu
remains a guided shell rather than a complete teacher-facing application.

Menu help describes Quillan as a local-first, teacher-controlled
writing-evidence tool; keeps teacher judgment primary; states that Quillan is
not automated grading software; identifies currently unsupported AI, OCR,
scan-routing, and review workflows; and summarizes repository safe-data
expectations and current direct commands.

The menu clears the screen only when both standard input and standard output
are interactive terminals. A normal exit or `KeyboardInterrupt` returns status
`0`.

A future menu may guide teachers through additional multi-step work after
those workflows are actually implemented. It should orchestrate reusable
application functions rather than becoming the only route to core operations.

CLI parsing and presentation belong in `quillan/cli.py`. Validation, storage,
workspace resolution, and other domain behavior belong in their relevant
modules or in shared `pds-core` services. This separation allows direct
commands and the menu to share behavior and tests.

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

A future command that writes files must document its destination, overwrite
policy, and partial-failure behavior before that behavior is treated as
stable.

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
Invalid standards profile: ...
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

| Status | Meaning |
| --- | --- |
| `0` | The requested operation or menu session completed successfully, or help was requested or printed for a no-operation command-specific parser level. |
| `1` | The command was understood, but validation or an operational action failed. |
| `2` | Command-line usage was invalid, as reported by `argparse`. |
| Other nonzero | An unexpected failure or a future explicitly documented category. |

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
`quillan/cli.py`, its CLI tests, and this document. If they disagree, the
implementation and tests describe executable behavior, and the mismatch
should be corrected rather than treated as an undocumented feature.

## Not Currently Part of the CLI

The following capabilities are implemented only as Python APIs, planned, or
explicitly outside the current end-to-end foundation:

* printable response generation as a dedicated command;
* submission validation as a dedicated command;
* workspace creation or selection;
* production scan routing or QR extraction;
* OCR or handwriting interpretation;
* requirements checking, tagging, scoring, feedback, and reporting
  workflows;
* AI grading, scoring, tagging, or feedback; and
* complete teacher-facing assignment, printable-response, submission
  review, tagging, scoring, feedback, or reporting workflows.

Their presence in design documents or Python modules does not add them to the
CLI contract.
