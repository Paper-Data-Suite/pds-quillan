# Student Review Status Contract

`quillan review-status <class_id> <assignment_id> <student_id> [--format text|json]`
is a direct, non-interactive, read-only diagnostic for one student. Text is the
default. JSON emits one newline-terminated document with `schema_version: "1"`
and `record_type: "quillan_student_review_status"`.

The required top-level keys, in order, are `schema_version`, `record_type`,
`class_id`, `assignment_id`, `student_id`, `assignment`, `student`,
`routed_evidence`, `submission`, `review`, and `warnings`. Paths are canonical,
workspace-relative POSIX strings. Warnings are deduplicated code strings in
deterministic discovery order.

## Fixed Sections and Null Semantics

Assignment context includes title, writing type, standards profile, configured
Focus Standard and minimum-requirement counts, and path. Student context uses
`rostered`, `unrostered`, or `roster_unavailable`. Routed evidence reports
availability, presence, selected-student file count, and assembly need.

Submission and review status is `missing`, `valid`, `invalid`, or
`identity_mismatch`; review separately reports `orphaned`. Fixed nested groups
cover pages, evidence, progress, requirements, units, observations, overall
ratings, feedback, private-note count, and PDF/Markdown exports. A valid
zero-page or plain-paper manifest has available integer zero counts. Missing,
invalid, or mismatched manifests use unavailable groups and JSON `null` counts.
Missing reviews have known zero stored-artifact counts and assignment-derived
configured/missing counts. Invalid or mismatched reviews use `available: false`
and `null` review-derived counts. Zero never means unreadable.

Export objects include path, metadata/file presence, `present`, `stale`,
`missing`, or `unknown` status, stale boolean, and metadata timestamps. Their
summary counts both formats.

## Warnings, Privacy, and Compatibility

Stable warnings cover unavailable/unrostered context, routed assembly need,
missing/invalid/mismatched records, orphaned reviews, stale or unconfigured
review artifacts, and feedback-export file, freshness, and metadata conditions.
These are successful diagnostics. Invalid identifiers, missing/invalid or
identity-mismatched assignments, class incompatibility, and workspace failures
are fatal and emit no partial JSON.

The command reads only the canonical assignment, optional roster, assignment
scan filenames, the selected canonical submission and review, and selected
export file presence. It does not inspect siblings or evidence content. It emits
no assignment prompt, student writing, evidence, notes, rationales, feedback
text/identifiers, reusable-comment data, or private-note content/identifiers.
It creates and modifies nothing and performs no assembly, OCR, QR decoding, AI,
inference, grading, workflow mutation, scan resolution, or export.

Within schema version `"1"`, required keys and types, null/zero meaning, status
semantics, privacy exclusions, ordering, and path formatting are stable.
Breaking changes require a new schema version; additions must be documented and
contract-tested.
