# Quillan Scan Routing Design

## Overview

This design describes how Quillan accepts a selected writing-response scan with
an already-decoded PDS1 payload, validates its page identity, retains the active
source copy, and files routed evidence in the Paper Data Suite workspace. It
also describes how that evidence feeds the v0.6 student submission and review
workflow.

Quillan scan routing follows the shared active scan contract defined
by `pds-core` in `docs/active_scan_contract.md`. That contract owns active
source retention, routing review, shared failure metadata, and provenance
semantics. This document adds only Quillan-specific response-page validation,
routed evidence, submission assembly, and teacher-review design.

Quillan currently generates printable response PDFs and embeds canonical PDS1
Quillan response payloads in QR codes on those pages. That implemented output
is the upstream artifact assumed by this design; Quillan does not yet extract
those QR payloads from scanned PDFs or images.

The PDS1 payload is the machine-readable source of class, assignment, student,
and page identity. A successfully routed file may be copied or derived as
routed evidence in the assignment-level `scans/` directory. The canonical
active retained source remains in `scans/source/YYYY-MM-DD/`. Routing does not
make the page a complete submission and does not perform or imply teacher
review.

Quillan now implements the first successful-write slice through
`quillan.evidence_filing.file_routed_response_evidence()`. Given a readable
source file and an existing successful `RoutePlan`, it exclusively copies the
source into `scans/source/YYYY-MM-DD/`, files the retained source or a
caller-supplied page artifact into assignment `scans/`, preserves duplicates,
and returns provenance. Quillan also implements metadata-only failure
preservation through `quillan.routing_review`, writing shared failure records
under `scans/review/`. The direct
`quillan route-scan <source-file> --payload "<PDS1|...>"` command orchestrates
these slices for a caller-supplied decoded payload. It does not implement QR
extraction, PDF splitting, image processing, or OCR. Submission assembly is a
separate implemented step through `quillan assemble-submissions`.

## Design Goals

The future router should:

* accept decoded payload data without depending on a QR scanner or PDF/image
  processing library;
* validate PDS1 structure and Quillan response-page identity before using any
  payload value in a path;
* use shared `pds-core` parsers, identifier validators, and route helpers where
  available;
* keep every computed destination inside the resolved PDS workspace root;
* follow the shared copy-first, no-overwrite, and provenance requirements;
* produce deterministic normal filenames and deterministic duplicate suffixes;
* record routing failures under the shared `scans/review/` contract when the
  workspace is available; and
* leave scoring, feedback, and review status under teacher control.

## Non-Goals

Scan routing does not:

* detect or decode QR codes;
* split PDFs or transform image files;
* interpret handwriting or run OCR;
* determine page completeness or image quality;
* assemble a multi-page submission;
* create scores, feedback, tags, or requirements results; or
* mark a response as reviewed.

## Shared Intake and Retention Prerequisite

Before Quillan-specific parsing or routing, a future active scan workflow must
follow the shared `pds-core` contract:

1. Leave the teacher's original selected file untouched.
2. Copy every readable selected source into
   `scans/source/YYYY-MM-DD/`.
3. Avoid silent overwrites of retained sources, review records, and routed
   evidence.
4. Process the retained source or keep explicit provenance back to it.
5. Copy or derive Quillan evidence into assignment or student locations only
   after source retention.
6. Preserve provenance from every routed Quillan artifact back to the retained
   source scan.

`scans_inbox/` remains the shared teacher-facing intake/drop location. It is
not the canonical retained source store. The exact retained-source naming,
copying, and helper APIs belong to `pds-core`, not this Quillan design.

## Assumed Quillan Routing Input

The Quillan-specific routing boundary begins after shared source retention and
QR extraction. A future routing operation should accept a value equivalent to:

```text
source_file_path
retained_source_identity_or_path
decoded_pds1_payload
optional source_page_index
optional source_file_type
```

`source_file_path` identifies the retained source or a derived page artifact to
route. It must refer to a readable regular file at routing time.

`retained_source_identity_or_path` provides the provenance link to the
canonical active retained source in `scans/source/YYYY-MM-DD/`. The future
shared contract implementation will determine the exact typed representation.

`decoded_pds1_payload` is the decoded text, not a QR image or partially parsed
field map. Keeping the canonical text at this boundary allows
`pds_core.pds1.parse_pds1_payload()` to apply one shared parser.

`source_page_index` records which page in a multi-page source produced the
routed page. It is provenance metadata and must not replace the one-based
response `page` value in the payload.

