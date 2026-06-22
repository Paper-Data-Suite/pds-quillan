# Quillan Development Plan

## Project Definition

Quillan is a local-first standards-based writing evidence capture system for teachers.

Its purpose is to help teachers review student writing, tag evidence by standard and location, enter scores, generate feedback, and export structured instructional data.

Quillan is not an autonomous essay grader. It is a teacher-controlled system for turning student writing into structured instructional evidence.

## Current Status

Quillan currently has:

* initial Python package scaffold;
* documented MVP data contracts;
* synthetic example files;
* standards profile loading and validation;
* initial CLI support;
* teacher-facing shared-roster creation, viewing, staged editing, and
  validation;
* teacher-facing writing assignment config creation and read-only validation;
* teacher-facing combined printable response class-packet generation from
  existing canonical rosters and assignment configs;
* automated tests for standards validation and CLI behavior;
* configured development checks using `pytest`, `ruff`, and `mypy`.

## MVP Scope

The MVP should avoid hard problems such as handwriting OCR, automatic grading, complex GUI design, hosted workflows, gradebook sync, and AI scoring.

The first useful version should support:

* standards profile creation/loading;
* assignment configuration;
* plain-text submission loading;
* manual subdivision setup;
* basic requirements checks;
* standard/comment-based tagging;
* rubric score entry;
* feedback export;
* class and standards summary exports.

## Early Non-Goals

The MVP should not attempt:

* autonomous AI grading;
* handwriting OCR;
* precise word-level annotation;
* cloud sync;
* multi-user collaboration;
* district dashboards;
* gradebook integration;
* GUI application;
* parent/student emailing.

These may be considered later, but they should not be part of the initial MVP.

## Development Principles

### Local-First

Quillan should store project data locally by default.

Student work, standards profiles, assignments, tags, scores, and feedback should remain on the user's machine unless the user explicitly exports or shares them.

### Teacher Judgment Remains Primary

Quillan may organize evidence and eventually summarize patterns, but the teacher remains responsible for final scores and feedback decisions.

### Structured Data Over Loose Comments

Freeform comments are useful, but Quillan's main value comes from structured records:

* standard code;
* comment ID;
* location in the writing;
* polarity;
* severity or performance level;
* teacher note;
* final rubric score.

### Subject-Agnostic Design

Quillan should not assume that all writing is literary analysis or argument writing.

The standards profile, assignment configuration, and tagging mode should determine what is evaluated.

### Synthetic Data Only

The repository must not include real student data.

Examples and tests should use:

* fake student IDs;
* fake class IDs;
* synthetic writing samples;
* synthetic scores;
* synthetic teacher comments.

## Initial Architecture

Package modules:

* `standards.py`
* `classes.py`
* `assignments.py`
* `submissions.py`
* `requirements.py`
* `tagging.py`
* `scoring.py`
* `feedback.py`
* `reports.py`
* `storage.py`
* `validation.py`
* `cli.py`

## Module Responsibilities

### `standards.py`

Responsible for:

* loading standards profiles;
* validating standards profile structure;
* validating standard codes and comments;
* validating comment polarity;
* eventually resolving active standards by tagging mode.

Current status:

* implemented JSON loading;
* implemented validation;
* covered by tests.

### `classes.py`

Shared responsibility is implemented through `pds-core` class and roster
contracts plus Quillan's `roster_workflows.py` menu orchestration:

* discover canonical class folders;
* create, load, edit, and validate `classes/<class_id>/roster.csv`;
* preserve leading-zero IDs and optional columns; and
* stage edits until explicit save without deleting historical evidence.

### `assignments.py`

Current responsibility:

* load and validate the existing assignment configuration contract;
* connect assignments to standards profiles;
* support writing type, focus standards, tagging mode, and rubric configuration;
* create one-class writing assignment configs from teacher prompts at the
  canonical shared route; and
* view and validate existing assignment configs without rewriting them.

The menu workflow requires an existing class roster and protects existing
configs with exact `OVERWRITE` confirmation. The Assignment Management menu
does not edit, delete, or import assignments and does not perform scoring,
feedback, tagging execution, requirements checking, reports, scan routing,
OCR, AI, or printable packet generation.

### `printable_response.py`

Current responsibility:

* generate one combined printable response class packet from validated
  assignment data and shared `pds-core` roster records;
* expose that supported mode through the Printable Response Pages menu; and
* protect an existing stable output from menu-driven replacement unless the
  teacher types exact `OVERWRITE`.

Individual student PDFs, scan routing, OCR, review, scoring, feedback, reports,
AI, and a direct printable CLI command remain out of scope.

### Scan routing

Future Quillan scan routing must use the shared active scan contract defined by
`pds-core`. Canonical active retained sources belong in
`scans/source/YYYY-MM-DD/`, routing failure records belong in
`scans/review/`, and assignment-level `scans/` contains routed evidence rather
than canonical source retention.

