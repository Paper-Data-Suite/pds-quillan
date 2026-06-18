# Security Policy

## Project Status and Supported Versions

Quillan is in early pre-1.0 development. It is a local-first,
teacher-controlled project and is not yet a stable production release.

Only the current development branch is actively maintained. No released
version currently receives long-term security support.

## Reporting Security or Privacy Concerns

Use GitHub Issues for concerns that can be described without sensitive
information.

Do not open public GitHub issues containing real student data or private classroom records.
If a concern depends on sensitive details, describe the issue only in general
terms and request a private follow-up channel. Do not attach sensitive files,
screenshots, credentials, or private configuration to a public issue.

## Student Data and Privacy

All repository examples, fixtures, and tests must use synthetic data only.

Do not commit or post publicly:

- real rosters;
- real student names or IDs;
- real student writing;
- scanned student work;
- teacher feedback tied to identifiable students;
- rubric scores or grades;
- parent or guardian contact information;
- exported reports containing identifiable student information;
- local workspace folders;
- generated PDFs or scan files from real classroom use;
- screenshots containing identifiable classroom records;
- secrets, credentials, tokens, or private configuration; or
- private school or district documents.

Synthetic examples should use clearly fictional identifiers, names, writing,
scores, and feedback. Before committing a fixture, example, screenshot, log,
or generated file, verify that it contains no copied classroom data or
identifying metadata.

## Local-First Assumptions

Quillan is designed around local, teacher-controlled storage. Student writing,
submission metadata, teacher-review artifacts, scores, feedback records,
reports, scans, generated PDFs, and workspace data should remain in the
teacher's private local environment unless the teacher deliberately exports
or shares them through an approved process.

Repository ignore rules reduce accidental commits but are not a privacy
boundary. Users should keep classroom workspaces outside the repository,
review staged changes before committing, and protect local devices, backups,
and exported files according to their organization's requirements.

## Dependencies and Security Updates

Dependencies should be kept minimal and reviewed before updates are merged.
Security-related dependency updates should be evaluated promptly, tested
against the supported development environment, and documented in the
changelog when they materially affect the project.

Because Quillan is in early development, users should review dependency
advisories and update their local environment rather than assuming that an
older checkout remains supported.
