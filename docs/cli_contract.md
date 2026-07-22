# Quillan CLI Contract

## Installed module availability

The profile is discoverable as
`paper_data_suite.modules: quillan = quillan.pds_module:get_module_profile` and is
safe to load before a workspace or scan is selected. This does not migrate the
teacher CLI or menu to PDS2 intake. QR extraction, mixed-module batch dispatch,
retained-source orchestration, routed evidence, scan review, and submission assembly
remain #338–#339 work.

## Direct Student Review Status

`quillan review-status <class_id> <assignment_id> <student_id> [--format text|json]`
prints compact record conditions, workflow state, aggregate review counts, and
feedback-export freshness for one student. Text is the default; JSON follows
the versioned [student review status contract](review_status_contract.md).
Missing, invalid, identity-mismatched, and orphaned selected records are
successful diagnostics. Plain-paper manifests are valid zero-digital-page
submissions. Fatal assignment/workspace errors are concise and nonzero.

This command is strictly read-only and performs no automated judgment. It does
not inspect evidence or student writing, assemble submissions, create reviews,
mutate workflow, or generate exports. It excludes teacher-entered and student
prose. Current Review Details remains the content-oriented teacher view;
`review-dashboard` remains the assignment-wide overview.

## Purpose and Status

This document defines Quillan's command-line contract during pre-1.0
development. It records:

* the command surface that is implemented now;
* the boundary between direct commands and the interactive menu;
* conventions for help, errors, paths, output, and exit status; and
* the compatibility expectations contributors should use when changing the
  CLI.

The CLI includes a developer-oriented, scriptable command layer and a
teacher-facing terminal menu. The menu now covers assignment management, roster
management, printable response pages, QR-aware scan intake, review navigation,
retained review-entry actions, guided export actions, workspace settings, help,
and exit.

As of the v0.8.6 standards-based review redesign gate, legacy generic
review-material workflows are no longer active CLI or menu workflows. The old
`add-tag`, `add-comment`, and `set-score` commands are intentionally removed
from argparse and must not write v1 tag, comment, or score review data.

This contract describes implemented behavior separately from future design. A
command or workflow documented elsewhere as planned is not part of the current
CLI until it is implemented, tested, and added here.

Quillan is pre-1.0. Command names, output, and conventions may evolve, but
changes should be intentional, documented, and covered by tests.

## Invocation

Installing the project exposes the `quillan` console command through the
entry point in `pyproject.toml`:

```text
quillan = "quillan.cli:main"
```

The supported user-facing invocation is therefore:

```powershell
quillan [command] [arguments]
```

Calling `quillan.cli.main()` from Python is useful for tests, but it is not a
separate public Python API contract.

## Assignment Review Dashboard

```powershell
quillan review-dashboard <class_id> <assignment_id> [--format text|json]
```

`text` is the default. `json` writes exactly one JSON document to standard
output using dashboard schema version `1`; it never names or creates an output
file. The command is direct, non-interactive, deterministic for unchanged
workspace data, and read-only. It shares its immutable dashboard service and
text formatter with Assignment Review Actions. See
[`review_dashboard_contract.md`](review_dashboard_contract.md) for population,
warning, ordering, read-boundary, and JSON details.

Missing work, malformed student records, stale exports, roster unavailability,
and active scan-review items are successful diagnostic results. Invalid
identifiers or assignment configuration, assignment identity/class mismatch,
unrecoverable routed discovery, and unsafe serialization are fatal and return
nonzero without a traceback.

## Direct Reusable Focus Standard Comments

The non-interactive `comments` namespace manages teacher-authored shared
reusable source material without requiring a class, assignment, student,
submission, review record, rating, or feedback-composition context:

```powershell
quillan comments list [--profile-id <profile_id>] [--writing-type <type>] [--standard-id <standard_id>] [--rating-value <number>]
quillan comments show <comment_set_id>
quillan comments create <comment_set_id> --profile-id <profile_id> --writing-type <type> --standard-id <standard_id> --label <label> --text <text> [--purpose <purpose>] [--rating-values <number,...>] [--teacher-tags <tag,...>]
```

Running `quillan comments` without a subcommand prints namespace help and
returns success. It does not resolve the workspace, scan comment files, create
directories, or write data.

`comments list` reads every JSON file beneath
`shared/focus_standard_comments` in case-insensitive filename order and keeps
comment order within each set. It shows only active, student-facing comments.
Optional filters are combined with logical AND: profile and standard IDs match
exactly; a supplied writing type must satisfy both set-level and comment-level
restrictions, where an empty array means all writing types; and a supplied
finite numeric rating matches either an unrestricted empty array or an array
containing that value. With no rating filter, rating-specific comments remain
visible. Purpose and teacher tags never affect compatibility. Valid results
are still printed when another file is invalid, followed by invalid-file
diagnostics and a nonzero status. An absent directory or no matches is a
successful empty result and creates nothing.

`comments show` resolves only a canonical comment-set ID, never an arbitrary
path. It displays complete set metadata and every stored comment in order,
including inactive and teacher-only comments, source provenance, usage data,
timestamps, and module details. Listing and showing are byte-for-byte
read-only; showing a missing or invalid set fails rather than treating it as
empty. The displayed file is current reusable source material, while existing
student reviews retain their earlier copied snapshots.

`comments create` creates one active, student-facing manual reusable comment
through the same validated append and atomic-write service used by feedback
composition. A missing set is created with schema version `1`, the supplied
profile and writing type, a generated title, a source-neutral description,
`grade_band: null`, and empty top-level module details. A compatible existing
set is appended without rebuilding it; profile or writing-type incompatibility
and malformed existing data fail before any replacement. The label supplies a
generated ID, with `_2`, `_3`, and later suffixes used for collisions.

Purpose defaults to `general` and accepts only `praise`, `next_step`,
`clarification`, `evidence`, `reasoning`, `organization`, `style`,
`conventions`, `revision`, and `general`. Rating values preserve order and may
be integers, finite floats, zero, or negative; blank elements, duplicates,
non-numbers, NaN, and infinities fail. Omission means all ratings. Teacher tags
are trimmed and normalized to unique ASCII-safe lowercase snake case in first
occurrence order; omission stores no required tag key. Tags remain display and
organization metadata only.

Manual source provenance uses `source.type: manual`, the creation timestamp as
`saved_at`, and null class, assignment, student, review, and feedback-comment
fields. Creation does not increment usage. Surrounding whitespace is trimmed
from required teacher-facing strings, but internal text, capitalization,
punctuation, and line structure are preserved exactly. Teachers must not put
student names, student IDs, assignment-specific private details, or other
identifying information in reusable text.

The create write boundary is exactly one selected
`shared/focus_standard_comments/<comment_set_id>.json` file. It does not touch
assignments, submissions, reviews, rosters, evidence, scans, exports, reports,
standards libraries, other reusable sets, legacy comment banks, Core, or
ScoreForm. This namespace does not provide editing, activation, deactivation,
deletion, migration, import, raw JSON patching, AI generation, inference,
automatic selection, scoring, grading, or feedback export.

## Direct Minimum-Requirement Review

The `requirements` namespace exposes the teacher-facing minimum-requirement
workflow as direct, non-interactive commands. Running `quillan requirements`
prints namespace help and exits successfully without resolving a workspace or
loading any records.

All three subcommands require a valid canonical assignment and an existing,
valid canonical `submission.json` for the requested class, assignment, and
student. Routed evidence alone is not review-ready; teachers must assemble the
submission first. Evidence-less plain-paper manifests are valid, and a valid
historical or unrostered submission does not require a current roster entry.

`requirements list` prints configured requirements, current checks, summary
counts, review state, and outcome in teacher-facing text. It is strictly
read-only. When `review.json` is absent it reports `not_started`, shows each
requirement as `not checked`, reports outcome `not_checked`, and creates
nothing. Stale checks whose keys are no longer configured are excluded from
configured completion counts.

`requirements set-check` accepts only a key currently derived from the
assignment's `basic_requirements`. Numeric keys are `paragraphs_min`,
`paragraphs_max`, `word_count_min`, and `word_count_max`; required-element keys
use `required_elements:<element>`. Labels and expected values come from the
assignment and cannot be supplied by the caller. `--met` becomes a boolean. A
supplied note is trimmed and stored; omission clears an earlier note. Updating
a key retains its check ID and does not infer or recalculate the outcome.

`requirements set-outcome` accepts exactly `met`, `unmet_continue_review`, or
`returned_without_full_review`. `met` requires every configured requirement to
be checked and met. `unmet_continue_review` requires at least one configured
unmet check; unchecked requirements may remain. Returning without full review
also requires a configured unmet check, an explicit nonblank note, and
`minimum_requirement_policy.allow_return_without_full_review: true` in the
assignment. No CLI flag overrides that policy.

