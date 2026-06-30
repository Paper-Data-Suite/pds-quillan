# Quillan

Quillan is a local-first standards-based writing evidence capture system for teachers.

It helps teachers organize, review, tag, score, and respond to student writing by connecting specific written work to standards, comments, rubric scores, review states, and structured instructional data.

Quillan is part of the broader Paper Data Suite concept, alongside ScoreForm.

## Current Status

Quillan is an early pre-1.0 foundation. The v0.8.0 milestone provides a teacher-controlled paper-response intake, review, and export workflow through both direct CLI commands and guided terminal-menu workflows.

Quillan currently supports:

* assignment configuration validation;
* pds-core standards profile selection for assignment configuration;
* validation of legacy text-oriented submission metadata;
* documented writing-evidence and teacher-review data contracts;
* validated shared reusable comment banks with synthetic examples;
* teacher-controlled comment selection into `review.json`;
* loading and validation for version `1` reviewable-evidence submission manifests;
* assembly of version `1` submission manifests from routed response evidence;
* deterministic evidence IDs;
* missing, duplicate, damaged, needs-rescan, replacement, and excluded evidence semantics;
* retained-source provenance;
* canonical workspace-relative paths;
* overwrite protection for generated canonical records and exports;
* assignment-level discovery and assembly of already-routed response evidence through `quillan assemble-submissions`;
* printable writing-response PDF generation with student, class, assignment, and page identity;
* QR codes containing canonical PDS1 Quillan response payloads on printable response pages;
* roster-aware printable response generation using shared `pds-core` roster records and display-name helpers;
* teacher-facing class roster creation, viewing, staged editing, and validation through the Roster Management menu;
* teacher-facing writing assignment config creation and validation through the Assignment Management menu;
* teacher-facing generation of one combined printable response class packet from an existing canonical roster and assignment config;
* teacher-facing Manage Review Materials guidance for reusable review aids;
* shared Paper Data Suite workspace status reporting;
* assignment-local storage paths based on shared `pds-core` route helpers;
* decoded response-page route planning that validates class, assignment, roster, and student relationships before writing routed evidence;
* successful-route evidence filing that retains selected source scans under `scans/source/YYYY-MM-DD/` and files routed response evidence under the assignment `scans/` directory;
* routing failure preservation under `scans/review/`, including retained-source provenance when available;
* a direct `route-scan` command for:

  * already-decoded PDS1 payloads;
  * one supported QR-bearing image;
  * one QR-bearing PDF processed page by page;
  * a non-recursive folder of supported QR-bearing scan files;
* QR-aware scan-intake summaries with explicit post-intake `assemble-submissions` guidance;
* read-only assignment submission status listing;
* workspace-safe local evidence opening;
* student-aware selected-evidence opening;
* explicit lightweight submission review-state updates;
* teacher-controlled quick-note, structured-tag, reusable-comment, and criterion-score updates to canonical `review.json` records;
* guided teacher review-entry actions from the Review Student Work menu;
* derived student feedback, class review summary, and standards summary exports;
* guided export actions from the Review Student Work menu; and
* synthetic examples and fixtures for safe testing and documentation.

Printable response generation is exposed through the teacher-facing menu and the Python API in `quillan.printable_response`. It is not currently exposed as a dedicated direct CLI command.

Current classroom-data workflows are local-first. They read and write the teacher-selected Paper Data Suite workspace and do not upload student work, review records, comment banks, rosters, scans, or exports to a hosted service.

Canonical v0.8.0 records and exports live at:

```text
classes/<class_id>/roster.csv
classes/<class_id>/assignments/<assignment_id>/assignment.json
classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
classes/<class_id>/assignments/<assignment_id>/scans/
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
scans/source/YYYY-MM-DD/
scans/review/
shared/comment_banks/<bank_id>.json
shared/standards/library.json
```

Opening evidence delegates only to the local system viewer. Exports are derived files and never replace the canonical submission manifest or review record.

## Core Principle

Quillan is not an AI essay grader.

It is a teacher-controlled system for turning student writing into structured instructional evidence.

Teacher judgment remains primary. Teachers read the work, decide what matters, choose tags and comments, enter scores, and decide review state.

