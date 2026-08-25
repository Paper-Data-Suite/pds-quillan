# Quillan Module Operations Provider

Quillan exposes a Core module-operations provider for bounded, privacy-minimal
teacher-attention summaries.

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

The profile is intentionally attention-only for issue #391:

```text
module_id = quillan
attention_provider = present
readiness_provider = absent
```

Issue #392 owns Quillan readiness and should extend this same profile rather
than creating another provider family.

## Ownership

The authority boundary is:

```text
Quillan
  owns interpretation of Quillan persisted state
  owns Quillan attention codes and action identities

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

The attention callable accepts only Core's neutral `ModuleOperationsRequest`.

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

Attention evaluation never resolves an implicit workspace and never creates one.

### Class filter

When `class_id` is supplied, Quillan evaluates only that exact class scope.
Any returned class or work context must match the requested class.

No class-name matching or fallback substitution occurs.

### Active school year

The Core request may contain `active_school_year`, but #391 does not invent a
new Quillan school-year state machine. The field is used only if an existing
Quillan/Core authority requires it.

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

Attention evaluation is observational.

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

Deleting #390 diagnostic history does not alter attention meaning.

## Installed-wheel qualification

Current development qualification builds a real Quillan wheel and sdist, checks their metadata/entry-point contracts, installs the wheel into a clean environment outside the source checkout, and independently exercises:

```text
application/full installed workflow
routing/publication producer lifecycle
module-operations provider diagnostics and attention invocation
```

The reusable harness is:

```text
scripts/run_operations_wheel_acceptance.py
```

It accepts only authenticated Core 0.6.2 or 0.6.3 inputs. The active CI uses this built-artifact gate for the new minimum and current Core endpoints. Source-tree or editable-install success is not treated as proof that the installed operations entry point is packaged correctly.

## Relationship to other Quillan/Core surfaces

```text
#390 diagnostics
  bounded local troubleshooting event history

#391 attention
  current privacy-minimal teacher-attention projection

#392 readiness
  whether Quillan can operate correctly for supplied neutral context

paper_data_suite.modules
  routing provider contract

paper_data_suite.publication_producers
  publication compatibility contract
```

These are deliberately independent.

Attention is not readiness, launchability, routing capability, publication
capability, suite qualification, educational risk, urgency, or grouping-signal
meaning.
