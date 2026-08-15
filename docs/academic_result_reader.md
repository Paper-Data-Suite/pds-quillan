# Quillan Academic Result Reader and Authorized Artifacts

## Purpose

Quillan exposes two deliberately separate consumer-neutral integration boundaries:

```text
quillan.academic_result_reader
quillan.academic_result_artifacts
```

The reader interprets already-authorized immutable
`quillan_academic_result_manifest_v1` bytes and models. It performs no workspace,
filesystem, Core registry/catalog, publication-selection, or authorization I/O.

The artifact module performs the separate operation of resolving exact Quillan-owned
student-work or feedback artifacts after an external application/deployment
authorization decision.

The split is normative:

```text
Core-authorized and Core-verified immutable manifest bytes
-> pure Quillan manifest reader
-> exact producer-native models
-> consumer policy

separately authorized artifact request
-> external authorization gate
-> exact manifest-bound native-source verification
-> exact producer artifact
```

Neither boundary calculates Grades, proficiency/mastery, or portfolio policy.

## Ownership

Quillan owns Academic Result Manifest v1 parsing and validation; native
assignment/submission/review semantics; exact student, source, review-unit,
observation, rating, feedback, and selected-PDS2 evidence-reference lookup; native
source verification needed for artifact access; selected-evidence eligibility;
feedback-export relationship checks; and the producer privacy floor.

Core owns Publication Records and Withdrawals, Academic Work Registration,
publication-series state, publication selection, manifest path containment and
Publication Record SHA-256 verification, compatibility metadata, and the rebuildable
academic catalog.

The application/deployment owns actor identity, purpose, manifest/result
authorization, artifact authorization, recipient/disclosure authorization, filesystem
permissions, and deployment trust.

Meridian owns grading/reporting policy after authorized producer parsing. Vitrine owns
portfolio Candidate/Selection/Profile/disclosure policy after authorized producer
parsing. Quillan imports neither consumer.

## Pure manifest reader

Stable imports come from `quillan.academic_result_reader`.

`read_academic_result_manifest(value)` accepts only exact immutable `bytes`. It
delegates decoding and whole-manifest validation to the authoritative
`quillan.academic_result_manifest` contract, canonicalizes the model with the
authoritative serializer, and requires byte-for-byte equality with the caller input.

Equivalent but noncanonical JSON fails closed, including alternate whitespace, key
order, missing final newline, and trailing whitespace. Core's Publication Record
digest remains a separate prior verification step; the reader does not replace Core
publication-envelope integrity.

`validate_academic_result_manifest(manifest)` accepts the exact immutable public model,
delegates to the authoritative validator, returns the same model, and performs no I/O.

Public reader failures are:

```text
QuillanAcademicResultReaderError
  QuillanAcademicResultReaderValidationError
    QuillanAcademicResultReaderDecodeError
  QuillanAcademicResultReaderNotFoundError
```

Decode and not-found messages are bounded and do not echo manifest payloads or hidden
student content.

## Exact lookup semantics

The reader exposes exact producer-native lookup only:

```python
lookup_academic_result_student(...)
lookup_academic_result_source(...)
lookup_academic_result_review_unit(...)
lookup_academic_result_observation(...)
lookup_academic_result_overall_rating(...)
lookup_academic_result_standard_feedback(...)
lookup_academic_result_evidence_reference(...)
```

Source names are exactly `assignment`, `submission`, and `review`. Assignment lookup
takes no student ID; student sources require an exact represented student. These are
metadata lookups only and never open native records.

Review units resolve only by exact `unit_id`; observations only by exact
`observation_id`; overall ratings and standard feedback only by exact native
`standard_id`. Focus Standard IDs are bounded native text, not path-safe identifiers,
and are never normalized into another module's scale.

A present native minimum rating remains a real rating. An absent rating remains absent.
Non-applicable observations and applicable observations without evidence retain their
native null states and are never converted to numeric scores.

`PublishedText` remains exactly `absent`, `withheld`, or `included`. The reader cannot
recover withheld native text.

Evidence-reference lookup searches only selected PDS2 provenance already represented
in the manifest. It never derives a routed path, retained-source path, source filename,
candidate evidence, duplicate evidence, excluded evidence, or replacement history.

## Artifact kinds and authorization

Stable artifact imports come from `quillan.academic_result_artifacts`.

Supported kinds are closed:

```text
student_work
feedback_pdf
feedback_markdown
```

There is no arbitrary-path, generic-file, or generic-native-record API.

Artifact access requires an externally supplied authorization gate. Decision states are
exactly:

```text
allowed
denied
unresolved
```