Quillan may eventually help summarize teacher-created data, but final scoring and feedback decisions belong to the teacher.

## Implemented v0.8.0 Workflow

Quillanâ€™s v0.8.0 workflow separates retained source scans, routed evidence, submission manifests, teacher review records, and exports.

A **retained source scan** is the canonical active source copy Quillan keeps during scan intake.

**Routed evidence** is a file copied or derived from retained source material and filed under an assignmentâ€™s `scans/` directory for student/assignment review.

A **student submission manifest** is the structured record connecting one student and assignment to pages, page states, selected evidence, alternate evidence, and provenance.

A **review record** is the teacher-controlled `review.json` containing notes, tags, selected comments, criterion scores, and teacher-entered requirement checks.

An **export** is a derived artifact produced from canonical records.

A routed evidence file by itself is not a complete student submission. Routing does not mean that work is complete, reviewed, scored, or ready for feedback.

The supported sequence is:

1. The teacher creates or selects a local Paper Data Suite workspace.
2. The teacher creates or loads a class roster.
3. The teacher creates or loads a writing assignment config.
4. The teacher generates printable response pages.
5. Students write on the printed pages.
6. The teacher scans the completed pages.
7. Quillan routes QR-bearing response pages into assignment evidence storage.
8. Quillan preserves retained source scans and handled failures for review.
9. The teacher runs or follows post-intake submission assembly guidance.
10. Quillan assembles submission manifests from routed evidence.
11. The teacher lists submission status.
12. The teacher opens selected evidence locally.
13. The teacher records minimum requirement checks and adds notes, structured tags, reusable comments, and scores.
14. The teacher updates lightweight submission review state when appropriate.
15. The teacher exports student feedback, class review summary, and standards summary.

Opening evidence and updating review state are separate teacher-controlled actions. Opening a file never marks a submission reviewed.

## Teacher-Facing Menu

Launch the teacher-facing terminal menu:

```powershell
quillan
```

or:

```powershell
quillan menu
```

The current top-level menu is:

```text
1. Assignment Management
2. Review Student Work
3. Roster Management
4. Workspace Settings
5. Help
6. Exit
```

### Assignment Management

The Assignment Management menu supports:

```text
1. Create writing assignment
2. View/validate assignment
3. Printable Response Pages
4. Back
```

Assignment creation requires an existing canonical class roster and writes to:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The creation workflow prompts for:

* class;
* assignment title;
* assignment ID;
* writing type;
* pds-core standards profile selection;
* tagging mode;
* pds-core focus-standard selection;
* basic requirements;
* rubric ID.

`writing_type` is currently a required teacher-entered value, not a discovered list.

`standards_profile_id` is selected from the active pds-core standards library and stored as a durable pds-core `profile_id`. Focus standards are selected from that profile and stored as durable pds-core `standard_id` values.

`tagging_mode` is constrained to the allowed values shown by the prompt.

This menu creates and validates assignment configs. It does not edit existing assignments, delete assignments, check requirements, route scans, score work, tag work, generate feedback, or perform OCR or AI work.

### Roster Management

The Roster Management menu creates and reads canonical shared rosters at:

```text
<PDS workspace root>/classes/<class_id>/roster.csv
```

Canonical roster columns are:

```text
class_id, student_id, last_name, first_name, period
```

Student IDs remain strings so leading zeros are preserved.

Existing optional columns are displayed and preserved when students are added, edited, or removed. Edits remain staged until the teacher saves them. Removing a student changes only the active roster and does not delete assignments, submissions, printable PDFs, scans, exports, tags, scores, feedback, or historical evidence.

### Printable Response Pages