These commands record teacher judgments only. They do not open evidence, count
words or paragraphs, detect required elements, run OCR or AI, infer outcomes,
grade, score, create observations or ratings, or compose feedback. The list
command writes nothing. The two set commands may create or replace only the
canonical
`classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/review.json`,
through the validated atomic review-record writer. They do not modify the
assignment, submission manifest, roster, evidence, scans, exports, reports, or
other suite data.

## Current Command Surface

The implemented command surface currently exposed through argparse is:

```powershell
quillan
quillan --help
quillan review-dashboard <class_id> <assignment_id> [--format text|json]
quillan review-status <class_id> <assignment_id> <student_id> [--format text|json]
quillan review-workflow set-state <class_id> <assignment_id> <student_id> --state <state> --yes
quillan assignment create <class_id> <assignment_id> --title <title> --writing-type <type> (--prompt <text> | --prompt-file <path>) --standards-profile-id <profile_id> --focus-standard-ids <id,...> [--review-unit-type <type>] [--review-unit-singular <label>] [--review-unit-plural <label>] [--rating-scale default] [--paragraphs-min N] [--paragraphs-max N] [--word-count-min N] [--word-count-max N] [--required-elements <items>] [--allow-return-without-full-review true|false] [--overwrite] [--yes | --dry-run]
quillan assignment show <class_id> <assignment_id>
quillan assignment validate <class_id> <assignment_id>
quillan printable-responses generate <class_id> <assignment_id> [--pages-per-student N] [--overwrite] (--yes | --dry-run)
quillan requirements list <class_id> <assignment_id> <student_id>
quillan requirements set-check <class_id> <assignment_id> <student_id> --requirement-key <key> --met true|false [--note <text>]
quillan requirements set-outcome <class_id> <assignment_id> <student_id> --outcome met|unmet_continue_review|returned_without_full_review [--note <text>]
quillan review-units show <class_id> <assignment_id> <student_id>
quillan review-units set <class_id> <assignment_id> <student_id> --count <positive_integer>
quillan review-units set <class_id> <assignment_id> <student_id> --units <units.json>
quillan observations list <class_id> <assignment_id> <student_id>
quillan observations set <class_id> <assignment_id> <student_id> --unit-id <unit_id> --standard-id <standard_id> --applicable true|false [--evidence-present true|false] [--rating <integer>] [--rationale <text>] [--include-in-feedback true|false]
quillan observations mark-complete <class_id> <assignment_id> <student_id> --yes
quillan ratings list <class_id> <assignment_id> <student_id>
quillan ratings set <class_id> <assignment_id> <student_id> --standard-id <standard_id> --rating <integer> [--rationale <text>] --include-in-feedback true|false
quillan ratings mark-complete <class_id> <assignment_id> <student_id> --yes
quillan feedback show <class_id> <assignment_id> <student_id>
quillan feedback set-options <class_id> <assignment_id> <student_id> --standard-id <standard_id> --include-overall-rating true|false --include-overall-rationale true|false [--observation-ids <id,...>]
quillan feedback add-comment <class_id> <assignment_id> <student_id> --standard-id <standard_id> --text <text> --include-in-feedback true|false [--save-for-reuse --reusable-label <label> [--reusable-text <text>] [--purpose <purpose>] [--teacher-tags <tag,...>] [--tag-current-rating true|false]]
quillan feedback use-reusable-comment <class_id> <assignment_id> <student_id> --standard-id <standard_id> --comment-set-id <comment_set_id> --comment-id <comment_id> --include-in-feedback true|false
quillan feedback mark-composed <class_id> <assignment_id> <student_id> --yes
quillan comments list [--profile-id <profile_id>] [--writing-type <type>] [--standard-id <standard_id>] [--rating-value <number>]
quillan comments show <comment_set_id>
quillan comments create <comment_set_id> --profile-id <profile_id> --writing-type <type> --standard-id <standard_id> --label <label> --text <text> [--purpose <purpose>] [--rating-values <number,...>] [--teacher-tags <tag,...>]
quillan roster create <class_id> --input <roster.csv> [--school-year YYYY-YYYY] [--overwrite] (--yes | --dry-run)
quillan roster show <class_id>
quillan roster validate <class_id>
quillan roster add-student <class_id> --student-id <student_id> --last-name <name> --first-name <name> --period <period> [--field <column=value> ...] (--yes | --dry-run)
quillan roster update-student <class_id> <student_id> [--last-name <name>] [--first-name <name>] [--period <period>] [--field <column=value> ...] (--yes | --dry-run)
quillan roster remove-student <class_id> <student_id> (--yes | --dry-run)
quillan printable-responses generate <class_id> <assignment_id> [--pages-per-student N] [--overwrite] (--yes | --dry-run)
quillan route-scan <source-image-or-pdf-or-folder>
quillan list-scan-review [--include-resolved] [--limit N] [--class-id <class_id>] [--assignment-id <assignment_id>] [--failure-category <category>]
quillan resolve-scan-review <failure_id> --action <action> [--message "..."] [--evidence-path <workspace-relative-path>] [--route-id <route_id> --route-class-id <class_id> --route-assignment-id <assignment_id>]
quillan list-post-dispatch-review <class_id> <assignment_id> [--include-resolved] [--limit N] [--category <category>]
quillan resolve-post-dispatch-review <class_id> <assignment_id> <failure_id> --action <action> [--message "..."]
quillan decode-scan <source-file> [--show-payload]
quillan assemble-submissions <class_id> <assignment_id>
quillan create-plain-paper-submission <class_id> <assignment_id> <student_id> [--yes | --dry-run]
quillan list-submissions <class_id> <assignment_id>
quillan pages list <class_id> <assignment_id> <student_id>
quillan pages exclude <class_id> <assignment_id> <student_id> --page N --yes
quillan pages restore <class_id> <assignment_id> <student_id> --page N --yes
quillan pages mark-needs-rescan <class_id> <assignment_id> <student_id> --page N --yes
quillan open-submission <class_id> <assignment_id> <student_id> [--page N] [--evidence-id <evidence_id>]
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan export-feedback <class_id> <assignment_id> <student_id> [--format markdown|pdf|both] [--overwrite]
quillan export-student-performance-summary <class_id> <assignment_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-comprehensive-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan workspace --help
quillan menu
```

Running `quillan` without a command launches the teacher-facing terminal menu.
Running `quillan workspace` without a subcommand prints top-level help and
exits successfully; it does not inspect or modify the workspace.

Running `quillan roster` without a subcommand prints roster help and exits
successfully without resolving or inspecting the workspace.

Running `quillan printable-responses` without a subcommand prints namespace
help and exits successfully without resolving the workspace, loading an
assignment or roster, checking an output target, or creating directories.

Running `quillan review-units` without a subcommand prints review-unit help
and exits successfully without resolving or inspecting the workspace.

Running `quillan observations` without a subcommand prints observation help
and exits successfully without resolving or inspecting the workspace.

The inventory above is authoritative and exhaustive for the implemented
top-level argparse commands and aliases. `set-review-state` changes only the
lightweight `submission.json.submission_state`; `review-workflow set-state`
changes only the standards-based `review.json.review_state` and is an explicit
manual override.

## Direct Standards-Based Review Lifecycle

After a canonical submission is available, a teacher can complete the ordinary
review lifecycle without entering the menu. Every judgment and every piece of
feedback below is teacher-entered, and phase completion is explicit:

```powershell
quillan requirements set-check `
  <class_id> <assignment_id> <student_id> `
  --requirement-key paragraphs_min --met true

quillan requirements set-outcome `
  <class_id> <assignment_id> <student_id> --outcome met

quillan review-units set `
  <class_id> <assignment_id> <student_id> --count 1

quillan observations set `
  <class_id> <assignment_id> <student_id> `
  --unit-id paragraph_1 --standard-id <standard_id> `
  --applicable true --evidence-present true --rating <rating> `
  --rationale "Teacher-entered observation." --include-in-feedback true

quillan observations mark-complete `
  <class_id> <assignment_id> <student_id> --yes

quillan ratings set `
  <class_id> <assignment_id> <student_id> `
  --standard-id <standard_id> --rating <rating> `
  --rationale "Teacher-entered overall rationale." `
  --include-in-feedback true

quillan ratings mark-complete `
  <class_id> <assignment_id> <student_id> --yes

quillan feedback set-options `
  <class_id> <assignment_id> <student_id> `
  --standard-id <standard_id> --include-overall-rating true `
  --include-overall-rationale true --observation-ids observation_0001

quillan feedback add-comment `
  <class_id> <assignment_id> <student_id> `
  --standard-id <standard_id> --text "Teacher-authored feedback." `
  --include-in-feedback true

quillan feedback mark-composed `
  <class_id> <assignment_id> <student_id> --yes

quillan export-feedback `
  <class_id> <assignment_id> <student_id> --format pdf

quillan review-status `
  <class_id> <assignment_id> <student_id> --format json
