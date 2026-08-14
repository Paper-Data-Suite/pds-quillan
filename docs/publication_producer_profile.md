# Quillan Publication Producer Profile

Quillan exposes publication compatibility independently from PDS2 routing. Core
discovers the metadata-only provider through the installed entry point:

```text
paper_data_suite.publication_producers
    quillan = quillan.pds_publication:get_publication_producer_profile
```

`quillan.pds_publication:get_publication_producer_profile` is a zero-argument,
deterministic provider returning Core's immutable `PublicationProducerProfile`.
It contains no parser, reader, generator, publication callback, route handler,
registration callback, CLI callback, or menu callback.

## Exact compatibility declaration

| Field | Supported value |
|---|---|
| Module ID | `quillan` |
| Display name | `Quillan` |
| Core Publication Record schema | `1` |
| Academic Work producer contract | `quillan_academic_work_v1` |
| Publication kind | `academic_result_set` |
| Manifest contract | `quillan_academic_result_manifest_v1` |
| Capability | `standards_ratings` |
| Publication source-record contracts | none |
| Missing Publication Record source | allowed and required for compatibility |

`standards_ratings` means the manifest contract can preserve Quillan's native,
assignment-local standards ratings. It does not promise that every student or
standard has a rating and does not make ratings points, percentages, mastery,
Meridian proficiency, or Grades. Quillan does not advertise `points`,
`question_evidence`, `multiple_attempts`, `criterion_scores`, `moderated_scores`,
or any intervention capability. Selected PDS2 writing evidence, review units,
immutable revisions, and ordinal rating-scale values are not those contracts.

## Source identity boundaries

The Academic Work Registration identifies the canonical assignment as a
`quillan` / `assignment` / contract `2` source. A compatible Publication Record
has `source_record=None` because no single native `ModuleRecordRef` represents
the complete academic result set. The manifest separately binds exact snapshots
of assignment schema 2, submission schema 1, and review schema 2 records, plus
privacy-approved selected PDS2 provenance where applicable. These three layers
must not be collapsed or used to fabricate a result-set source record.

## Purity and responsibility boundaries

Import, direct invocation, installed discovery, and Core registry construction
read no workspace, environment setting, native record, registration, manifest,
Publication Record, withdrawal, or catalog and create no state. Discovery makes
compatibility metadata available; it is neither authorization nor proof that a
publication exists or that a consumer may read it.

Routing remains independently discoverable through `paper_data_suite.modules`.
Its `ModuleProfile` owns PDS2 schemas, dispatch status, the route handler, and the
registration validator; none appears in the publication profile.

Publication Record creation, supersession, withdrawal, republication, and
catalog reconciliation are implemented separately in
[Academic Result Publication Lifecycle](academic_result_publication.md). The
metadata-only producer profile performs none of those operations. Issue #364 owns
the consumer-neutral authorized reader. Meridian owns proficiency and Grade policy;
Vitrine owns Candidate, Selection, Snapshot, and portfolio policy.

Core's package version, Publication Record schema, routing contract, registration
schema, Quillan producer contract, manifest contract, and package version are
independent version axes. The Core dataclass is not a serialized Quillan profile
schema and Quillan defines no profile revision or compatibility schema.