Printable Response Pages is available from Assignment Management. It selects
an existing canonical class roster and assignment config, prompts for a
positive number of pages per student, and generates one combined class packet
at:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
```

Replacing an existing packet requires exact overwrite confirmation.

Generated response pages include student, class, assignment, page identity, and QR codes containing canonical Quillan PDS1 response payloads.

Generation does not alter the roster or assignment config. Generated PDFs are local workspace artifacts and should not be committed.

### Scan Intake / Route Paper Responses

Scan Intake / Route Paper Responses is available from Review Student Work. It
asks for an image, PDF, or non-recursive folder path and uses the same
QR-aware behavior as:

```powershell
quillan route-scan <source> --decode-qr
```

It prints the structured scan-intake summary, preserves handled failures for review, and shows explicit `assemble-submissions` next steps when pages were routed.

It does not expose direct payload mode. It does not move or archive original source files, assemble submissions automatically, run OCR, score work, tag work, or generate feedback.

### Review Student Work

The Review Student Work menu supports scan intake, review-material management,
class/assignment/student navigation, and guided review actions.

The top Review Student Work menu is:

```text
1. Assignment Review Actions
2. Scan Intake / Route Paper Responses
3. Manage Review Materials
4. Back
```

The assignment-level review actions menu is:

```text
1. Select student/submission
2. Assemble routed submissions
3. Export class review summary
4. Export standards summary
5. Refresh submission status
6. Back
```

The selected-student review menu is:

```text
1. Open submission evidence
2. View current review details
3. Record minimum requirement checks
4. Manage submission pages
5. Add teacher note
6. Add structured tag
7. Select reusable comment
8. Set criterion score
9. Update submission review state
10. Export student feedback
11. Refresh summary
12. Back
```

These guided actions reuse the same underlying services and data contracts as the direct CLI commands. The menu does not implement separate export logic, scoring logic, routing logic, or AI logic.

Review mode is selection-first. Selection screens clear between major levels so the current student, assignment, bank, category, or criterion context is visible without old summaries above it. `B. Back` returns to the immediate previous selection screen. Teacher notes open with private-note guidance and safe Back behavior. Minimum requirement checks are generated from assignment `basic_requirements` and stored as teacher-entered booleans in `review.json.requirement_checks`; Quillan does not count words or paragraphs, parse writing, run OCR, use AI, infer requirement completion, or change scores from those checks. Reusable comments are selected by comment bank, category, and comment, with label, feedback preview, target, and include-in-feedback setting shown before writing. Reusable tags are selected by tag bank, category, and tag template, with a custom one-off fallback. Tags and comments can optionally be attached to whole submission, page, paragraph, multiple paragraphs, or page plus paragraphs. Paragraph targets are teacher-entered metadata; Quillan does not parse the student's writing to determine paragraph numbers or infer where feedback belongs. Rubric scoring uses the assignment's resolved shared rubric when available, then asks the teacher to choose a criterion and level before confirming the saved score; custom scoring remains available when the rubric is missing or does not contain the needed criterion.

Selected Student Review includes a read-only `View current review details` option near the top of the menu. It displays the current student's saved requirement checks, notes, tags, comments, scores, feedback-inclusion choices, and tag/comment targets in the terminal. It does not generate an export file and is separate from full reporting and student feedback export, so Quillan remains useful as a standalone review tool with only pds-core.

Review-time standards metadata is display-only. When reusable comments or tags reference durable pds-core `standard_id` values, Quillan may resolve readable code/name metadata through pds-core read-only helpers for display. It still stores durable IDs in review records and does not create, import, edit, retire, reactivate, or authoritatively validate standards.

Review state updates are explicit and teacher-controlled. The state screen explains `unreviewed`, `in_progress`, `needs_rescan`, and `reviewed`, then asks for confirmation before saving. It does not infer state from notes, tags, comments, scores, or exports.

Guided export actions preserve overwrite protection. Student feedback export explains that it formats the current review record, does not rescore work, and does not generate AI feedback. Existing export files are not replaced unless the teacher explicitly confirms overwrite behavior.

### Manage Review Materials

Manage Review Materials is available from Review Student Work. It is the
preparation area for reusable teacher-authored review aids. It includes
Comment Banks, Tag Banks, and Rubrics / Scoring Profiles submenus for
creating, viewing, editing, extending, and validating shared reusable review
materials. It also includes optional synthetic starter materials for
onboarding and local testing.

These materials help teachers review written student work more quickly by selecting prepared comments, tags, and scoring criteria instead of typing everything during review.

Review materials are subject-agnostic. They may support essays, constructed responses, lab reports, journals, reflections, creative writing, research papers, mathematical explanations, technical writing, and other local writing tasks.

Authoring prompts distinguish teacher-facing labels from stored system IDs. Labels may use spaces and capitalization. IDs such as `bank_id`, `tag_bank_id`, `rubric_id`, `category_id`, `comment_id`, `tag_template_id`, and `criterion_id` are short JSON names; the menus suggest IDs from labels and ask for lowercase letters, numbers, underscores, or hyphens. Multi-word ID-style values and `writing_types` values should use underscores instead of spaces. The teacher-facing term for `writing_types` is "writing assignment types."

Comment banks created through the menu are stored at `shared/comment_banks/<bank_id>.json` and validate against the same version `1` contract used by review-time selection. Banks are subject-agnostic and writing-type-aware, so they can support essays, constructed responses, lab reports, reflections, research papers, mathematical explanations, technical documentation, design rationale, portfolio reflection, and other local written-work contexts.

Comment banks store reusable teacher-authored feedback language. They do not grade work, imply mastery, generate comments automatically, or change student records by themselves. When a teacher selects a reusable comment during Review Student Work, Quillan snapshots the selected label and text into the review record with `source: "comment_bank"`, `bank_id`, and `comment_id`; later bank edits do not silently rewrite prior student review records.

Tag banks created through the menu are stored at `shared/tag_banks/<tag_bank_id>.json` and validate against the version `1` tag-bank contract. Tag banks store reusable teacher-authored observations for quick review tagging. They are not grades, scores, mastery determinations, generated feedback, or automatic judgments. During Review Student Work -> Add structured tag, teachers can select a reusable tag by bank, category, and tag template, or choose a custom one-off tag. Selected reusable tags snapshot label, polarity, optional severity, optional standard/criterion metadata, teacher notes, and `source: "tag_bank"` provenance into `review.json.tags`.

Tag-bank authoring asks for optional tag details in teacher-facing language. Optional details can include a description, writing assignment type limits, linked standards, linked rubric criteria, priority/severity, a private note question, and display order. `severity_default` is optional priority/severity for concerns only; it is not a grade and does not affect scoring. `teacher_note_prompt` is shown during review and stores the teacher's answer as a private tag note. `student_facing_default` remains a schema field, but the teacher menu does not prompt for it because it does not yet send anything to students by itself. `sort_order` is displayed as optional display order.

Rubrics / scoring profiles created through the menu are stored at `shared/rubrics/<rubric_id>.json` and validate against the version `1` rubric contract. Assignment creation can select a valid shared rubric by number, while custom or unresolved rubric IDs remain allowed for compatibility. During Review Student Work -> Set criterion score, teachers can score from the assignment rubric by selecting a criterion and level, or choose Custom criterion score. Selected rubric scores snapshot the criterion ID, label, selected score, max score, scale, and optional teacher note into the existing `review.json.scores` shape. Rubric level feedback metadata does not automatically create comments or feedback entries.

Starter Materials can preview, validate, and install clearly synthetic example
comment banks, tag banks, and rubrics for onboarding, plus larger
teacher-editable NJ ELA starter materials for English 10 and English 12 writing
review. Installation copies only validated JSON files into
`shared/comment_banks/`, `shared/tag_banks/`, and `shared/rubrics/`. Existing
workspace files are skipped by default; overwriting requires exact `OVERWRITE`
confirmation. Starter materials do not create assignments, rosters, scans,
submissions, review records, exports, pds-core standards, pds-core route
helpers, or pds-core standards profiles. See
[`docs/starter_materials.md`](docs/starter_materials.md) and
[`docs/nj_ela_starter_materials.md`](docs/nj_ela_starter_materials.md).

Optional `standard_ids` in comment metadata are durable pds-core references only. Quillan comment-bank authoring does not create, import, edit, retire, reactivate, or validate standards as authoritative.

Optional `standard_ids` in tag templates are also durable pds-core references only. Optional `criterion_ids` are rubric/scoring metadata only. Quillan tag-bank authoring does not mutate pds-core standards, route helpers, workspace preferences, rosters, assignments, submissions, scans, exports, comment banks, or rubric files.

Comment-bank authoring does not modify student submissions, scans, rosters, assignments, exports, pds-core workspace preferences, pds-core route helpers, or pds-core standards. Tag-bank authoring writes only confirmed, valid files under `shared/tag_banks/`; comment-bank authoring writes only confirmed, valid files under `shared/comment_banks/`.

Review materials augment Quillan review workflows but do not replace pds-core ownership of standards, workspace resolution, or shared routes.

### Workspace Settings

Workspace Settings can:

```text
1. Show current workspace
2. Set workspace folder
3. Validate/create current workspace
4. Reset saved workspace preference
5. Back
```

Quillan uses the shared `pds-core` workspace configuration. It does not create a Quillan-specific workspace config.

Setting a root validates or creates it and saves the shared preference, but does not move or migrate existing files.

Resetting clears only the saved preference and does not delete workspace files.

`PDS_WORKSPACE_ROOT` takes precedence over the saved preference when it is set.

## Direct CLI Commands

Show direct CLI help:

```powershell
quillan --help
```

The current command surface is:

```powershell
quillan
quillan --help
quillan validate-assignment <assignment.json>
quillan route-scan <source-file> --payload "<PDS1|...>"
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
quillan open-evidence <workspace-relative-path>
quillan open-submission <class_id> <assignment_id> <student_id>
quillan add-note <class_id> <assignment_id> <student_id> --text "..."
quillan add-tag <class_id> <assignment_id> <student_id> --label "..." --polarity developing
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
quillan set-score <class_id> <assignment_id> <student_id> --criterion <criterion_id> --label "..." --score <number> --max-score <number>
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
quillan workspace show
quillan workspace set <path>
quillan workspace validate
quillan workspace reset
quillan menu
```

Legacy text-oriented submission metadata validation and printable response generation currently use Python APIs rather than dedicated CLI commands.

## Scan Intake and Routing

Route one selected scan using an already-decoded Quillan PDS1 payload:

```powershell
quillan route-scan <source-file> --payload "PDS1|module=quillan|doc=response|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page>"
```

Route one supported local image, PDF, or non-recursive folder by decoding Quillan response-page QR payloads:

```powershell
quillan route-scan <source-image> --decode-qr
quillan route-scan <source-pdf> --decode-qr
quillan route-scan <source-folder> --decode-qr
```

Successful routing retains the selected source under:

```text
scans/source/YYYY-MM-DD/
```

and files response evidence under:

```text
classes/<class_id>/assignments/<assignment_id>/scans/
```

PDF intake converts pages independently and files routed page evidence as PNG files, preserving the physical `source_page_number` separately from the decoded `payload_page_number`.

Decode, payload, planning, filing, and PDF conversion failures are preserved under:

```text
scans/review/
```

when possible.

QR-aware image and PDF intake prints a structured summary with source, page, routed, preserved, failed, skipped unsupported, and review-required counts.

Folder intake produces one aggregate summary across all processed sources and continues after recoverable failures that can be preserved for review.

Partial success is explicit: exit code `0` can mean every page routed or that expected failures were safely preserved for review. Exit code `1` means an unexpected or unpreserved failure occurred.

Preserved failures require review before intake is treated as complete.

Folder intake is QR-aware only. `--payload` requires a source file and rejects folders.

Folder intake processes only direct child files in deterministic filename order. It does not recurse. Unsupported files are skipped and counted.

QR-aware intake supports:

```text
.jpeg
.jpg
.pdf
.png
.tif
.tiff
```

PDF conversion uses `pdf2image` and requires Poppler installed on the user's machine.

Scan intake does not:

* move original source files;
* delete original source files;
* archive original source files;
* run OCR;
* perform handwriting recognition;
* extract PDF text;
* score work;
* tag work;
* generate feedback;
* assemble submissions automatically;
* create review records;
* create reports.

After QR-aware intake, `route-scan` derives class/assignment assembly targets from the current structured intake summary and prints safe next-step commands, such as:

```powershell
quillan assemble-submissions <class_id> <assignment_id>
```

It does not rescan assignment `scans/` directories and does not include preserved or failed pages as assembly targets.

Submission assembly remains an explicit teacher-controlled step.

## Submission Assembly and Status

Assemble all student manifests discoverable from routed filenames in an assignment's `scans/` directory:

```powershell
quillan assemble-submissions <class_id> <assignment_id> [--expected-pages N] [--overwrite]
```

Discovery recognizes routed PDF and image filenames such as:

```text
response_00107_pg_003.pdf
response_00107_pg_003__dup_001.png
```

`assemble-submissions` creates missing manifests from routed filenames. Existing manifests are skipped by default. `--overwrite` fully regenerates them without preserving prior review state or teacher selections.

It does not inspect evidence file contents, OCR writing, or choose among ambiguous duplicate evidence.

List current manifest and routed-evidence status without changing files:

```powershell
quillan list-submissions <class_id> <assignment_id> [--expected-pages N]
```

The status includes:

* submission states;
* page states;
* present-but-unselected pages;
* students with routed evidence but no manifest;
* unassembled routed files;
* malformed or unrelated routed filenames;
* missing pages;
* duplicate pages;
* needs-rescan pages;
* excluded pages.

Selected Student Review includes Manage Submission Pages. Teachers can exclude a page from active review, restore an excluded page, or mark a page as needing rescan. These actions update only that student's `submission.json`, preserve evidence records and files, and do not change review notes, tags, comments, scores, feedback exports, rosters, assignments, review materials, pds-core standards, or pds-core routes. Excluded pages are preserved, not deleted.

Existing manifests are loaded and validated. An invalid manifest is an error.

`list-submissions` does not open evidence, assemble or update manifests, select evidence, score work, tag work, run OCR, or generate feedback.

Allowed submission review states are:

```text
unreviewed
in_progress
needs_rescan
reviewed
```

## Opening Evidence

Open one local evidence file with the system default application:

```powershell
quillan open-evidence classes/<class_id>/assignments/<assignment_id>/scans/<file>
```

The path must be relative to and remain inside the active PDS workspace.

Open the selected routed evidence for one student's canonical submission:

```powershell
quillan open-submission <class_id> <assignment_id> <student_id>
```

Quillan loads and validates the student's manifest, verifies its identity, and uses the same local evidence-opening support as `open-evidence`.

Exactly one selected evidence item is currently required. Use `list-submissions` first for missing, duplicate, needs-rescan, or unselected submissions.

Opening is read-only. It does not change review state, select evidence, score work, tag work, evaluate writing, inspect file content, run OCR, or generate feedback.

## Teacher Review Records

Append a quick teacher note:

```powershell
quillan add-note <class_id> <assignment_id> <student_id> --text "Strong claim, but evidence explanation needs work."
```

Notes are stored in `review.json` with stable local IDs and timezone-aware timestamps.

If `review.json` does not exist, Quillan creates it only after the adjacent `submission.json` validates and matches the requested class, assignment, and student.

Adding a note never mutates `submission.json`, routed evidence, or retained source scans. It does not score, tag, or generate feedback.

Append a structured teacher tag:

```powershell
quillan add-tag <class_id> <assignment_id> <student_id> --label "Evidence needs more explanation" --polarity developing
```

Tags are stored in the `tags` array of the student's canonical `review.json`.

Optional flags can reference:

* a standard;
* a profile comment;
* severity;
* teacher note;
* page;
* evidence ID;
* controlled location metadata, including optional teacher-entered paragraph
  or page targets.

A missing review record is created only for a valid matching `submission.json`.

Tags remain teacher-entered review artifacts. Adding one does not mutate the submission manifest or evidence, calculate a score, establish standard mastery, analyze writing, or generate feedback.

Select a reusable teacher-authored comment:

```powershell
quillan add-comment <class_id> <assignment_id> <student_id> --bank <bank_id> --comment-id <comment_id>
```

Reusable teacher-authored comment banks live at:

```text
shared/comment_banks/<bank_id>.json
```

The direct `add-comment` workflow validates a bank and copies selected teacher-authored language into the canonical review record.

Reusable comments selected from the guided review menu can also store optional
teacher-entered page and paragraph targets in `review.json.comments`. Existing
comments without targets remain valid, and exports continue to use the
snapshotted comment text and include-in-feedback setting.

The selected review comment stores `bank_id + comment_id` provenance and copies label and text, so later bank edits do not change an existing review.

Feedback inclusion uses the bank default unless explicitly included or excluded. This command does not export feedback.

Set or update one teacher-entered criterion score:

```powershell
quillan set-score <class_id> <assignment_id> <student_id> --criterion evidence --label "Evidence" --score 3 --max-score 4
```

Scores are stored in the `scores` array of the student's canonical `review.json`.

Repeating the command for the same `criterion_id` preserves its score ID, updates that criterion, and preserves unrelated notes, tags, scores, comments, and metadata.

Optional `--scale` and `--note` values describe the latest explicit teacher input. Omitting them during an update removes stale prior values.

Quillan does not derive scores from student writing, tags, notes, comments, requirements, standards references, or evidence metadata.

This command does not calculate totals, weighted scores, percentages, grades, mastery, or any other overall score. The guided review menu can additionally select criteria and levels from a resolved shared rubric, but the direct command remains manual and compatible.

Explicitly update one submission's lightweight teacher review state:

```powershell
quillan set-review-state <class_id> <assignment_id> <student_id> <state>
```

Allowed states are:

```text
unreviewed
in_progress
needs_rescan
reviewed
```

The command changes only `submission_state` and `updated_at` in the validated manifest. Opening a submission does not update its state.

This command does not open or inspect evidence, score work, tag work, evaluate writing, run OCR, or generate feedback.

## Exports

Export student feedback:

```powershell
quillan export-feedback <class_id> <assignment_id> <student_id> [--overwrite]
```

This reads a valid matching `submission.json` and `review.json`, then writes:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

It includes criterion scores and only snapshotted comments marked:

```json
"include_in_feedback": true
```

Private notes, score notes, tags, and comment provenance are excluded.

Existing feedback is protected unless `--overwrite` is supplied.

Export a class review summary:

```powershell
quillan export-class-summary <class_id> <assignment_id> [--overwrite]
```

This discovers immediate student directories under the assignment `submissions/` directory and writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
```

