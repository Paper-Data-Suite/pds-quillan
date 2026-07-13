# Assignment Review Dashboard Contract

## Command and boundary

```powershell
quillan review-dashboard <class_id> <assignment_id> [--format text|json]
```

Text is the default. The command and Assignment Review Actions menu use the
same immutable service. JSON is printed only to standard output. A successful
dashboard may read the canonical assignment, class roster, student submission
and review records, routed-evidence filenames and routing metadata, feedback
export metadata and file existence, and scan-review failure and resolution
metadata. Paths are workspace-relative POSIX strings.

There is no workspace write boundary. The service creates no directories,
records, manifests, exports, reports, temporary files, locks, caches, scan
resolutions, or audit entries and changes no timestamps. It does not open or
inspect student evidence, PDFs, or images; decode QR data; run OCR, handwriting
recognition, or AI; infer requirements, ratings, grades, mastery, or feedback;
assemble submissions; resolve scan items; or invoke an export writer.

## Population and diagnostics

Students are ordered as current roster entries in roster order, followed by
submission-directory students sorted by exact ID, then routed-evidence-only
students sorted by exact ID. Exact IDs are deduplicated. Roster names display
as `First Last`; other rows fall back to the student ID. If the roster is
missing or invalid, assignment-local students remain visible in ID order,
`roster_available` is false, `rostered` is null, and no complete expected
population is claimed.

Submission and review files are independently classified as `missing`,
`valid`, `invalid`, or `identity_mismatch`; a review beside no valid submission
is `orphaned`. A malformed student file produces student and dashboard warnings
without hiding other rows. Valid plain-paper manifests are valid submissions
with zero digital pages. Only valid, identity-matching records contribute
stored workflow-state counts.

Page states are `present`, `missing`, `duplicate`, `needs_rescan`, and
`excluded`, plus `present_unselected`. Feedback PDF and Markdown are counted
separately as `present`, `stale`, `missing`, or `unknown` using canonical export
metadata freshness rules. Assignment-filtered unresolved and deferred scan
items are included; resolved items are excluded. Scan discovery failure sets
`available` false rather than inventing zero availability.

Diagnostic conditions return success once the dashboard is safely built.
Fatal assignment validation, identifier, discovery, or serialization failures
return nonzero and no partial dashboard.

## JSON schema version 1

The top-level object always contains, in stable order:

```text
schema_version, record_type, class_id, assignment_id, assignment, summary,
students, unassembled_routed_files, unused_duplicate_routed_files,
skipped_routed_files, scan_review_items, warnings
```

`schema_version` is `"1"`; `record_type` is
`"quillan_assignment_review_dashboard"`. `assignment` contains `title`,
`writing_type`, `standards_profile_id`, `focus_standard_count`, and `path`.
`summary` always contains `students`, `submissions`, `pages`,
`routed_evidence`, `reviews`, `minimum_requirements`, `feedback_exports`, and
`scan_review`. Fixed state groups remain present even when every count is zero.

Each student has stable `student_id`, `display_name`, `roster_status`,
`routed_evidence_present`, `needs_assembly`, `submission`, `review`, `exports`,
and `warnings` keys. Submission objects include status, canonical path, stored
state or null, plain-paper boolean, and all page counts. Review objects include
status, canonical path, stored state or null, minimum-requirement status or
null, and returned-without-full-review boolean.

Counts are JSON integers, flags are JSON booleans, genuinely unavailable
scalars are JSON null, and ordered collections are arrays. Empty arrays are not
omitted. No execution timestamp, random identifier, absolute path, or `Path`
representation is emitted, so repeated unchanged invocations are structurally
identical. Renaming or removing keys, changing their JSON types or meanings, or
changing path semantics requires a dashboard schema-version change.
