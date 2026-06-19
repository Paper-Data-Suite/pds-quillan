# Changelog

All notable changes to this project will be documented in this file.

Quillan is in early pre-1.0 development. Package versions describe the
installable project state; GitHub issues and milestones may be used for
planning and do not by themselves represent releases.

## Unreleased

### Changed

- Adding a student to an existing single-period roster now offers that shared
  period as the default while preserving explicit entry for mixed rosters.

### Added

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