Each student gets one deterministic row, including status rows for missing, invalid, or identity-mismatched records.

Ready rows summarize states, teacher-entered score totals, selected comments, tags, notes, and feedback-file existence.

The totals are transparent arithmetic, not grades.

Export a standards summary:

```powershell
quillan export-standards-summary <class_id> <assignment_id> [--overwrite]
```

This reads valid matching `submission.json` and `review.json` records and writes:

```text
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

It creates one sorted row per `standard_id` referenced by a structured tag or selected comment, including tag polarity, feedback-inclusion, and distinct-student counts.

It does not include individual student IDs, scores, notes, mastery determinations, or grades.

All exports are derived files. Exports do not mutate:

* `submission.json`;
* `review.json`;
* routed evidence files;
* retained source scans;
* rosters;
* assignment configs;
* comment banks;
* pds-core standards definitions and profiles.

The guided menu export actions reuse these same export services and output formatters. The menu does not implement a second export system.

## Standards and Assignment Validation

Validate an assignment configuration:

```powershell
quillan validate-assignment <assignment.json>
```

This command keeps structural assignment validation available without requiring a workspace standards library.

Workspace-aware review workflows can additionally check that `standards_profile_id` exists in the shared standards library and that referenced standards are valid for that profile.

Quillan does not maintain an independent standards universe. Shared standards definitions, durable `standard_id` values, reusable `profile_id` values, and profile validation are owned by pds-core. Legacy Quillan standards-profile files are removed before production use; this is a pre-1.0 breaking cleanup with no production-data migration.

## Data Contracts

Quillan's data contracts are documented in:

```text
docs/data_contracts.md
```

The canonical teacher-review `review.json` contract is documented in:

```text
docs/review_record_contract.md
```

The printable response contract and implemented generator are described in:

```text
docs/printable_response_template.md
```

The shared workspace layout and the distinction between active and reserved paths are documented in:

```text
docs/workspace_lifecycle.md
```

The scan-routing rules and failure behavior are documented in:

```text
docs/scan_routing_design.md
```

The comment-bank contract is documented in:

```text
docs/comment_bank_contract.md
```

The tag-bank contract is documented in:

```text
docs/tag_bank_contract.md
```

Synthetic example files are available in:

```text
examples/
```

## v0.8.0 Smoke Test

The v0.8.0 workflow is covered by an end-to-end smoke test:

```text
tests/test_v080_end_to_end_smoke.py
```

This test uses an isolated synthetic workspace and verifies the integrated path for:

* synthetic class roster setup;
* assignment config creation and validation;
* pds-core standards library setup;
* comment bank setup;
* scan routing from a Quillan response payload;
* submission manifest assembly;
* selected evidence discovery;
* teacher note entry;
* structured standards-linked tag entry;
* reusable comment selection;
* criterion score entry;
* submission review-state update;
* student feedback export;
* class review summary export;
* standards summary export.

It is a high-level integration confidence check. It is not a replacement for the focused unit and workflow tests.

## Local Setup

`pds-core` is required for local Paper Data Suite development.

Check out `pds-core` and `pds-quillan` as sibling repositories. The parent directory name and location can vary:

```text
Paper-Data-Suite/
  pds-core/
  pds-quillan/
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

