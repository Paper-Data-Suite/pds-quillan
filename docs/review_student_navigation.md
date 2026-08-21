# Deterministic review student navigation

Issue: #384 — class-set student navigation

## Boundary

Quillan class-set review navigation is a read-only derived view over the exact
`AssignmentReviewWorkQueue` introduced by #383. It does not define roster order,
review-work categories, teacher priority, or review-stage guidance independently.

Core remains authoritative for the canonical class roster and roster order. #383
remains authoritative for Quillan's assignment-local work classification. #384 only
answers where the selected roster student sits in that queue and which bounded roster
targets are available.

Navigation state is not persisted in the workspace.

## Canonical order and identity

Normal navigation uses `AssignmentReviewWorkQueue.items` exactly as ordered by #383.
Exact `student_id` is authoritative; display names are labels only. Duplicate display
names do not affect navigation identity.

An unrostered diagnostic record is not a queue member and therefore has no canonical
roster position. If a selected student is absent from the queue, normal class-set
navigation fails closed rather than inventing a position.

## Previous and next

For a selected queue item at zero-based index `i`:

```text
previous = items[i - 1] when i > 0
next     = items[i + 1] when i + 1 < len(items)
```

There is no wraparound. The first student has no previous target and the final student
has no next target.

Adjacent navigation does not skip students because of submission state, integrity
state, or completion state.

## Next student needing review

A student needs work for #384 exactly when the existing #383 category is not:

```text
complete
```

Starting strictly after the current position, the target is the first later queue item
whose category is not `complete`.

This includes every #383 non-complete category:

```text
no_submission
needs_assembly
minimum_requirements_pending
observations_pending
ratings_pending
feedback_pending
export_pending
attention_required
```

No category is ranked above another. Search is forward-only and never wraps to an
earlier roster student.

## Counts

The navigation projection exposes:

```text
position
roster_count
needs_work_count
needs_work_after_current_count
```

`position` is one-based for teacher-facing display. `needs_work_count` counts every
queue item whose category is not `complete`. `needs_work_after_current_count` applies
the same predicate only to subsequent roster items.

These are operational workflow counts, not estimates of difficulty, severity,
performance, or time.

## Freshness and writes

The workspace-facing builder obtains a fresh #383 work queue each time it is invoked.
The pure resolver performs no filesystem access and no writes.

Later menu integration should rebuild navigation after returning from student actions
so explicitly persisted review/export changes can alter the next-needing-review target
before the teacher navigates.

## Later issue boundary

#384 decides **which student** is before, after, or the next later non-complete roster
student. It deliberately does not decide **which review stage** should be opened for a
student. That stage-routing concern belongs to #385 `Continue Review`.

Likewise, #384 does not redesign the selected-student action surface; #386 may later
consume this navigation model while creating the compact routine review screen.

## Teacher menu integration

The root `Selected Student Review` screen rebuilds this navigation from current
canonical #383 state on every redraw. It shows the selected student's display name
with exact `student_id`, exact roster position, the current queue work category, total
students needing work, and forward remaining-work count.
It also exposes local class-set controls without renumbering the existing review
actions:

```text
P. Previous student — <exact target or first-roster boundary>
N. Next student — <exact target or final-roster boundary>
W. Next student needing review — <first later non-complete target or none>
```

Targets include exact `student_id` when a display name exists. `P` and `N` move only
to the immediately adjacent canonical roster item. `W` searches strictly forward
for the first #383 item whose category is not `complete`. None of these commands
wraps around the roster.

Navigation is available from the clean selected-student root for missing-submission,
routed-evidence, plain-paper, and review-ready states. It is not injected into child
teacher-input workflows, so pending requirement, observation, rating, feedback,
note, page-management, workflow-state, or export input must first save, cancel, or
return to the root screen. A successful child write is reflected when the root
rebuilds; a canceled child operation is not converted into a navigation write.

If the selected identity is outside the canonical roster queue, or the queue cannot
be built safely, class-set navigation is unavailable rather than inferred. Existing
`B`, `M`, and `Q` behavior remains owned by the shared menu-navigation layer. #385
will add stage routing for one already-selected student and must not be folded into
these student-to-student controls.
