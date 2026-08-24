# Share Results with Meridian

## Purpose

`Share Results with Meridian` is Quillan's guided teacher workflow for taking one
already-selected class/assignment through the existing producer publication chain:

```text
managed Quillan assignment
-> explicit Core Academic Work Registration
-> immutable Quillan Academic Result Manifest
-> explicit Core Publication Record
-> authorized compatible Meridian discovery
```

The teacher-facing name describes the intended downstream use. Quillan does **not**
send a request to Meridian and does not depend on the Meridian package.

The supported dependency direction remains:

```text
Quillan
  -> producer-native state
  -> immutable producer manifest
  -> Core Academic Work / publication state

Meridian
  -> Core publication discovery
  -> authorization and exact manifest verification
  -> Quillan public reader
  -> Meridian evidence projection
```

A successful Quillan share therefore means:

```text
Published through Core and ready for authorized compatible Meridian discovery.
```

It does not prove that Meridian has already discovered, authorized, imported, or used
the publication.

## Routine entry point

The routine teacher path is:

```text
Review Student Work
-> selected class
-> selected assignment
-> Assignment Review Actions
-> S. Share Results with Meridian
```

The exact active `class_id` and `assignment_id` are passed into the workflow. The
teacher is not asked to select the same class or assignment again.

The advanced independent interfaces remain:

```text
Assignment Management
5. Academic Work Registration
6. Academic Result Manifests
7. Academic Result Publications
```

and the direct CLI namespaces remain:

```text
quillan academic-work ...
quillan manifest ...
quillan publication ...
```

There is no separate `share-results` CLI command.

## Read-only share status

`quillan.share_results` builds an ephemeral, assignment-scoped status projection from
existing canonical state. It does not persist a readiness record or create a Core
provider.

The status includes bounded metadata such as:

```text
assignment identity/title
current Academic Work Registration revision/intent/lifecycle
stale-registration-title flag
represented native-result count
producer manifest head revision/SHA-256
canonical Core publication head
head withdrawal state
current-selectable publication
catalog availability
ordinary next step
optional aggregate class-review context
```

It does not expose student identities, ratings, rationales, feedback text, private
notes, observations, evidence arrays, withdrawal reasons, or raw manifest JSON.

Read-only status does not create a missing academic catalog.

## Review-completion boundary

The focused class-review projection from issue #388 is advisory context only.

The workflow may show:

```text
Review completion: X / N
Needs work: Y
Attention required: Z
```

when canonical roster-based completion is available.

If it is unavailable, the workflow shows that condition and continues to use the
actual registration/manifest/publication contracts.

The following are deliberately **not equivalent**:

```text
review complete
feedback exported
manifest generated
publication authorized
Meridian ingestion
```

In particular, 100% #388 completion does not authorize publication, and incomplete
#388 completion does not independently block a manifest that the existing producer
contract accepts.

The manifest generator remains authoritative for determining which native Quillan
results are representable.

## Academic Work Registration

When no registration exists, the guided workflow requires the teacher to select:

```text
academic_intent
lifecycle
```

explicitly and previews the exact registration request.

The teacher must type:

```text
REGISTER
```

before the existing `register_quillan_academic_work(...)` service is called.

The workflow never infers academic intent or lifecycle from assignment title, writing
type, standards, review state, dates, ratings, or student results.

A `cancelled` registration cannot support a new publication. The routine share flow
offers an explicit update to an eligible lifecycle; it never silently reactivates a
cancelled registration.

### Stale title

If the current assignment title differs from the current Core registration title, the
condition is shown explicitly.

The teacher chooses either:

```text
Continue using this registration
Update registration before sharing
```

An update previews the exact request and requires typed:

```text
UPDATE
```

The update uses the exact observed current registration revision. A concurrent change
fails safely rather than silently retargeting the teacher's prior confirmation.

Continuing with an otherwise eligible historical registration is an explicit teacher
choice; the guided workflow does not rewrite it merely because the title is stale.

## Manifest generation

Once registration is eligible, the workflow uses the existing immutable manifest
generator.

Before generation it explains that generation may:

```text
byte-exactly reuse the existing producer head
or
create the immutable successor required by Quillan revision policy
```

and that generation alone does not publish through Core.

The teacher must type:

```text
GENERATE
```

The workflow then calls only:

```python
generate_academic_result_manifest(...)
```

Revision selection, exact replay, source validation, privacy projection, immutable
storage, source-stability checks, and partial-success behavior remain owned by the
existing manifest-generation contract.

The routine result is bounded to:

```text
disposition
revision reason
producer revision
represented-student count
workspace-relative manifest path
SHA-256
```

No raw academic content is printed.

## Publication planning

After generation/replay, the workflow rebuilds its status from canonical state.

The ordinary publication planner distinguishes:

```text
no producer head                   -> generate manifest
producer head + no Core series     -> first publication
later producer head + valid Core   -> ordinary supersession
producer head already Core head    -> already current
withdrawn Core head                -> advanced republication required
contradictory history              -> advanced inspection required
```

