# Quillan Publication Revision Policy

## Purpose and ownership

`quillan_publication_revision_v1` is Quillan's producer-owned policy for immutable
Academic Result manifest history. It defines stable record-set identity, revision
allocation, exact replay, correction history, historical reversion, supersession,
withdrawal boundaries, and explicit republication after withdrawal.

It governs `quillan_academic_result_manifest_v1` without changing that manifest's
serialized shape and without changing `quillan_publication_projection_v1`.

The central rule is:

```text
mutable current Quillan native state
-> immutable manifest revision
-> immutable Core Publication Record
-> later correction
-> new immutable manifest revision
-> explicit Core supersession
```

Current `assignment.json`, `submission.json`, and `review.json` are mutable producer
records. Published manifest history is not.

## Policy identity

Stable policy version:

```text
quillan_publication_revision_v1
```

Production Academic Result record-set ID:

```text
academic_results
```

The production series identity is the complete Quillan work identity plus:

```text
publication_kind = academic_result_set
record_set_id = academic_results
```

The record-set ID is stable across ordinary review progress, corrections,
withdrawal, and later republication.

The following remain independent concepts:

```text
assignment schema version
submission schema version
review schema version
review_state
manifest contract version
publication projection policy version
publication revision policy version
record-set revision
Core Academic Work Registration revision
Core Publication Record identity
Core publication-series head
Quillan package version
```

## Pure policy boundary

`quillan.publication_revision_policy` is side-effect free. It compares already-valid
manifest models and returns immutable planning values.

It performs no workspace, filesystem, hashing, registry, catalog, publication,
withdrawal, authorization, grading, proficiency, or portfolio work. The separate
[Academic Result Manifest Generation](academic_result_manifest_generation.md)
implementation applies this pure policy to durable producer filesystem history.
Core-backed lifecycle orchestration is implemented separately in
[Academic Result Publication Lifecycle](academic_result_publication.md).

## Revision allocation

The first production manifest revision is `1`.

Normal allocation is:

```text
highest already allocated producer revision + 1
```

Allocated gaps remain consumed. A revision number is not freed by nonpublication,
withdrawal, a missing historical manifest, or later cleanup.

Explicit transition validation permits a greater noncontiguous revision. Revision
order never comes from timestamps, filenames, directory order, or Core catalog state.

## Publication-content equality

Two valid manifests have the same publication content only when every serialized
value matches except:

```text
generated_at
record_set.revision
```

Everything else remains significant, including work and record-set identity, exact
source paths/versions/digests, assignment context, represented students, submission
state/provenance, review state, minimum-requirement outcome, observations, ratings,
feedback projection, `PublishedText` dispositions, comments, and selected evidence
references.

The comparison is deterministic, in-memory, and nonmutating.

## Exact native source lineage

Exact assignment, submission, and review source snapshots are publication content.
A changed source path, contract version, or SHA-256 prevents exact replay even when
visible academic values otherwise appear unchanged.

This preserves the meaning:

```text
these exact native source bytes produced this immutable projection
```

A privacy-sensitive source-only change uses the bounded reason:

```text
native_source_changed
```

The policy does not reveal whether a private note, hidden comment, or another
nonpublished field caused that source-byte change.

Native changes do not automatically publish anything. They affect the decision only
when an explicit manifest-generation operation occurs.

## Revision dispositions

The policy returns one of:

```text
reuse_existing
create_initial
create_successor
```

and one bounded reason:

```text
exact_replay
initial_publication
native_source_changed
publication_projection_changed
historical_reversion
republication_after_withdrawal
```

Reasons are producer planning metadata. They are not added to Academic Result
Manifest v1.

## Exact replay

If complete publication content matches the current producer head, reuse the existing
manifest revision and exact bytes.

Replay preserves:

```text
record_set_id
record_set revision
generated_at
canonical manifest bytes
manifest SHA-256
```

Replay does not allocate another revision or create a new authoritative timestamp.
A withdrawn publication is not reactivated through replay.

## Changes requiring a successor

A complete successor snapshot is required when publication content changes.
Representative cases include:

- assignment source or assignment snapshot changes;
- submission source, state, entry method, or selected provenance changes;
- review source or review-state changes;
- minimum-requirement outcome changes;
- overall rating, rationale, or feedback-inclusion changes;
- observation or feedback-composition changes;
- selected evidence changes;
- represented student additions or removals;
- privacy-safe serialized projection changes.

