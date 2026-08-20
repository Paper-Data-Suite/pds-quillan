# Safe Writing-Assignment Copying

Issue #380 adds a teacher-controlled way to create a fresh Quillan assignment from
one existing canonical schema-v2 assignment. Copying reuses assignment configuration;
it does not clone work state.

## Identity

The source is selected by exact `class_id` plus `assignment_id`. The destination is
one or more explicitly selected target classes plus one target `assignment_id`.
Quillan work identity remains `module_id + class_id + assignment_id`, so the same
assignment ID may be used in a different clean class work root. The exact source work
identity cannot be its own destination. A same-class copy therefore needs a new
assignment ID.

## Reusable allowlist

A copy constructs a new schema-v2 assignment through the normal assignment builder.
It reuses these source values by value:

```text
writing_type
standards_profile_id
focus_standard_ids
review_unit
rating_scale
basic_requirements
minimum_requirement_policy
```

The source `title` and `student_prompt` are defaults that the teacher may replace.
The target `assignment_id` and `class_ids` are always target-specific. `created_at`
and `updated_at` are one fresh timezone-aware creation timestamp, and
`module_details` starts as `{}`.

The implementation deliberately does not clone the source JSON object and delete
known unsafe fields afterward. Unknown future assignment-local state is therefore
excluded unless a later contract explicitly makes it reusable.

## State that is never copied

Assignment copying does not copy, create, replay, or inherit:

- response-page PDFs, templates, issuances, page records, page IDs, or issuance IDs;
- Core route registrations or PDS2 route identity;
- scans, routed evidence, observations, scan-review state, or post-dispatch records;
- submission manifests, review records, minimum-requirement outcomes, observations,
  ratings, rationales, feedback, notes, page-management state, or workflow state;
- student or assignment exports;
- Academic Result Manifest revisions;
- Core Academic Work Registration;
- Core Publication Records, heads, withdrawals, supersession state, or catalog state;
- rosters, standards definitions/profiles, shared comments, or workspace settings.

The copy operation does not inspect student writing or teacher review content.

## Create-only target policy

Copying has no overwrite mode. Every target is preflighted before save and again at
commit. A target is eligible only when its work root is absent or contains solely
Quillan's empty canonical static managed-directory skeleton. Any file, link-like
entry, unexpected directory, assignment record, submission, evidence, export,
manifest, or other state causes the copy to fail without cleanup. A target
identity that already has an explicit Core Academic Work Registration also fails
closed, even if its Quillan work root is otherwise absent or empty.

This is stricter than ordinary assignment creation because replacing
`assignment.json` at an existing work identity could attach the copied definition to
historical descendants.

## Preview and concurrency

Planning is non-mutating. The plan binds the target preview to the exact source
`assignment.json` bytes. Before commit, Quillan reloads the canonical source and
aborts if those bytes changed. Target cleanliness, current standards references,
target rosters, and absence of target Academic Work Registration are also rechecked
immediately before the create-only write.

Multi-class persistence reuses Quillan's existing guarded assignment writer and its
conservative compensation behavior. The operation never claims filesystem-wide
transaction atomicity.

## Standards and target classes

The source profile and Focus Standard references are revalidated against the current
Core-owned workspace standards library. Every target class must have a valid current
Core roster. Copying never creates, repairs, remaps, or duplicates shared standards
or roster data.

## Teacher menu

Assignment Management includes `Copy writing assignment` immediately after ordinary
creation. The flow is:

```text
select exact source
-> review source
-> select target class(es)
-> choose target assignment ID
-> reuse/edit title
-> reuse/edit student prompt
-> review complete target assignment and destinations
-> explicitly save or cancel
```

The teacher is not re-prompted for the reusable review configuration listed above.
Cancellation before commit writes nothing.

## Direct CLI

The direct command is:

```powershell
quillan assignment copy `
  --source-class-id <source_class_id> `
  --source-assignment-id <source_assignment_id> `
  --target-class-id <target_class_id> `
  [--target-class-id <additional_target_class_id> ...] `
  --assignment-id <target_assignment_id> `
  [--title <target_title>] `
  [--prompt <target_prompt> | --prompt-file <path>] `
  (--yes | --dry-run)
```

Omitting `--title` or both prompt options reuses the source value. `--dry-run`
performs full source, standards, roster, target, identity, and path validation but
creates no directories or files. There is intentionally no copy-time `--overwrite`.

Copying stops after the new assignment record or records are written. It does not
print packets, create routes, register Academic Work, generate manifests, or publish
results automatically.

## Presets are separate

Assignment copying is source-assignment based. Reusable named review-configuration
presets are #381 and are not introduced by this workflow.
