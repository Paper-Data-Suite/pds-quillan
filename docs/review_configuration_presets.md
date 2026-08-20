# Reusable Review-Configuration Presets

Issue #381 introduces a Quillan-owned, workspace-level record for review
configuration that can be intentionally reused when creating new writing
assignments.

## Canonical path

```text
<PDS workspace root>/shared/review_configuration_presets/<preset_id>.json
```

The directory is created only when a preset is actually persisted. Presets are
not class records and do not live under an assignment work root.

## Schema v1

Every preset uses:

```text
schema_version = "1"
module = "quillan"
record_type = "review_configuration_preset"
```

The reusable configuration allowlist is exactly:

```text
writing_type
standards_profile_id
focus_standard_ids
review_unit
rating_scale
basic_requirements
minimum_requirement_policy
```

Preset metadata is:

```text
preset_id
title
description
created_at
updated_at
module_details
```

Unknown top-level fields are rejected.

## Assignment semantics

Preset review configuration is validated through the active schema-v2
assignment configuration rules. A preset additionally rejects duplicate Focus
Standard IDs and requires current Core standards/profile validation before it
may be persisted or applied.

Core remains authoritative for standards definitions and profiles. Presets
store references only.

## Snapshot, not inheritance

A preset is an assignment-creation convenience, not a live template. Applying a
preset must materialize its values into an ordinary schema-v2 `assignment.json`.
Existing assignments must never depend on a preset file remaining present or
unchanged.

Preset lineage is not required in assignment schema v2 or `module_details`.

## Explicit exclusions

Presets do not contain:

```text
class or assignment identity
assignment title or student prompt
student identity
submissions or evidence
minimum-requirement checks/outcomes
review-unit instances for student work
observations
ratings or rationales
teacher notes
feedback composition or feedback text
exports or reports
routes, scans, page/issuance identity
Academic Work Registration
Academic Result Manifests
Publication Records
```

Reusable Focus Standard feedback text remains owned by the existing
`focus_standard_comment_set` record family and is not copied into presets.

## Creation modes

The service supports two creation sources:

1. direct teacher-specified reusable configuration;
2. the explicit reusable-field allowlist extracted from one exact canonical
   assignment selected by `class_id + assignment_id`.

Source-assignment planning binds the proposal to the exact canonical
`assignment.json` bytes. Commit fails if the source changes, disappears, or
becomes invalid before persistence.

Neither mode writes during planning.

## Persistence

Preset persistence is create-only in #381. An existing `<preset_id>.json`
blocks creation; there is no overwrite mode.

Writes use Quillan's guarded atomic-record primitive with:

- canonical workspace containment;
- validated identifier-derived filenames;
- link-like ancestor rejection;
- preflight immediately before installation;
- exclusive create;
- exact-byte and schema verification after installation;
- explicit propagation of durability uncertainty.

A failed ordinary write removes newly created empty preset directories when it
can do so safely. A durability-uncertain write preserves the atomic primitive's
possibly-durable-path diagnostics instead of claiming rollback.

## Discovery

Preset discovery isolates malformed files from valid files and classifies each
JSON file as:

```text
valid
invalid
stale
```

`stale` means the preset is structurally valid but its current Core
standards/profile references cannot be validated. Quillan does not silently
drop, replace, remap, or infer standards.


## Direct CLI

```powershell
quillan review-preset list
quillan review-preset show --preset-id <preset_id>
quillan review-preset validate --preset-id <preset_id>
quillan review-preset create ... (--yes | --dry-run)
quillan review-preset save-from-assignment ... (--yes | --dry-run)

quillan assignment create <class_id> <assignment_id> `
  --title "<title>" `
  (--prompt "<text>" | --prompt-file <path>) `
  --preset-id <preset_id> `
  (--yes | --dry-run)
```

`show` can display a structurally valid but standards-stale preset with its
status; `validate` requires current standards validity.

## Teacher menu

Assignment Management includes:

```text
8. Review Configuration Presets
```

The submenu supports direct creation, save-from-assignment, and
view/validation. Existing Assignment Management options 1–7 are unchanged.

When current valid presets exist, Create Writing Assignment explicitly offers:

```text
1. Use a saved review preset
2. Configure review settings manually
B. Back
M. Main Menu
Q. Quit
```

The saved-preset path requires exact selection and a complete preset review.
The student-facing prompt remains a fresh assignment input. Quillan then shows
the normal complete assignment preview and requires the existing final save
authorization.

Immediately before assignment persistence, Quillan reloads the selected preset,
revalidates current Core standards, and verifies that the current preset model
still equals what the teacher reviewed. A changed, removed, invalid, or stale
preset fails without writing the assignment.

Recorder-backed acceptance asserts that accepted preset use does not re-prompt
for writing type, standards profile, Focus Standards, review-unit setup, rating
scale, basic requirements, or minimum-requirement policy. The #379 historical
baseline is not modified.
