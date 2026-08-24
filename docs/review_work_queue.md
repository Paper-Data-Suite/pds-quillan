# Deterministic review work queue

Issue: #383 — deterministic review work queue

## Boundary

The Quillan review work queue is an immutable, read-only view of one exact
class/assignment. It is rebuilt from current canonical workspace records whenever a
caller asks for it. It is not persisted, cached in menu session context, or treated as
authoritative review state.

Core remains authoritative for the class roster and roster order. Quillan remains
authoritative for assignment validity, submission/review state, minimum-requirement
semantics, and feedback-export freshness.

Queue construction does not create or modify assignment, submission, review, export,
roster, routing, registry, preference, or publication records.

## Population and order

The normal queue contains every canonical roster student exactly once, in canonical
roster order. Exact `student_id` is the durable identity; display names are
supplemental labels only.

Unrostered submissions or routed artifacts do not become queue members. They are
reported separately as bounded diagnostic state. If the canonical roster cannot be
loaded, queue construction fails rather than substituting submission-directory,
display-name, timestamp, performance, or category order.

## Categories and precedence

The fixed queue categories are:

```text
no_submission
needs_assembly
minimum_requirements_pending
observations_pending
ratings_pending
feedback_pending
export_pending
complete
attention_required
```

Classification follows a deterministic earliest-gate policy:

1. unsafe/invalid canonical record state -> `attention_required`;
2. routed evidence without a valid submission -> `needs_assembly`;
3. no valid submission and no pending routed evidence -> `no_submission`;
4. configured minimum requirements without an explicit usable outcome ->
   `minimum_requirements_pending`;
5. explicit `returned_without_full_review` bypasses observations, ratings, and normal
   feedback composition, then requires a current feedback export;
6. otherwise explicit review workflow state determines observations, ratings, and
   feedback stages in order;
7. an export-capable review with no current supported feedback export ->
   `export_pending`;
8. an applicable completed review path with at least one current supported canonical
   feedback export -> `complete`.

The classifier never reads student writing to decide a category and never infers a
teacher-entered minimum-requirement outcome, applicability decision, observation,
rating, feedback decision, or completion decision.

## Export freshness

Queue completion uses the existing Quillan feedback-export status boundary. A current
PDF or Markdown export is sufficient. A missing optional companion does not make an
otherwise current export incomplete. Stale exports, missing artifacts referenced by
metadata, or artifacts lacking usable canonical metadata remain `export_pending`.

`review_state == exported` alone is not sufficient for `complete`.

## Integrity handling

`attention_required` is an exceptional fail-closed classification, not a workflow
phase. It is used when invalid submissions/reviews, identity mismatches, orphan
reviews, or inconsistent returned-work state prevent safe normal classification.

The queue exposes bounded reason/warning codes, not student writing, feedback bodies,
private notes, rating values, rationales, or teacher-note text.

## Downstream integration

The queue remains the mechanical classification authority consumed by completed
teacher-workflow layers:

```text
#384 next/previous/next-needing-review navigation
#385 Continue Review routing
#387 batch feedback export
#388 Class Review Progress
```

#388 derives a focused class-completion projection from the same dashboard snapshot
used to derive this queue. It preserves these categories, roster order, exact student
identity, completion semantics, and no-write boundary while adding filtering and
per-format feedback freshness for export-capable reviews.

#391 remains future shared attention-provider work. It may consume privacy-minimal
Quillan-owned facts but must not change this queue's local classification semantics.
## Direct CLI

The supported direct command is:

```text
quillan review-queue <class_id> <assignment_id> [--format text|json]
```

Text is the default. JSON emits `quillan_assignment_review_work_queue` schema
version `1`. Both representations are rebuilt from current canonical state and write
nothing. Workspace, assignment, or roster failures return nonzero; isolated invalid
student records use the queue's bounded `attention_required` category.

The command has no navigation, priority, mutation, assembly, continuation, or export
options. Those remain later workflow concerns.
## Teacher menu integration

The exact queue remains directly available through `quillan review-queue`. The routine
assignment menu now uses #388 `Class Review Progress` as the teacher-facing class-set
view:

```text
7. Review class progress
```

That focused screen consumes this queue rather than redefining it. It adds ephemeral
filtering, per-format export freshness for export-capable reviews, and exact-student
drill-down while preserving canonical roster order and read-only viewing semantics.

The existing `Select Student/Submission` path remains available as a broader
submission/diagnostic picker and still labels roster students with the same queue
category. Unrostered diagnostic records can remain visible in comprehensive diagnostic
surfaces but are never promoted into the normal roster completion population.

Neither the queue nor the focused progress view automatically assembles submissions,
advances review state, creates feedback, or exports artifacts.