From inside `pds-quillan`, install the project, development tools, and the editable sibling checkout of `pds-core`:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Installing only Quillan's ordinary third-party dependencies is not sufficient for Paper Data Suite development because Quillan depends on shared infrastructure from `pds-core`.

PDF scan intake uses `pdf2image` and requires Poppler installed on the user's machine.

Quillan uses `pds-core` workspace and route contracts. Assignment-local files follow this convention beneath the resolved shared workspace root:

```text
<PDS workspace root>/classes/<class_id>/assignments/<assignment_id>/
```

## Quality Checks

Run tests:

```powershell
pytest
```

Run lint checks:

```powershell
ruff check .
```

Run type checks:

```powershell
mypy .
```

Before opening a pull request, all three should pass:

```powershell
pytest
ruff check .
mypy .
```

Run the complete validation sequence, including the diff whitespace check:

```powershell
.\run_tests.ps1
```

## Synthetic Data Policy

The repository should not include real student data.

Committed examples and tests should use:

* fake student IDs;
* fake class IDs;
* synthetic writing samples;
* synthetic scores;
* synthetic teacher comments;
* synthetic rosters;
* synthetic pds-core standards libraries;
* synthetic scans or scan-like fixtures.

Do not commit:

* real student names;
* real rosters;
* real student writing;
* real grades;
* real parent contact information;
* real scanned student work;
* real review notes;
* real feedback;
* real exports;
* real screenshots of student work or workspace data.

