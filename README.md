# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It is designed to help teachers tag, score, and respond to student writing by connecting specific locations in written work to standards, comments, rubric scores, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Early planning and development.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

## Planned MVP

The first useful version should support:

1. Creating or importing standards profiles.
2. Creating writing assignments.
3. Loading or entering plain-text submissions.
4. Checking basic assignment requirements.
5. Tagging subdivisions of writing by standard and comment.
6. Entering teacher-controlled rubric scores.
7. Exporting structured JSON, Markdown, and CSV outputs.

## Development

Quillan is written in Python.

Planned development priorities:

- clear data models;
- local-first file storage;
- structured JSON/CSV outputs;
- CLI-first workflow;
- tests around validation, tagging, scoring, and reporting.