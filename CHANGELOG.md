# Changelog

All notable changes to this project will be documented in this file.

Quillan is in early pre-1.0 development. Package versions describe the
installable project state; GitHub issues and milestones may be used for
planning and do not by themselves represent releases.

## Unreleased

### Changed

- Split the CLI implementation into smaller internal parser, argument,
  output, and command-handler modules. Public command behavior and the
  `quillan.cli:main` console-script entrypoint remain unchanged.
- Removed obsolete standalone review-artifact storage helpers and empty stale
  placeholder modules. Canonical review data remains in `review.json`, with
  feedback and assignment summaries written only as derived exports.
- Added explicit shared-bank provenance to selected version `1` review
  comments. `comment_bank` snapshots now require a valid `bank_id` and
  `comment_id`; standards-profile snapshots require `standard_code` and
  `comment_id`; and custom comments reject source identifiers. Bank provenance
  does not perform lookup or turn snapshotted label and text into live
  references.
- Defined the v0.7 canonical `review.json` contract, separating
  teacher-entered notes, tags, criterion scores, selected comments, and
  `review_state` from the `submission.json` evidence manifest.
- Reconciled older `tags.json`, `scores.json`, and `feedback.md` design
  language: the first two are historical concepts, while feedback and summary
  files are derived exports from the canonical review record.
- Documented the v0.6 reviewable-evidence workflow, including retained source
  scans, routed evidence, student submission manifests, local evidence opening,
  student submission opening, status listing, and lightweight review-state
  updates.
- Refined routed-evidence assembly so callers can preserve candidate,
  replacement, and excluded roles plus active, damaged, needs-rescan, and
  excluded states. Only a single ordinary active item with no explicit role is
  auto-selected; replacement, problematic, excluded, and ambiguous evidence
  remains preserved and unselected for later teacher choice.
- Aligned the future Quillan scan-routing design with the shared `pds-core`
  active scan contract, including source retention, routed evidence,
  `scans/review/`, shared failure metadata, and ownership boundaries.
- Adding a student to an existing single-period roster now offers that shared
  period as the default while preserving explicit entry for mixed rosters.

### Added

- Added a synthetic end-to-end v0.7 smoke test covering routed-evidence
  submission assembly, canonical teacher notes, structured tags, reusable
  comments, criterion scores, and all three review exports, with explicit
  non-mutation checks for manifests, review records, evidence, and comment
  banks.
- Added `quillan export-standards-summary` and a focused read-only API for
  writing assignment-level `exports/standards_summary.csv`. Rows are sorted by
  `standard_code` and aggregate standards-linked tag polarity, selected
  comment feedback inclusion, and distinct-student counts while retaining
  assignment-level missing, invalid, and identity-mismatch counts. The export
  excludes scores and notes, does not load standards profiles, read evidence
  or comment banks, infer mastery or grades, use a roster, or mutate canonical
  records.
- Added `quillan export-class-summary` and a focused read-only API for writing
  assignment-level `exports/class_summary.csv`. The deterministic CSV includes
  one row per discovered student directory, status rows for missing, invalid,
  and identity-mismatched records, review/submission states, transparent
  teacher-entered score totals, selected-comment, tag, and note counts, and
  feedback-export existence. It does not read evidence or comment banks,
  calculate grades or mastery, use a roster, or mutate canonical records.
- Added `quillan export-feedback` and a focused read-only API for generating
  `submissions/<student_id>/exports/feedback.md` from valid matching
  `submission.json` and `review.json` records. The Markdown includes ordered
  teacher-entered criterion scores and snapshotted comments marked for
  feedback, excludes private notes, tags, score notes, excluded comments, and
  provenance, and never reads source comment banks. Existing exports require
  `--overwrite`; canonical records, evidence, timestamps, and `review_state`
  remain unchanged.
- Added `quillan add-comment` and a focused reusable-comment selection API.
  Shared comment banks are fully validated before selection; student-facing
  comments are appended to `review.json.comments` with sequential local IDs,
  `bank_id + comment_id` provenance, snapshotted label and text, optional
  standard selection, and bank-default or teacher-overridden feedback
  inclusion. Existing review content and later review states are preserved,
  while comment banks, submission manifests, and evidence remain unchanged.
- Defined the version `1` shared reusable comment bank contract at
  `shared/comment_banks/<bank_id>.json`, including writing-type filters,
  categories, standards and criterion links, polarity, severity defaults,
  search metadata, student-facing controls, future assignment activation,
  and snapshot semantics for selected `review.json.comments`. Added a
  synthetic multi-category example without implementing runtime loading,
  selection, export, grading, or AI behavior.
- Added `quillan set-score` and a focused criterion-score API for setting
  teacher-entered scores in canonical `review.json` records. New criteria
  receive stable sequential IDs; existing criteria update in place by
  `criterion_id` while preserving their IDs and unrelated review data.
  Inputs, timestamps, identities, and complete proposed records validate
  before atomic writes. The workflow does not infer scores, calculate an
  overall score, validate against a rubric profile, or mutate submission
  manifests or evidence.
- Added `quillan add-tag` and a focused structured-tag API for appending
  teacher-entered tags to canonical `review.json` records. The workflow
  validates tag fields, timestamps, pages, evidence IDs, locations, assignment
  standards, and reusable profile comments; assigns stable sequential IDs;
  preserves existing review content and later review states; and never mutates
  submission manifests or evidence.
- Added `quillan add-note` and a focused quick-note API for appending
  timestamped, teacher-entered notes to a student's canonical `review.json`.
  The workflow requires a valid matching `submission.json`, creates a missing
  review record in `in_progress`, advances only `not_started` records, preserves
  later review states and all existing review sections, and never mutates the
  submission manifest or student evidence.