`pds-core` owns shared source retention, review paths, failure metadata and
categories, copy-first behavior, no-overwrite rules, and provenance semantics.
Quillan owns interpretation of its `PDS1` response payloads, response-page
validation, routed student evidence layout, submission assembly, completeness
and rescan decisions, and any future OCR behavior. Quillan-specific failure
details belong under the shared record's `module_details`.

The first version `1` reviewable-evidence submission manifest contract is
documented, with loading, validation, canonical Quillan-owned path helpers,
safe writing, and new-manifest assembly from caller-provided routed evidence
metadata implemented. It defines page entries, duplicate and replacement
candidates, teacher-controlled selection and review states, retained-source
provenance, workspace-relative paths, and timezone-aware timestamps. Assembly
does not discover scan folders, merge manifests, or preserve prior teacher
review state during overwrite.

Target milestone:

```text
v0.6.0 — Reviewable Evidence and Submission Assembly
```

The first successful-write helper is implemented in `quillan.evidence_filing`.
It accepts an existing successful `RoutePlan`, retains the selected source
under `scans/source/YYYY-MM-DD/`, files the retained source or a supplied page
artifact under assignment `scans/`, preserves duplicate copies, and returns
provenance.

Metadata-only failure preservation is implemented in `quillan.routing_review`.
It writes shared `pds-core` failure records under `scans/review/`, preserves
route failure and evidence filing context, and records workspace-relative
retained-source provenance when available. It does not copy review artifacts.

The direct
`quillan route-scan <source-file> --payload "<PDS1|...>"` command is
implemented for one selected source and an already-decoded payload. It
orchestrates the existing parser, planner, evidence filer, and review adapters.
QR extraction, PDF splitting, OCR, menu integration, batch routing, and
automatic evidence discovery remain unimplemented. Submission assembly is
available as a focused Python API and is not part of `route-scan`.

### `submissions.py`

Current responsibility:

* load and validate the earlier text-oriented submission metadata shape.

The v0.6 reviewable-evidence manifest loader is implemented separately as
`quillan.submission_manifest` in `quillan/submission_manifest.py`. The legacy
metadata loader remains distinct and has not been repurposed into the
page-oriented submission manifest loader.

### `requirements.py`

Planned responsibility:

* evaluate basic assignment requirements;
* store requirements-check results;
* keep requirements separate from standards scoring.

### `tagging.py`

Planned responsibility:

* support standard/comment selection;
* store structured tag records;
* validate tag locations;
* support teacher notes.

### `scoring.py`

Planned responsibility:

* summarize tags;
* support rubric score entry;
* store final teacher scores;
* eventually suggest score bands without making final decisions.

### `feedback.py`

Planned responsibility:

* generate student-readable feedback from tags, scores, and teacher notes;
* export feedback as Markdown.

### `reports.py`

Planned responsibility:

* aggregate class-level results;
* summarize standards performance;
* summarize rubric performance;
* export CSV reports.

### `storage.py`

Planned responsibility:

* centralize paths and file writing;
* support local project-root configuration;
* eventually integrate with Paper Data Suite shared storage.

### `validation.py`

Planned responsibility:

* hold shared validation helpers once multiple modules need them.

### `cli.py`

Responsible for:

* teacher-facing terminal commands;
* direct CLI workflows;
* the initial menu shell and future menu workflows.

Current status:

* implemented `validate-standards`;
* implemented the initial bare `quillan` / `quillan menu` skeleton;
* covered by tests.

## Development Sequence

### Phase 1 — Project Scaffold

Status: complete.

Completed work:

* Create repo structure.
* Add package files.
* Add README.
* Add `.gitignore`.
* Add `pyproject.toml`.
* Add basic CLI entry point.
* Confirm test/lint/type-check tooling.

### Phase 2 — Data Contracts

Status: complete.

Completed work:

* Document MVP data contracts.
* Add synthetic standards profile example.
* Add synthetic assignment example.
* Add synthetic submission example.
* Add synthetic output examples.
* Document synthetic data policy.

### Phase 3 — Standards Profiles

Status: partially complete.

Completed work:

* Load standards profile from JSON.
* Validate standards profile structure.
* Validate required top-level fields.
* Validate standard records.
* Validate comment records.
* Validate allowed polarity values.
* Add tests.

Remaining possible work:

* Add more example standards profiles.
* Add optional subskill validation.
* Add optional feedback-template validation.
* Add duplicate code/comment ID checks.
* Add active standards resolution by tagging mode.

### Phase 4 — CLI Foundation

Status: partially complete.

Completed work:

* Add argparse-based CLI structure.
* Add `validate-standards` command.
* Add the initial bare `quillan` menu entry point, explicit `quillan menu`
  alias, and navigation skeleton.