```

This sequence uses the dedicated commands rather than
`review-workflow set-state` to simulate progress. Export and status inspection
are separate operations; `review-status` is read-only.

## Direct Printable Response Packet Generation

`printable-responses generate` creates the same one-file class packet available
through Assignment Management's Printable Response Pages workflow. It requires
the requested canonical `assignment.json` and shared class `roster.csv`, keeps
students in stored roster order, and defaults to one numbered response page per
student. The command reports aggregate student, per-student page, and total PDF
page counts; it does not list student identities.

Exactly one of `--yes` and `--dry-run` is required. Dry-run validates identifier
syntax, assignment schema and path identity, assignment class membership,
roster structure and class identity, a nonempty student collection, the page
count, canonical output route, predecessor counts, and existing-target state.
It allocates no generation, artifact, issuance, page, or route IDs; does not call
the renderer, create `templates/`, generate QR images or temporary files, touch
an existing PDF, or write any file. `--overwrite` requires `--yes`; an existing
packet otherwise fails unchanged with guidance to use `--overwrite --yes`.

Actual generation may create the selected assignment's `templates/` directory
and create or replace only:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/templates/printable_response_pages.pdf
```

All displayed paths are workspace-relative POSIX paths. The direct command
does not accept alternate output paths or filenames and does not open the PDF
or its folder. It uses the shared managed PDS2 transaction also used by the
menu. The transaction writes and reload-verifies one Core route per immutable
physical page, renders a same-directory temporary PDF, issues new records,
atomically installs the packet, and only then supersedes predecessors.
Assignment, roster, class,
submission, review, evidence, scan, reusable-comment, feedback, and report data
remain unchanged. Generation performs no scan processing, QR decoding, OCR,
handwriting recognition, AI, inference, assembly, review, grading, feedback,
or export work.

## Direct Submission Page Management

The `pages` namespace exposes the same shared submission-page services used by
Manage Submission Pages in the teacher menu. Bare `quillan pages` prints
namespace help and succeeds without resolving a workspace, loading a manifest,
inspecting routed evidence, creating directories, or writing files.

`pages list` loads only the requested student's canonical
`submissions/<student_id>/submission.json`. It does not scan sibling students,
the roster, assignment configuration, or routed evidence. It reports canonical
identity and path, lightweight submission state, expected page count, manifest
timestamps, page-state counts, pages lacking selected evidence, and page and
evidence summaries. Pages are displayed by ascending logical `page_number`;
evidence remains in stored order. A null selection is displayed as `none` and
is never inferred or repaired. Listing never opens or stats evidence files and
does not normalize or rewrite the manifest.

The mutation commands require `--page` with a positive logical page number
that exists in the manifest and the explicit non-interactive confirmation
`--yes`. Omission is an argument error; no prompt or implicit confirmation is
used. These commands do not accept arbitrary manifest paths.

Exclusion retains the page and every evidence record, clears selection, saves
each evidence record's current role and state as temporary pre-exclusion
metadata, and marks it excluded from active review. It does not delete files.
Restore uses that preserved role and state, including a valid prior lack of
selection. For legacy excluded records without preservation metadata, zero,
one, and multiple evidence records safely restore to missing, uniquely selected
present, and unselected duplicate states respectively. No duplicate candidate
is chosen automatically.

Marking needs rescan retains every evidence record, clears selection, and makes
the records candidates needing rescan; an empty page remains evidence-less.
Changing an excluded page to needs rescan removes obsolete exclusion-transition
metadata so a later exclude/restore cycle returns to the current rescan state.
Page state and top-level `submission_state` are distinct: page management never
changes the latter.

A valid plain-paper manual manifest lists successfully as zero digital pages;
the physical paper remains outside Quillan. Page mutations fail because no
digital page exists. A missing manifest is not treated as plain paper: every
command fails with submission-assembly guidance and never assembles or creates
a manifest or review record.

The sole write boundary is the selected student's canonical `submission.json`,
validated in full and atomically replaced. Created timestamps, evidence paths,
retained-source provenance, and unrelated module metadata are preserved;
successful changes update only the manifest update timestamp and page-management
metadata. Review records, assignments, rosters, routed and retained files,
ratings, observations, feedback, exports, and reports remain untouched. These
commands perform no evidence inspection, OCR, handwriting recognition, AI,
grading, scoring, feedback composition, or export work.

## Direct Focus Standard Feedback Composition

The `feedback` namespace exposes the menu's composition model through five
direct, non-interactive commands. Bare `quillan feedback` prints namespace
help without resolving a workspace. Every subcommand requires a valid
canonical assignment and assembled `submission.json`; write commands also
require an existing valid `review.json`. A valid historical, unrostered, or
plain-paper submission remains usable. Routed evidence without a manifest
produces assembly guidance and is never assembled automatically.

`feedback show` is strictly read-only. It reports canonical paths, review and
completion state, global flags and counts, then lists assignment Focus
Standards in configured order. Each standard shows its current rating and
rationale, feedback options, selected observations, eligible candidate
observations, stored comment snapshots, and compatible reusable comments with
the set/comment IDs needed for selection. A missing review is reported as
`not_started` with empty choices; malformed reviews fail. Returned reviews are
displayable for audit but clearly unavailable for full composition.

`feedback set-options` replaces one configured Focus Standard's complete
rating/rationale choices and selected-observation list. Both booleans are
required. Omission of `--observation-ids` clears the list; comma order is
preserved and blanks or duplicates fail. An observation must exist, belong to
the same standard, and already have `include_in_feedback: true`; the command
never enables it. The shared service creates a missing standard-feedback
record or updates the existing record while preserving comments and module
metadata, and recomputes the global observation-inclusion flag.

`feedback add-comment` copies the teacher's text after outer whitespace
trimming without rewriting its internal content. Inclusion is explicit and no
export occurs. `--save-for-reuse` requires a nonblank label. Separately
approved `--reusable-text` is stored when supplied; otherwise the custom text
is reused. Teachers must remove student-specific details from reusable text.
Purposes are `praise`, `next_step`, `clarification`, `evidence`, `reasoning`,
`organization`, `style`, `conventions`, `revision`, and `general` (the
default). Teacher tags use the shared lowercase snake-case normalization.
`--tag-current-rating true` stores the current rating restriction when a
rating exists; omission or `false` stores no rating restriction.

`feedback use-reusable-comment` accepts only an active, student-facing comment
compatible through the shared lookup rules with the assignment standards
profile, writing type, Focus Standard, and current rating. Selection copies
the exact reusable text into the review as a stable snapshot, assigns the next
review-wide sequential feedback-comment ID, and increments source usage once.
Later source edits do not change that snapshot.

Every standard-specific command validates against the assignment's configured
Focus Standards, not merely the shared standards library. Feedback edits move
`feedback_composed`, `ready_for_export`, and `exported` back to
`ratings_complete`; earlier states remain unchanged and export metadata and
files are preserved. `mark-composed` requires `--yes`. Missing ratings,
feedback records, selected observations, or included comments produce summary
warnings but do not block this explicit action. Returned-without-full-review
records reject all four write commands.

Write boundaries are exact: show writes nothing; set-options, ordinary
add-comment, and mark-composed modify only canonical `review.json`; saving for
reuse modifies that review and its service-selected comment set; reusable
selection modifies that review and the explicitly selected comment set's
usage metadata. Assignment and submission records, evidence, scans, rosters,
unrelated comment sets, exports, reports, Core, and ScoreForm are unchanged.
Composition is separate from export. These commands never inspect evidence,
run OCR or handwriting recognition, invoke AI, generate or rewrite language,
infer observations or ratings, grade, score, auto-select, auto-complete, or
auto-export.

Running `quillan ratings` without a subcommand prints ratings help and exits
successfully without resolving or inspecting the workspace.

### `review-units` commands

`review-units show` loads the canonical assignment and assembled submission
manifest, plus `review.json` when it exists. It reports assignment-derived
unit labels, canonical paths, review state, units, and observation counts. If
there is no review record it reports `not_started`, zero units, and zero
observations without creating a file or directory.

`review-units set` is an immediate, non-interactive replacement operation.
Exactly one of `--count` and `--units` is required. Count mode generates
sequences `1..N`. JSON mode reads a non-empty UTF-8 JSON array whose objects
may contain only `sequence`, `label`, `page_number`, and `evidence_id`.
`sequence` is explicit, unique, positive, non-boolean, and sorted ascending
before writing; it need not be contiguous. Labels must be nonblank. Page and
evidence references are validated only against submission-manifest metadata,
including page/evidence membership. Unknown fields and raw record fields such
as `unit_id`, `unit_type`, `standard_observations`, and `module_details` are
rejected.