A successor is a complete record-set snapshot, never a delta containing only the
changed rating or student.

Package versions, report regeneration, catalog rebuilds, profile rediscovery, and
consumer grading/proficiency/portfolio policy do not by themselves create producer
manifest revisions.

## Quillan correction semantics

Quillan does not add ScoreForm-style attempt semantics to mutable teacher review.
Current review workflows may replace an overall Focus Standard rating, rationale,
feedback selection, observation, or review state in `review.json`.

When a published value is corrected:

1. preserve the historical manifest and Publication Record;
2. update current native Quillan state through the existing review workflow;
3. create a new complete immutable manifest revision;
4. later explicitly supersede the current Core publication head.

No native `rating_attempt`, `rating_revision_id`, `corrected_rating_id`, or similar
history field is introduced.

## Corrected ratings and missingness

A historical overall rating is distinguished by its work, record-set revision,
student, and Focus Standard context.

Example:

```text
revision 1: student_alpha / standard_x / rating 2
revision 2: student_alpha / standard_x / rating 3
```

Revision 1 continues to preserve rating `2`; revision 2 preserves the corrected
rating `3`.

If a later valid review removes an overall rating, the successor represents current
absence. Absence is not zero, the assignment scale minimum,
`returned_without_full_review`, or an inferred Grade state.

Each historical manifest carries the assignment-local scale that interprets its own
ratings. A later scale-label or scale-definition correction never retroactively
changes older rating meaning.

## Review state and minimum requirements

Review states and minimum-requirement outcomes are explicit native states, not
performance levels.

A valid current change may therefore require a successor without implying stronger or
weaker performance. In particular, `exported` is not academically stronger than
`ratings_complete`, and `returned_without_full_review` is not a low numeric rating.

## Selected-evidence corrections

When authoritative selected PDS2 evidence changes, the successor records the new
bounded selected provenance. Historical manifests retain the provenance that was
authoritative for their own revisions.

Old manifests must not be rewritten to current evidence and must not fall back to
candidate, duplicate, replacement, or excluded evidence.

## Historical reversion

If current publication content returns exactly to an older historical state while the
current head differs, allocate a new greater revision.

```text
revision 1 = A
revision 2 = B
revision 3 = A
```

Do not reuse revision 1 or restore its Publication Record as current. The full
`A -> B -> A` history remains explicit.

## Same logical revision means one immutable state

The identity:

```text
work
+ academic_result_set
+ academic_results
+ record_set_revision
```

must identify exactly one immutable manifest state. Explicit transition validation
rejects same-revision reuse and backwards revision movement. Different work or
record-set identity is a different series, not a successor.

## Producer history and Core history are separate

Producer manifest allocation and Core publication are independent histories. A
manifest may exist without publication, and Core may still point to an older
published producer revision.

The pure revision policy does not inspect Core state. The manifest
generation/storage layer owns durable producer manifest history. The
[Academic Result Publication Lifecycle](academic_result_publication.md) reloads
canonical Core state and reconciles publication.

## Supersession

Ordinary valid corrections and newer result snapshots use Core supersession when
published.

The later Core workflow must retain the same work, publication kind, and record-set
ID; use a greater producer revision; reload the exact canonical Core head; and
supersede that expected head explicitly.

Do not infer the predecessor from revision magnitude, timestamp, filename, or catalog
ordering. Supersession preserves the predecessor as historical; it does not withdraw
it.

## Withdrawal

Withdrawal is stronger than ordinary correction. It is appropriate when one exact
published revision should no longer be newly relied upon because of a serious
privacy, authorization, identity, selected-evidence, or integrity defect.

Routine rating, rationale, feedback, review-state, or assignment corrections normally
use successor publication rather than withdrawal.

Withdrawal is publication-level, not rating-level. Quillan does not invent
`withdraw_rating`, `withdraw_observation`, or similar Core lifecycle concepts.

Withdrawal preserves the immutable Publication Record, producer manifest, native
records, supersession history, and prior consumer provenance. It is not deletion,
erasure, historical rewriting, or predecessor restoration. Withdrawal reasons must
remain privacy-minimized.

## Republishing after withdrawal