- Added Quillan-owned version `1` review-record infrastructure with strict
  loading and validation for identities, canonical manifest references,
  review states, timestamps, notes, tags, locations, scores, comments, and
  extension objects, plus canonical `review.json` path helpers and atomic
  UTF-8 writing with explicit overwrite protection.
- Added a synthetic submission review record demonstrating notes, positive and
  developing tags, a criterion score, selected reusable feedback language,
  evidence references, and timezone-aware timestamps.
- Added a synthetic v0.6 reviewable-evidence smoke test covering routed
  evidence, submission assembly, manifest validation, status listing, mocked
  submission opening, review-state updates, and non-destructive behavior.
- Added `quillan set-review-state` and a focused API for explicit
  teacher-controlled updates to a validated submission manifest's
  `submission_state` and `updated_at`, supporting only `unreviewed`,
  `in_progress`, `needs_rescan`, and `reviewed` while preserving all evidence,
  selection, provenance, and other manifest content.
- Added read-only `quillan open-submission` support for locating and validating
  one student's canonical submission manifest, requiring exactly one selected
  evidence item, and opening its routed evidence through Quillan's existing
  workspace-safe local evidence opener without changing review state.
- Added `quillan open-evidence` and a focused evidence-opening API for safely
  opening an existing workspace-relative evidence file through the shared
  `pds-core` system opener, without inspecting or modifying evidence or review
  state.
- Added read-only `quillan list-submissions` status reporting for validated
  assignment manifests and routed evidence, including submission/page states,
  present-but-unselected pages, students needing assembly, unassembled routed
  files, skipped filenames, and optional expected-page visibility without
  creating or modifying manifests.
- Added `quillan assemble-submissions` and an assignment-level assembly API
  that discover routed PDF/image evidence by filename convention, group it by
  student, write canonical version `1` manifests, report malformed or
  unrelated files plus missing and duplicate pages, skip existing manifests
  by default, and support explicit full regeneration with `--overwrite`.
- Added a focused routed-evidence assembly API for building and safely writing
  new version `1` submission manifests. It preserves workspace-relative source
  provenance, represents expected missing pages and ambiguous duplicates,
  assigns deterministic evidence IDs, and refuses overwrites by default.
- Added Quillan-owned helpers for canonical version `1` submission manifest
  paths and safe writing of caller-provided manifests, with validation,
  parent-directory creation, readable UTF-8 JSON, and overwrite protection.
- Added a distinct v0.6 reviewable-evidence submission manifest loader and
  validator with page, evidence, retained-source, selection, path, timestamp,
  state, and identifier validation. The legacy text-oriented loader remains
  unchanged.
- Documented the draft version `1` reviewable-evidence `submission.json`
  contract, including page and evidence states, duplicate and replacement
  preservation, retained-source provenance, safe relative paths, and a fully
  synthetic three-page example.
- Added a direct `route-scan` command for already-decoded Quillan PDS1
  payloads, including successful evidence filing, safe review preservation,
  concise workspace-relative summaries, and documented handled/failure exit
  codes.
- Added a routing failure preservation API that writes shared `pds-core`
  failure metadata exclusively under `scans/review/`, adapts route-planning and
  evidence-filing failures, and records workspace-relative retained-source
  provenance when available without copying review artifacts.
- Added a successful-route evidence filing API that exclusively retains source
  scans under `scans/source/YYYY-MM-DD/`, files response evidence under
  assignment `scans/`, preserves duplicate rescans, and returns retained-source
  and routed-evidence provenance.
- Added a teacher-facing Printable Response Pages menu that generates one
  combined class packet from an existing canonical roster and assignment
  config using the existing roster-aware PDF generator.
- Added positive pages-per-student validation, clear assignment validation and
  class-mismatch errors, canonical output-path reporting, and exact
  `OVERWRITE` protection for existing printable packets.
- Added a teacher-facing Assignment Management menu for creating validated
  one-class writing assignment configs at the canonical shared assignment
  route and viewing/validating existing configs without rewriting them.
- Added exact overwrite confirmation for existing assignment configs and
  roster-gated class selection for assignment creation.
- Added a teacher-facing Roster Management menu for creating, viewing, staged
  editing, and validating canonical shared `pds-core` class rosters.
- Added preservation of leading-zero student IDs and existing optional roster
  columns, with explicit `SAVE`, `DISCARD`, `REMOVE`, and overwrite
  confirmations.
- Added a full Workspace Settings menu and matching direct commands for
  showing, setting, validating/creating, and resetting the shared Paper Data
  Suite workspace root through `pds-core`.
- Added a root security policy covering private classroom data, synthetic
  repository fixtures, local artifacts, concern reporting, and dependency
  updates.
- Added this changelog to track notable project changes and future releases.

## 0.1.0 - Foundation

### Added

- Added assignment configuration loading and validation for local writing
  assignments.
- Added submission metadata loading and validation for teacher-controlled
  writing evidence records.
- Added standards profile validation for standards-aligned writing review.
- Added teacher-review model documentation emphasizing that teacher judgment
  remains central.
- Added printable writing-response PDF generation for paper-based writing
  workflows.
- Added PDS1 Quillan response payload support for printable response pages.
- Added synthetic paper-workflow fixtures for repository-safe tests and
  examples.
- Added canonical synthetic roster fixture support using the shared
  `pds-core` roster contract.
- Added printable response generation support using shared `pds-core` roster
  records.
- Added workspace status reporting using the shared `pds-core` workspace
  status API.
- Added scan-routing design documentation for future routed scan evidence.

### Notes

- Quillan remains an early local-first, teacher-controlled writing evidence
  project.
- This foundation does not implement OCR, production scan routing, AI scoring,
  AI feedback, automatic grading, or full teacher menu workflows.