The assignment supplies `review_unit.type` and its singular and plural labels.
Canonical IDs are `<type>_<sequence>` and omitted labels become the title-cased
singular label plus the sequence, such as `paragraph_2` / `Paragraph 2`.
Stable canonical IDs preserve their observations when labels or evidence
metadata change. Removed IDs remove their observations, and stale feedback
observation references are cleaned while feedback records, ratings, minimum
requirements, exports, private notes, metadata, and surviving observations
remain intact.

### `observations` commands

The `observations` namespace exposes review-unit Focus Standard observations
as direct, non-interactive commands. All commands validate the canonical
assignment, require an existing valid canonical `submission.json`, and validate
an existing `review.json` rather than treating a malformed or mismatched record
as empty. Routed evidence is not assembled automatically. A valid plain-paper
manual submission and a valid unrostered historical submission are accepted.

`observations list` is strictly read-only. It reports canonical paths, review
state, review-unit and Focus Standard totals, expected/recorded/unrecorded pair
counts, applicability, evidence, unit-rating and feedback-inclusion counts, and
the assignment rating scale. It then displays every active unit-standard pair,
with units ordered by `sequence` and standards ordered by the assignment's
`focus_standard_ids`. Recorded rows include the observation ID, applicability,
evidence presence, optional unit-level rating and assignment label, rationale,
feedback eligibility, and timestamp. Unit-level ratings are clearly separate
from overall Focus Standard ratings. When no review or no units exist, list
reports zero units and explains that units must be defined first; it returns
success and creates nothing. A `returned_without_full_review` record remains
readable.

`observations set` requires an existing review with defined units. `--unit-id`
must match an active unit and `--standard-id` must match an assignment Focus
Standard. The command completely replaces the editable values for that pair;
it is not a sparse patch. A new pair receives the next globally unique
`observation_NNNN` ID. Updating a pair preserves its observation ID and clears
an earlier rating or rationale when the corresponding optional argument is
omitted.

`--applicable` accepts exactly `true` or `false`. Applicable observations
require an explicit `--evidence-present true|false`; this records only whether
the teacher found related evidence and does not imply mastery. `--rating` is
optional for applicable observations. When present it must be an integer value
from the current assignment's `rating_scale.levels`; when omitted the stored
rating is `null`. Not-applicable observations reject `--evidence-present` and
`--rating`, and store both fields as `null`. Rationale text is trimmed; omission
or blank text stores `null`. Omitted `--include-in-feedback` defaults to `true`
for applicable observations and `false` for not-applicable observations, while
either default may be explicitly overridden.

Feedback eligibility belongs to the observation. Setting it does not compose
feedback or add/remove IDs in `feedback.standard_feedback`. Observation writes
do not create or alter `overall_standard_ratings`. They preserve unrelated
units, observations, minimum-requirement data, feedback records and comments,
exports, notes, top-level metadata, and the original creation timestamp. The
shared observation service performs review-state transitions and refuses to
modify `returned_without_full_review` records until the minimum-requirements
outcome changes.

`observations mark-complete` is an explicit teacher-controlled phase transition.
It requires `--yes`, never prompts, and calls the same shared completion service
as the teacher menu. A valid existing review with at least one review unit is
required. A missing review is not created, and missing units produce guidance to
define review units first. The returned-without-full-review guard also applies;
the minimum-requirement outcome must change before completion can proceed.

Complete observation coverage is not required. Some, most, or every configured
unit-standard pair may remain unobserved, including when the review has zero
observations. The command still sets `review_state` to `observations_complete`
and updates `updated_at`. It reports the exact missing-pair count returned by the
shared service and, when that count is nonzero, warns that completion occurred
with unobserved pairs and that no observations were created. It does not infer
or fill applicability, evidence presence, ratings, rationales, or feedback
choices.

List writes nothing. Set and mark-complete may modify only
`classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/review.json`
through the shared validated atomic writer. Completion changes only
`review_state` and `updated_at`; it preserves units, observations, minimum-
requirement data, overall ratings, feedback and comments, private notes, export
metadata, module details, array ordering, and `created_at`. No observation
command opens evidence, parses PDFs or images, decodes QR codes, runs OCR,
handwriting recognition, or AI, infers any teacher judgment, calculates overall
ratings, mastery, percentages, grades, or scores, assembles submissions, mutates
pages, composes feedback, generates exports, or modifies assignments,
submissions, rosters, evidence, reports, Core data, or ScoreForm data.

### `ratings` commands

The `ratings` namespace exposes teacher-entered overall Focus Standard ratings
as direct, non-interactive commands. All commands require a valid canonical
assignment and assembled `submission.json`; routed evidence is not assembled
automatically. Plain-paper manual and valid unrostered submissions are
accepted. An existing malformed, mismatched, unsupported, or noncanonical
`review.json` is an error rather than an empty review.

`ratings list` is strictly read-only. It reports canonical paths, review and
completion states, every assignment-owned rating-scale level, rating and
missing counts, and every assignment Focus Standard in configured order. Each
standard shows its current overall value and assignment label or `not rated`,
rationale, feedback-inclusion choice, update timestamp, and advisory
observation counts. With no review it reports `not_started`, zero ratings,
zero observations, and creates nothing. Stored ratings no longer configured by
the assignment appear separately for audit and do not count toward completion.
Returned-without-full-review records remain listable, with ratings identified
as not applicable to that completed workflow state.

`ratings set` requires an existing review and completely replaces one
configured standard's rating, optional rationale, feedback-inclusion choice,
timestamp, and rating-level module details. It prevents duplicates and reports
`created` or `updated`. `--standard-id` must occur in the assignment's current
`focus_standard_ids`; existence in a shared standards library is insufficient.
`--rating` must be an exact integer value from the assignment-owned scale, so
zero, negative, gapped, and non-1-to-4 scales remain valid. Supplied rationale
is trimmed; omission or blank text stores `null` and clears an earlier value.
The direct CLI requires `--include-in-feedback true|false` and has no default.
That choice does not compose feedback or change feedback options.

Observation summaries and warnings are advisory. Missing units, missing or
incomplete observations, and unobserved pairs never block `ratings set` and
never produce or infer a rating. The shared service owns state transitions:
early states return to `observations_in_progress`, downstream composed/export
states return to `ratings_complete`, and other documented rating states remain
unchanged. Existing observations, feedback, exports, notes, requirement data,
metadata, and the original creation timestamp are preserved.

`ratings mark-complete` requires the explicit `--yes` flag and never prompts.
It calls the shared completion service and may mark `ratings_complete` with all,
some, or none of the assignment Focus Standards rated. Missing ratings are
counted and warned about, but never filled from observations or placeholders.
Observation readiness is not a completion gate. Both write commands reject a
`returned_without_full_review` record until its minimum-requirements outcome
changes.

List writes nothing. Set and mark-complete may modify only canonical
`classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/review.json`
through the validated atomic writer. They do not modify assignments,
submission manifests, rosters, evidence, scans, observations, feedback
composition, exports, reports, Core, or ScoreForm. They do not open evidence,
parse PDFs or images, run OCR, handwriting recognition, or AI, infer or average
ratings, calculate mastery, percentages, grades, or scores, generate feedback,
or complete ratings automatically after a set operation.

Both commands require a valid canonical `submission.json`, including for
plain-paper submissions without digital evidence. They do not require current
roster membership and never assemble a submission automatically. `show` is
read-only and remains available for returned submissions. `set` may create or
atomically update only the canonical `review.json` and rejects a
`returned_without_full_review` record. Neither command opens evidence files,
parses PDFs or images, runs OCR or AI, counts or segments writing, or creates
observations, ratings, feedback, or grades.

The teacher-facing menu may also be launched explicitly:

```powershell
quillan menu
```

Bare `quillan` and the explicit `menu` command launch the same interactive
menu. The other commands remain direct and non-interactive.

### `roster` commands

The `roster` namespace manages canonical shared roster artifacts under
`classes/<class_id>/`. All commands resolve the active Paper Data Suite
workspace through PDS Core; Quillan has no separate roster workspace setting.
Direct roster commands never enter the menu or prompt with `input()`.

`roster create` loads `--input` through the shared roster CSV loader. The CSV
must contain `class_id`, `student_id`, `last_name`, `first_name`, and `period`,
with at least one valid row. Its class ID must exactly match the positional
class ID. The validated roster is written through the shared canonical writer,
not copied byte-for-byte. Student IDs remain strings, so leading zeros are
preserved. Optional columns, their order, blank values, and row order are also
preserved.

Creation uses an explicit valid `--school-year` when supplied, otherwise the
workspace's active school year. If neither exists, creation fails with guidance
and writes nothing. A confirmed creation writes exactly the paired canonical
artifacts `classes/<class_id>/roster.csv` and
`classes/<class_id>/class.json`. If either target already exists, replacement
requires both `--overwrite` and `--yes`; the paired plan is fully validated
before writing. A failed new paired write removes artifacts newly created by
that operation.

