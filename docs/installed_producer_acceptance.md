# Installed Producer Acceptance

This acceptance is Quillan's authoritative clean-distribution proof for the
Core 0.6 academic-publication producer boundary. It runs the built Quillan wheel
noneditably with the exact released `pds_core-0.6.0-py3-none-any.whl` baseline
(SHA-256
`be28c061b38463ef59ebc328ed1aa443767fe7f2c626babb769c2d8e5932f308`)
in a fresh virtual environment outside the source checkout.

The proof has two deliberately separate layers. First,
`scripts/run_installed_acceptance.py --full-workflow` creates synthetic native
Quillan work through the production PDS2, submission, review, and feedback
workflows. Before handing off that workspace it proves those ordinary operations
created no Academic Work Registration, Publication Record, withdrawal, catalog,
or academic-registry lock. Then
`scripts/verify_installed_producer_acceptance.py` performs the explicit mutations.

## Lifecycle proved

The producer acceptance checks installed distribution versions, dependency
metadata, module origins, the exact publication-producer entry point, Core
profile discovery, and the absence of `PYTHONPATH` or sibling-product imports.
It consumes one managed synthetic assignment with a two-level native rating
scale, one reviewed PDS2 submission, one unreviewed submission, selected routed
evidence, PDF and Markdown feedback, and a private teacher note.

The explicit lifecycle then proves:

1. Quillan creates Academic Work Registration revision 1 through its public
   registration service and exact replay creates no new revision.
2. Quillan generates immutable Academic Result Manifest revision 1, independently
   verifies its bytes and SHA-256, and represents only reviewed native work.
3. The public reader resolves the exact assignment, submission, review, review
   unit, observation, native rating `2`, feedback dispositions, and bounded
   selected-evidence provenance without exposing the private note or retained/routed
   private paths.
4. Quillan publishes revision 1 through Core, exact replay preserves Core-owned
   identity and time, and an independent catalog query is used only for discovery.
5. The canonical Publication Record and its exact referenced registration are
   reloaded, the series and withdrawal state are checked, Core producer
   compatibility is evaluated, an acceptance-owned manifest-read authorization
   decision is established, and only then does Core verify the manifest path and
   digest. Only those verified bytes are passed to the Quillan reader.
6. A separate acceptance-owned authorization gate allows only the exact synthetic
   work, result set, revision, student, artifact kind, and purpose. Student-work,
   feedback PDF, and feedback Markdown bytes are independently hashed; a denied
   request raises the public authorization error.
7. A registration-only lifecycle update creates registration revision 2 while
   manifest generation replays revision 1 byte-for-byte and publication replay
   remains bound to registration revision 1.
8. The installed review CLI changes the native overall rating from `2` to the
   genuine minimum value `1`, and feedback is regenerated with overwrite through
   the production exporter.
9. Quillan creates immutable manifest revision 2 for the changed review source,
   and Core creates a new Publication Record that supersedes publication 1 and
   binds registration revision 2. Exact supersession replay remains idempotent;
   a contradictory expected-head request fails closed without creating a branch.
10. Independent rediscovery, canonical reload, compatibility evaluation, Core
    verification, exact public reading, and separately authorized current
    artifacts all succeed for revision 2.
11. Historical manifest revision 1 still verifies and reads rating `2` after the
    native correction. Its changed-source feedback fails closed: immutable
    manifest validity does not imply that mutable native state can still prove a
    historical derived artifact. Unchanged selected evidence remains governed by
    its exact manifest-bound source bytes.
12. The final Core head is withdrawn through the public lifecycle, exact replay
    returns the existing separate withdrawal, and the rebuilt catalog has no
    current selectable result while retaining the withdrawn head and historical
    predecessor.
13. Core's registry audit checks registrations, publications, manifests,
    contracts, catalog, and locks. Final byte checks cover both manifests, both
    Publication Records, the withdrawal, and both registration revisions, with no
    mutable manifest alias.

Catalog rows are disposable discovery projections. The canonical Publication
Record, exact referenced Academic Work Registration, withdrawal state, installed
producer profile, Core manifest verification, and explicit authorization are the
consumer preconditions. The acceptance does not parse a catalog row as a manifest
or treat compatibility as authorization.

## Privacy and scope

Routine output contains bounded stage names and pass/fail state only. It never
prints manifest bodies, native review JSON, feedback text, private notes, routed
evidence bytes, retained scans, or the withdrawal reason. All identities and
content are synthetic.

The lifecycle uses production Quillan and Core APIs. It contains no mocks,
monkeypatches, direct registry JSON writes, SQLite fixtures, source-checkout
imports, grading policy, proficiency calculation, Academic Period assignment,
or portfolio policy. Artifact availability remains distinct from downstream
eligibility and disclosure decisions.

## Release harness

`scripts/validate_release_candidate.ps1` runs the full producer lifecycle once
for the built wheel, after the ordinary installed workflow has proved the
no-implicit-academic-state boundary. The sdist retains its installed smoke without
duplicating the mutation-heavy PDS2 lifecycle. Both exact tested artifacts are
persisted only after installed validation, and release authorization remains
explicitly ungranted.

This completes #365's integration evidence. It does not change a production
contract, version Quillan as v0.9.0, create a tag, publish an artifact, or grant
release authority. #366 owns final compatibility, version, and release closeout.
