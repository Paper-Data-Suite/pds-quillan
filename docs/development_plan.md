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
* retained source scan routing and routed assignment evidence filing;
* student submission manifest assembly and read-only status listing;
* local evidence opening and student submission opening;
* teacher-controlled lightweight review-state updates;
* canonical `review.json` records with direct teacher-entered notes, structured
  tags, reusable comment-bank selection, and criterion scores;
* student feedback, class review summary, and standards summary exports;
* a refactored direct CLI implementation under `quillan/cli_app`, with
  `quillan/cli.py` retained as the compatibility facade;
* a teacher-facing menu for assignment management, roster management,
  printable response pages, workspace settings, help, and exit;
* automated tests for standards validation and CLI behavior;
* configured development checks using `pytest`, `ruff`, and `mypy`.

The v0.7 review and export foundation is primarily a direct CLI/API workflow.
The menu does not yet guide submission review, notes, tags, reusable comments,
scores, exports, scan intake, or QR recognition. Raw-scan QR decoding, PDF
splitting, batch intake, OCR, AI judgment, automatic grading, automatic
mastery calculation, and automatic evidence selection remain unimplemented.

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

## Original Architecture Sketch

The list below records the initial planning decomposition. The current source
tree uses focused modules such as `review_record.py`, `review_notes.py`,
`review_tags.py`, `review_comments.py`, `review_scores.py`,
`feedback_export.py`, the summary exporters, and `quillan/cli_app`.

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
preserves explicit candidate, replacement, and excluded roles plus damaged,
needs-rescan, and excluded states without choosing among ambiguous evidence.
Only a single ordinary active item with no explicit role is selected
automatically. Assignment-level filename discovery and assembly from existing
routed evidence is implemented through `quillan assemble-submissions`.
Assembly does not inspect evidence contents, reconstruct retained-source
provenance, merge manifests, or preserve prior teacher review state during
overwrite. Evidence selection remains a future workflow; lightweight
review-state updates are implemented as a separate teacher-controlled,
metadata-only command.

Target milestone:

```text
v0.6.0 â€” Reviewable Evidence and Submission Assembly
```

The completed/current v0.6 workflow includes:

* retained source scan routing into the active source scan store;
* routed evidence filing under assignment `scans/`;
* student submission manifest assembly from routed evidence;
* read-only submission and evidence status listing;
* workspace-safe local evidence opening;
* student submission opening for exactly one selected evidence item;
* lightweight review-state updates limited to `submission_state` and
  `updated_at`; and
* end-to-end workflow documentation.

Smoke testing remains pending after the documentation update. v0.6 does not
include OCR, handwriting recognition, PDF text extraction, automatic evidence
selection, automatic grading, automatic review-state updates, AI scoring, AI
feedback, AI suggestions, rubric scoring, tagging, comment entry, feedback
export, or report generation.

Teacher tags, teacher comments, rubric/score entry, feedback export, and
reporting remain likely v0.7 work rather than v0.6 scope.