`roster show` and `roster validate` are read-only. Both load the canonical CSV
through PDS Core. Show displays every required and optional column, the student
count, paths, and the class school year when valid metadata exists. Missing
metadata is reported as `not set`; malformed metadata is reported without a
traceback. Validate also checks canonical folder identity and any existing
metadata. Missing metadata remains valid for older class folders, while invalid
existing metadata makes validation fail.

`add-student`, `update-student`, and `remove-student` construct a new immutable
roster through shared PDS Core mutation functions and replace only
`classes/<class_id>/roster.csv` after `--yes`. They never modify `class.json`.
Add appends a student; update preserves both row position and the positional
student ID as stable identity; remove affects only the active roster and cannot
remove its final student.

Optional values use repeatable `--field column=value` arguments. Only columns
already present in the roster's optional schema are allowed. Required columns,
unknown columns, and duplicate keys fail. Add fills omitted optional values
with blank strings. Update retains omitted values, while `--field name=` clears
that value. These commands cannot add CSV columns.

Every roster write requires exactly one of `--yes` or `--dry-run`. Omitting
both fails without prompting or writing. Dry runs perform normal validation,
show the target and resulting count, and create no directories or files.
Active-roster removal does not traverse or delete class metadata, assignments,
submission manifests, reviews, scans, printable PDFs, evidence, notes,
observations, ratings, feedback, exports, reports, historical results, or other
module data.

### `assignment create`, `show`, and `validate`

```powershell
quillan assignment create <class_id> <assignment_id> ...
quillan assignment show <class_id> <assignment_id>
quillan assignment validate <class_id> <assignment_id>
```

`assignment create` builds the same schema-version-2 shape and uses the same
defaults and structural validation as menu assignment creation. It requires an
existing canonical class roster and validates the selected profile and Focus
Standards against the active workspace's PDS Core standards library. New writes
require `--yes`; replacing an existing config requires both `--overwrite` and
`--yes`. `--dry-run` validates and reports the canonical path without creating
an assignment directory or writing files.

New menu and CLI assignments include equal initial `created_at` and `updated_at`
values as timezone-aware UTC ISO 8601 strings and include an empty
`module_details` object.

The prompt may be supplied inline with `--prompt` or read as UTF-8 text with
`--prompt-file`. Basic paragraph, word-count, and required-element options are
optional. Review-unit labels and the four-level standards rating scale default
to the same values used by the menu.

`assignment show` loads the canonical workspace config, validates its structure
and path identity, and prints the shared assignment summary. `assignment
validate` additionally validates the standards profile and every Focus Standard
against the active workspace library. Both commands are read-only. They reject
older records missing required schema-version-2 fields and do not normalize or
rewrite them.

These commands write or inspect only
`classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json`; they do not
create submission, review, evidence, scan, export, Core, or ScoreForm data.

### Retired raw-path interfaces

`validate-assignment <path>` and `open-evidence <path>` are not public
commands. Assignment inspection and validation require the canonical
`<class_id> <assignment_id>` identity. Evidence opening requires the canonical
`<class_id> <assignment_id> <student_id>` identity and may be narrowed by
logical page and evidence ID. Argparse rejects the retired command names with
exit status 2.

### `workspace show`

```powershell
quillan workspace show
```

Uses the shared `pds-core` workspace status API to report:

* the resolved Paper Data Suite workspace root;
* the source used to resolve it;
* whether the root exists;
* whether it is a directory;
* whether it is writable;
* the shared configuration-file path; and
* the default workspace root.

This command reports status only. It does not create, select, repair, or
change a workspace. A reported `no` value is status information and does not
by itself make the command fail.

### `workspace set`

```powershell
quillan workspace set <path>
```

Uses shared `pds-core` behavior to validate/create the supplied workspace root
and save it as the Paper Data Suite workspace preference. This operation does
not move, copy, migrate, delete, archive, or reorganize existing Quillan or
Paper Data Suite files. If `PDS_WORKSPACE_ROOT` is set, the environment value
still takes precedence over the saved preference.

### `workspace validate`

```powershell
quillan workspace validate
```

Resolves the active root using the shared precedence rules, creates the
workspace and shared metadata if needed, and verifies that it is writable. It
does not prompt for a different root or change the saved preference.

### `workspace reset`

```powershell
quillan workspace reset
```

Clears only the saved Paper Data Suite workspace-root preference. It does not
delete workspace directories or files. The command reports the newly resolved
root after reset; `PDS_WORKSPACE_ROOT`, when set, still takes precedence.

All workspace commands use shared `pds-core` APIs and configuration. Quillan
does not maintain a separate workspace config. Expected workspace errors are
reported as `Error: ...` without a traceback and return a nonzero status.

## Direct CLI and Menu Boundary

Direct CLI commands and the interactive menu serve different use cases.
They may call the same application services, but neither should implement
business rules independently.

### Direct CLI commands

A direct command should be preferred when the operation:

* has an explicit name and a bounded set of arguments;
* can run without a sequence of interactive prompts;
* is useful in development, diagnostics, scripts, or repeatable workflows;
* can report a clear success or failure status; and
* does not require the user to navigate a teacher-facing session.

Validation, status inspection, import/export, and other discrete operations
are natural direct-command candidates. Direct commands should remain usable
without the menu.

### Interactive menu

Bare `quillan` launches the current menu. `quillan menu` is an explicit alias
for the same behavior.

The top-level menu provides:

```text
1. Assignment Management
2. Review Student Work
3. Roster Management
4. Workspace Settings
5. Help
Q. Quit
```

Menu workflows should orchestrate reusable application functions. They should
not become the only route to core operations, and they should not duplicate
business rules that already live in CLI handlers or domain modules.

**The menu should look and feel like a modern application menu, not a dump of
CLI commands or a legacy operator console.** Menus therefore use staged list,
detail, action, confirmation, and result screens with compact labels and a
small number of context-relevant choices.

**Screen clearing and redrawing after a teacher selects an option is the
default. Information remains visible only when it is essential or directly
useful for the teacher's current action.** This is a mandatory behavioral
contract, not a visual suggestion:

* parent menus are compact;
* selection lists are compact;
* detail appears only after selection;
* action screens are focused on the selected identity and current task;
* confirmation screens are concise;
* result workflows clear before rendering the result;
* result screens are concise, then pause for acknowledgment;
* returning redraws the parent screen without accumulated child output;
* direct non-interactive CLI commands are exempt from terminal screen clearing;
  and
* context is retained intentionally only when it is needed for the teacher's
  current decision.

#### Assignment Management

Assignment Management provides:

```text
1. Create writing assignment
2. View/validate assignment
3. Printable Response Pages
4. Back
```

Creation selects one class with an existing canonical roster, prompts for the
fields in the active schema version `2` assignment config contract, and writes:

```text
<workspace_root>/classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
```

Assignment creation prompts for:

* assignment title;
* assignment ID;
* writing type;
* student prompt;
* pds-core standards profile selection;
* pds-core Focus Standard selection stored as `focus_standard_ids`;
* review-unit configuration;
* rating-scale configuration;
* basic requirements; and
* minimum-requirement return policy.

`writing_type` is currently a typed teacher-entered value, not a discovered or
selectable list.

`standards_profile_id` is selected from the active pds-core standards library
and stored as a durable pds-core `profile_id`. Focus standards are selected
from that profile and stored as durable pds-core `standard_id` values.

An existing config is replaced only after exact `OVERWRITE` confirmation.

View/validate selects a canonical class and assignment identity, uses the
existing assignment loader and validator, prints a concise summary, and does
not rewrite the file. It does not accept an arbitrary assignment JSON path.

These workflows do not add assignment editing, deletion, import, scoring,
feedback, generic tagging, reports, scan routing, OCR, or AI.

#### Roster Management

Roster Management provides:

```text
1. Create class roster
2. View class roster
3. Edit class roster
4. Validate class roster
5. Back
```

These menu-only workflows use shared `pds-core` class and roster APIs.
Canonical rosters are stored at:

```text
<workspace_root>/classes/<class_id>/roster.csv
```

Student IDs remain strings, including leading zeros, and existing optional
columns remain in their original order. Viewing and validation are read-only.

Editing stages shared immutable roster mutations in memory. Add, edit, and
active-roster removal do not write immediately. Saving requires typing `SAVE`;
canceling staged changes requires typing `DISCARD`.

Active-roster removal never deletes assignments, submissions, printable PDFs,
scans, reports, tags, scores, feedback, or historical evidence.

#### Printable Response Pages

Printable Response Pages is reached through Assignment Management and provides:

```text
1. Generate class packet
2. Back
```

Generation selects a class with an existing canonical roster, then selects a
canonical assignment config for that class. Invalid configs are identified and
cannot be selected; the assignment must include the selected class in
`class_ids`.

Blank pages-per-student input defaults to `1`, and nonblank input must be a
positive integer.