The authorization request contains only bounded manifest-derived identity:

```text
work
record_set_id
record_set_revision
student_id
artifact_kind
purpose
```

It contains no artifact path.

Quillan calls the gate before canonicalizing or inspecting the workspace and before
checking source or artifact existence. `denied` and `unresolved` therefore cannot leak
whether a submission source, selected-evidence file, or feedback export exists.

Quillan defines no teacher/admin/student role matrix here. Authorization policy remains
deployment-owned.

## Historical source integrity

Artifact resolution is permitted only against the exact native source bytes bound into
the immutable manifest. For each required source Quillan derives the exact canonical
work descendant, requires agreement with the manifest source path, rejects link-like
path components, reads an ordinary regular file, checks exact SHA-256, validates the
existing native schema, and requires exact class/assignment/student identity.

Quillan does not reconstruct historical source bytes and does not use newer native
state under an older manifest. If the canonical native record changed after
publication, artifact resolution fails closed even though the immutable manifest and
Core Publication Record remain historically valid.

## Selected PDS2 student work

`student_work` is available only for `pds2_response_pages` results with represented
public selected-evidence provenance.

After authorization and exact `submission.json` verification, Quillan independently
requires:

```text
page.selected_evidence_id == evidence.evidence_id
evidence.evidence_role == selected
```

and exact agreement of:

```text
page_id
evidence_id
observation_id
route_id
issuance_id
generation_id
artifact_id
source_page_number
source_scan_id
source_sha256
routed_evidence_sha256
```

Only then may Quillan use the private native `routed_evidence_path`. The routed file
must remain inside the exact work root, contain no link-like path component, use a
supported image format, and hash exactly to public `routed_evidence_sha256`.

Returned artifacts preserve manifest evidence-reference order. Candidate, unselected
duplicate, excluded, unrelated replacement evidence, retained full scans,
`retained_source_path`, `source_filename`, QR/route payloads, and another student's
evidence are never returned.

For `plain_paper_manual`, student work is explicitly unavailable; no digital artifact
is fabricated.

## Feedback PDF and Markdown

Feedback reads are format-exact. PDF never falls back to Markdown and Markdown never
falls back to PDF.

After authorization Quillan requires the exact manifest-bound `review.json` source,
schema-2 validation, exact identity, existing metadata under the requested
`review.json.exports` field, the exact canonical feedback path, and:

```text
source_review_updated_at == review.updated_at
```

Artifact existence alone is insufficient.

Markdown-only export now records the existing schema-2
`exports.feedback_markdown` metadata, matching the persistence model already used by
PDF and companion Markdown export. This is a consistency fix, not a schema change.

The SHA-256 returned for feedback is the digest of the exact artifact bytes observed
and returned by that read. It is not the Core Publication Record manifest digest and
does not claim the derived feedback file was independently immutable since
publication.

Feedback reads do not regenerate artifacts and do not return `review.json`. Private
notes, unselected comments, withheld rationales, reusable-comment provenance, and
arbitrary module details remain outside the result.

## Authorized artifact result

`AuthorizedAcademicResultArtifact` is frozen and slotted and returns immutable bytes
plus bounded metadata:

```text
artifact_kind
work
record_set_revision
student_id
workspace-relative artifact path
media_type
sha256
byte_size
data
```

Student work may also carry the exact public `EvidenceReference`. Feedback may carry
safe `generated_at` and `source_review_updated_at` metadata. Absolute workspace paths
and private native source locators are not returned.

## Core-backed consumer sequence

```text
discover candidate publication through Core
-> reload canonical Core publication state
-> evaluate producer compatibility
-> establish manifest/result authorization
-> Core verifies exact manifest path and Publication Record SHA-256
-> pass exact immutable bytes to quillan.academic_result_reader
-> apply consumer-owned policy

if a producer artifact is separately required:
-> establish artifact authorization through deployment policy
-> call quillan.academic_result_artifacts
-> Quillan verifies exact historical native-source relationship
-> receive bounded immutable artifact bytes
```

Manifest authorization, feedback authorization, student-work authorization, and
underlying-source authorization remain distinct.

## Packaging and side effects

Both public modules ship in the Quillan wheel. Import and pure manifest reading create
no workspace, registry, catalog, publication, withdrawal, or Academic Work
Registration state. The artifact module performs no workspace/source/artifact I/O
until the request is valid and the external gate returns `allowed`.

There is no CLI or teacher-menu artifact reader. These modules are integration/library
boundaries for authorized consumers.

Issue #365 owns the complete clean-wheel producer-to-Core end-to-end acceptance flow.
Issue #366 owns final compatibility/release authorization.
