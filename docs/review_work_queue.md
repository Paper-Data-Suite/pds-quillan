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

## Later integration

This model deliberately does not implement:

```text
#384 next/previous/next-needing-review navigation
#385 Continue Review routing
#387 batch feedback export
#388 redesigned class completion views
#391 shared attention provider
```

Later work may consume roster order, exact student identity, category, counts, and
reason codes from this read-only model without changing its no-write boundary.
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

`Assignment Review Actions` exposes `View review work queue`. The screen rebuilds the
queue from current canonical state on entry and on `R. Refresh`, shows the #382 exact
active class/assignment header, then renders complete/needs-work counts and roster
students in canonical roster order. `B. Back` and `M. Main Menu` retain the active
class/assignment context; `Q. Quit` ends the process. Viewing and refreshing write no
workspace files and do not cache queue state in `MenuSessionContext`.

The existing `Select Student/Submission` screen remains the explicit student-selection
path. It keeps concise submission/evidence detail and appends the same queue category
as `work=<category>` for roster students. Unrostered diagnostic records remain
selectable where the pre-existing dashboard exposes them, but they are labeled outside
the normal roster queue rather than being silently promoted into it.

This integration does not implement next/previous student navigation, automatic opening
of a queue item, `Continue Review`, automatic assembly, or automatic export.