The current output mode is one combined class packet PDF:

```text
<workspace_root>/classes/<class_id>/modules/quillan/work/<assignment_id>/templates/printable_response_pages.pdf
```

An existing packet is replaced only after exact `OVERWRITE` confirmation.

The workflow uses the existing roster-aware printable generator and does not
alter roster or assignment data. It does not add individual PDFs, scan
routing, OCR, review, scoring, feedback, reports, AI, or a direct printable
CLI command.

#### Scan Intake / Route Paper Responses

Scan Intake / Route Paper Responses is reached through Review Student Work and
prompts for a local scan source path:

```text
Scan file or folder path (leave blank to cancel):
```

Blank input cancels without routing files.

Nonblank input trims surrounding whitespace and removes one matching pair of
surrounding quotes, so pasted Windows paths such as
`"C:\Users\Teacher\Desktop\scan folder"` work as a single path.

The source may be a supported image file, a PDF, or a non-recursive folder
containing supported image/PDF scan files.

The workflow uses the same QR-aware implementation path as:

```powershell
quillan route-scan <source>
```

It does not expose payload mode.

It prints the retained PDS2 dispatch-stage summary: selected and retained
sources, source failures, enumerated and terminal pages, dispatch successes,
Core dispatch failures, pre-dispatch failures, Quillan integration failures,
persisted review occurrences, review-persistence failures, skipped entries,
failure categories, and the exact batch status.

It prints the same retained-source dispatch summary as the direct command,
followed by observation persistence, routed-evidence, and manifest assembly
counts.

If review is required, the preserved-failure caution is printed.

The workflow automatically assembles observation-backed submissions after safe
persistence. It does not move or archive original sources, create `review.json`,
run OCR, score, tag, generate feedback, or perform AI work.

#### Review Student Work

Review Student Work provides guided scan intake, class, assignment, and
student/submission navigation plus retained review-entry and export actions.

The first Review Student Work menu provides:

```text
1. Assignment Review Actions
2. Scan Intake / Route Paper Responses
R. Resolve Scan Review Items
B. Back
```

The workflow lists available classes from the active workspace, lists
assignments for the selected class, and prints the current assignment
submission status through the existing status formatting path.

Roster students remain visible even when they do not yet have an assembled
submission.

After a class and assignment are selected, the assignment-level review actions
menu provides:

```text
1. Select student/submission
2. Assemble routed submissions
3. Export Comprehensive Class Summary
4. Export Standards Summary
5. Export Student Performance Summary
6. Back
```

Selecting a student/submission lets the teacher pick a student by number. The
selected-student view shows a compact current review summary with class,
assignment, student, submission/evidence status, review state, and existing
`review.json` counts when a valid review record is already present. Long file
paths are reserved for detail/output actions.

Assignment-level student selection clears the prior assignment-status summary
before showing the student list. Nested review selections clear between levels
so each screen stands on its own. `B. Back` returns to the immediate previous
selection screen.

Terminal review screens should clear and redraw after a teacher selects an
option by default. Retaining prior output is intentional only when that
information provides necessary context for the current action. Parent
dashboards may show broader status, but focused action screens should show
only the current task, selected student, selected review unit/requirement/Focus
Standard when relevant, and immediately useful status. Confirmation screens
should be concise, and `Back` should return to the previous menu with its
fuller context restored. Prior menu options, parent dashboard blocks, and
debug-style details should not remain on screen merely because the terminal
transcript stacked them there.

The selected-student review menu provides:

```text
1. Open submission evidence
2. View current review details
3. Review minimum requirements
4. Review units and Focus Standard observations
5. Overall Focus Standard ratings
6. Compose Focus Standard feedback
7. Manage submission pages
8. Add teacher note
9. Update review workflow state
10. Export student feedback
11. Refresh summary
12. Back
```

Opening submission evidence delegates to the same existing safe selected
evidence-opening path as:

```powershell
quillan open-submission <class_id> <assignment_id> <student_id>
```

Missing manifests or missing selected evidence are reported clearly.

`Review minimum requirements` lists checks generated from the selected
assignment's `basic_requirements`: minimum/maximum paragraph count,
minimum/maximum word count, and each configured required element. The teacher
records each check as `1` for met/yes or `2` for not met/no. Quillan stores
the teacher-entered boolean in `minimum_requirement_checks` and stores the
teacher-selected result in `minimum_requirement_outcome`. It does not count
words or paragraphs, parse writing, run OCR, use AI, infer a result, or change
standards ratings.

`Review units and Focus Standard observations` lets the teacher define or
replace review units and record teacher-entered observations for assignment
Focus Standards. Observations may be applicable or not applicable, may record
teacher-entered evidence presence, may omit a rating, and may be included or
excluded from feedback consideration.

`Overall Focus Standard ratings` summarizes observations by Focus Standard and
lets the teacher enter overall ratings from the assignment `rating_scale`.
Ratings are not inferred from observations. Marking ratings complete is an
explicit teacher action.

`Compose Focus Standard feedback` stores per-standard rating/rationale
inclusion choices, selected observation IDs, custom comments, reusable Focus
Standard comment snapshots, and save-for-reuse choices under
`feedback.standard_feedback`. Marking feedback composed is explicit.

