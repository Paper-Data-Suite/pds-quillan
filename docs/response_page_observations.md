# Response-Page Observations

Observation and routed-evidence records are Quillan-owned descendants of the
exact module-qualified work root. Their paths are derived from the shared work
identity; submission and review services do not reinterpret routed filenames.
Post-dispatch persistence failures are stored separately from Core routing
failures as append-only Quillan occurrences. See
[Module-qualified record services](module_qualified_record_services.md).

One durable Quillan page observation is identified by the deterministic SHA-256
key `source_scan_id + source_page_number + route_id + page_id` under the domain
`quillan-response-page-observation-v1`. Its ID is `obs_` plus the first 32
lowercase hexadecimal digest characters. A later Core retention event, another
physical source page, page ID, or route ID therefore remains a distinct,
append-only observation.

Records use schema `1`, record type `response_page_observation`, and module ID
`quillan`. They preserve immutable generation, artifact, issuance, page and
route identity; logical page meaning; complete retained provenance; and routed
evidence path, hash, size, and kind. `created_at` equals the intake timestamp.
Strict JSON rejects unknown or missing fields, duplicate keys, nonstandard
constants, malformed UTF-8, unsafe paths, and noncanonical IDs.
The serialized retained fields must reconstruct one exact Core retention event:
the timestamp, original filename, lowercase source hash, retained filename,
`scan_` ID, intake-date bucket, normalized extension, and canonical relative
path must all agree. Workspace discovery also requires the corresponding
ordinary, contained, non-link Core path without rehashing or rewriting it.

Canonical storage is:

```text
classes/<class>/modules/quillan/work/<assignment>/
  scans/observations/<observation_id>.json
  scans/evidence/<issuance_id>/response_<student>_pg_<logical>__<observation_id>.<ext>
  submissions/<student>/submission.json
```

The evidence filename is diagnostic only. Identity and membership come from
the observation plus immutable issuance/page records. Retained images are
copied without transcoding. A PDF contributes only the requested physical page,
rendered as PNG. Evidence is reopen-verified by SHA-256 and size.

Exact retries return `existing` without rewriting. Partial, contradictory, or
orphan state is an integrity failure. Rescans create new observations even when
source or evidence hashes match.

Assembly groups by exact issuance ID, enumerates every authoritative page in
issuance order, and retains missing slots. Multiple observations for one page
become duplicate candidates without an automatic winner. Existing selections,
needs-rescan/excluded state, evidence roles, and evidence states are preserved.
The only additional PDS2 evidence module-detail accepted for teacher state is
`quillan_before_page_exclusion`, with exact `evidence_role` and
`evidence_state` keys from the existing vocabularies. Assembly compares the
immutable observation projection and retains this reserved state instead of
reconstructing the whole evidence object.

One canonical digital manifest represents exactly one issuance. Mixed
issuances, a different existing issuance, or an existing plain-paper manifest
are conflicts. Matching manifests merge idempotently, increment assembly
revision only on semantic change, and use a same-directory lock plus
revision-guarded atomic replacement.

Assembly failures use a closed vocabulary: `observation_invalid`,
`observation_missing_evidence`, `observation_evidence_hash_mismatch`,
`issuance_not_found`, `issuance_invalid`, `issuance_not_issued`,
`unexpected_page`, `identity_conflict`, `route_conflict`,
`source_page_conflict`, `mixed_issuances`,
`existing_manifest_issuance_conflict`, `existing_plain_paper_submission`,
`existing_manifest_invalid`, `manifest_concurrency_conflict`,
`manifest_write_failed`, and batch-only `unexpected_error`. Unexpected
programming failures propagate from the single-student boundary and retain
their original exception object when a scan batch must continue.

Issue #340 owns scan-review resolution and wider review-service failure
migration. Issue #341 owns broader CLI, menu, dashboard, and remaining path
migration.
