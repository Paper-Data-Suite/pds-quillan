# Retained PDS2 Scan Intake

This boundary accepts exactly `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, and
`.tiff` sources. A file operation handles one source. Folder intake is
nonrecursive, orders direct children by case-folded then exact name, skips
unsupported ordinary files, reports unsafe/nonfile children, and reuses one
validated installed-module registry for every selected source.

## Intake sequence

The sequence is fixed: validate the existing canonical non-link workspace and
source, call Core `retain_source_scan` exactly once, enumerate only the retained
copy, detect exact raw QR text, call only Core `parse_pds2_payload`, construct
ordered `RouteDispatchRequest` values, call `dispatch_routes` once, integrate
the aligned outcomes, then preserve actionable failures. The external original
is never read after retention. PDFs are counted once and converted exactly one
requested page at a time, so a page conversion failure cannot suppress a later
physical page.

## Runtime states

A source result has exactly one state:

- pre-retention failure: no retained source, no pages, one source error;
- retained source-level failure: the exact retained event, no pages, one
  source error; or
- enumerated source: the exact retained event, a positive ordered tuple with
  one outcome for every physical page, and no source error.

Each enumerated page has exactly one terminal category:

- `dispatch_success`: an exact Core success aligned with its request;
- `core_dispatch_failure`: an exact Core expected failure and actual exception;
- `pre_dispatch_failure`: page loading, QR detection, strict payload parsing,
  or request construction failed; or
- `quillan_integration_failure`: Core output alignment/structure or a
  Quillan-owned success result contradicted the submitted request.

The aggregate requires immutable source tuples, deterministic registry IDs,
exact terminal totals, and nonnegative skip counts. Its deterministic status is
one of `complete_success`, `partial_success`, `zero_success`, `source_failure`,
`integration_failure`, or `review_persistence_failure`.

## Core dispatch and mixed modules

The PDS2 locator carries module, class, work, and route identity. Physical
`source_page_number` is retained scan order, not a Quillan logical-page number.
Core owns route resolution and expected dispatch failures. A Quillan success
must be a valid `QuillanResponsePageDispatchResult` and match every request and
retention field. Successful foreign-module results are counted but remain
opaque; the orchestrator does not inspect their module result.

Non-PDS2 declarations are `payload_schema_unsupported`; oversized ASCII is
`payload_too_large`; Core identifier/routing exception chains are
`identifier_invalid`; other malformed PDS2 is `payload_invalid`. No partial
payload identity becomes a locator and there is no PDS1 fallback.

## Failure occurrence persistence

Every actionable post-retention page or source failure is independently
offered to the Core-v2 occurrence writer under
`scans/review/<failure_id>.json`. Normal Core failures use Core's dispatch
failure factory. Pre-dispatch and integration records retain the exact source
event, page, raw payload, and only Core-validated locator/target values.
Records use schema version `2`, bounded JSON-native module details, exclusive
creation, and reload/equality verification. Persistence errors are orthogonal:
a successful occurrence stays attached even when another occurrence fails,
and a possibly durable path is reported when verification fails after writing.
Source-level review paths and persistence errors appear in the summary.

## Post-dispatch persistence (#339)

After the immutable #338 summary is complete, Quillan processes only successful
Quillan-owned outcomes. It persists or reload-verifies one deterministic
observation/evidence pair per physical occurrence, then assembles every affected
student by authoritative issuance membership. Foreign successes remain opaque.
Dispatch, persistence, and assembly counts are reported separately; a
post-dispatch conflict makes `route-scan` nonzero without changing Core outcomes.