The canonical Core predecessor is never inferred from timestamp, producer revision,
publication ID ordering, directory order, or derived catalog ordering.

## First publication

Immediately before first publication, the workflow rebuilds the share status and
renders a bounded preview including:

```text
class
assignment
Academic Work Registration revision
academic intent
lifecycle
producer manifest revision
represented-student count
manifest SHA-256
Core publication head: none
```

The teacher must type:

```text
PUBLISH
```

After confirmation, the workflow reloads the same bounded canonical state again. If
the registration revision, producer head, manifest SHA-256, or Core-series state has
changed, no publication call is made.

When the preview still matches, Quillan calls only:

```python
publish_quillan_academic_results(...)
```

## Ordinary supersession

When a nonwithdrawn canonical Core head exists and a later current producer head is
ready, the preview includes the exact expected Core publication head ID.

The teacher must type:

```text
SUPERSEDE
```

After confirmation the workflow reloads state again. If the exact head or producer
state changed, no supersession call is made.

When the preview remains current, Quillan calls only:

```python
supersede_quillan_academic_results(
    ...,
    expected_current_publication_id=<fresh exact Core head>,
)
```

The underlying lifecycle service independently revalidates the exact canonical head
and rejects stale, branching, withdrawn, or otherwise invalid transitions.

## Already-current state

If the current producer head is already represented by the current valid Core
publication, the routine workflow performs no publication write.

It reports:

```text
Already published and current.
```

Exact replay therefore remains idempotent.

A later cancellation of the *current* Academic Work Registration does not
retroactively invalidate an already-existing historical publication that is still the
canonical current-selectable result. A genuinely new publication still requires a
current eligible registration.

## Withdrawn head

A withdrawn canonical Core head is never ordinary-superseded or silently reactivated.

The guided workflow reports that advanced republication is required and leaves
`republish-after-withdrawal` to the existing Academic Result Publications workflow.

The routine share flow does not perform:

```text
withdrawal
republish-after-withdrawal
manual catalog rebuild
historical publication repair
```

## Final verification

The publication lifecycle service already verifies canonical Core state, exact
manifest binding, the historical registration revision, producer-profile
compatibility, and full catalog reconciliation.

After that service returns, the guided workflow performs one additional bounded status
reload and requires the resulting publication to be:

```text
canonical series head
not withdrawn
current selectable
present in a verified reconciled catalog
```

The final message is:

```text
Status: published through Core
...
Meridian handoff:
Ready for authorized compatible Meridian discovery.
```

It never claims that Meridian has already imported or graded the result.

## Multi-step durability and cancellation

The guided workflow is not one cross-system transaction.

Each explicitly confirmed step retains its existing durability semantics:

```text
REGISTER succeeds; later GENERATE is canceled
=> registration remains

GENERATE creates/replays a manifest; later PUBLISH is canceled
=> registration and manifest remain

PUBLISH/SUPERSEDE succeeds
=> canonical publication remains even if a later UI step cannot render
```

No earlier legitimate history is deleted or compensated merely because the teacher
stops at a later stage.

## Partial success

Academic Work Registration, manifest generation, and publication each retain their
existing partial-success models.

If a step reports that durable state may already exist, the guided workflow stops the
linear mutation sequence and tells the teacher to inspect canonical state before any
retry.

It does not blindly repeat the write.

For publication partial success, bounded output may include:

```text
operation
canonical-state confidence
publication ID
producer revision
manifest path/SHA-256
catalog rebuild/replacement/verification state
recommended next action
```

Sensitive raw exception payloads and student academic content are not printed.

## Artifact authorization boundary

Core publication is not authorization to expose all Quillan artifacts.

Successful sharing does not automatically grant access to:

```text
feedback PDF
feedback Markdown
student writing
PDS2 source pages
retained scans
routed evidence
underlying private source files
```

The existing public Academic Result reader and separately authorized artifact
resolution remain distinct boundaries.

## No educational inference

`Share Results with Meridian` does not:

```text
calculate proficiency
calculate percentages
create a Grade
select attempts
infer academic intent
infer lifecycle
infer ratings
infer applicability
infer review completion
generate feedback
change review state
rank students
prioritize students
```

It publishes the existing teacher-authored producer result contract; downstream
Meridian policy remains Meridian-owned.

## Dependency and compatibility boundary

Quillan does not import or call Meridian.

The Quillan package remains compatible with its existing Core dependency range:

```text
pds-core>=0.6,<0.7
```

This workflow does not change:

```text
quillan_academic_work_v1
quillan_academic_result_manifest_v1
academic_results
standards_ratings
```

Exact released-version qualification between a future Quillan v0.10.0 package and
Meridian remains release/installed acceptance work rather than a claim made by this
menu.

## Related contracts

- [Academic Work Registration](academic_work_registration.md)
- [Academic Result Manifest Generation](academic_result_manifest_generation.md)
- [Academic Result Publication Lifecycle](academic_result_publication.md)
- [Class Review Progress](class_review_completion.md)
- [CLI Contract](cli_contract.md)
