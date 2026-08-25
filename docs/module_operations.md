# Quillan Module Operations Provider

Quillan exposes one Core module-operations provider for bounded,
privacy-minimal teacher-attention summaries and contextual readiness.

This provider is an interoperability surface for neutral consumers such as
Paper Data Suite. It is not a teacher-facing Quillan dashboard, a telemetry
system, or a new source of authoritative workflow state.

## Core compatibility

The provider requires the module-operations API introduced by PDS Core 0.6.2.

Quillan therefore declares:

```text
pds-core>=0.6.2,<0.7
```

The provider uses:

```text
entry-point group: paper_data_suite.module_operations
entry-point name:  quillan
provider:          quillan.pds_operations:get_module_operations_profile
contract version:  1
```

The single v1 profile now exposes both operational capabilities:

```text
module_id = quillan
attention_provider = present
readiness_provider = present
```

Readiness extends the profile introduced by #391. It does not create another
provider family, launcher identity, routing profile, or Suite-specific API.

## Ownership

The authority boundary is:

```text
Quillan
  owns interpretation of Quillan persisted state
  owns Quillan attention codes and action identities
  owns the meaning of Quillan readiness
  owns Quillan readiness notice vocabulary

Core
  owns the neutral module-operations structures
  validates provider profiles and reports
  isolates provider failures
  owns installed provider discovery

Paper Data Suite
  may aggregate and present validated reports
  does not read Quillan private storage
  does not reinterpret Quillan review semantics
```

Quillan's routing, publication, and module-operations entry points use the same
module identity in separate Core provider families. Their presence is not proof
of suite launchability, application health, or one another's capability.

## Request semantics

Both operations callables accept only Core's neutral
`ModuleOperationsRequest`.

### Workspace

An explicit `workspace_root` is required.

No workspace:

```text
evaluation = unavailable
summaries = empty
```

A valid explicit workspace in which Quillan successfully finds no teacher
attention returns:

```text
evaluation = evaluated
summaries = empty
```

Those outcomes are deliberately different.

Attention and readiness evaluation never resolve an implicit workspace and never
create one.

For readiness, an explicit valid canonical workspace with no structural Quillan
blocker evaluates as:

```text
evaluation = evaluated
ready = true
```

A missing or otherwise safely uninspectable workspace evaluates as:

```text
evaluation = unavailable
ready = null
```

### Class filter

When `class_id` is supplied, Quillan evaluates only that exact class scope.
Any returned attention class/work context must match the requested class.

Readiness distinguishes an inspectable negative result from an unavailable
evaluation:

```text
existing structurally usable exact class
  evaluation = evaluated
  ready = true

safe missing or structurally invalid exact class
  evaluation = evaluated
  ready = false

unsafe or uninspectable requested class context
  evaluation = unavailable
  ready = null
```

No class-name matching, recent-context substitution, or fallback selection occurs.

### Active school year

The Core request may contain `active_school_year`, but Quillan does not invent a
new school-year state machine for module operations. The field is used only if an
existing Quillan/Core authority requires it; its mere presence or absence does not
change readiness.

## Readiness semantics

Readiness answers one narrow question:

> Can Quillan meaningfully operate in the supplied workspace/class context?

Quillan readiness is structural and contextual. It reuses canonical workspace,
class-roster, and Quillan work-path authorities rather than deriving state from
teacher workflow backlog.

The readiness provider uses the following stable notices:

```text
quillan_readiness_unavailable
  readiness could not be safely evaluated for the supplied context

quillan_class_not_ready
  the requested class is safely inspectable but missing or structurally invalid
```

Core retains the distinction among:

```text
module_operations.evaluated
module_operations.evaluation_unavailable
module_operations.provider_failed
module_operations.result_invalid
```

A provider report with `ready = false` is therefore not a failure to evaluate.
It means Quillan successfully inspected the requested context and determined that
the context is not currently structurally usable.

Ordinary teacher work does not make Quillan not ready. In particular, readiness
does not become false merely because attention exists for:

```text
scan review
post-dispatch recovery
submission assembly
minimum-requirement review
observations
ratings
feedback
feedback export
Share Results
publication/supersession state
```

