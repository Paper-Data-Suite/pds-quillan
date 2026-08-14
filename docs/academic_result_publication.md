# Quillan Academic Result Publication Lifecycle

## Purpose

Quillan publishes immutable producer-owned Academic Result Manifest revisions through
PDS Core's canonical publication services.

Publication is explicit. Manifest generation alone does not make a result discoverable
through the Core academic catalog, and ordinary Quillan assignment, scan, review,
feedback, or report workflows never publish implicitly.

The exact production contract is:

```text
module_id                 = quillan
publication_kind          = academic_result_set
record_set_id             = academic_results
manifest_contract_version = quillan_academic_result_manifest_v1
capabilities              = standards_ratings
source_record             = None
```

Core owns Publication Record identity, timestamps, canonical registry storage,
supersession, Publication Withdrawals, and the disposable academic catalog. Quillan
owns producer manifest selection, producer revision policy, explicit teacher intent,
and post-service reconciliation.

## Canonical write boundary

Quillan creates no Publication Record IDs and writes no Core publication JSON or
SQLite rows directly. Canonical writes go only through:

```text
publish_manifest_revision(...)
supersede_manifest_revision(...)
withdraw_publication(...)
```

Catalog maintenance uses only:

```text
rebuild_academic_catalog(...)
```

The catalog is derived state. Canonical Publication Records, Publication Withdrawals,
Academic Work Registration revisions, and immutable producer manifests remain the
authorities.

`quillan.pds_publication` remains metadata-only. It contains no publication,
supersession, withdrawal, catalog, CLI, menu, reader, or authorization callback.

## Producer head selection

Initial publication and ordinary supersession require the caller-selected manifest
revision to be the current Quillan producer head.

These operations do not generate an ordinary manifest revision automatically. The
teacher first uses the explicit manifest workflow, then explicitly publishes that
immutable revision.

The first Core publication may begin above producer revision 1. For example, if
producer revisions 1, 2, and 3 exist but none has been published, revision 3 may be
the first Core publication. Revisions 1 and 2 remain producer-only history.

## Academic Work Registration binding

Every newly created academic Publication Record binds the exact current,
non-cancelled Core Academic Work Registration revision for the work.

Quillan does not create or update registration as part of publication. The existing
registration must use:

```text
producer_contract_version = quillan_academic_work_v1
work_kind                  = assignment
source record:
  module_id        = quillan
  record_kind      = assignment
  record_id        = <assignment_id>
  contract_version = 2
```

Registration revision and producer record-set revision are independent identities.

### Replay preserves historical registration

Exact replay never substitutes a newer registration revision.

If a logical producer revision already has a canonical Core Publication Record,
Quillan reloads the exact registration revision already referenced by that record and
uses it for replay reconciliation. This preserves the original publication identity,
publication timestamp, and historical registration binding even when current
registration metadata has since changed or the current registration is later
cancelled.

A later genuinely new publication binds the registration that is current at the time
of that new publication.

## Initial publication

The direct API is:

```python
publish_quillan_academic_results(
    workspace_root,
    class_id,
    assignment_id,
    *,
    manifest_revision=<producer head revision>,
)
```

For a new publication series, Quillan requires an exact current eligible registration
and asks Core to create the first Publication Record.

For exact replay, Quillan requires the existing logical revision to match the selected
producer bytes and publication metadata exactly. Replay returns Core's existing
Publication Record and any existing withdrawal. It does not allocate a new publication
identity or reactivate a withdrawn publication.

If the Core series is already nonempty and the selected logical revision does not
already exist, the initial-publication workflow fails closed and requires explicit
supersession.

## Canonical Core head

Quillan loads the complete exact Core series for:

```text
work
+ academic_result_set
+ academic_results
```

and derives the unique canonical head from `supersedes_publication_id`
relationships.

The predecessor is never inferred from:

- highest producer revision;
- newest timestamp;
- publication ID;
- filename or directory order;
- derived catalog ordering; or
- current-selectable state alone.

A withdrawn head remains the canonical supersession-chain head.

## Ordinary supersession

The direct API is:

```python
supersede_quillan_academic_results(
    workspace_root,
    class_id,
    assignment_id,
    *,
    manifest_revision=<producer head revision>,
    expected_current_publication_id=<exact Core head>,
)
```

A new successor requires:

- the caller's expected Publication Record to be the exact canonical Core head;
- the selected producer revision to be the Quillan producer head;
- the successor producer revision to be greater than the predecessor revision;
- the exact predecessor producer manifest to remain available and valid;
- the transition to satisfy `quillan_publication_revision_v1`;
- an exact current non-cancelled Academic Work Registration; and
- the Core supersession service to accept the same expected predecessor.

