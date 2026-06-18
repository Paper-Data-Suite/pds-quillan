# Quillan CLI Contract

## Purpose and Status

This document defines Quillan's command-line contract during pre-1.0
development. It records:

* the command surface that is implemented now;
* the boundary between direct commands and a future interactive menu;
* conventions for help, errors, paths, output, and exit status; and
* the compatibility expectations contributors should use when changing the
  CLI.

The CLI is currently a developer-oriented and scriptable interface, not a
complete teacher-facing application. This contract describes implemented
behavior separately from future design. A command documented elsewhere as
planned is not part of the current CLI until it is implemented, tested, and
added here.

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
quillan --help
quillan validate-standards <path>
quillan validate-assignment <path>
quillan workspace show
quillan workspace --help
```

Running `quillan` without a command currently prints top-level help and exits
successfully. Running `quillan workspace` without `show` also prints
top-level help and exits successfully. These no-operation forms do not
validate data, inspect the workspace, or modify files.

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

## Direct CLI and Future Menu Boundary

Direct CLI commands and a future interactive menu serve different use cases.
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
without the future menu.

### Future interactive menu

A future menu may guide teachers through multi-step work such as selecting a
class and assignment, reviewing submissions, entering tags or scores, and
confirming output. It may improve discoverability and preserve session
context, but it should orchestrate reusable application functions rather than
becoming the only route to core operations.

The menu is not currently implemented. In particular:

* running `quillan` does not launch a menu;
* no current command should prompt for missing required arguments;
* documentation must not present planned menu workflows as available; and
* adding a menu must not silently change an existing direct command into an
  interactive workflow.

CLI parsing and presentation belong in `quillan/cli.py`. Validation, storage,
workspace resolution, and other domain behavior belong in their relevant
modules or in shared `pds-core` services. This separation allows direct
commands and a future menu to share behavior and tests.

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

During the current pre-1.0 period, running a parser level without selecting an
operation may continue to print help and return `0`. If that policy changes
to require a command, the behavior and tests should change together.

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
| `0` | The requested operation completed successfully, or help was requested or printed for a no-operation parser level. |
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
* a teacher-facing interactive terminal menu.

Their presence in design documents or Python modules does not add them to the
CLI contract.