A workspace may validly have:

```text
readiness.ready = true
attention.summaries != empty
```

Readiness also does not derive meaning from #390 diagnostic events, publication
state, grouping signals, risk/priority concepts, or recent-context selection.

### External prerequisites

Suite installation/release qualification owns external executable checks such as
`pdftoppm`.

Core v1 `ModuleOperationsRequest` does not identify a requested Quillan operation,
and Quillan has meaningful workflows that do not require PDF rasterization.
Therefore absence of `pdftoppm` is not a global Quillan `ready = false` condition.

## Attention sources

The provider derives current attention from existing Quillan read projections,
including:

```text
scan-review discovery
post-dispatch review/recovery discovery
deterministic assignment review work queue
class review completion/export projection
Share Results next-step projection
```

It does not reconstruct those state machines independently from raw JSON when
an existing Quillan service already owns the interpretation.

It also does not derive current attention from #390 diagnostic-event history.
Diagnostic events are retained troubleshooting history and may be absent,
pruned, or incomplete.

## Stable attention codes

Core v1 codes must be lowercase path-safe identifiers containing only letters,
numbers, underscores, and hyphens. Quillan therefore uses underscore-based
module-owned codes rather than dotted names.

Current codes are:

```text
quillan_scan_review
quillan_post_dispatch_review
quillan_needs_assembly
quillan_minimum_requirements_pending
quillan_observations_pending
quillan_ratings_pending
quillan_feedback_pending
quillan_feedback_export_pending
quillan_review_state_attention

quillan_results_registration_pending
quillan_results_registration_update
quillan_results_native_state_attention
quillan_results_manifest_pending
quillan_results_publication_pending
quillan_results_supersession_pending
quillan_results_republication_attention
quillan_results_publication_state_attention
```

Report-level notices currently use:

```text
quillan_attention_partial
quillan_attention_unavailable
```

These identifiers are Quillan-owned interoperability vocabulary. Core does not
assign their domain meaning.

## Count units

Attention is aggregated rather than emitted per student.

Count meaning is stable per code:

```text
quillan_scan_review
  unresolved/deferred scan-routing review items

quillan_post_dispatch_review
  unresolved post-dispatch review occurrences

quillan_needs_assembly
  affected review work items awaiting assembly

quillan_minimum_requirements_pending
quillan_observations_pending
quillan_ratings_pending
quillan_feedback_pending
quillan_feedback_export_pending
quillan_review_state_attention
  affected roster/review work items in that existing Quillan category

quillan_results_*
  affected assignments requiring that existing Share Results action/state
```

`no_submission` is not automatically converted into shared teacher attention.
`complete` is not an attention category.

## Result-sharing boundary

Result-sharing attention reuses the #389 Share Results next-step projection.

Routine publication-oriented actions such as registration, manifest generation,
first publication, and supersession are exposed as attention only when the
existing review projection proves the assignment's review is complete.

Publication-integrity states such as withdrawn/advanced republication handling
or inconsistent publication state may require attention independently because
they describe already-existing publication state.

Attention never performs:

```text
Academic Work Registration
manifest generation
publication
supersession
withdrawal
republication
catalog reconciliation
```

Preserve:

```text
review completion != publication
attention != publication authorization
```

## Owner-routed actions

Every shared action is a Core `ModuleOwnerActionRef` with:

```text
module_id = quillan
action_id = stable opaque Quillan identifier
```

Current action identifiers are:

```text
open_scan_review
open_post_dispatch_review
open_review_queue
open_feedback_export
open_share_results
```

An action ID is not executable data. It is not a command, path, URL, import
target, serialized function, or context payload.

Class and assignment context belongs in permitted Core fields such as
`class_id` and `ModuleWorkRef`, not inside `action_id`.

Issue #391 does not add a generic action executor.

## Aggregation and determinism

For identical persisted state and request context, the provider returns the same
semantic ordering, codes, labels, counts, class/work context, actions, and
notices.

The order follows a fixed Quillan workflow-oriented definition order. It is not
an educational urgency ranking.

One shared summary aggregates matching private state. The provider does not emit
one summary per student and does not serialize the private work queue.

## Partial and unavailable evaluation