Exact replay does not restore a withdrawn publication. When publication intentionally
resumes after withdrawal, create a new greater producer revision and later supersede
the withdrawn Core head.

This is permitted even when current native source bytes are unchanged from the
withdrawn revision. The pure planner receives an explicit Boolean
`republish_after_withdrawal`; it never inspects Core withdrawal state itself and never
infers republication automatically.

## Missing or altered historical manifests

If trusted exact historical bytes are available and reproduce the recorded digest,
restoring those exact bytes is recovery, not a new revision.

If exact historical bytes are unavailable, do not reconstruct different bytes under
the old revision. The later lifecycle workflow may withdraw the unverifiable
publication and publish a new greater revision from current authoritative native
state.

A missing or corrupt derived Core catalog does not create a producer revision.

## Historical native-source drift

After current native records are corrected, an older manifest's recorded source digest
may no longer match the current file at the same path. That is expected historical
drift and never authorizes rewriting the old manifest.

A future reader must not silently substitute current native bytes when a historical
manifest records a different digest. Historical native-file archival is outside this
policy.

## Privacy-policy evolution

A future privacy-policy change never rewrites historical manifests.

If current serialized projection content changes, create a successor. If already
published bytes are no longer safe for continued selection, withdraw those exact
Publication Records explicitly.

A policy implementation/version change with identical publication content does not by
itself require another record-set revision. An incompatible semantic change requires
an appropriate manifest-contract decision rather than disguising it as an ordinary
record-set revision.

## Decision matrix

| Change | New revision? | Later Core action | Rule |
| --- | --- | --- | --- |
| exact replay | no | reuse existing | preserve exact bytes |
| only candidate `generated_at`/revision differs | no | none | non-content fields |
| assignment source changes | yes | supersede | complete snapshot |
| submission source changes | yes | supersede | exact source lineage |
| review source changes | yes | supersede | includes corrections |
| rating corrected | yes | supersede | old rating stays historical |
| rating removed | yes | supersede | missing is not low |
| feedback projection changes | yes | supersede | never rewrite old projection |
| selected evidence changes | yes | supersede | old provenance stays historical |
| represented students change | yes | supersede | complete result-set snapshot |
| state returns to older content | yes | supersede current head | new greater revision |
| ordinary newer publication | yes | supersede | do not withdraw predecessor |
| exact publication unsafe | context | withdraw exact publication | stronger lifecycle action |
| unchanged state republished after withdrawal | yes | supersede withdrawn head | explicit only |
| Core catalog rebuild | no | none | derived state |
| consumer grading policy changes | no | none | consumer-owned |

## Worked correction sequence

```text
revision 1
  rating = 2

revision 2
  corrected rating = 3
  later publication supersedes revision 1 publication

revision 3
  feedback corrected
  later publication supersedes revision 2 publication

publication for revision 3 withdrawn
  revision 2 does not become current again

revision 4
  current native state intentionally republished
  later publication supersedes the withdrawn revision 3 publication
```

## Ownership and downstream boundaries

Quillan owns native educational semantics, Manifest v1, privacy projection, stable
record-set identity, producer revision rules, correction semantics, and later producer
orchestration.

Core owns Academic Work Registration, Publication Records, exact manifest path/digest
binding, supersession, withdrawal, canonical publication state, and the rebuildable
catalog.

Meridian owns authorized evidence selection, rating/proficiency mapping, Grades,
Academic Period membership, reporting, and downstream correction consequences.

Vitrine owns portfolio candidacy, selection, snapshot, and disclosure policy.

Milestone implementation status:

- #359: Core 0.6 dependency upgrade — complete;
- #360: Academic Work Registration — complete;
- #361: source loading, hashing, immutable manifest generation/storage — complete;
- #362: producer compatibility profile — complete;
- #363: Core publication, supersession, withdrawal, republication, reconciliation — complete;
- #364: consumer-neutral reader and authorized source/artifact resolution;
- #365–#366: installed acceptance and release audit.

No consumer policy belongs in this revision module.

## Academic Work Registration revision boundary

Core Academic Work Registration revision is independent of Quillan's producer
record-set revision. Updating registration metadata neither allocates a manifest
revision nor rewrites an immutable manifest. Later publication workflow #363
must preserve the exact registration revision used by each Publication Record.
See [Academic Work Registration](academic_work_registration.md).
