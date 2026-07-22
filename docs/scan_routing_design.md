# Scan Routing Design

Core continues to own workspace-level routing failures and scan resolutions.
Quillan consumes Core schema-version-2 metadata and establishes ownership from
exact locators, targets, or its bounded pre-dispatch marker. Failures after a
successful Quillan dispatch use the distinct work-local post-dispatch occurrence
contract described in
[Module-qualified record services](module_qualified_record_services.md).

## Installed Quillan handler (#337)

Core invokes the installed Quillan response-page handler with a validated
`RouteResolution`, one canonical `RetainedSourceScan`, and a positive physical
source-page number. Quillan's installed `ModuleProfile` declares the supported
Core routing contract, PDS2 QR schema, registration schema, dispatchable route
statuses, registration validator, and handler. Core remains the owner of
registry discovery, route resolution, and dispatch ordering.

The route registration must name target
`quillan/response_page/<page_id>`, contract version `1`, the canonical route ID,
and the exact immutable page authority. The handler derives workspace context
from the resolved class root, validates canonical class/module/work roots,
loads the immutable response-page and issuance context required by the route,
and rejects contradictory target or lifecycle data. It does not consult current
assignment or roster data; mutable records cannot change issued page authority.
Printed labels and fallback diagnostics never become routing authority.

The shared `validate_quillan_retained_source` service validates Core retention
provenance, absolute canonical workspace containment, every path component,
symlinks and Windows junctions, ordinary readable file type, and image page-one
semantics. The same provenance consistency service backs public Quillan result
validation. The retained filename, source scan ID, source filename, SHA-256,
relative and absolute paths, intake timestamp, and intake date must describe
one retention event. A Core-supplied intake-date override is valid and need not
equal the timestamp's UTC date.

The handler returns a validated `QuillanResponsePageDispatchResult` carrying
route/class/assignment identity and the complete retained-event provenance. It
writes no evidence, observations, submissions, or review resolution.

## Retain-once intake and Core dispatch (#338)

Each selected supported source is preflighted and retained exactly once through
Core. All subsequent page count, conversion, QR detection, parsing, request
construction, and dispatch work reads only that retained event. Raw QR
detection is grammar-independent; Core alone parses strict PDS2 and resolves
the locator. There is no caller payload mode, PDS1 parser, PDS1 route planner,
or legacy compatibility fallback.

Every enumerated physical page receives exactly one terminal outcome, including
unexpected `Exception` failures at page loading, QR detection, request creation,
dispatch integration, and Quillan-result validation. PDF pages are converted
one at a time, folder sources are independently contained, and one failure does
not suppress later pages or files. Core dispatch requests and outcomes remain in
physical-page order. Foreign-module successes are retained and counted without
reading their result objects.

Actionable failures are immutable Core routing-failure schema version `2`
occurrences under `scans/review/`. Their persistence status does not replace the
primary terminal outcome. After #338 returns its summary, the #339 layer persists
successful Quillan observations and assembles affected submissions without
modifying any terminal outcome.

The detailed state model, categories, persistence behavior, and CLI boundary
are documented in [`pds2_scan_intake.md`](pds2_scan_intake.md).

## Durable successful-page layer (#339)

Only an exact successful Quillan Core dispatch may create an observation. The
service revalidates the request, resolution, registration target, retained
source, immutable page context, complete issuance membership, and issued
lifecycle. Images are copied byte-for-byte from Core retention; one requested
PDF page is rendered to PNG. Observation JSON and evidence are installed as one
exclusive logical transaction and exact retries return `existing`.

Assembly enumerates `scans/observations/*.json`, verifies evidence hashes, and
groups by exact issuance ID. It loads all expected pages in issuance order,
represents missing slots, preserves rescans as duplicate candidates, and never
parses a routed filename for identity.
