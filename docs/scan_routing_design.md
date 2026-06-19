# Quillan Scan Routing Design

## Overview

This design describes how a future Quillan scan router should accept a scanned
writing-response page with an already-decoded PDS1 payload, validate its page
identity, and select a safe location in the Paper Data Suite workspace.

Future Quillan scan routing must follow the shared active scan contract defined
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

This document is a design spike only. It does not implement scan routing, QR
extraction, image processing, or OCR.

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
for the caller to surface the problem. Exact review-record and optional
problem-artifact naming belong to the shared `pds-core` contract and its future
implementation.

## Routing Failure Metadata

A future implementation must use the shared `pds-core` routing failure metadata
shape and shared failure categories. Quillan must not define a parallel
failure-record schema. Validated Quillan identity and payload information use
the shared base fields where available; Quillan-only details, such as response
page validation or submission completeness context, belong under:

```text
module_details
```

Canonical failure JSON records live in `scans/review/`. They must preserve
provenance back to the retained source, use workspace-relative paths, avoid
guessed identities, and follow the shared no-overwrite and path-safety rules.
Failure metadata must not contain a score, feedback, or an inferred student
identity.

## Relationship to Submissions

A routed scan page is evidence derived or copied from a retained source scan,
not automatically a reviewed submission. Routing a page must not:

* score the response;
* generate feedback;
* create requirements results or evidence tags;
* mark work as `needs_review` or `reviewed`; or
* necessarily create or update `submission.json`.

A student response may have multiple pages, missing pages, duplicate pages,
rescans, or damaged scans. Future submission assembly may link routed pages to
a student submission only after page completeness, provenance, and teacher
review requirements are defined. The original routed files should remain
traceable to the canonical retained source after any such linking.

Quillan owns the future routed evidence layout inside
`submissions/<student_id>/`, submission assembly, page completeness rules,
teacher review and rescan decisions, and any future Quillan OCR policy. Those
module decisions must continue to use the shared source-retention, provenance,
and routing-review contract.

## Ownership Boundaries

`pds-core` owns the shared active source-scan and routing-review contract,
including source and review paths, retained-source naming, base failure
metadata, shared failure categories, copy-first behavior, no-overwrite rules,
and provenance semantics.

Quillan owns future module-specific behavior, including:

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

1. **Shared retention integration.** Use future `pds-core` source-retention and
   routing-review helpers without redefining their contracts in Quillan.
2. **Decoded-payload routing helper.** Define typed inputs and results; parse
   PDS1; validate Quillan response identity, identifiers, assignment
   relationships, extensions, filenames, and path containment without writing
   routed evidence.
3. **Routed evidence writes.** Create assignment scan destinations, implement
   exclusive no-overwrite copies or derived artifacts, and preserve provenance
   to the retained source.
4. **QR extraction and splitting.** Add Quillan adapters that decode PDS1 text
   from scanned PDFs or images and pass canonical routing inputs to the
   independent routing helper.
5. **Duplicate and failure review metadata.** Use shared failure records and
   categories, put Quillan-specific context under `module_details`, and expose
   duplicates and failures for teacher review.
6. **Submission assembly and linking.** Define page manifests, completeness
   checks, rescan selection, and traceable links from routed evidence to
   student submission records.
7. **Teacher review integration.** Present assembled evidence to the teacher
   and allow teacher-controlled lifecycle changes without automated judgment.

Each phase should add focused tests for validation, traversal resistance,
collision races, preservation on failure, and the absence of unintended
submission mutations.

## Out of Scope

This spike does not implement:

* scan routing, copying, moving, or filing;
* QR detection or extraction;
* PDF splitting, image processing, or OCR;
* submission assembly or production roster workflows;
* requirements checking, tagging, scoring, feedback, or reporting;
* AI tagging, scoring, feedback, or automatic grading;
* CLI, menu, or workspace-settings workflows; or
* changes to `pds-core`, `pds-scoreform`, or Python behavior.