Historical note (superseded by the PDS2 intake and #339 observation pipeline):
the first successful-write helper in `quillan.evidence_filing` once accepted a
legacy route plan, retained the selected source under
`scans/source/YYYY-MM-DD/`, and filed assignment-scan evidence. That behavior
is no longer an active identity or assembly contract.

Metadata-only failure preservation is implemented in `quillan.routing_review`.
It writes shared `pds-core` failure records under `scans/review/`, preserves
route failure and evidence filing context, and records workspace-relative
retained-source provenance when available. It does not copy review artifacts.

The direct
`quillan route-scan <source-file> --payload "<PDS1|...>"` command is
implemented for one selected source and an already-decoded payload. It
orchestrates the existing parser, planner, evidence filer, and review adapters.
QR extraction, PDF splitting, OCR, menu integration, and batch routing remain
unimplemented. Assignment submission assembly is available through a focused
Python API and `quillan assemble-submissions`; it is not part of `route-scan`.

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

Implemented responsibility is now split across `review_tags.py`,
`review_notes.py`, `review_comments.py`, and the canonical
`review_record.py` model:

* direct teacher-controlled standard/comment selection;
* structured tags and validated locations;
* reusable comment-bank snapshots; and
* teacher-entered notes.

### `scoring.py`

Implemented criterion-score responsibility now lives in `review_scores.py`:

* record or update teacher-entered criterion scores in `review.json`;
* preserve unrelated review data; and
* avoid inferred scores, overall grades, mastery calculations, or automatic
  score suggestions.

### `feedback.py`

Implemented feedback responsibility now lives in `feedback_export.py`:

* export student-readable Markdown from selected comments and
  teacher-entered criterion scores; and
* keep private notes, tags, score notes, and provenance out of the export.

### `reports.py`

Implemented reporting responsibility is split across
`class_summary_export.py` and `standards_summary_export.py`:

* export assignment-level class review status and transparent score totals;
* aggregate standards-linked tags and selected comments; and
* avoid grades, mastery conclusions, evidence inspection, or roster inference.

### `storage.py`

Current storage responsibility is distributed across focused path and writer
modules and shared `pds-core` services:

* resolve and manage the shared Paper Data Suite workspace;
* compute canonical submission, review, comment-bank, and export paths; and
* use safe local writes with explicit overwrite policies.

### `validation.py`

Validation remains colocated with the relevant contracts and focused modules:

* standards, assignments, manifests, reviews, and comment banks validate
  before use; and
* shared cross-module primitives come from `pds-core` where applicable.

### `cli.py`

Responsible for:

* retaining the public `quillan.cli:main` compatibility entrypoint.

Current status:

* parser construction, argument conversion, output, dispatch, and handlers
  live under `quillan/cli_app`;
* direct commands cover validation, decoded-payload routing, submission
  assembly/status/opening, explicit review updates, and all v0.7 exports;
* bare `quillan` and `quillan menu` launch the current teacher-facing menu;
* guided teacher-facing review/export and raw-scan intake remain future work;
  and
* the command surface is covered by focused tests.

## Development Sequence

### Phase 1 â€” Project Scaffold

Status: complete.

Completed work:

* Create repo structure.
* Add package files.
* Add README.
* Add `.gitignore`.
* Add `pyproject.toml`.
* Add basic CLI entry point.
* Confirm test/lint/type-check tooling.

### Phase 2 â€” Data Contracts

Status: complete.

Completed work:

* Document MVP data contracts.
* Add synthetic standards profile example.
* Add synthetic assignment example.
* Add synthetic submission example.
* Add synthetic output examples.
* Document synthetic data policy.

### Phase 3 â€” Standards Profiles

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

### Phase 4 â€” CLI Foundation

Status: partially complete.

Completed work:

* Add argparse-based CLI structure.
* Superseded: shared standards validation now belongs to pds-core.
* Add the initial bare `quillan` menu entry point, explicit `quillan menu`
  alias, and navigation skeleton.
* Add the Roster Management submenu using shared `pds-core` contracts.
* Add the Printable Response Pages submenu for combined class-packet
  generation.
* Add a direct `route-scan` command for already-decoded Quillan PDS1 payloads.
* Add `assemble-submissions`, `list-submissions`, `open-evidence`,
  `open-submission`, and `set-review-state`.
* Add CLI tests.

Remaining possible work:

* Add version/status command.
* Improve user-facing error formatting.
* Add examples to CLI help text.
* Expand menu workflows only as supported application behavior is implemented.

### Phase 5 â€” Assignments

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

### Phase 6 â€” Submissions and Requirements

Completed reviewable-evidence work:

* Implement loading and validation for the documented version `1` submission
  manifest.
* Add canonical submission path helpers.
* Assemble routed evidence into teacher-controlled manifests.
* Represent missing, duplicate, replacement, damaged, and excluded evidence
  without deleting candidates.
* Add lightweight review-state updates through `quillan set-review-state`,
  changing only `submission_state` and `updated_at`.
* Preserve retained-source provenance and workspace-relative artifact paths.
* Open individual workspace-relative evidence files safely through the shared
  `pds-core` local opener. Implemented as a low-level helper,
  `quillan open-evidence`, and the read-only student-aware
  `quillan open-submission`, which currently requires exactly one selected
  evidence item and does not update review state. State changes occur only
  through the explicit `quillan set-review-state` command.

Remaining requirements and review work:

* Add teacher-controlled evidence selection and duplicate resolution.
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

### Phase 7 â€” Tagging

Planned work:

* Select active standards.
* Select numbered comments.
* Store structured tag records.
* Validate tag records.
* Add teacher notes.
* Add tests.

Likely first workflow:

* load assignment;
* use pds-core standards references;
* choose subdivision;
* choose standard;
* choose comment;
* save tag record.

### Phase 8 â€” Scoring and Feedback

Planned work:

* Enter rubric scores.
* Store final score records.
* Summarize tags.
* Generate feedback Markdown.
* Add tests.

### Phase 9 â€” Reports

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

* **Backlog** â€” captured but not ready.
* **Ready** â€” clearly scoped and ready to start.
* **In Progress** â€” branch is active.
* **In Review** â€” pull request is open.
* **Done** â€” merged or intentionally closed.

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

## Plain-paper manual submission entry

Quillan supports a focused teacher-facing setup path for students who wrote on
plain paper when printable response pages were unavailable. The path creates
the existing submission and review contracts without scans, OCR, placeholder
files, fake evidence, bulk creation, or changes to QR/PDS1 printing. Subsequent
work remains in the active standards-based review and assignment-local export
model.