`source_file_type` may carry a trusted type discovered by an earlier pipeline
stage. If it is absent, the router may infer the type from the source file
extension. A future implementation must use a controlled extension mapping
rather than append unchecked input to a destination filename.

The routing result should report success or failure, the selected routed
evidence destination or review record, retained-source provenance, and whether
duplicate naming was required. It should not mutate submission metadata.

## PDS1 Payload Fields

Quillan printable response pages use this canonical payload:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

The routing fields are:

| Payload field | Meaning |
| --- | --- |
| `PDS1` | Payload schema and required prefix |
| `module` | Must be `quillan` |
| `class` | Shared PDS `class_id` |
| `aid` | Shared PDS `assignment_id` |
| `sid` | Shared PDS `student_id` |
| `page` | Positive integer response-page number |
| `doc` | Must be `response` |

Human-readable names and labels printed on the page are handling aids. They do
not override decoded payload identity.

## Payload Validation

Quillan-specific validation should happen after shared source retention and
before routed-evidence writes, in the following order.

1. **Input validation.** Require a readable source file and a nonblank decoded
   payload string. Validate or map the source type to a supported, normalized
   extension.
2. **PDS1 parsing.** Parse with `pds_core.pds1.parse_pds1_payload()`. Reject a
   missing or malformed payload, a prefix other than `PDS1`, missing fields,
   blank values, duplicate fields, malformed segments, and a non-integer page.
3. **Document validation.** Require `module=quillan` and metadata
   `doc=response`. A valid PDS1 payload for another module or document type is
   not a routable Quillan response page.
4. **Identifier validation.** Validate `class`, `aid`, and `sid` as
   `class_id`, `assignment_id`, and `student_id` with
   `pds_core.identifiers.validate_identifier()`. Current shared identifiers
   allow only letters, numbers, underscores, and hyphens, with no blanks or
   leading/trailing whitespace.
5. **Page validation.** Require `page` to be an integer greater than zero.
   Boolean values must not be accepted as integers by any alternate structured
   input boundary.
6. **Workspace relationship validation.** Resolve the configured workspace
   root, derive the assignment through shared route helpers, and require the
   target assignment to be a known workspace assignment before filing a scan.
   Where `assignment.json` is consulted, its validated `assignment_id` and
   `class_ids` must agree with the payload. A mismatch is a routing failure,
   not permission to create a new assignment from QR data.
7. **Path safety validation.** Build the scans directory with
   `pds_core.routes.assignment_scans_dir()` and construct the filename only
   from validated identifiers, the validated page number, and a controlled
   extension. Resolve the candidate path without requiring it to exist and
   verify that it remains inside the resolved workspace root. Reject any path
   that escapes the root, including through traversal or filesystem links.

Quillan's decoded response route planner requires the canonical class roster
to exist and validates exact student-ID membership before returning a route
plan. An unknown student produces a structured `student_unknown` failure; the
planner never substitutes a student based on names or other context. The
planner only reads routing context and computes destination paths. It does not
write routed evidence or review metadata.

Validation should return stable, machine-readable failure codes in addition to
human-readable reasons. It must not attempt to repair identifiers, guess a
missing field, or route from printed names.

## Routed Evidence Destination

A valid Quillan response page may route as evidence to:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/scans/
```

The future implementation should obtain this directory from
`pds_core.routes.assignment_scans_dir()` rather than reconstruct the shared
route in Quillan.

This assignment-level `scans/` directory contains routed scan evidence, not
canonical source retention. It can contain individual pages, duplicates,
rescans, missing-page sets, and damaged evidence without claiming that any
student's response is complete. Every artifact must remain traceable to its
retained source in `scans/source/YYYY-MM-DD/`.

Student submission records remain under:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/
```

## File Naming

The normal routed filename is:

```text
response_<student_id>_pg_<page_number>.<ext>
```

`page_number` uses a minimum width of three digits:

```text
response_stu_0001_pg_001.pdf
```

Values above 999 remain intact rather than being truncated. For example, page
1000 is `pg_1000`.

The extension should preserve or accurately reflect the routed source type
when possible. It should be normalized to a safe canonical extension, such as
mapping `.jpeg` consistently according to the future supported-type policy.
The router must not transcode a file merely to make its extension match.

## Collision Behavior

Routing must never silently overwrite an existing file. If the normal path
exists, select the first available duplicate number:

```text
response_<student_id>_pg_<page_number>__dup_<duplicate_number>.<ext>
```

For example:

