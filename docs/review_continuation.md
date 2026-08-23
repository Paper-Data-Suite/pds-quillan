# Review Continuation

## Purpose

`Continue Review` is Quillan's read-only answer to one narrow question for an
already-selected, canonical roster student:

> Which explicit mechanical review stage comes next?

It does not answer what the teacher should decide at that stage. It does not
evaluate student writing, infer a requirement outcome, infer Focus Standard
applicability, infer ratings, generate feedback, or infer that a review is
complete.

The teacher-facing `Selected Student Review` root displays the projection as:

```text
C. Continue Review — <current continuation label>
```

When a safe target exists, selecting `C` enters the same existing child workflow.
The #386 compact root keeps direct non-linear access to those stages through
`Advanced Actions`; continuation does not own or duplicate the child workflows.

## Ownership and dependency direction

Continuation is deliberately a projection over the deterministic review work
queue rather than a second review-state classifier:

```text
canonical Quillan records
  -> #383 deterministic ReviewWorkQueueItem
      -> #385 ReviewContinuation
          -> existing teacher-controlled child workflow
```

The #383 queue owns classification precedence, including invalid-state failure,
submission preparation, explicit minimum-requirement outcomes, explicit phase
completion, the returned-without-full-review path, and feedback-export freshness.
`Continue Review` does not inspect `review.json` independently to reinterpret any
of those facts.

See [Review Work Queue](review_work_queue.md) for the authoritative category
semantics and precedence.

## Derived model

`quillan.review_continuation.ReviewContinuation` is immutable and is never
persisted. It carries only:

- exact `class_id`;
- exact `assignment_id`;
- exact `student_id`;
- source #383 category;
- source bounded reason code;
- continuation status;
- optional symbolic target;
- teacher-facing target label; and
- existing bounded warning codes.

The supported statuses are:

```text
available
complete
unavailable
```

The supported symbolic targets are:

```text
minimum_requirements
review_unit_observations
overall_focus_standard_ratings
focus_standard_feedback
feedback_export
```

Targets are symbolic workflow identities, not menu numbers. This keeps the
resolver independent of teacher-menu numbering and lets menu code dispatch to the
existing child functions rather than duplicate their behavior.

## Exact category mapping

| #383 category | Continuation status | Target / label |
| --- | --- | --- |
| `no_submission` | `unavailable` | `unavailable (no reviewable submission)` |
| `needs_assembly` | `unavailable` | `unavailable (submission needs assembly)` |
| `minimum_requirements_pending` | `available` | `Review minimum requirements` |
| `observations_pending` | `available` | `Review units and Focus Standard observations` |
| `ratings_pending` | `available` | `Overall Focus Standard ratings` |
| `feedback_pending` | `available` | `Compose Focus Standard feedback` |
| `export_pending` | `available` | `Export student feedback` |
| `complete` | `complete` | `complete` |
| `attention_required` | `unavailable` | `unavailable (attention required)` |

An unknown category or malformed source identity fails closed rather than being
mapped heuristically.

## Freshness and selected-student identity

The selected-student root already rebuilds #384 class-set navigation on every
redraw. `Continue Review` derives from that fresh
`ReviewStudentNavigation.current` item for the exact selected student. It does
not construct a second queue, cache a target, or persist recent stage state.

After a child workflow returns, the root is redrawn and continuation is derived
again from current canonical state. Therefore:

- cancellation normally leaves the same target;
- an explicit completed phase advances to the next #383 category;
- contradictory state fails closed;
- a newly current export produces `complete`; and
- a stale or missing export produces `export_pending`.

`P`, `N`, and `W` may change the selected student. The next root redraw derives a
new continuation for that exact student's #383 item. `C` itself never changes
`student_id` and is never an alias for next-student navigation.

See [Review Student Navigation](review_student_navigation.md) for roster ordering
and P/N/W semantics.

## Explicit completion, not inferred completeness