Local workspace artifacts should not be committed.

## Current Non-Goals

Quillan does not currently provide:

* OCR;
* handwriting recognition;
* PDF text extraction;
* AI tagging;
* AI scoring;
* AI feedback;
* automatic grading;
* automatic mastery calculation;
* automatic evidence selection among duplicates;
* automatic review-state decisions;
* automatic requirements evaluation;
* recursive raw scan folder intake;
* production inbox draining;
* source cleanup/archive automation;
* LMS integration;
* cloud sync;
* gradebook sync;
* parent/student emailing;
* district dashboards;
* hosted multi-user collaboration;
* a mobile app workflow;
* a complex GUI.

Quillan's implemented printable pages are identity-bearing writing surfaces. They do not evaluate student work.

Quillan's scan intake routes QR-identified paper responses. It does not read the student's writing.

Quillan's review tools record teacher decisions. They do not replace teacher judgment.

## Guided Paper-Response Workflow

From the Quillan menu, teachers select assignments by class and assignment name;
they do not normally need to paste an `assignment.json` path. Scan Intake creates
and lists the shared workspace `scans_inbox/` drop zone. Select a PDF or supported
image there (or use the custom-path fallback), route its QR-bearing pages, then
choose **Assemble submissions**. Routing preserves source scans and files routed
evidence; assembly creates the review-ready `submission.json` record. Existing
submission records are skipped by default, so teacher review records are not
replaced. Review actions become available only after assembly.

## Development Workflow

Use issue branches for changes:

```powershell
git checkout main
git pull
git checkout -b issue-number-short-description
git push -u origin issue-number-short-description
```

Recommended pull request workflow:

1. Make a focused change.
2. Run `pytest`, `ruff check .`, and `mypy .`.
3. Prefer `.\run_tests.ps1` before merge.
4. Commit and push the branch.
5. Open a pull request into `main`.
6. Link the relevant issue using `Closes #<issue-number>`.
7. Use squash merge for most feature branches.
8. Delete the remote branch after merging.
9. Pull the updated `main` branch locally.

## License

MIT