Ordinary supersession preserves the predecessor. It does not withdraw it.

### Withdrawn-head guard

Quillan deliberately rejects a new ordinary supersession when the canonical head is
withdrawn. Intentional resumption must use the explicit
`republish-after-withdrawal` workflow.

Exact replay of an already-created successor remains idempotent and does not remove
any withdrawal.

## Withdrawal

The direct API is:

```python
withdraw_quillan_academic_result_publication(
    workspace_root,
    class_id,
    assignment_id,
    *,
    publication_id=<exact Publication Record>,
    reason=<operator-supplied reason>,
)
```

Any exact Publication Record in the selected Quillan series may be withdrawn,
including a historical predecessor. Withdrawal does not require the current Academic
Work Registration to remain active or non-cancelled.

Quillan attempts bounded manifest verification before withdrawal and records one
diagnostic state:

```text
verified
missing
digest_mismatch_or_unsafe
unreadable
```

A missing, damaged, unsafe, or unreadable historical manifest does not block
withdrawal. Core writes a separate immutable Publication Withdrawal; the producer
manifest, native Quillan records, Publication Record, and supersession history are not
rewritten.

The operator-supplied withdrawal reason is accepted by Core but is not echoed in
routine CLI or menu output.

Withdrawing the series head does not restore its predecessor. The withdrawn
Publication Record remains the canonical head while current-selectable state becomes
empty. Withdrawing a historical predecessor does not disturb a later head.

Repeating the same publication/reason pair is an exact replay. A different reason for
an already-withdrawn publication is a conflict.

## Explicit republication after withdrawal

The direct API is:

```python
republish_quillan_academic_results_after_withdrawal(
    workspace_root,
    class_id,
    assignment_id,
    *,
    expected_withdrawn_head_publication_id=<exact withdrawn predecessor>,
)
```

Intentional resumption requires an exact withdrawn canonical predecessor and its exact
producer manifest.

If a greater producer head was already durably created by an earlier failed
republication attempt but Core publication was not confirmed, Quillan reuses that
producer revision. It does not allocate another revision merely because the caller is
retrying.

Otherwise Quillan explicitly calls manifest generation with
`republish_after_withdrawal=True`, which allocates a greater producer revision even
when current native content is unchanged from the withdrawn revision.

The new Core Publication Record supersedes the withdrawn predecessor. The predecessor
remains immutable and withdrawn.

If Core already durably created the intended successor but later verification or
catalog reconciliation failed, retry may reconcile that exact successor while the
caller continues to name the original withdrawn predecessor. Quillan accepts this only
when the existing successor directly supersedes that predecessor and all intended
metadata and producer bytes match exactly.

A successor that was itself later withdrawn is never silently reactivated.

## Missing historical predecessor boundary

Withdrawal remains possible when historical manifest bytes are missing or damaged.

Ordinary supersession and republication fail closed when the exact predecessor
manifest needed to prove the producer transition is unavailable or invalid. Quillan
does not reconstruct different bytes under an old revision and does not reuse a
consumed producer revision number.

Broader destroyed-history recovery is outside this lifecycle contract.

## Post-service verification

Every successful or exact-replay publication write is followed by producer-side
verification:

1. reload the canonical Publication Record by ID;
2. reload any Publication Withdrawal;
3. compare canonical state with Core's service result;
4. reload and revalidate the complete Core series;
5. verify Core's exact manifest path and SHA-256 binding;
6. require the resolved manifest path to equal the selected stored producer path;
7. load the exact referenced Academic Work Registration revision;
8. validate Quillan registration identity and producer contract;
9. evaluate the Publication Record against the installed Quillan producer profile;
10. require compatibility with no compatibility codes; and
11. rebuild and reconcile the full Core academic catalog.

The same canonical-series checks apply after withdrawal.

## Catalog reconciliation

After every successful or replayed publication, supersession, republication, or
withdrawal operation, Quillan performs a full:

```text
rebuild_academic_catalog(workspace_root)
```

It never patches one SQLite row directly.

For the selected publication, Quillan requires exactly one rebuilt catalog row and
reconciles canonical metadata plus:

```text
is_series_head
is_withdrawn
withdrawn_at
is_current_selectable
```

A catalog failure after canonical Core state is durable is partial success. Quillan
does not roll back the canonical write.

