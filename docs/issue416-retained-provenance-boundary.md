# Issue #416 Slice 1 — persisted Core retained-provenance boundary

This slice changes Quillan's retained-source consistency validator from
**current-writer reconstruction** to **persisted-event consistency**.

## Ownership boundary

Core owns retained-source identity. Quillan receives and persists:

- `source_scan_id`
- `source_filename`
- `source_sha256`
- `retained_source_relative_path`
- `intake_timestamp`
- `intake_date`

Quillan validates those values without asking the currently installed Core
writer what filename it would generate today.

## What remains strict

Slice 1 still checks the durable Core 0.6 retention envelope:

- safe Core retained filename/date grammar;
- retained timestamp component against `intake_timestamp`;
- retained digest prefix against `source_sha256`;
- source/retained extension agreement;
- date bucket against `intake_date`;
- `source_scan_id == "scan_" + retained filename stem`;
- absolute/relative retained-path agreement; and
- canonical workspace placement when `workspace_root` is supplied.

The middle retained-name component is treated as historical persisted identity.
It is not reconstructed from `source_filename`.

This accepts both the historical Core 0.6.3 long-name form and the new bounded
Core 0.6.4 form while preserving their exact stored identities.

## Compatibility

This slice performs no migration and no filesystem mutation. It does not rename
Core retained scans, Quillan observations, routed evidence, manifests, or review
records.

A valid historical record remains valid at its existing path.

## Deferred to later #416 slices

This slice does **not** yet:

- replace `pdfinfo_from_path` / `convert_from_path`;
- replace `cv2.imread` for retained-source image decoding;
- introduce bounded new Quillan routed-evidence filenames;
- add legacy/new routed-evidence dual-reader behavior; or
- add installed Windows deep-path acceptance.

Those are separate implementation boundaries so provenance compatibility can be
qualified independently before changing byte-decoding or Quillan-owned writers.
