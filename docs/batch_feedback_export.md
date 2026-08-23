# Batch Feedback Export and Verification

## Purpose

Issue #387 adds assignment-level orchestration for student feedback export without
changing Quillan's teacher-judgment model or the existing single-student renderers.

The batch layer answers:

```text
Which roster students are already on an export-capable review path, what requested
feedback artifacts are current/stale/missing, what would this batch write, and did
each authorized write finish as a current canonical export?
```

It does **not** answer whether student writing is good enough to export. That
judgment remains represented by canonical teacher-controlled review state.

## Ownership

The batch workflow composes existing boundaries:

```text
#383 review work queue
  -> #387 read-only batch plan
      -> existing single-student feedback exporters
          -> existing review.json export metadata
              -> #387 post-export verification
```

#387 does not create a second review-stage classifier or a second feedback
renderer.

The authoritative export-capable #383 categories are:

```text
export_pending
complete
```

`complete` means at least one supported feedback export is already current. It
does not mean every possible requested format is current. A student can therefore
be `complete` while, for example, PDF is current and Markdown is missing.

## Batch scopes

Two scopes are supported.

### Completed scope

`completed` selects roster students whose current #383 category is either
`export_pending` or `complete`, preserving canonical roster order.

Earlier review stages and `attention_required` are excluded from the batch and
reported in aggregate. Unrostered diagnostic records are not silently added.

### Explicit selection

`selected` accepts exact canonical roster `student_id` values. Display names are
never used as identifiers.

Explicit selection controls scope only. It does not bypass review readiness.
Selected students in an incomplete category are planned as `blocked_incomplete`;
selected `attention_required` students are planned as `blocked_attention`.
Unknown or duplicate student IDs are rejected before a plan is produced.

## Formats

The supported batch formats are the same formats owned by the existing
single-student exporter:

```text
pdf
markdown
both
```

`both` is a coupled per-student operation. PDF and Markdown are generated through
the existing combined exporter so one metadata update cannot immediately make the
other newly generated artifact stale.

If a coupled pair is mixed, such as PDF current plus Markdown missing, a safe
policy does not silently generate only the missing companion. The plan requires a
replacement policy that authorizes rewriting the pair.

## Overwrite policies

The teacher selects one policy before preview.

### `none`

- create when every requested target is missing;
- skip when every requested target is current;
- do not replace stale/current files;
- mixed or stale existing target sets are blocked by policy.

### `stale`

- create fully missing requested target sets;
- replace when any requested target in the set is stale;
- skip fully current sets;
- preserve deterministic coupled behavior for `both`.

### `all`

- create fully missing target sets;
- replace any existing requested target set;
- still requires explicit batch confirmation and canonical validation.

An existing file is never treated as implicit overwrite authorization.

## Plan model

`build_batch_feedback_export_plan(...)` is read-only and returns an immutable,
ephemeral `BatchFeedbackExportPlan`.

The plan contains only bounded operational data:

- class and assignment identity;
- scope, format, and overwrite policy;
- roster count;
- excluded incomplete/attention counts for completed scope;
- roster-ordered student identity;
- #383 category and reason code;
- bounded warnings;
- review update timestamp used for freshness comparison;
- requested export statuses; and
- planned action.

The action vocabulary is:

```text
create
replace
skip_current
blocked_incomplete
blocked_attention
blocked_conflict
blocked_unknown_state
```

The plan contains no student writing, feedback bodies, private notes, rationales,
rating values, or observation text. No plan file is persisted.

## Preview and confirmation

Interactive batch export always renders the read-only plan before any mutation.
The preview reports assignment identity, scope, format, overwrite policy, selected
and writable counts, aggregate planned actions, and one concise line per planned
student.

A plan with zero writable students performs no writes.

The menu requires one explicit `y`/`yes` confirmation after preview. Back, any
other response, or cancellation before confirmation starts no batch write.

The direct CLI likewise separates preview from mutation:

```powershell
quillan export-feedback-batch <class_id> <assignment_id> `
  --completed --format pdf --dry-run