* Add the Roster Management submenu using shared `pds-core` contracts.
* Add the Printable Response Pages submenu for combined class-packet
  generation.
* Add a direct `route-scan` command for already-decoded Quillan PDS1 payloads.
* Add CLI tests.

Remaining possible work:

* Add version/status command.
* Improve user-facing error formatting.
* Add examples to CLI help text.
* Expand menu workflows only as supported application behavior is implemented.

### Phase 5 — Assignments

Planned work:

* Define assignment config model.
* Load assignment JSON.
* Validate required assignment fields.
* Validate tagging mode.
* Validate focus standards.
* Validate basic requirements.
* Connect assignment to standards profile.
* Add tests.

Likely first commands:

* `quillan validate-assignment <path>`
* later: `quillan create-assignment`

### Phase 6 — Submissions and Requirements

Planned work:

* Implement loading and validation for the documented version `1` submission
  manifest.
* Add canonical submission path helpers.
* Assemble routed evidence into teacher-controlled manifests.
* Represent missing, duplicate, replacement, damaged, and excluded evidence
  without deleting candidates.
* Add teacher-controlled evidence selection and review-state updates.
* Preserve retained-source provenance and workspace-relative artifact paths.
* Continue supporting plain-text writing evidence where applicable.
* Count words.
* Count paragraphs.
* Manually enter or store subdivision count.
* Check basic requirements.
* Store requirements results.
* Add tests.

Likely first commands:

* `quillan check-requirements <assignment-path> <submission-path>`
* later: interactive requirements workflow.

### Phase 7 — Tagging

Planned work:

* Select active standards.
* Select numbered comments.
* Store structured tag records.
* Validate tag records.
* Add teacher notes.
* Add tests.

Likely first workflow:

* load assignment;
* load standards profile;
* choose subdivision;
* choose standard;
* choose comment;
* save tag record.

### Phase 8 — Scoring and Feedback

Planned work:

* Enter rubric scores.
* Store final score records.
* Summarize tags.
* Generate feedback Markdown.
* Add tests.

### Phase 9 — Reports

Planned work:

* Export class summary CSV.
* Export standards summary CSV.
* Export rubric summary CSV.
* Add tests.

## Development Workflow

Use focused issue branches.

Recommended workflow:

1. Start from clean `main`.
2. Pull latest remote changes.
3. Create an issue branch.
4. Push the branch upstream.
5. Make a focused change.
6. Run validation checks.
7. Commit and push.
8. Open a pull request.
9. Link the issue with `Closes #<issue-number>`.
10. Use squash merge for most feature branches.
11. Delete the remote branch after merging.
12. Pull updated `main` locally.
13. Delete the local feature branch.

## Required Checks Before Pull Request

Before opening or merging a pull request, run:

```powershell
pytest
ruff check .
mypy .
```

All three should pass.

## GitHub Board Workflow

Use the following board columns:

* Backlog
* Ready
* In Progress
* In Review
* Done

Recommended use:

* **Backlog** — captured but not ready.
* **Ready** — clearly scoped and ready to start.
* **In Progress** — branch is active.
* **In Review** — pull request is open.
* **Done** — merged or intentionally closed.

## AI Assistance Workflow

AI tools such as Codex, Copilot, and ChatGPT can help with implementation, review, and refactoring, but they should be used conservatively.

Recommended rules:

* Keep issues small.
* Ask AI for one focused change at a time.
* Review generated code before committing.
* Prefer tests before expanding features.
* Do not allow AI to introduce real student data.
* Do not accept broad architectural rewrites without review.
* Keep CLI logic separate from core business logic.
* Require `pytest`, `ruff`, and `mypy` to pass before merging.

## Near-Term Issue Backlog

Possible next issues after the initial documentation milestone:

1. Add duplicate standards/comment validation.
2. Implement assignment config loading and validation.
3. Add `validate-assignment` CLI command.
4. Define basic requirements evaluation.
5. Implement plain-text submission loading.
6. Add paragraph and word counting.
7. Store requirements-check output.
8. Define tag record validation.
9. Implement first tag-entry workflow.
10. Define rubric score record validation.
11. Generate basic feedback Markdown.
12. Export initial class summary CSV.
13. Export initial standards summary CSV.

## Longer-Term Possibilities

Future enhancements may include:

* assignment templates;
* standards-profile import/export;
* reusable rubric libraries;
* tag-to-feedback templates;
* batch feedback export;
* class dashboards;
* longitudinal standards tracking;
* integration with ScoreForm reports;
* gradebook export rules;
* optional AI-assisted tag suggestions for teacher approval;
* optional AI-assisted feedback drafting;
* optional desktop packaging.

These should not distract from the MVP.
