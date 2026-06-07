# Quillan Development Plan

## Project Definition

Quillan is a local-first standards-based writing evidence capture system for teachers.

Its purpose is to help teachers review student writing, tag evidence by standard and location, enter scores, generate feedback, and export structured instructional data.

## MVP Scope

The MVP should avoid hard problems such as handwriting OCR, automatic grading, complex GUI design, hosted workflows, gradebook sync, and AI scoring.

The first useful version should support:

- standards profile creation/loading;
- assignment configuration;
- plain-text submission loading;
- manual subdivision setup;
- basic requirements checks;
- standard/comment-based tagging;
- rubric score entry;
- feedback export;
- class and standards summary exports.

## Early Non-Goals

- autonomous AI grading;
- handwriting OCR;
- precise word-level annotation;
- cloud sync;
- multi-user collaboration;
- district dashboards;
- gradebook integration;
- GUI application.

## Initial Architecture

Package modules:

- `standards.py`
- `classes.py`
- `assignments.py`
- `submissions.py`
- `requirements.py`
- `tagging.py`
- `scoring.py`
- `feedback.py`
- `reports.py`
- `storage.py`
- `validation.py`
- `cli.py`

## Development Sequence

### Phase 1 — Project Scaffold

- Create repo structure.
- Add package files.
- Add README.
- Add `.gitignore`.
- Add `pyproject.toml`.
- Add basic CLI entry point.
- Confirm test/lint tooling.

### Phase 2 — Standards Profiles

- Define standards profile data model.
- Load standards profile from JSON.
- Validate standards profile structure.
- Add example ELA and science standards profiles.
- Add tests.

### Phase 3 — Assignments

- Define assignment config model.
- Connect assignment to standards profile.
- Support writing type, focus standards, tagging mode, and basic requirements.
- Add tests.

### Phase 4 — Submissions and Requirements

- Load plain-text submissions.
- Manually enter subdivision count.
- Check basic requirements.
- Store requirements results.
- Add tests.

### Phase 5 — Tagging

- Select active standards.
- Select numbered comments.
- Store structured tag records.
- Add teacher notes.
- Add tests.

### Phase 6 — Scoring and Feedback

- Enter rubric scores.
- Summarize tags.
- Generate feedback markdown.
- Add tests.

### Phase 7 — Reports

- Export class summary CSV.
- Export standards summary CSV.
- Export rubric summary CSV.
- Add tests.