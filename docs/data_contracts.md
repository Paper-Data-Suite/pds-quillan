# Quillan Data Contracts

Quillan stores structured evidence and teacher review data in local files under
the teacher-selected Paper Data Suite workspace.

The active v0.8.6 review model is standards-based:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

This index distinguishes active v0.8.6 runtime contracts from legacy or
compatibility material. Legacy comment banks, tag banks, and rubrics may remain
documented for history, but they are not the current teacher review workflow.

## Active Contracts

### Assignment

Active assignments use schema version `2` and live at:

```text
classes/<class_id>/assignments/<assignment_id>/assignment.json
```

The v0.8.6 assignment contract is defined in
[`assignment_contract.md`](assignment_contract.md). It covers:

* `student_prompt`;
* `standards_profile_id`;
* `focus_standard_ids`;
* `review_unit`;
* `rating_scale`;
* `basic_requirements`;
* `minimum_requirement_policy`; and
* assignment identity, timestamps, and module metadata.

Legacy fields such as `tagging_mode`, `focus_standards`, and `rubric_id` are
not active schema version `2` fields.

### Submission Manifest

Submission manifests live at:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/submission.json
```

They describe routed evidence, retained-source provenance, page state, selected
evidence, duplicate/missing evidence conditions, and lightweight submission
state. They do not store teacher ratings, comments, feedback, or reports.

### Review Record

The active teacher-review artifact is schema version `2` `review.json`:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/review.json
```

The contract is defined in
[`review_record_contract.md`](review_record_contract.md). It covers:

* `minimum_requirement_checks`;
* `minimum_requirement_outcome`;
* `review_units`;
* `standard_observations`;
* `overall_standard_ratings`;
* `feedback.standard_feedback`;
* `private_notes`;
* `exports.feedback_pdf`; and
* `exports.feedback_markdown`.

Top-level v1 fields such as `notes`, `tags`, `comments`, `scores`, and
`requirement_checks` are legacy and are not active v0.8.6 review fields.

### Reusable Focus Standard Comments

Reusable Focus Standard comments live at:

```text
shared/focus_standard_comments/<comment_set_id>.json
```

The contract is defined in
[`focus_standard_comment_contract.md`](focus_standard_comment_contract.md).
Runtime support includes validation, lookup, saving teacher-approved comments
from feedback composition, usage updates, and safe writes.

Reusable Focus Standard comments are source material. When selected for a
student, their text is copied into `feedback.standard_feedback` as a stable
snapshot. Exports use the copied review-record text rather than live reusable
comment lookup.

### Feedback Export

Student feedback exports are derived artifacts:

```text
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/assignments/<assignment_id>/submissions/<student_id>/exports/feedback.md
```

The export contract is defined in
[`feedback_export_contract.md`](feedback_export_contract.md). Runtime export
supports Markdown, PDF, and both formats. Feedback is organized by Focus
Standard and may include minimum-requirement return feedback, teacher-selected
overall ratings, rationales, selected observations, and teacher-approved
comments.

Feedback exports exclude private notes, internal review IDs,
reusable-comment provenance, routed evidence paths, unselected observations,
and unselected comments.

### Assignment-Local Reporting

Assignment-level reports are derived artifacts:

```text
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

The reporting contract is defined in
[`assignment_reporting_contract.md`](assignment_reporting_contract.md).

The class summary reports submission/review status, minimum-requirement
outcomes, returned-without-full-review status, overall Focus Standard ratings,
feedback PDF/Markdown status, and validation warnings.

The Focus Standard summary reports assignment-local rating distributions,
missing-rating counts, returned-without-full-review counts, and feedback
coverage.

Reports do not calculate grades, percentages, mastery, or cross-assignment
results.

### Printable Response Payloads

Printable response pages use pds-core PDS1 payloads:

```text
PDS1|module=quillan|class=<class_id>|aid=<assignment_id>|sid=<student_id>|page=<page_number>|doc=response
```

Printable response generation embeds the payload as a QR code on each response
page and writes:

```text
classes/<class_id>/assignments/<assignment_id>/templates/printable_response_pages.pdf
```

The printable response contract is documented in
[`printable_response_template.md`](printable_response_template.md).

## Standards References

Shared standards definitions, durable `standard_id` values, reusable standards
profiles, and profile validation are owned by `pds-core`.

Quillan stores durable pds-core references in:

* assignment `standards_profile_id`;
* assignment `focus_standard_ids`;
* review-unit Focus Standard observations;
* overall Focus Standard ratings;
* Focus Standard feedback records;
* reusable Focus Standard comments;
* student feedback exports; and
* assignment-local reports.

Quillan does not maintain an independent standards universe and does not
create, import, edit, retire, or reactivate pds-core standards.

## Workflow Docs

The active workflow and review philosophy are documented in:

* [`prepared_review_workflow.md`](prepared_review_workflow.md)
* [`teacher_review_model.md`](teacher_review_model.md)
* [`cli_contract.md`](cli_contract.md)
* [`workspace_lifecycle.md`](workspace_lifecycle.md)

## Legacy And Compatibility Docs

The following documents describe historical or compatibility material, not the
active v0.8.6 standards-based review workflow:

* [`comment_bank_contract.md`](comment_bank_contract.md)
* [`tag_bank_contract.md`](tag_bank_contract.md)
* [`rubric_contract.md`](rubric_contract.md)
* [`starter_materials.md`](starter_materials.md)
* [`nj_ela_starter_materials.md`](nj_ela_starter_materials.md)

Legacy files may remain if they are clearly historical, inactive, disabled, or
compatibility-only. Active docs and examples should not instruct teachers to
use generic comment banks, tag banks, rubric criteria, old direct write
commands, or schema version `1` top-level review fields as the current path.

## Synthetic Data Policy

Repository examples and tests must use synthetic data only.

Do not commit real student names, real student IDs, real rosters, real student
writing, real scans, real review notes, real feedback, real grades,
accommodations, attendance or discipline context, parent/guardian data, or
other personally identifiable student information.

Reusable comments and reporting examples must avoid student-identifying details
and private classroom context, even when the example is synthetic.
