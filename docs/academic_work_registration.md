# Quillan Academic Work Registration

## Purpose

Quillan Academic Work Registration is the explicit producer-owned boundary that declares an existing managed writing assignment eligible for later Core academic publication.

Registration is not publication and is not grading. It does not generate an Academic Result Manifest, create a Publication Record, assign an Academic Period, calculate proficiency, create a Grade item, or apply portfolio policy.

The stable Quillan producer contract is:

```text
quillan_academic_work_v1
```

## Complete work identity

One registration describes one exact Core work identity:

```text
ModuleWorkRef(
    module_id="quillan",
    class_id=<class_id>,
    work_id=<assignment_id>,
)
```

The same assignment definition may be represented in multiple classes, but each class/work identity is registered independently.

Only an existing canonical managed assignment is eligible. Quillan validates the current `assignment.json` under:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
```

The assignment must remain valid schema 2 Quillan work, its `assignment_id` must agree with the work identity, and the selected class must occur in `class_ids`. Linked, missing, malformed, mismatched, or otherwise unsafe managed work fails closed. Registration never creates an assignment or work directory to satisfy eligibility.

## Exact Core request

Quillan maps eligible work to Core's `AcademicWorkRegistrationRequest` with:

```text
producer_contract_version = quillan_academic_work_v1
work_kind                = assignment
title                    = current assignment.title
academic_intent          = explicit caller value
lifecycle                = explicit caller value
source_records            = exactly one Quillan assignment reference
```

The assignment source record is:

```text
module_id        = quillan
record_kind      = assignment
record_id        = <assignment_id>
contract_version = 2
```

The source contract version is the native Quillan assignment schema version. It is distinct from the Core Academic Work Registration schema, the Quillan Academic Work producer contract, and the Academic Result Manifest contract.

## Explicit policy values

Academic intent is chosen explicitly from Core's supported values:

```text
formative
summative
diagnostic
practice
feedback_only
reporting_only
```

Lifecycle is chosen explicitly from:

```text
planned
active
closed
cancelled
```

Quillan does not infer either value from title, writing type, prompt, Focus Standards, rating scale, review state, ratings, submissions, feedback, dates, or generated response pages.

## Core-owned immutable history

Quillan delegates canonical writes to Core's registry services:

```text
register_academic_work
update_academic_work_registration
```

Core owns registration revision allocation, timestamps, immutable revision storage, the explicit current selection, write locking, optimistic concurrency, reconciliation, and partial-success state.

Quillan does not call Core's registration storage writer directly and never infers current state from the highest revision filename or timestamp.

### Initial registration and replay

The first registration creates revision 1. Repeating exactly the same request returns Core's `existing` disposition and creates no new revision.

If different current registration metadata already exists, the initial-registration workflow fails with a conflict. It does not silently perform an update.

### Updates

Updates require an explicit positive `expected_current_revision`. A changed title snapshot, academic intent, or lifecycle may create a new Core registration revision. Work identity, producer contract, work kind, assignment source identity, and source contract remain fixed.

Core's idempotent retry semantics are preserved: an older expected revision may still return `existing` when the already-current registration exactly matches the requested update. A stale differing request remains a conflict.

## Assignment edits

Editing native assignment state never automatically updates Core registration state.

If the assignment title changes, the existing registration keeps its historical title snapshot until the teacher explicitly updates registration. The teacher menu identifies this stale-title condition.

Changes to prompt, standards, review units, rating scale, requirements, or other assignment fields not represented by Academic Work Registration do not by themselves create a registration revision. They may affect later producer manifest content.

If a class is removed from `assignment.class_ids`, existing Core registration history remains visible and immutable. New registration/update attempts for that class fail eligibility validation until the native assignment again represents that class.

## CLI

Read current registration:

```text
quillan academic-work show \
  --class-id <class_id> \
  --assignment-id <assignment_id>
```

Create or exactly replay initial registration:

```text
quillan academic-work register \
  --class-id <class_id> \
  --assignment-id <assignment_id> \
  --academic-intent <intent> \
  --lifecycle <lifecycle>
```

Explicit update:

```text
quillan academic-work update \
  --class-id <class_id> \
  --assignment-id <assignment_id> \
  --academic-intent <intent> \
  --lifecycle <lifecycle> \
  --expected-current-revision <revision>
```

There is no CLI title option. The current validated assignment supplies the title.

Expected registration failures return nonzero without a traceback. Partial-success failures warn that durable Core state may exist and must be inspected before retrying.

## Teacher menu

`Assignment Management -> Academic Work Registration` lets the teacher select a valid managed assignment, inspect current registration state, and explicitly register or update it.

Writes require explicit academic-intent and lifecycle choices, a rendered request preview, and typed `REGISTER` or `UPDATE` confirmation. Updates use the exact current registration revision observed before confirmation. Quillan does not silently refresh the expected revision after confirmation; a concurrent change is a Core conflict.

Cancellation creates no registration state.

## Registration revision versus publication revision

These are independent identities:

```text
Core registration revision != Quillan record-set revision
```

The intended later chain is:

```text
managed Quillan assignment
-> explicit Core Academic Work Registration revision N
-> immutable Quillan Academic Result Manifest revision M
-> Core Publication Record references registration revision N
```

A later registration revision never rewrites an older manifest or Publication Record. Explicit manifest generation is implemented independently; see [Academic Result Manifest Generation](academic_result_manifest_generation.md). The [Publication Producer Profile](publication_producer_profile.md) declares compatible registration metadata without loading it. [Academic Result Publication Lifecycle](academic_result_publication.md) binds the exact current registration for a new Publication Record and preserves each existing Publication Record's exact historical registration revision on replay.

## Explicit-only boundary

No ordinary Quillan workflow registers or updates Academic Work implicitly. This includes assignment creation/editing, printable-response generation, PDS2 routing and scan intake, response-page observation persistence, submission assembly, plain-paper submission, review, ratings, feedback, reports, imports, help/version display, and routing-profile discovery.

Registration may create only Core-owned Academic Work Registration state. It does not create Academic Period, publication, withdrawal, catalog, manifest, submission, review, feedback-export, or report state, and it does not mutate producer-owned assignment/submission/review/evidence bytes.
