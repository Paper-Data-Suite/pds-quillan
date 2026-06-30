# Starter Review Materials

Quillan includes optional starter review materials for onboarding, testing,
local development, and teacher-editable classroom starting points.

Starter materials are examples and starting points only. They are not official
curriculum, not a recommended grading policy, and not a substitute for
teacher-created local review materials.

## What Is Included

The starter set includes two groups.

Synthetic examples are small portable examples for testing and onboarding:

* general written responses;
* lab reports;
* research responses;
* reflection journals;
* creative writing and creative project reflections.

NJ ELA starter materials are larger teacher-editable starter libraries for high
school ELA review. They include English 10 and English 12 comment banks, tag
banks, and rubrics for argument, informational/expository writing, literary and
comparative analysis, research writing, narrative/creative writing, poetry,
journals, reflections, open responses, short responses, short stories, and
memoir/personal narrative contexts.

The source files live under:

```text
examples/comment_banks/
examples/tag_banks/
examples/rubrics/
```

Each file is validated with the same runtime validators used for teacher-created
comment banks, tag banks, and rubrics.

See [`nj_ela_starter_materials.md`](nj_ela_starter_materials.md) for the NJ ELA
file inventory and standards-metadata notes.

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
helpers.

The synthetic examples do not include pds-core `standard_ids`, so they stay
portable across workspaces with different standards libraries. The NJ ELA files
include optional durable `njsls-ela:` standards metadata selected from the local
2023 NJSLS-ELA reference. Those references are metadata only: they do not
import standards, infer mastery, calculate grades, or evaluate student work.

Teachers should customize or replace starter materials before local classroom
use.
