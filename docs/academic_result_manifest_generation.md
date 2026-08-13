# Quillan Academic Result Manifest Generation

## Purpose

Quillan explicitly generates immutable producer-owned Academic Result Manifest
revisions from one existing canonical managed assignment and its represented
native submission/review records.

The generated contract remains:

```text
record_type        = quillan_academic_result_manifest
contract_version   = quillan_academic_result_manifest_v1
producer_module_id = quillan
record_set_id      = academic_results
```

Generation creates producer bytes only. It does not register Academic Work,
create a Core Publication Record, publish or withdraw through Core, rebuild the
academic catalog, infer Academic Period membership, calculate proficiency or a
Grade, or select portfolio content.

## Canonical storage

Each immutable revision lives at:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/
  exports/
    manifests/
      academic_results/
        <revision>.json
```

Revision names are canonical positive decimal integers such as `1.json` and
`17.json`. Quillan creates no mutable `latest.json`, `current.json`, or similar
alias. The workspace-relative path is validated through Core's publication
manifest path contract.

## Native source population

Generation starts from canonical schema-2 `assignment.json`. Student population
is discovered only from direct canonical student directories under
`submissions/`; the roster does not create result entries.

A represented student requires both:

```text
submissions/<student_id>/submission.json  # schema 1
submissions/<student_id>/review.json      # schema 2
```

A valid submission with no review is omitted as no represented result. An orphan
review, malformed existing native record, unsafe/link-like path, or identity
mismatch fails closed. An absent student entry means only that the manifest does
not represent a Quillan result for that student; it is not zero, failure,
missing work, excused work, or an inferred review state.

Represented students are sorted deterministically by `student_id`.

## Exact-byte source lineage

Generation reuses Quillan's canonical record-context loaders. The exact bytes
that are parsed and validated are the bytes hashed into manifest source
snapshots.

Source paths are work-root relative:

```text
assignment.json
submissions/<student_id>/submission.json
submissions/<student_id>/review.json
```

SHA-256 is calculated over exact source bytes without JSON normalization,
line-ending normalization, decoding/re-encoding, or source rewriting.

Before a new durable manifest revision is installed, Quillan reloads the
generation context and requires the authoritative native source snapshot to
remain unchanged. Concurrent edits, disappearance, type changes, unsafe links,
or changed exact bytes fail the operation before the new manifest is claimed.

## Standards and native educational meaning

Generation loads the current Core standards library and validates the
assignment's exact `standards_profile_id` and ordered `focus_standard_ids`.
Unknown, duplicate, or out-of-profile standards fail closed.

The manifest preserves the assignment-local rating scale exactly, including
level order, integer values, labels, and descriptions. Every represented
observation or overall rating must use one exact native scale value.

Quillan does not map ratings to percentages, proficiency thresholds, mastery,
Meridian values, or Grades. Overall Focus Standard ratings remain explicit
teacher judgments and are never calculated from review-unit observations.
Missing ratings remain missing rather than becoming the lowest scale value.

Review state, submission state, minimum-requirement outcome, applicability,
evidence presence, and nullable ratings remain distinct native states.

## Plain paper and PDS2 provenance

`plain_paper_manual` preserves:

```text
expected_pages = null
digital_provenance = null
```

and never receives fabricated issuance, page, route, scan, observation, or
artifact identity.

For `pds2_response_pages`, generation publishes only authoritative selected
evidence permitted by `quillan_publication_projection_v1`. Each selected
reference must agree with its canonical response-page observation. Quillan
also validates retained-source provenance and independently recomputes the
retained source SHA-256, then verifies exact routed-evidence size and SHA-256.

Candidate, unselected replacement, excluded, and unselected duplicate evidence
do not enter the manifest. Source filenames, retained-source paths,
routed-evidence paths, QR payloads, and other private locators are excluded.

## Privacy projection

Generation applies the existing pure
`quillan_publication_projection_v1` functions for:

- minimum-requirement outcome teacher notes;
- review-unit observation rationales;
- overall-rating rationales;
- feedback comments; and
- selected PDS2 evidence.

`PublishedText` preserves `absent`, `withheld`, and `included` as different
states. Existing native text is not automatically publication-approved.

Always excluded from Manifest v1 are private notes, individual requirement-check
internals, roster display data, emails/guardian data, reusable-comment
provenance/live state, feedback-export metadata, arbitrary module details,
private locator paths, and diagnostic/debug content.

## Pure builder and workspace orchestration

`quillan.academic_result_manifest_generation` separates validated immutable
generation context from durable workspace orchestration.

Pure builders construct the existing Manifest v1 model and serialize only
through the canonical Manifest v1 serializer. They perform no registry,
publication, catalog, roster, or consumer-policy I/O.

Workspace orchestration owns native discovery, source/evidence validation,
history loading, revision planning, locking, immutable creation, replay, and
digest verification.

## Strict history and revision planning

Durable history is read only from the exact `academic_results` manifest
directory. Every revision must:

- use canonical `<positive integer>.json` naming;
- be an ordinary non-link file;
- contain exact canonical Manifest v1 bytes;
- identify the expected work and `academic_results` record set; and
- contain the same revision encoded by its filename.

Unexpected durable entries fail closed. Revision gaps remain allocated.
The highest durable revision is the producer predecessor.

Generation delegates all revision classification to
`quillan_publication_revision_v1`; it does not implement a second revision
policy.

The normal outcomes are:

```text
reuse_existing / exact_replay
create_initial / initial_publication
create_successor / native_source_changed
create_successor / publication_projection_changed
create_successor / historical_reversion
create_successor / republication_after_withdrawal
```

## Exact replay

When current publication content matches the producer head, generation returns
the predecessor's exact stored bytes, path, revision, original `generated_at`,
and SHA-256.

Replay does not rewrite or touch the predecessor, call the production clock,
create another revision, or allocate another revision number.

## Immutable creation and durability

One producer-owned lock covers the whole series operation:

```text
exports/manifests/academic_results/.write.lock
```

A pre-existing lock is a conflict and is never automatically deleted as stale.

New revisions are installed exclusively through Quillan's immutable
exclusive-record primitive. Manifest files never use the mutable
`revision_guarded_update()` path. Existing revisions are never overwritten,
repaired, deleted, renumbered, or normalized.

The allocation boundary is:

```text
failure before durable immutable creation -> revision not consumed
durable immutable creation               -> revision consumed
```

If failure occurs after a revision may be durable, Quillan preserves that file
and returns explicit partial-success metadata rather than rolling it back or
reusing the revision number.

The returned digest is lowercase SHA-256 over the exact stored canonical
manifest bytes, including the final newline.

## Read-only producer APIs

Producer-local read APIs list, load, and validate exact immutable revisions.
They do not repair history or create Core publication state.

The direct CLI is:

```powershell
quillan manifest list --class-id <class_id> --assignment-id <assignment_id>
quillan manifest show --class-id <class_id> --assignment-id <assignment_id> --revision <revision>
quillan manifest validate --class-id <class_id> --assignment-id <assignment_id> --revision <revision>
quillan manifest generate --class-id <class_id> --assignment-id <assignment_id>
```

Routine output is privacy-minimized to producer metadata such as revision,
timestamp, path, digest, and represented-student count. It does not print raw
manifest JSON, student IDs, ratings, rationales, comments, observations, or
evidence arrays.

The teacher menu exposes:

```text
Assignment Management -> Academic Result Manifests
```

and requires typed `GENERATE` confirmation before generation.

## Registration and publication boundaries

Academic Work Registration and manifest generation are independent explicit
operations. A manifest can exist without a registration, and a registration
change alone does not allocate a manifest revision.

Later #363 publication orchestration must independently reload canonical Core
state and bind the exact applicable Academic Work Registration revision, exact
manifest path, and exact manifest SHA-256 in the Core Publication Record.

Producer profile registration belongs to #362; Core publication/supersession/
withdrawal to #363; consumer-neutral authorized reading to #364; installed
end-to-end producer acceptance to #365; and final release audit/version work to
#366.

## Explicit-only generation boundary

Ordinary Quillan workflows do not generate manifests. This includes assignment
creation/editing, Academic Work Registration, printable response generation,
PDS2 routing/intake, observation persistence, submission assembly, plain-paper
submission creation, page management, requirement review, review observations,
overall ratings, feedback composition/export, reports, scan-review resolution,
imports, help/version display, and module-profile discovery.

Only the explicit manifest CLI/menu surfaces and later deliberately added typed
producer orchestration may call durable manifest generation.
