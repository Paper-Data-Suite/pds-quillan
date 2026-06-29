# Synthetic Starter Review Materials

Quillan includes optional synthetic starter review materials for onboarding,
testing, and local development.

Starter materials are examples only. They are not official curriculum, not a
recommended grading policy, and not a substitute for teacher-created local
review materials.

## What Is Included

The starter set includes synthetic examples for varied written-work contexts:

* general written responses;
* lab reports;
* research responses;
* reflection journals;
* creative writing and creative project reflections.

The source files live under:

```text
examples/comment_banks/
examples/tag_banks/
examples/rubrics/
```

Each file is validated with the same runtime validators used for teacher-created
comment banks, tag banks, and rubrics.

## Installation

Use:

```text
Quillan -> Review Student Work -> Manage Review Materials -> Starter Materials
```

The submenu can preview, validate, install all, or install selected starter
materials.

Installed files are copied into the active workspace:

```text
shared/comment_banks/
shared/tag_banks/
shared/rubrics/
```

Existing workspace files are skipped by default. Bulk overwrite requires the
exact confirmation text `OVERWRITE`; lowercase `overwrite`, `yes`, and `y` do
not replace existing files.

## Safety Boundaries

Starter material installation creates or edits only:

```text
shared/comment_banks/
shared/tag_banks/
shared/rubrics/
```

It does not create assignments, rosters, scans, submissions, review records,
exports, pds-core standards files, pds-core standards profiles, or pds-core route
helpers. The starter files do not include pds-core `standard_ids`, so they stay
portable across workspaces with different standards libraries.

The examples are synthetic and subject-agnostic. Teachers should customize or
replace them before local classroom use.