Continuation respects Quillan's existing explicit workflow-state semantics.
Examples include:

- a saved requirement check does not substitute for an explicit usable
  minimum-requirements outcome;
- explicitly completing observations advances to ratings even if some possible
  unit/standard observation entries are absent;
- explicitly completing ratings advances to feedback even if some Focus
  Standards have no rating;
- explicitly completing feedback advances to export without a new
  `Continue Review` content-sufficiency judgment; and
- `review_state == exported` does not override #383's current/stale/missing
  export-artifact semantics.

This is routing over explicit persisted state, not a second validator that adds
new educational policy.

## Returned without full review

When canonical state consistently records `returned_without_full_review`, #383
owns the alternate-path classification. `Continue Review` therefore skips:

```text
observations
ratings
ordinary Focus Standard feedback composition
```

and routes directly to `Export student feedback` while a current supported
returned-work export is missing. Once a current supported export exists, the
continuation state is `complete`.

If returned-work fields are contradictory, #383 classifies the item as
`attention_required`; continuation then remains unavailable rather than choosing
a normal standards-review stage.

## Complete and unavailable states

Selecting `C` for `complete` reports that no incomplete review stage remains and
returns to the same selected-student root without writing anything.

Unavailable continuation also writes nothing:

- `no_submission` does not create a plain-paper submission;
- `needs_assembly` does not assemble routed evidence;
- `attention_required` does not repair or reinterpret records; and
- unavailable class-set navigation / missing canonical queue membership does not
  fall back to dashboard details, filenames, display names, timestamps, or
  student content.

The existing explicit preparation and recovery actions remain separately
available.

## Evidence opening and auxiliary actions

`Open submission evidence` is intentionally not a continuation stage because
Quillan has no canonical persisted semantic equivalent to
`teacher_has_read_this_evidence`. #385 does not add one.

These useful operations also remain outside the ordered continuation sequence:

```text
View current review details
Manage submission pages
Add teacher note
Update review workflow state
Refresh summary
P / N / W navigation
```

They remain reachable through the compact root or `Advanced Actions` and do not
become artificial prerequisites for mechanical progression.

## Cancellation and write safety

`Continue Review` appears only on the clean selected-student root. Once it enters
an existing child workflow, that workflow's established confirmation, save,
Back, and cancellation behavior remains authoritative.

The continuation layer does not:

- save pending child input;
- mark a phase complete on Back/cancel;
- preserve draft judgments across stages or students;
- replay a completed write;
- duplicate a child write;
- auto-advance to another student; or
- create a continuation-state file.

The projection itself performs no filesystem write.

## Privacy

Continuation contains operational state only. It may expose exact selected
identity already required by the review screen plus bounded #383 reason/warning
codes and the target label. It does not reproduce student writing, scan contents,
teacher feedback bodies, private notes, observation/rating rationales, rating
values, performance comparisons, grades, or inferred proficiency.

## CLI and suite boundary

There is no new direct `quillan continue-review` command. Existing direct review
commands remain the noninteractive interfaces for the underlying stages.

This feature is Quillan-owned and requires no Core schema/API change, no suite
shell dependency, no data migration, and no dependency-floor change beyond the
existing `pds-core>=0.6,<0.7` support line.

## Scope boundary

#385 adds one deterministic convenience route. It does not perform the compact
routine-review redesign planned for #386, batch export from #387, class
completion views from #388, Meridian publication from #389, diagnostics from
#390, shared operations providers from #391/#392, installed/physical acceptance
from #393, or the final v0.10.0 workflow/release audit from #394.

The historical #379 teacher-workflow audit remains the authoritative before-state.
Its recorded measurements are not rewritten by this feature. Recorder-backed #385
acceptance demonstrates reduced repeated stage-selection friction while retaining
all explicit teacher judgments and child-workflow confirmation boundaries.

For the broader teacher-review sequence, see
[Prepared Review Workflow](prepared_review_workflow.md).
