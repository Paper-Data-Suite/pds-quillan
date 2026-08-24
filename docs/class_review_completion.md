# Class Review Completion

Issue: #388 — class review completion views

## Purpose

`Class Review Progress` is Quillan's focused, read-only assignment-level view for
answering two routine teacher questions:

```text
How much of this class set is complete?
Which exact roster student should I open for the work state I care about?
```

It is intentionally narrower than the comprehensive
[Assignment Review Dashboard](review_dashboard_contract.md) and intentionally richer
than the exact [#383 review work queue](review_work_queue.md).

The focused view does not create a third review classifier. It projects existing
canonical status into a lower-density teacher workflow.

## Authorities and dependency direction

The derivation is:

```text
canonical Quillan/Core records
  -> AssignmentReviewDashboard
      -> #383 AssignmentReviewWorkQueue
          -> ClassReviewCompletionView
              -> teacher menu filtering and drill-down
```

The dashboard owns comprehensive assignment diagnostics and per-format feedback
freshness. The #383 queue owns mechanical review-work classification. The #388 model
combines those existing facts without independently inspecting `review.json` to decide
review stage, completion, returned-work validity, or export freshness.

Core remains authoritative for the canonical class roster, roster order, shared
identifiers, workspace conventions, and standards. Quillan remains authoritative for
review workflow semantics and feedback-export freshness.

## Snapshot consistency

`derive_class_review_completion_view_from_dashboard(...)` derives the focused view
from one already-built `AssignmentReviewDashboard` snapshot. The #383 queue is then
derived from that same dashboard.

This prevents a displayed queue category from being paired with export freshness read
from a different assignment snapshot.

The convenience builder may build the dashboard itself, but a caller that already has
a dashboard should reuse that snapshot.

## Population and identity

The focused population is the canonical roster.

Every roster student appears exactly once and remains in canonical roster order.
`student_id` is the durable identity. A display name is only a teacher-facing label.

Unrostered assignment-local records are excluded from:

```text
roster count
complete count
needs-work count
category counts
export-capable count
filtered student rows
```

Their number may be shown as bounded diagnostic context. Full details belong to the
comprehensive dashboard.

If the canonical roster is unavailable, focused completion fails closed. Quillan does
not substitute submission-directory order, routed-evidence IDs, display-name order, or
other discovered records for the roster.

The comprehensive dashboard may still show assignment-local diagnostics under its
existing roster-unavailable contract.

## Mechanical categories

The focused view passes through the exact #383 categories:

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

No additional review-state classifier or alternate precedence exists in #388.

`attention_required` remains an exceptional fail-closed state, not a normal linear
review phase.

## Completion counts

`complete_count` is exactly the #383 `complete` count.

Under #383, `complete` means the applicable teacher-controlled review path is complete
and at least one supported canonical feedback export is current. A current PDF or
current Markdown export is sufficient. A missing optional companion does not make an
otherwise current queue item incomplete.

`needs_work_count` is:

```text
roster_count - complete_count
```

It therefore includes ordinary pending stages, `export_pending`, and
`attention_required`.

`export_capable_count` is the presentation-only sum:

```text
export_pending + complete
```

It is not a new queue category and is not synonymous with `complete`.

## Per-format feedback status

For export-capable students only, the focused view carries the dashboard's existing
PDF and Markdown status independently:

```text
present
stale
missing
unknown
```

Teacher-facing menu text renders `present` as `current`.

The summary intentionally scopes per-format counts to:

```text
export_pending
complete
```

An earlier-stage student is not treated as a meaningful "missing PDF" merely because
feedback should not exist yet.

A valid focused row can therefore be:

```text
category = complete
PDF = current
Markdown = missing
```

That does not contradict #383 completion.

## Filters

Filters are immutable, deterministic, and ephemeral. They only change which roster
rows are displayed.

Supported filters are:

```text
All students
Needs work
Complete
exact #383 review-work category
PDF current / stale / missing / unknown
Markdown current / stale / missing / unknown
```

Export-state filters consider only `export_pending` and `complete`.

All filtered results preserve canonical roster order. Filtering never ranks students,
persists a preference, changes queue state, or changes review priority.

The current filter is retained only while the teacher remains inside the
`Class Review Progress` workflow.

An empty filter is a valid successful view and is displayed as no matching roster
students rather than as an error.

## Teacher menu

`Assignment Review Actions` presents a compact completion summary before its action
list:

```text
Students: N
Complete: X / N
Needs work: Y
Export pending: Z
Attention required: A
Assembly needed: B
Page problems: C
Active Core scan-review items: D
Warnings: W
```

The routine action is:

```text
7. Review class progress
```

The focused `Class Review Progress` screen shows:

```text
completion summary
export-capable PDF/Markdown summary
current filter
shown/roster count
roster-ordered matching students
bounded unrostered/warning counts
```

Navigation remains:

```text
F. Filter
D. Full diagnostic dashboard
R. Refresh
B. Back
M. Main Menu
Q. Quit
```

## Exact-student drill-down

Selecting a numbered row or an exact displayed `student_id` routes to the existing
Selected Student Review workflow for that exact identity.

It does not create a parallel student-details workflow.

Selection itself performs no implied task. For example, selecting an
`export_pending` student does not export feedback, and selecting a
`needs_assembly` student does not assemble a submission.

After the selected-student workflow returns, class progress is rebuilt from current
canonical state and the active ephemeral filter is reapplied. A student therefore
naturally disappears from a filter when their canonical state no longer matches it.

## Refresh and full diagnostics

`R. Refresh` rebuilds current state and retains the current ephemeral filter.

`D. Full diagnostic dashboard` reuses the existing comprehensive dashboard formatter.
The focused view does not copy raw paths, page-level diagnostics, scan-review detail,
or malformed-record detail into the routine progress screen.

The direct commands remain unchanged:

```text
quillan review-queue <class_id> <assignment_id> [--format text|json]
quillan review-dashboard <class_id> <assignment_id> [--format text|json]
```

No third class-status CLI is introduced.

## Read-only boundary

Building, opening, filtering, refreshing, or navigating the focused view creates no:

```text
directories
records
manifests
exports
reports
temporary workspace files
locks
caches
filter preferences
completion records
audit records
publication records
```

Drilling into a selected student may enter an existing child workflow where a teacher
later chooses an explicit write. The drill-down itself is read-only.

## Privacy and judgment boundary

The focused view may expose:

```text
class and assignment identity
roster display name
exact student_id
mechanical #383 category
bounded reason/warning labels
PDF/Markdown freshness
aggregate counts
```

It does not expose student writing, OCR text, evidence content, feedback bodies,
teacher notes, rating values, rationales, grades, proficiency, or raw publication
records.

It does not inspect evidence, run OCR or AI, infer requirement outcomes, infer
observations or ratings, generate feedback, calculate grades, rank students, assemble
submissions, or create exports.

## Relationship to adjacent milestone work

[#387 batch feedback export](batch_feedback_export.md) remains the owner of batch
scope planning, overwrite policy, execution, TOCTOU protection, and post-write
verification. `Class Review Progress` reports current state but does not execute or
reimplement a batch.

#389 owns Share Results with Meridian and publication. A class can be 100% complete in
this view while having no publication at all.

#390 owns persisted diagnostic events. Routine viewing and filtering create no event
history.

#391 will expose privacy-minimal Quillan attention through Core's shared
module-operations provider. #388 remains a Quillan-local class/assignment teacher
workflow and is not a suite-wide provider contract.