Retained guided review-entry actions reuse the same underlying review services
as the direct commands:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan review-workflow set-state <class_id> <assignment_id> <student_id> --state <state> --yes
```

The generic structured-tag, comment-bank, rubric, and criterion-score runtime
workflows have been removed. Quillan does not create, import, edit, retire,
reactivate, or authoritatively validate pds-core standards from review mode.

`Update review workflow state` displays the allowed states with
teacher-facing descriptions and requires confirmation before saving. This is
an explicit workflow status change, not a grade, and is not inferred from
notes, tags, comments, scores, or exports.

Guided export actions reuse the same underlying export services as the direct
commands:

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-student-performance-summary <class_id> <assignment_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-comprehensive-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

Menu export actions preserve overwrite protection. Student feedback export
explains that it formats the current review record and does not rescore work
or generate AI feedback. Existing export files are not replaced unless the
teacher explicitly chooses overwrite.

Major selected-student actions clear and reframe the action screen before
prompting. `B`/Back cancels safely; blank input means Back only where the
screen says so. Cancellation does not write review records, submission
manifests, exports, scans, rosters, assignments, review materials, pds-core
workspace preferences, or pds-core route/standards files.

The Review Student Work menu does not automatically assemble submissions,
route scans, run OCR, parse evidence contents, score work automatically, infer
mastery, generate AI feedback, or perform AI work.

Selected Student Review includes Manage Submission Pages. Teachers can exclude
a page from active review, restore an excluded page, or mark a page as needing
rescan after confirmation. These actions update only the selected student's
`submission.json`, validate before writing, preserve evidence records and
routed files, and do not modify review notes, tags, comments, scores, feedback
exports, rosters, assignments, review materials, pds-core standards, or
pds-core routes.

#### Workspace Settings

Workspace Settings provides:

```text
1. Show current workspace
2. Set workspace folder
3. Validate/create current workspace
4. Reset saved workspace preference
5. Back
```

Showing the workspace calls the same status behavior as:

```powershell
quillan workspace show
```

and remains read-only.

Setting prompts for a folder; blank input cancels without changing the saved
preference. Nonblank input validates/creates the folder and saves it through
shared `pds-core` configuration.

Validate/create operates on the currently resolved root.

Reset clears only the saved preference and then reports the current resolved
root.

The menu warns that setting does not migrate files, resetting does not delete
files, and `PDS_WORKSPACE_ROOT` still takes precedence.

The workspace submenu does not include school-year settings.

#### Help, Exit, and Shared Menu Behavior

Menu help describes Quillan as a local-first, teacher-controlled
writing-evidence tool; keeps teacher judgment primary; states that Quillan is
not automated grading software; identifies unsupported AI and OCR workflows;
notes that guided scan intake routes QR-coded response pages only; and
summarizes repository safe-data expectations and current direct commands.

The menu clears the screen only when both standard input and standard output
are interactive terminals.

A normal exit or `KeyboardInterrupt` returns status `0`.

CLI parser construction lives in `quillan/cli_app/parser.py`; argument
conversion, output helpers, top-level dispatch, and command handlers live
under `quillan/cli_app`. `quillan/cli.py` remains the public compatibility
facade and `quillan.cli:main` console-script entrypoint. Validation, storage,
workspace resolution, and other domain behavior belong in their relevant
modules or in shared `pds-core` services.

## Help and Discoverability

`--help` is the canonical discovery mechanism at each parser level:

```powershell
quillan --help
quillan workspace --help
```

Help output should:

* identify Quillan and its purpose;
* list implemented commands only;
* show required positional arguments and available options;
* use the command names and argument forms documented here; and
* exit with status `0`.

Command summaries should describe effects accurately, especially whether an
operation reads, writes, or modifies workspace data. Planned commands belong
in design or roadmap documentation, not active help output.

During the current pre-1.0 period, a command-specific parser level without a
selected operation may continue to print help and return `0`. The top-level
parser is different: bare `quillan` launches the teacher-facing menu.

## Paths and Filesystem Behavior

Path arguments use the platform's normal path syntax and Python's `pathlib`
semantics.

* Relative paths are interpreted from the process's current working
  directory.
* Absolute paths are accepted.
* Paths containing spaces should be quoted by the invoking shell.
* File-validation commands require a readable file; they do not search the
  PDS workspace or example directories for a missing path.
* JSON inputs are read as UTF-8.
* Commands should not expand `~`, environment variables, or shell wildcards
  themselves. Any expansion performed by a shell occurs before Quillan sees
  the argument.
* User-facing path errors should include the relevant path when doing so is
  safe and useful.

Commands that operate on managed Paper Data Suite records should use shared
`pds-core` workspace and route contracts rather than constructing competing
workspace layouts. The active layout is documented in
[`workspace_lifecycle.md`](workspace_lifecycle.md).

Commands that write files document their destination, overwrite policy, and
handled-failure behavior in their command sections and help output.

## Scan Routing

```powershell
quillan route-scan <source-image-or-pdf-or-folder>
```

This command accepts no caller-supplied route payload. It preflights the
workspace and selected source, builds one installed Core registry, retains each
selected source exactly once, and reads only retained bytes afterward. Raw QR
text is parsed exclusively by Core's strict PDS2 parser.

Supported scan extensions are:

```text
.jpeg
.jpg
.pdf
.png
.tif
.tiff
```

PDF intake uses `pdf2image`, which requires Poppler installed on the user's
machine.

Folder intake is non-recursive. It processes only direct child files in
deterministic order by case-insensitive filename with a stable filename
tie-breaker. Unsupported files such as `.txt`, `.csv`, `.DS_Store`, or
`Thumbs.db` are skipped, counted in the structured summary, and are not
failures.

An empty folder, or a folder with no supported scan files, prints a clear
error and exits `1`.

On success, route-scan retains the source under:

```text
scans/source/YYYY-MM-DD/
```

PDF pages dispatch independently. `source_page_number` is physical retained
scan order and is not Quillan logical-page meaning.

Page loading, QR detection, payload parsing, dispatch, and integration failures are preserved
under:

```text
scans/review/
```

when they can be handled safely.

Every enumerated page has exactly one of four terminal categories:
`dispatch_success`, `core_dispatch_failure`, `pre_dispatch_failure`, or
`quillan_integration_failure`. Exit `0` requires complete dispatch success;
partial success, zero success, source failure, integration failure, or review
write failure exits `1`.

The command does not move, delete, or archive source files after folder
intake. The Scan Intake / Route Paper Responses menu invokes this same
QR-aware intake path.

The direct command and menu both return the same typed full-workflow result.
Successful Quillan dispatches persist immutable observations and assemble
issuance-authoritative submissions. Pre-dispatch failures remain Core-owned;
post-dispatch persistence, assembly, and review-preservation failures are
preserved as immutable Quillan occurrences beneath the exact module-qualified
work root. No caller callback or second assembly pass is used. See
[`pds2_scan_intake.md`](pds2_scan_intake.md).

## Scan Review Resolution

`quillan list-scan-review` lists valid unresolved and deferred Quillan routing
review records from the active workspace. `--include-resolved` also shows items
whose latest valid resolution is resolved; `--limit`, `--class-id`,
`--assignment-id`, and `--failure-category` narrow the display. Malformed or
unreadable metadata is skipped with a warning count instead of making the
entire listing fail.

`quillan resolve-scan-review <failure_id> --action <action>` accepts
`route_selected`, `route_corrected`, `rescan_needed`, `cannot_route`,
`evidence_filed`, `dismissed_duplicate`, `deferred`, or `other` (with the
documented `defer` and `mixed_assignment` aliases retained by Core). Common
actions have safe default messages; `other` requires `--message`.
`--evidence-path` is accepted only with `evidence_filed` and must be
workspace-relative. Route actions require an exact current registered route
identity through `--route-id`, `--route-class-id`, and
`--route-assignment-id`; the service reloads and validates that route before
writing the resolution.

The command writes a new exclusive-create Core resolution record under
`scans/review/resolutions/`. It does not change the referenced failure record,
retained scan, submission manifest, submission review state, or teacher review
record. The interactive **Review Student Work > Resolve Scan Review Items**
path discovers assignment work with active Quillan post-dispatch occurrences.
After compact work selection it enters the sole active source directly or,
when both sources exist, offers Core routing problems, Quillan post-dispatch
problems, and all active problems. Compact list, detail, contextual action,
confirmation, and result screens follow the mandatory clear/redraw contract.

`quillan list-post-dispatch-review <class_id> <assignment_id>` lists immutable
Quillan-owned occurrences for one exact module-qualified work root. Resolved
items are hidden by default, deferred items remain visible, and category,
limit, and include-resolved filters are deterministic. `quillan
resolve-post-dispatch-review` appends a schema-version-1 Quillan resolution;
it never changes the occurrence, Core review records, observations, evidence,
manifests, or teacher reviews. Generic direct actions are `rescan_needed`,
`record_corrected`, `cannot_recover`,
`dismissed_duplicate`, `deferred`, and `other`; `other` requires a message.
The generic direct command does not accept `resolved_after_retry` because a
caller may not assert a successful retry. For safe occurrence categories, the
menu can retry the existing shared submission-assembly service, show its typed
result, and only after success ask whether to append `resolved_after_retry`
with bounded operation, work, student/issuance, result-status, and timestamp
provenance. Retry success never resolves an occurrence automatically. The menu
also provides read-only current status and validated occurrence-owned possible
evidence/manifest opening without arbitrary-path input or automatic resolution.

## Submission Assembly and Status

```powershell
quillan assemble-submissions <class_id> <assignment_id>
quillan list-submissions <class_id> <assignment_id>
```

`assemble-submissions` discovers strict immutable observation JSON, verifies its
evidence, loads complete issuance/page records, and atomically creates, updates,
or leaves unchanged each canonical student `submission.json`. Expected pages
come only from issuance membership. Existing teacher state is preserved; mixed
issuances and plain-paper conflicts are reported without overwriting.

`list-submissions` is read-only. It reports manifest and page states,
present-but-unselected evidence, students needing assembly, and unassembled
observation-backed evidence without creating or modifying records.

These commands do not open evidence, update review state, create review
records, score work, tag work, generate feedback, run OCR, or perform AI work.

## Plain-Paper Manual Submission

```powershell
quillan create-plain-paper-submission <class_id> <assignment_id> <student_id> --yes
quillan create-plain-paper-submission <class_id> <assignment_id> <student_id> --dry-run
```

This command is for student work completed on physical plain paper when no
digital, QR, or scanned evidence exists. It creates only the canonical
evidence-less `submission.json` and paired empty `review.json`; it does not
create scans, routed evidence, OCR output, PDFs, images, or feedback.

`--yes` is required to write without an interactive prompt. `--dry-run` runs
the same identity, assignment, roster, and existing-record validation and
reports the workspace-relative target paths without writing files. The flags
are mutually exclusive.

## Evidence and Submission Opening

```powershell
quillan open-submission <class_id> <assignment_id> <student_id> [--page N] [--evidence-id <evidence_id>]
```

`open-submission` validates one canonical manifest. With no narrowing option it
opens each selected page evidence item. `--page` narrows by logical page;
`--evidence-id` selects an exact evidence candidate within that canonical
submission identity. Raw workspace-relative paths are not accepted as public
identity.

Both commands are read-only. They do not inspect content, select evidence,
score work, tag work, create review records, generate feedback, or update
review state.

## Two State Models

Quillan deliberately keeps two independent state fields. They are never
automatically synchronized:

* lightweight submission state is stored in `submission.json.submission_state`;
* standards-based review workflow state is stored in `review.json.review_state`.

Changing either field leaves the other record unchanged.

## Lightweight Submission State

```powershell
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

The allowed states are:

```text
unreviewed
in_progress
needs_rescan
reviewed
```

This compatibility command updates only `submission_state` and `updated_at` in
the validated `submission.json`. It does not open or inspect evidence, make an
automatic review decision, or change `review.json.review_state`.

## Review Workflow State

```powershell
quillan review-workflow set-state <class_id> <assignment_id> <student_id> --state <state> --yes
```

Bare `quillan review-workflow` prints namespace help successfully without
resolving a workspace or reading or creating records. The nine ordered workflow
states are:

```text
not_started
requirements_checked
returned_without_full_review
observations_in_progress
observations_complete
ratings_complete
feedback_composed
ready_for_export
exported
```