quillan export-feedback-batch <class_id> <assignment_id> `
  --student-id <student_id> --student-id <student_id> `
  --format both --overwrite-policy stale --yes
```

Exactly one of `--completed` or one-or-more `--student-id` arguments defines
scope. Exactly one of `--dry-run` and `--yes` is required. `--overwrite-policy`
defaults to `none`.

## State freshness between preview and execution

A confirmed plan freezes the selected student IDs and the state that authorized
each write. The executor does not broaden the batch because another student
became eligible later.

Before each writable student is attempted, Quillan rebuilds current canonical
state and compares it with the confirmed plan. A write is refused for that
student if, for example:

- the student is no longer on the canonical roster;
- the #383 category changed;
- the review update timestamp changed; or
- the requested export status changed.

The bounded result is `state_changed`, and later independent students are still
attempted.

## Execution and failure isolation

Batch execution is not a cross-student transaction. Each student is an
independent bounded operation.

Actual rendering delegates to:

```text
export_student_feedback(...)
export_student_feedback_pdf(...)
```

The batch layer therefore does not duplicate:

- Focus Standard ordering/display resolution;
- rating/rationale inclusion behavior;
- feedback-comment inclusion behavior;
- returned-without-full-review rendering;
- canonical feedback path construction;
- PDF generation;
- Markdown generation; or
- `review.json.exports` provenance updates.

A failure for one student is recorded and does not prevent later students from
being attempted.

## Post-export verification

A renderer returning successfully is not enough for a batch success.

After each write, #387 rebuilds the student's canonical review/export status and
verifies every requested artifact:

```text
status == present
file is present
metadata is present
source_review_updated_at == current review updated_at
```

For `both`, both artifacts must satisfy those checks together.

If verification fails, the result is `verification_failed`; Quillan does not
claim success or delete an artifact to conceal the mismatch.

Successful writes are reported as `created` or `replaced` with canonical
workspace-relative artifact paths.

Other result states include:

```text
skipped_current
skipped_by_policy
blocked_incomplete
blocked_attention
blocked_unknown_state
state_changed
export_failed
verification_failed
```

## CLI exit behavior

`--dry-run` succeeds when a valid plan can be produced because it performs no
writes.

An executed command returns nonzero when a student outcome represents an
ineligible explicit selection, unsafe/unknown state, state change, export failure,
or verification failure. Ordinary policy outcomes such as an already-current
artifact or an intentionally blocked replacement remain visible without being
reported as successful export writes.

## Teacher menu

Assignment Review Actions exposes:

```text
F. Batch Feedback Export
```

without renumbering the established numbered actions.

The normal flow is:

```text
Assignment Review Actions
  -> Batch Feedback Export
      -> scope
      -> exact roster selection, when requested
      -> format
      -> overwrite policy
      -> preview
      -> one confirmation
      -> verified result
```

The selected-student compact screen still retains:

```text
E. Export Feedback
```

for intentional one-student export. Batch export does not auto-navigate students
and does not replace that recovery/diagnostic path.

## Provenance and privacy

There is no batch-history record family. Successful artifacts continue to use
the existing per-student metadata in:

```text
review.json.exports.feedback_pdf
review.json.exports.feedback_markdown
```

Batch export never creates or alters teacher judgments merely to make a student
exportable. It does not infer or generate minimum-requirement outcomes,
observations, ratings, rationales, feedback comments, or completion state.

Preview/result output intentionally excludes student writing, feedback bodies,
private notes, rationale text, rating values, observation text, retained scan
paths, and evidence details.

## Publication boundary

Feedback export remains a local derived student-facing artifact workflow. #387
does not register Academic Work, create Academic Result Manifest revisions,
publish through Core, share with Meridian, calculate Grade, or infer proficiency.
Those remain separate explicit workflows.

## Core boundary

#387 remains Quillan-owned orchestration on the existing compatibility line:

```text
pds-core>=0.6,<0.7
```

Core remains authoritative for canonical roster identity/order, shared
identifiers, workspace conventions, and standards. No new Core API or suite-shell
dependency is introduced.