```text
response_stu_0001_pg_001__dup_001.pdf
```

Duplicate numbers use a minimum width of three digits and increase
monotonically for the same normal filename and extension. Selection and file
creation must be exclusive so concurrent routing operations cannot choose the
same destination.

Duplicates are preserved because they may be legitimate rescans or evidence
of an ingest mistake. A future implementation should record or flag duplicate
routing events for teacher review; it should not compare content and discard a
file automatically.

## Routing Failures

When a page cannot be safely routed to an assignment, preserve it for review
through the shared workspace-level review location:

```text
<PDS workspace root>/scans/review/
```

Canonical failure records live here because invalid scans may have no usable
class or assignment identity. The shared contract may also permit problem
artifacts in this location. Failure handling must preserve retained-source
provenance, avoid overwrites, and never fall back to a guessed assignment.

Failure cases include:

* unreadable source files or missing decoded payloads;
* malformed PDS1 payloads;
* wrong module or document type;
* missing or blank class, assignment, or student identifiers;
* invalid identifier formats;
* missing, non-integer, or non-positive page numbers;
* unsupported or inconsistent file types;
* unknown or mismatched workspace assignments;
* unsafe destinations or failed path-containment checks; and
* filesystem errors that prevent the normal route from being completed.

If the workspace root itself cannot be resolved or written, the router cannot
safely retain a source or create a shared review record. It should leave the
teacher's original file untouched and return a hard failure with enough context
for the caller to surface the problem. Review-record naming and exclusive JSON
writes use the shared `pds-core` contract. Quillan does not currently create or
copy optional problem artifacts.

## Routing Failure Metadata

`quillan.routing_review` implements metadata-only failure preservation using
the shared `pds-core` routing failure metadata model, writer, paths, and failure
categories. It accepts general failures and provides adapters for `RouteFailure`
and `EvidenceFilingError`; it does not re-run planning or successful evidence
filing. Quillan does not define a parallel failure-record schema. Validated
Quillan identity and payload information use the shared base fields where
available; Quillan-only details belong under:

```text
module_details
```

Canonical failure JSON records live in `scans/review/`. They must preserve
provenance back to the retained source, use workspace-relative paths, avoid
guessed identities, and follow the shared no-overwrite and path-safety rules.
Failure metadata must not contain a score, feedback, or an inferred student
identity. Retained-source provenance is recorded only when available, and a
supplied review artifact path is recorded only as workspace-relative metadata;
the helper does not copy that artifact.

## Relationship to Reviewable Evidence and Submissions

A routed scan page is evidence derived or copied from a retained source scan,
not automatically a reviewed submission. Routing a page must not:

* score the response;
* generate feedback;
* create requirements results or evidence tags;
* set a submission manifest's `submission_state`; or
* necessarily create or update `submission.json`.

