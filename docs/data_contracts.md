# Quillan Data Contracts

The versioned, read-only selected-student diagnostic is defined separately in
[`review_status_contract.md`](review_status_contract.md). It composes canonical
assignment, submission-manifest, and review-record data without changing any of
those source schemas.

Quillan stores structured evidence and teacher review data in local files under
the teacher-selected Paper Data Suite workspace.

The active v0.8.6 review model is standards-based:

```text
student evidence -> review unit -> Focus Standard -> teacher judgment -> feedback/reporting
```

The old generic tag, comment-bank, rubric, and criterion-score runtime model
has been removed. This index documents the active v0.8.6 contracts.

## Active Contracts

### Assignment Review Dashboard

The live assignment review dashboard is an immutable derived read model, not a
stored workspace record. Its versioned JSON representation and exact read-only
boundary are defined in
[`review_dashboard_contract.md`](review_dashboard_contract.md). It does not
change the assignment, submission, review, feedback-export, or scan-review
schemas.

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

Page-management transitions retain excluded pages and evidence rather than
deleting them. Exclusion temporarily preserves each evidence role and state so
restoration can recover the prior selection (including no selection); older
excluded records use a conservative legacy fallback. Page state is independent
of top-level lightweight `submission_state`, which page management preserves.
A plain-paper manual manifest has `expected_pages: null` and no digital page
records because the physical evidence remains outside Quillan. Both the direct
`pages` CLI and teacher menu use the same shared page-management service.

The lightweight submission state in `submission.json.submission_state` is
separate from the standards-based review workflow state in
`review.json.review_state`. Neither field is synchronized to the other.

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
classes/<class_id>/assignments/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/class_summary.csv
classes/<class_id>/assignments/<assignment_id>/exports/standards_summary.csv
```

The reporting contract is defined in
[`assignment_reporting_contract.md`](assignment_reporting_contract.md).

The Student Performance Summary is the compact ordinary teacher-facing
student-by-standard table. The Comprehensive Class Summary at
`class_summary.csv` reports submission/review status, minimum-requirement
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

## Synthetic Data Policy

Repository examples and tests must use synthetic data only.

Do not commit real student names, real student IDs, real rosters, real student
writing, real scans, real review notes, real feedback, real grades,
accommodations, attendance or discipline context, parent/guardian data, or
other personally identifiable student information.

Reusable comments and reporting examples must avoid student-identifying details
and private classroom context, even when the example is synthetic.

## Plain-paper manual submissions

An evidence-less manual submission uses submission-manifest schema version 1
with `expected_pages: null`, `pages: []`, and `submission_state: "unreviewed"`.
Its `module_details` records `submission_entry_method: "plain_paper_manual"`,
`physical_evidence_status: "teacher_has_external_plain_paper"`, and
`created_by_workflow: "plain_paper_submission"`. No routed evidence path or
digital artifact is created; the physical paper remains outside Quillan.