Read-only `status`, `list`, and `show` do not create a missing catalog.

## Partial success and retry

The lifecycle distinguishes durable producer/Core state from derived-catalog
completion.

A partial-success result may report:

```text
operation
publication
withdrawal
producer manifest revision/path/SHA-256
canonical_state = uncertain | confirmed
catalog_rebuild_attempted
catalog_replacement_completed
catalog_verification_completed
withdrawal_manifest_verification
recommended_next_action
```

A Core `RegistryServicePartialSuccessError` maps to uncertain canonical state unless
later canonical reload proves otherwise.

If Core returned a service result and a later Quillan verification step fails,
canonical state is confirmed durable.

If full catalog replacement completes but exact row reconciliation fails, the partial
state records replacement as completed and verification as incomplete.

Retry is exact and idempotent. It must not allocate duplicate Publication Records or
additional producer revisions merely because a prior attempt reached durable state
before failing later qualification.

## Read-only status

The read-only series model distinguishes:

```text
work
producer revision history and producer head
canonical Core publications
Publication Withdrawals
canonical supersession-chain head
head withdrawal
current-selectable publication
catalog availability
catalog rows
```

A missing catalog is reported as unavailable and is not created by read-only status.

`load_quillan_publication(...)` loads one exact canonical Publication Record and
optional withdrawal after requiring that it belongs to the selected Quillan series.
It is publication metadata only; the consumer-neutral manifest/artifact reader belongs
to issue #364.

## Direct CLI

The scriptable lifecycle namespace is:

```powershell
quillan publication status --class-id <class_id> --assignment-id <assignment_id>
quillan publication list --class-id <class_id> --assignment-id <assignment_id>
quillan publication show --class-id <class_id> --assignment-id <assignment_id> --publication-id <publication_id>
quillan publication publish --class-id <class_id> --assignment-id <assignment_id> --revision <revision>
quillan publication supersede --class-id <class_id> --assignment-id <assignment_id> --revision <revision> --expected-current-publication-id <publication_id>
quillan publication republish-after-withdrawal --class-id <class_id> --assignment-id <assignment_id> --expected-current-publication-id <publication_id>
quillan publication withdraw --class-id <class_id> --assignment-id <assignment_id> --publication-id <publication_id> --reason <reason>
quillan publication rebuild-catalog
```

`publish` and `supersede` never generate an ordinary manifest revision. The caller
selects an existing immutable producer head.

`rebuild-catalog` is an explicit full Core catalog rebuild and does not publish,
supersede, withdraw, generate a manifest, or calculate a Grade.

Expected lifecycle errors return concise nonzero results without exposing raw Core
exception text.

## Teacher menu

The teacher-facing workflow is:

```text
Assignment Management -> Academic Result Publications
```

It provides:

```text
1. Refresh status
2. List publications
3. Show publication
4. Publish producer head
5. Supersede exact Core head
6. Republish after withdrawn head
7. Withdraw exact publication
8. Rebuild full Core catalog
9. Return
```

Publication assignment discovery does not require a roster. The assignment itself
must still be a valid canonical Quillan assignment.

Writes require the typed confirmations:

```text
PUBLISH
SUPERSEDE
REPUBLISH
WITHDRAW
REBUILD
```

Cancellation performs no write.

## Privacy-safe output

Routine publication CLI and menu output is limited to publication-management metadata,
including publication ID, producer revision, workspace-relative manifest path,
SHA-256, referenced registration revision, predecessor, withdrawal state/timestamp,
and catalog flags.

Routine output does not expose:

- student IDs;
- ratings or scale values;
- rationales;
- feedback text;
- private notes;
- observations or evidence arrays;
- retained/routed private paths;
- withdrawal reasons;
- absolute private paths; or
- raw Core exception dumps.

Publication management does not parse or display raw manifest academic content.

## Explicit-only and downstream boundaries

No ordinary Quillan workflow publishes, supersedes, republishes, withdraws, or
rebuilds the academic catalog automatically.

The metadata-only publication producer profile remains free of lifecycle callbacks.

This lifecycle does not implement:

- a public consumer manifest reader;
- arbitrary manifest-byte exposure;
- consumer authorization;
- Meridian adapter or Grade policy;
- Vitrine portfolio policy;
- Academic Period selection;
- proficiency calculation; or
- source-artifact authorization.

Issue #364 owns the consumer-neutral reader and authorized source/artifact-resolution
boundary. Issue #365 owns full installed end-to-end producer acceptance. Issue #366
owns release/version closeout.
