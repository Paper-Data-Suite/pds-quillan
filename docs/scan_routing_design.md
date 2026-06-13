# Quillan Scan Routing Design

## Overview

This design describes how a future Quillan scan router should accept a scanned
writing-response page with an already-decoded PDS1 payload, validate its page
identity, and select a safe location in the Paper Data Suite workspace.

The PDS1 payload is the machine-readable source of class, assignment, student,
and page identity. A successfully routed file is preserved as raw source
evidence in the assignment-level `scans/` directory. Routing does not make the
page a complete submission and does not perform or imply teacher review.

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
* preserve the original scan evidence and never silently overwrite it;
* produce deterministic normal filenames and deterministic duplicate suffixes;
* preserve failed inputs for teacher review when the workspace is available;
  and
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

## Assumed Input Contract

The routing boundary begins after QR extraction. A future routing operation
should accept a value equivalent to:

```text
source_file_path
decoded_pds1_payload
optional source_page_index
optional source_file_type
```

`source_file_path` identifies the evidence to preserve. The path must refer to
a readable regular file at routing time.

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

The routing result should report success or failure, the selected destination
or review location, and whether duplicate naming was required. It should not
mutate submission metadata.

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

Validation should happen before filesystem writes and in the following order.

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

Student roster membership is not an initial routing prerequisite because a
production roster workflow is outside this design and may not be available.
The student identifier must still be valid. A future roster-aware phase may
flag an unknown student for review, but it must preserve the source evidence
rather than infer a different identity.

Validation should return stable, machine-readable failure codes in addition to
human-readable reasons. It must not attempt to repair identifiers, guess a
missing field, or route from printed names.

## Normal Routing Destination

A valid page routes first to:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/scans/
```

The future implementation should obtain this directory from
`pds_core.routes.assignment_scans_dir()` rather than reconstruct the shared
route in Quillan.

The initial filesystem operation should be copy-first so the incoming source
is not destroyed if routing or later review fails. Moving or deleting an
ingest source requires a separate, explicit retention policy.

The scans directory is deliberately assignment-level. It can contain
individual pages, duplicates, rescans, missing-page sets, and damaged evidence
without claiming that any student's response is complete.

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
under the workspace-level directory:

```text
<PDS workspace root>/routing_review/
```

This location is workspace-level because invalid scans may have no usable
class or assignment identity. Failure handling should copy the source using a
collision-safe review filename, leave the original source untouched, and
return a failure result. It must not fall back to a guessed assignment.

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
safely create a workspace review copy. It should leave the source untouched
and return a hard failure with enough context for the caller to surface the
problem. The exact review-folder filename pattern is deferred to the implementation ticket, but it should preserve the original extension when safe, avoid overwrites, and include enough stable context for teacher review.

## Routing Failure Metadata

A future implementation should create structured metadata for each preserved
failure, preferably as a JSON sidecar or append-only review index. The record
should include:

* a stable failure record identifier;
* original source path and copied review path, when available;
* decoded payload text, when available;
* stable failure code and human-readable reason;
* UTC timestamp;
* source page index, when available;
* original extension and detected or declared file type;
* path or validation stage that failed;
* whether the source was successfully preserved; and
* a concise suggested teacher action.

Failure metadata must not contain a score, feedback, or an inferred student
identity. Metadata writes should follow the same no-overwrite and path-safety
rules as scan files.

## Relationship to Submissions

A routed scan page is source evidence, not automatically a reviewed
submission. Routing a page must not:

* score the response;
* generate feedback;
* create requirements results or evidence tags;
* mark work as `needs_review` or `reviewed`; or
* necessarily create or update `submission.json`.

A student response may have multiple pages, missing pages, duplicate pages,
rescans, or damaged scans. Future submission assembly may link routed pages to
a student submission only after page completeness, provenance, and teacher
review requirements are defined. The original routed files should remain
traceable after any such linking.

## Future Implementation Phases

1. **Decoded-payload routing helper.** Define typed inputs and results; parse
   PDS1; validate Quillan response identity, identifiers, assignment
   relationships, extensions, filenames, and path containment without writing.
2. **Filesystem copy behavior.** Create assignment scan destinations,
   implement exclusive no-overwrite copies, and return normal or duplicate
   routes. Any move or source cleanup policy remains explicit and separate.
3. **QR extraction.** Add adapters that decode PDS1 text from scanned PDFs or
   images and pass canonical routing inputs to the independent routing helper.
4. **Duplicate and failure review metadata.** Preserve failed files, write
   structured failure records, and expose duplicates and failures for teacher
   review.
5. **Submission assembly and linking.** Define page manifests, completeness
   checks, rescan selection, and traceable links from routed evidence to
   student submission records.
6. **Teacher review integration.** Present assembled evidence to the teacher
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
