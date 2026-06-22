# Changelog

All notable changes to this project will be documented in this file.

Quillan is in early pre-1.0 development. Package versions describe the
installable project state; GitHub issues and milestones may be used for
planning and do not by themselves represent releases.

## Unreleased

### Changed

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