A student response may have multiple pages, missing pages, duplicate pages,
rescans, or damaged scans. The draft version `1` submission manifest contract
in [`data_contracts.md`](data_contracts.md#submission-manifest) represents
those conditions without guessing which evidence the teacher intends to use.
The focused submission assembly API can create that record from
caller-provided routed evidence metadata, automatically selecting only
unambiguous ordinary active pages and preserving replacement, damaged,
needs-rescan, excluded, and duplicate evidence for later review. Explicit
candidate roles also remain unselected. The `quillan assemble-submissions`
command discovers supported routed filenames in the assignment `scans/`
directory and creates missing manifests. It does not inspect evidence contents,
infer teacher choice among ambiguous duplicates, merge existing manifests, or
update review metadata. The original routed files remain traceable to the
canonical retained source after linking when that provenance is available.

The canonical record location is:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

The manifest stores workspace-relative routed-evidence and retained-source
paths, page and evidence states, nullable teacher selection, and provenance.
It preserves duplicate, replacement, damaged, and excluded evidence rather
than overwriting or deleting candidates. Loading, validation, path helpers,
safe writing, and focused new-manifest assembly are implemented independently
of `route-scan`.

The supported review sequence after routing and assembly is deliberately
small:

1. `quillan list-submissions <class_id> <assignment_id>` reports manifests,
   routed evidence, missing pages, duplicate pages, needs-rescan pages,
   excluded pages, present-but-unselected evidence, and students needing
   assembly without modifying files.
2. `quillan open-evidence <path>` opens a specific workspace-relative evidence
   file as a low-level local helper; it has no student-submission context.
3. `quillan open-submission <class_id> <assignment_id> <student_id>` loads the
   canonical manifest and opens its evidence only when exactly one item is
   selected.
4. The teacher reviews the evidence in the system viewer.
5. `quillan set-review-state <class_id> <assignment_id> <student_id> <state>`
   may then set `unreviewed`, `in_progress`, `needs_rescan`, or `reviewed`.

Opening evidence and updating review state are separate actions. The
review-state command is teacher-controlled and metadata-only: it changes only
`submission_state` and `updated_at`. Routed evidence never automatically
implies reviewed work.

Quillan owns the manifest contract, submission assembly, page
completeness rules, teacher review and rescan decisions, and any future
Quillan OCR policy. Those module decisions must continue to use the shared
source-retention, provenance, and routing-review contract.

## Ownership Boundaries

`pds-core` owns the shared active source-scan and routing-review contract,
including source and review paths, retained-source naming, base failure
metadata, shared failure categories, copy-first behavior, no-overwrite rules,
and provenance semantics.

Quillan module responsibilities include:

* interpreting Quillan `PDS1` response payloads;
* validating response pages;
* QR extraction and PDF or image splitting for Quillan workflows;
* deciding routed evidence layout inside student submission folders;
* assembling student submissions and checking page completeness;
* supporting teacher review and rescan decisions;
* any future OCR decisions; and
* Quillan-specific failure details stored under `module_details`.

Inactive historical preservation and end-of-cycle archiving belong to future
`pds-sunset` workflows, not active Quillan scan intake or routing.

## Future Implementation Phases

1. **Shared retention and routing-review integration.** Partially implemented
   through successful retained-source filing with `pds-core` retained-source
   naming/path helpers and metadata-only failure preservation through shared
   `pds-core` routing failure records under `scans/review/`.
2. **Decoded-payload routing helper.** Implemented as the read-only
   `RoutePlan`/`RouteFailure` planner for already-decoded response-page data.
3. **Routed evidence writes.** Implemented for successful routes: create
   assignment scan destinations, use exclusive no-overwrite copies, preserve
   duplicate evidence, and return provenance to the retained source.
4. **Direct decoded-payload command.** Implemented as `quillan route-scan` for
   one selected source file and an already-decoded payload, with safe review
   preservation and no submission assembly.
5. **QR extraction and splitting.** Add Quillan adapters that decode PDS1 text
   from scanned PDFs or images and pass canonical routing inputs to the
   independent routing helper.
6. **Duplicate and failure review workflows.** Metadata-only failure preservation
   is implemented with shared `pds-core` records under `scans/review/`.
   Future work should expose preserved failures and duplicate routed evidence
   for teacher review.
7. **Submission assembly and linking.** The first page-oriented submission
   manifest contract, loader, validator, path helpers, safe writer, and focused
   assembly API are implemented. Assignment-level filename discovery and direct
   assembly are implemented through `quillan assemble-submissions`, including
   optional expected-page completeness reporting. Manifest merging, retained
   provenance reconstruction, and rescan selection remain future work.
8. **Teacher review integration.** Present assembled evidence to the teacher
   and allow teacher-controlled lifecycle changes without automated judgment.
   A low-level `quillan open-evidence` command now validates one existing file
   inside the active workspace and delegates opening to `pds-core`. The
   read-only `quillan open-submission` command locates a student's canonical
   validated manifest and opens its single selected routed evidence item
   through that same helper. It does not select evidence, update review state,
   score, tag, inspect, OCR, or generate feedback. Missing, duplicate,
   needs-rescan, and unselected submissions should be inspected with
   `quillan list-submissions` first. The separate teacher-controlled
   `quillan set-review-state` command can explicitly set `unreviewed`,
   `in_progress`, `needs_rescan`, or `reviewed`; it changes only
   `submission_state` and `updated_at` and does not inspect evidence or perform
   automated judgment.

Each phase should add focused tests for validation, traversal resistance,
collision races, preservation on failure, and the absence of unintended
submission mutations.

## Out of Scope

The v0.6 reviewable-evidence workflow does not implement:

* end-to-end production scan intake automation;
* QR detection or extraction;
* PDF splitting, PDF text extraction, image processing, OCR, or handwriting
  recognition;
* automatic evidence selection among duplicates;
* automatic review-state updates;
* requirements checking, rubric scoring, tagging, teacher comment entry,
  feedback export, or report generation;
* AI suggestions, AI scoring, AI feedback, or automatic grading;
* menu or workspace-settings routing workflows; or
* changes to `pds-core`, `pds-scoreform`, or Python behavior.
