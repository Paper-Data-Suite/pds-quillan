# Routine Student Review Screen

## Purpose

Issue #386 makes the review-ready `Selected Student Review` root task-oriented
without changing Quillan's review records, review-state semantics, or child
workflows.

The compact screen is a presentation and routing layer over the state already
owned by #383–#385:

```text
canonical Quillan records
  -> #383 ReviewWorkQueueItem
      -> #384 ReviewStudentNavigation
      -> #385 ReviewContinuation
          -> #386 compact selected-student presentation
```

It does not inspect `review.json` to create another progress classifier and does
not infer teacher judgments.

## Review-ready root

For a student with a canonical review-ready submission, the root emphasizes:

```text
O. Open Evidence
C. Continue Review — <current continuation label>
E. Export Feedback
N. Next Student — <student label, bounded end-of-roster state, or unavailable>
A. Advanced Actions

P. Previous Student — <student label or bounded first-student state>
W. Next Student Needing Review — <student label or bounded unavailable state>

B. Back
M. Main Menu
Q. Quit
```

The root also retains concise exact-student context, roster position, work state,
students-needing-work count, and bounded attention/warning information.

The old flat eleven-action review-ready root is no longer rendered.

## Primary actions

### Open Evidence

`O` routes to the existing safe submission-evidence opening workflow. It does not
create a persisted read/viewed flag, modify continuation, or perform OCR, AI,
scoring, or automated review.

A valid plain-paper submission remains review-ready even though it has no digital
evidence. Quillan does not fabricate a digital artifact for that case.

### Continue Review

`C` is the #385 continuation route. #386 does not change its category mapping,
status vocabulary, target vocabulary, completion rules, or fail-closed behavior.

After the child returns, the selected-student root is redrawn and continuation is
re-derived from current canonical state.

### Export Feedback

`E` routes to the existing single-student feedback export workflow. Export type,
overwrite behavior, current/stale/missing artifact semantics, and export metadata
remain owned by that workflow.

`E` does not batch students, auto-overwrite, synthesize missing review judgments,
auto-advance to another student, or publish results. Issue #387 adds a separate
assignment-level `F. Batch Feedback Export` workflow; it does not change the
selected-student `E` semantics.

### Next Student

`N` preserves #384 semantics: move to the next roster student, not the next student
needing review. The selected student ID changes only after a valid #384 target is
resolved. The new student's status, queue item, navigation, continuation, and
export state are rebuilt on the next root redraw.

### Advanced Actions

`A` opens direct, non-linear access to the less-common review and record-management
workflows for the exact selected student.

## Advanced Review Actions

The child menu retains:

```text
1. View current review details
2. Review minimum requirements
3. Review units and Focus Standard observations
4. Overall Focus Standard ratings
5. Compose Focus Standard feedback
6. Manage submission pages
7. Add teacher note
8. Update review workflow state
9. Refresh summary

B. Back
M. Main Menu
Q. Quit
```

These entries dispatch to the existing handlers. #386 adds no parallel review
business logic.

Direct access to earlier completed stages is intentional. `Continue Review` answers
which mechanical stage is next; it does not prevent a teacher from revisiting and
correcting an earlier teacher-authored requirement, observation, rating, or
feedback decision.

After a selected advanced workflow returns, control returns to the clean
selected-student root so current state is rebuilt rather than cached.

## Previous and next-needing-review

`P` and `W` remain directly available on the review-ready root.

```text
P -> ReviewStudentNavigation.previous
N -> ReviewStudentNavigation.next
W -> ReviewStudentNavigation.next_needing_review
```

The three meanings remain distinct. If canonical #384 navigation cannot be
resolved, P/N/W are shown as `unavailable` rather than being mislabeled as roster
boundaries. Navigation never matches by display name and does not mutate review
records merely because a student changed.

## Recovery screens are intentionally different

The compact review-ready hierarchy is not forced onto students who are not yet
review-ready.

### No submission

The existing missing-submission recovery screen remains explicit. Where valid, it
continues to offer plain-paper creation, routed-evidence status, refresh, bounded
`Continue Review` unavailability, P/N/W, and B/M/Q.

It does not show active `Open Evidence` or `Export Feedback` actions implying a
submission already exists, and it never auto-creates plain paper.

### Needs assembly

The existing routed-evidence/needs-assembly screen remains explicit. It continues
to offer assembly, routed-evidence status, refresh, bounded `Continue Review`
unavailability, P/N/W, and B/M/Q.

It never auto-assembles because the student was selected or because continuation
was attempted.

### Attention required

For `attention_required`, the compact root surfaces the bounded reason/warning
information supplied by the canonical work queue. `Continue Review` remains
unavailable and no stage is guessed.

## Plain paper

A canonical plain-paper submission is a valid review-ready submission. It uses the
compact root and normal review/feedback workflows. Absence of digital pages does
not make it equivalent to `no_submission`.

## Freshness and cancellation

The root rebuilds state after:

- a completed child workflow;
- a canceled child workflow;
- export;
- P/N/W navigation;
- an Advanced Actions operation.

No continuation target, export state, or pending teacher input is persisted by the
compact menu.

Existing child save/confirmation/cancellation rules remain authoritative. Back or
cancel never becomes an implicit save, phase completion, export, or student
advance.

## Privacy

Routine presentation is limited to exact selected identity already needed for the
teacher workflow plus bounded operational status, warnings, export state, and
navigation labels.

The compact root does not reproduce student writing, evidence contents, teacher
feedback bodies, private notes, rationales, grades, percentages, or inferred
proficiency.

## CLI and dependency boundary

#386 adds no direct CLI command, schema migration, Core API requirement, suite-shell
dependency, or dependency-floor change. Existing direct review/export commands and
application services remain available for scripting, diagnostics, and recovery.

The supported Core line remains:

```text
pds-core>=0.6,<0.7
```

## Scope boundary

#386 does not implement:

- #387 batch feedback export;
- #388 class-level completion/filter views;
- #389 guided Meridian publication;
- #390 diagnostics;
- #391/#392 shared operations providers;
- automated writing evaluation or teacher-judgment inference.

The #379 audit remains the historical before-state. Active recorder-backed tests may
change their current menu selections as the interface improves, but the historical
report and its recorded baseline are not rewritten.

## Relationship to batch feedback export

Issue #387 adds `F. Batch Feedback Export` to Assignment Review Actions rather
than expanding the compact selected-student root. The class-set workflow uses
#383 `export_pending`/`complete` state, exact roster identity, explicit format and
overwrite policy, a read-only preview, one confirmation, isolated per-student
execution, and post-write verification.

The selected-student screen remains responsible for intentional one-student
review and recovery. Batch export does not auto-navigate students, repair an
incomplete review, create plain-paper submissions, assemble evidence, or alter
#384/#385 navigation/continuation semantics.

See [`batch_feedback_export.md`](batch_feedback_export.md).

## Assignment-level resubmission action

`8. Review resubmissions / rescans` belongs to Assignment Review Actions and is
not added to the compact selected-student root. See
[Resubmission / Rescan Review](resubmission_inbox.md).
