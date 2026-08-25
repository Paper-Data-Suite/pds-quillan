# Quillan Local Diagnostic Events

## Purpose

Quillan diagnostic events are local, privacy-minimal troubleshooting records for
high-value operational boundaries. They record bounded mechanical facts such as
workflow, stage, outcome, stable diagnostic code, safe class/assignment identity,
installed Quillan/Core versions, time, and sanitized path context.

They are not usage analytics, a teacher activity history, or authoritative domain
state.

## Ownership and storage

Events are Quillan-owned under:

```text
shared/quillan/diagnostics/events/<event_id>.json
```

They are not Core registry records and do not add a Paper Data Suite runtime
dependency.

A missing diagnostics directory is the valid empty state. Read-only inspection does
not create it.

## Non-authoritative semantics

Deleting diagnostic events must not alter assignments, submissions, review records,
feedback, review queue/class completion, routing, scan review, Academic Work
Registration, Academic Result manifests, Publication Records/catalog, attention, or
readiness.

The existing Assignment Review Dashboard answers what is true now. Diagnostic events
answer what bounded operational events happened recently.

#391 attention and #392 readiness must continue to derive from current authoritative
state rather than event history.

## Schema v1

The fixed fields are:

```text
schema_version
module
record_type
event_id
occurred_at
quillan_version
core_version
component
workflow
stage
outcome
category
code
class_id
assignment_id
exception_type
safe_summary
path_context
```

Fixed identity values are:

```text
schema_version = "1"
module         = "quillan"
record_type    = "diagnostic_event"
```

Unknown fields are rejected. There is no arbitrary metadata/payload/context bag.

`event_id` is opaque (`diag_` plus 32 lowercase hex characters) and is also the
immutable filename identity.

`occurred_at` is canonical timezone-aware UTC text. Listing orders newest first by
timestamp and then event ID.

## Privacy boundary

The event code owns the only persisted `safe_summary`; callers cannot provide
arbitrary diagnostic prose.

Only the exception class name may be retained. The builder never persists
`str(error)`, `repr(error)`, traceback, stack frames, locals, or exception object
contents.

Schema v1 has no generic student-ID, subject-ID, or display-name field.

Optional paths are canonicalized inside the workspace and generalized where needed:

```text
.../submissions/<student>/review.json
scans/<source>
```

Diagnostic bytes must not contain student writing, OCR text, feedback bodies, ratings,
rationales, private notes, roster/contact data, raw scans, full QR payloads,
credentials/tokens, whole canonical records, raw exception dumps, or absolute
machine paths.

## Immutable persistence and retention

Each event is one canonical immutable UTF-8 JSON file created through Quillan's
exclusive atomic-record persistence boundary. Existing events are never overwritten.

The default retained-event cap is:

```text
500
```

Retention runs only after successful creation and removes only old files proven to be
valid canonical Quillan diagnostic events. Malformed, unknown, or unrelated entries
are preserved.

There is no background cleanup task, watcher, scheduler, or daemon.

## Non-interference

Production instrumentation uses:

```python
try_emit_diagnostic_event(...)
```

rather than the strict writer.

Diagnostic build/storage failure cannot replace a primary success, failure, or
partial-success result, trigger primary-operation retry, or roll back canonical
state. The diagnostics subsystem does not recursively diagnose its own write failure.

## Event-emission policy

Quillan does not log every function call, screen view, student selection, Back/Refresh
action, or teacher judgment.

Current high-value instrumentation covers:

```text
assignment copy
returned-paper intake
submission assembly
review-write failure/uncertainty
individual feedback export
batch feedback export
Academic Work Registration conflicts/partial success
Academic Result manifest failure/partial success/new verified revision
Core publication/supersession conflict/partial success/verified success
Share Results post-authorization freshness refusal
verified post-dispatch recovery
```

Routine successful review choices are not logged. Ratings, rationales, feedback
composition, private notes, and minimum-requirement judgments do not become event
history.

Exact replay of an existing Academic Result manifest head does not create a new
manifest-success event.

Core publication success is logged only after canonical reload, exact manifest
verification, producer compatibility, and catalog reconciliation complete.

`Share Results with Meridian` does not duplicate the successful publication event.
Its guided layer records only the case where state changed after typed
`PUBLISH`/`SUPERSEDE` authorization and before the Core write.

The wording boundary remains "published through Core and ready for authorized
compatible Meridian discovery"; diagnostics never claim Meridian ingested anything.

A `recovered` event is emitted only after the owner workflow has verified and
persisted the recovery.

## Direct CLI

Advanced read-only inspection is:

```powershell
quillan diagnostics list
quillan diagnostics list --limit 20
quillan diagnostics list --format json

quillan diagnostics show --event-id <event_id>
quillan diagnostics show --event-id <event_id> --format json
```

`list` defaults to 50 recent events and the service enforces a hard maximum of 200.
Text and JSON expose only the already privacy-minimized fixed event model. Malformed
retained files produce bounded warning codes rather than raw-byte dumps.

There is deliberately no diagnostics command for:

```text
delete
clear
tail
watch
stream
upload
send
share
```

No new teacher dashboard is added.

## No telemetry

The diagnostics implementation performs no HTTP request, socket connection, remote
logging, crash upload, email, analytics export, or background network activity. It
adds no Sentry, OpenTelemetry exporter, analytics SDK, remote-logging dependency, or
Paper Data Suite runtime dependency.

## Core compatibility

#390 does not require a Core API change. Quillan retains:

```text
pds-core>=0.6,<0.7
```

The installed Core version is recorded only as bounded troubleshooting context.

The release-qualification slice for #390 separately preserves exact Core 0.6.0
minimum-version coverage while adding exact authenticated Core 0.6.3 coverage.

## Related contracts

- [CLI Contract](cli_contract.md)
- [Assignment Review Dashboard](review_dashboard_contract.md)
- [Share Results with Meridian](share_results_with_meridian.md)
- [Academic Result Manifest Generation](academic_result_manifest_generation.md)
- [Academic Result Publication Lifecycle](academic_result_publication.md)

### Exact Core 0.6.3 qualification

The normal CI validation matrix continues to install and authenticate exact
`pds-core` 0.6.0 across Python 3.11–3.14 on Windows and Ubuntu. That remains the
proof that Quillan's declared minimum `pds-core>=0.6` is truthful.

A separate compatibility matrix additionally qualifies exact Core 0.6.3 on:

```text
Windows + Python 3.11
Windows + Python 3.14
Ubuntu  + Python 3.11
Ubuntu  + Python 3.14
```

The official wheel identity is pinned as:

```text
filename:
pds_core-0.6.3-py3-none-any.whl

distribution:
pds-core

version:
0.6.3

sha256:
98d7596ce0eed26e4d56a17bbbbd644db3014259b56a45783a173fe8237af5e5
```

The verifier requires the caller to select an explicitly known release contract;
a version-range match is never treated as artifact authentication. Each v0.6.3
qualification job verifies the wheel before installation, verifies installed package
metadata and import origin afterward, runs `pip check`, proves diagnostic events
report `core_version = 0.6.3`, runs focused diagnostic/wheel-contract tests, runs the
full Quillan suite, and runs release-compatibility validation.

Quillan does not use any v0.6.3-only Core API for diagnostic events and therefore
retains:

```text
pds-core>=0.6,<0.7
```