`--yes` is mandatory and is parsed before workspace resolution. This is a
manual teacher override: forward, backward, nonadjacent, and same-state updates
are allowed, and same-state saves refresh `updated_at`. The command does not
infer, require, remove, or create phase artifacts, feedback, ratings, exports,
evidence, or submission assemblies.

After validating the canonical assignment and submission, a missing
`review.json` may be created as an empty schema-version-2 record for a
non-returned state. This includes valid evidence-less plain-paper submissions
and historical submissions for students no longer on the roster. Existing
records preserve every field except `review_state` and `updated_at`.

Returned-without-full-review status remains controlled by `requirements
set-outcome`: the generic command cannot enter that state without a coherent
returned outcome, and cannot leave a coherent returned outcome until the
minimum-requirement outcome is changed. A legacy record whose workflow state is
returned but whose outcome is not marked returned may be repaired by moving to
a non-returned state.

The exact write boundary is the selected canonical `review.json` only. The
command never changes `submission.json.submission_state`, roster data,
assignment data, evidence, sibling records, exports, or reports.

## Quick Teacher Notes

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
```

This direct command appends one teacher-entered note to canonical
`review.json`, creating the record only when the adjacent `submission.json`
exists, validates, and matches the requested identity.

It preserves the manifest, evidence, and unrelated review content.

## Removed Legacy Review Writes

The legacy direct review-write commands `add-tag`, `add-comment`, and
`set-score` are no longer part of the active CLI surface. They were removed as
part of the v0.8.6 standards-based review redesign gate and must not write v1
`review.json.tags`, `review.json.comments`, or `review.json.scores` data.

The matching selected-student menu actions for structured tags, reusable
comments, and criterion scores are also removed. Replacement Focus Standard
observation, rating, feedback, and reporting workflows now live in the guided
selected-student menu and schema version `2` review record.

## Student Feedback Export

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--format markdown|pdf|both] [--overwrite]
```

This direct command requires valid matching canonical `submission.json` and
`review.json` records, then writes the selected derived artifact or artifacts:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

`--format` accepts `markdown`, `pdf`, or `both`. The default is `markdown` for
pre-1.0 compatibility with earlier scripts.

The export is standards-based. It uses the review record's
`minimum_requirement_outcome`, `overall_standard_ratings`, selected review-unit
observations, and `feedback.standard_feedback` content. It excludes private
notes, unselected observations, unselected comments, reusable-comment
provenance, routed evidence paths, and internal review IDs.

Success returns `0` and reports the identity, selected format, overwrite
status, and workspace-relative feedback path or paths.

Handled workspace, validation, missing-record, and overwrite failures return
`1`.

Without `--overwrite`, an existing feedback file is preserved.

The command does not mutate review state, timestamps, canonical records, or
evidence.

## Assignment-Local Class Summary Export

```powershell
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
```

This direct command reads the assignment config, roster when available,
submission manifests, review records, and feedback export metadata, then
writes:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/class_summary.csv
```

Rows follow roster order when a roster is available, then discovered
unrostered submission folders by `student_id`. Without a roster, rows are
sorted by discovered `student_id`.

Rows include submission and review states, minimum-requirement outcomes,
returned-without-full-review status, assignment Focus Standard ratings,
rating labels from the assignment rating scale, feedback PDF/Markdown status,
warnings, and workspace-relative paths.

Missing, invalid, and identity-mismatched student records produce
stable warnings such as `missing_submission`, `invalid_submission`,
`missing_review`, `invalid_review`, or `identity_mismatch` rather than
aborting the whole export.

A missing assignment config is a handled failure.

Success returns `0` and prints row/status counts, overwrite status, and the
summary path. Handled failures return `1`.

The export is read-only with respect to canonical records. It does not read
evidence files, source comment banks, student writing, private notes, or full
feedback text. It does not calculate percentages, grades, mastery, or
weighted results, or generate a standards summary.

Existing CSV files require `--overwrite`.

## Assignment-Local Focus Standard Summary Export

```powershell
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

This command reads the assignment's configured Focus Standards, discovered
or rostered student records, and feedback export metadata, then writes:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/standards_summary.csv
```

It validates each available `submission.json` and `review.json`, counts
missing, invalid, returned-without-full-review, and identity-mismatched
records without aborting the assignment export, and emits one row per
assignment Focus Standard in assignment order.

Rows aggregate teacher-entered overall Focus Standard ratings from
`overall_standard_ratings`, missing-rating counts, feedback-inclusion counts,
and feedback PDF coverage.

Ratings outside the assignment Focus Standards produce warnings rather than
ordinary rows.

If no valid reviews exist, the command still writes one row per assignment
Focus Standard with zero counts.

Success returns `0`. Handled workspace, validation, missing-directory, and
overwrite failures return `1`.

The export does not include notes or scores, map criteria to standards, inspect
student writing or evidence, read comment banks,
use AI, calculate grades or mastery, use a roster, or mutate canonical
records.

Existing CSV files require `--overwrite`.

## Export and Menu Overwrite Behavior

Direct export commands require `--overwrite` to replace existing export
artifacts.

Guided menu export actions prompt before replacing an existing export file.

Invalid overwrite responses cancel safely.

Exports do not mutate:

* `submission.json`;
* `review.json`;
* routed evidence files;
* retained source scans;
* rosters;
* assignment configs;
* reusable Focus Standard comments; or
* pds-core standards libraries.

The menu delegates to the same export services and output formatters as the
direct CLI handlers. It does not implement a parallel export system.

## Output and Error Handling

Human-readable command results are the default output contract. The
`review-dashboard` and `review-status` commands also provide stable
schema-version-1 JSON projections through `--format json`; other prose output
should not be treated as a machine-readable schema.

The intended convention is:

* successful results and requested help go to standard output;
* usage and argument-parsing errors go to standard error;
* expected operational or validation failures go to standard error, produce a
  concise actionable message, and exit 1;
* expected user errors do not display a Python traceback; and
* diagnostics should distinguish invalid input from an internal programming
  failure.

Expected failures use:

```text
Error: ...
```

Artifact paths in teacher-facing output are canonical workspace-relative POSIX
paths. Absolute host paths are not an artifact identity and are not printed as
successful workflow results.

Unexpected exceptions indicate defects and are not converted into a success
status. Sensitive classroom data must not be added to routine diagnostics,
examples, or trace output.

## Exit Codes

The process exit status is part of the CLI contract:

| Status        | Meaning                                                                                                                                            |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0`           | The requested operation or menu session completed successfully, or help was requested or printed for a no-operation command-specific parser level. |
| `1`           | The command was understood, but validation or an operational action failed.                                                                        |
| `2`           | Command-line usage was invalid, as reported by `argparse`.                                                                                         |
| Other nonzero | An unexpected failure or a future explicitly documented category.                                                                                  |

Examples of status `1` include a missing or invalid JSON input and failure to
resolve workspace status. Examples of status `2` include an unknown command,
a missing required path argument, and an unexpected extra argument.

Callers should generally treat `0` as success and any nonzero value as
failure. They should not depend on additional nonzero distinctions unless a
command documents them.

## Pre-1.0 Compatibility Expectations

Until Quillan reaches 1.0:

* the CLI may add, rename, reorganize, or remove commands;
* human-readable wording and formatting may change;
* exit-code conventions should remain coherent even when command details
  change;
* existing commands should not change meaning casually or silently;
* behavior changes should update this document, user-facing README examples,
  CLI help, and tests as applicable; and
* deprecation is preferred when a widely used command can reasonably be
  migrated, but pre-1.0 changes do not promise a fixed deprecation period.

The source of truth for the current surface is the combination of
`quillan.cli_app`, the public `quillan/cli.py` facade, CLI tests, menu tests,
and this document. If they disagree, the implementation and tests describe
executable behavior, and the mismatch should be corrected rather than treated
as an undocumented feature.

## Not Currently Part of the CLI

The following capabilities are implemented only as Python APIs, planned, or
explicitly outside the current end-to-end foundation:

* printable response generation as a dedicated command;
* submission validation as a dedicated command;
* recursive scan folder intake, source-file archiving, inbox draining, or
  automatic production scan routing;
* OCR or handwriting interpretation;
* PDF text extraction;
* a direct CLI command for feedback composition;
* AI grading, scoring, tagging, or feedback;
* automatic grading, mastery calculation, review-state decisions, or
  duplicate-evidence selection;
* LMS integration;
* cloud sync;
* email delivery; and
* dashboard/reporting automation.

Their presence in design documents or Python modules does not add them to the
CLI contract.

## Selected-student plain-paper action

When a roster student has no routed evidence and no submission manifest, the
interactive selected-student review menu offers creation of a plain-paper
manual submission. It requires `y` or `yes` confirmation. Existing manifests,
existing orphan review records, and routed-evidence-only students are not
converted. Opening evidence for a manual submission reports that no digital
evidence is attached instead of invoking an evidence opener.