Quillan preserves useful unrelated summaries when a safely isolatable work scope
cannot be inspected. In that case it returns an evaluated report with bounded:

```text
quillan_attention_partial
```

notice.

When the requested scope itself cannot be inspected safely, Quillan returns:

```text
evaluation = unavailable
summaries = empty
```

with bounded:

```text
quillan_attention_unavailable
```

notice.

Unexpected programming failures are not flattened into unavailable or empty
results. They may propagate to Core's invocation boundary, where Core can
classify them as `module_operations.provider_failed`.

Likewise, invalid returned reports remain distinguishable through Core as
`module_operations.result_invalid`.

## Privacy

The shared report is deliberately smaller than Quillan's private records.

It does not expose:

```text
student names
student IDs
student writing
teacher feedback bodies
teacher private notes
Focus Standard rating bodies
rating rationales
minimum-requirement rationales
raw evidence
raw scans
source filenames
QR payload bodies
route payload bodies
absolute paths
tracebacks
diagnostic-event records
grouping-signal values
```

Private state may be inspected internally only when an existing Quillan domain
projection requires it. That does not authorize its inclusion in the shared
report.

The shared surface is limited to bounded code/label/count values, optional exact
class/work references, owner-routed actions, and bounded safe notices.

## Read-only guarantee

Attention and readiness evaluation are observational.

It must not:

```text
create or repair a workspace
write assignments/submissions/reviews
assemble submissions
create exports
update recent context
register Academic Work
generate manifests
publish or supersede results
emit diagnostic events merely because it was queried
create caches
perform network access
launch menus
execute owner actions
```

Deleting #390 diagnostic history does not alter attention or readiness meaning.
Readiness evaluation does not emit a diagnostic event merely because it was
queried.

## Installed-wheel qualification

Current development qualification builds a real Quillan wheel and sdist, checks their metadata/entry-point contracts, installs the wheel into a clean environment outside the source checkout, and independently exercises:

```text
application/full installed workflow
routing/publication producer lifecycle
module-operations provider diagnostics, attention invocation, and readiness invocation
installed `quillan = quillan.cli:main` launcher metadata
```

The reusable harness is:

```text
scripts/run_operations_wheel_acceptance.py
```

It accepts only authenticated Core 0.6.2 or 0.6.3 inputs. The active CI uses this built-artifact gate for the new minimum and current Core endpoints. Source-tree or editable-install success is not treated as proof that the installed operations entry point is packaged correctly.

## Launcher and mixed-intake interoperability

The operations profile is not launcher authority.

The installed Quillan distribution continues to own exactly:

```text
console script:
  quillan = quillan.cli:main
```

Paper Data Suite owns exact release compatibility, executable/PATH health,
launch orchestration, and teacher-facing remediation. Quillan does not import
the Suite and does not decide whether its installed version belongs to a
supported Suite release.

Unified mixed-module paper intake is likewise Suite-owned orchestration. Quillan
does not implement a cross-module intake coordinator.

The existing Core routing contract is sufficient for isolation:

```text
mixed physical batch
  -> Core selects the profile by locator.module_id
  -> Core resolves that module's canonical registration
  -> Quillan receives only module_id = quillan routes
  -> foreign/unsupported routes remain foreign failures
```

Quillan's independent routing profile remains:

```text
paper_data_suite.modules
  quillan = quillan.pds_module:get_module_profile

Core routing contract = 1
QR schema = PDS2
route-registration schema = 1
dispatchable route status = active
```

Synthetic mixed-routing acceptance proves that a foreign route is never
fallback-routed to Quillan, including when the foreign module is absent.

## Relationship to other Quillan/Core surfaces

```text
#390 diagnostics
  bounded local troubleshooting event history

#391 attention
  current privacy-minimal teacher-attention projection

#392 readiness
  whether Quillan can meaningfully operate for supplied workspace/class context

paper_data_suite.modules
  routing provider contract

paper_data_suite.publication_producers
  publication compatibility contract
```

These are deliberately independent.

Attention is not readiness. Readiness is not launchability, Suite release
qualification, routing ownership, publication authorization, educational risk,
urgency, or grouping-signal meaning.
