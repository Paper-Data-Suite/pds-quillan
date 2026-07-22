# Quillan Data Contracts

Quillan-owned assignment records and all dependent submission, review, and export
records are rooted exclusively beneath
`classes/<class_id>/modules/quillan/work/<assignment_id>/`. Contextual loaders
validate identity and embedded paths before business services receive immutable
record data; the unqualified assignment tree is not read or migrated. See
[Module-qualified record services](module_qualified_record_services.md).

## Quillan response-page dispatch result

`QuillanResponsePageDispatchResult` is a frozen, slotted runtime model. Its route ID
comes from the resolved Core locator. Page, issuance, generation, artifact, class,
assignment, student, logical-page, total-page, and page-role fields come from the
immutable page and issuance context. Source scan ID, original filename, requested
source page, retained path and relative path, SHA-256, intake timestamp, and intake
date come from validated Core retained-source provenance.

That provenance is one indivisible Core retention event. The aware intake timestamp,
original filename, and SHA-256 generate the retained filename. The independently
authoritative `intake_date` selects the `scans/source/YYYY-MM-DD/` bucket, including
when Core receives an explicit date override. Quillan requires both values, the
retained path, POSIX relative path, extension, and `scan_<retained stem>` identity to
agree exactly. Original source filenames may contain no control or Unicode line- or
paragraph-separator characters.

The runtime result contains no display name, assignment title, or writable
continuation flag. Continuation is derived from page role. An exact successful
Quillan outcome is the sole authority accepted by immutable observation
persistence.

The retained scan intake models are frozen and slotted. A source result owns the
exact Core `RetainedSourceScan`; every page and request shares that same object
identity. Page outcomes preserve raw detected text, a locator only after complete
Core parsing, exact Core outcomes, and one terminal category. Core-v2 failure
records place routing identity only in `route_locator` and `target`; bounded
Quillan diagnostics remain under `module_details`.

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
classes/<class_id>/modules/quillan/work/<assignment_id>/assignment.json
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
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/submission.json
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
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/review.json
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
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.pdf
classes/<class_id>/modules/quillan/work/<assignment_id>/submissions/<student_id>/exports/feedback.md
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
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/student_performance_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/class_summary.csv
classes/<class_id>/modules/quillan/work/<assignment_id>/exports/standards_summary.csv
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

### Immutable Printable-response Records

Quillan owns a PDS2-only v1 identity contract for intended printable response
pages. The identities are deliberately distinct:

* a **generation** is one user-invoked generation operation and has a fresh
  `gen_<32 lowercase hex>` identity;
* an **artifact** is one intended PDF file and has a fresh
  `art_<32 lowercase hex>` identity;
* an **issuance** is one intended copy for one class, assignment, and student
  and has a fresh `iss_<32 lowercase hex>` identity; and
* a **page** is one intended physical page in an issuance and has a fresh
  `pg_<32 lowercase hex>` identity.

A Core route is separate from all four. Managed generation registers exactly
one immutable Core route per page, targeted at:

```text
module_id:        quillan
record_kind:      response_page
record_id:        <page_id>
contract_version: "1"
```

Managed packet generation creates one fresh Core route registration for every
immutable physical-page record. The page record itself still contains no route
ID or QR text. The QR carries only
`PDS2|m=quillan|c=<class_id>|w=<assignment_id>|r=<route_id>`; the registration
targets the exact `response_page` record with contract version `1` and contains
only `issuance_id`, `logical_page`, and `total_pages` as module details.

#### Storage

Only issuance and page records are persisted. There are no generation or
artifact aggregate files, indexes, or latest/current pointers.

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/
  response_pages/
    issuances/
      <issuance_id>.json
    pages/
      <page_id>.json
```

Core alone owns `routes/`; Quillan response records never live there.

#### Issuance schema version 1

```json
{
  "schema_version": "1",
  "issuance_id": "iss_0123456789abcdef0123456789abcdef",
  "generation_id": "gen_0123456789abcdef0123456789abcdef",
  "artifact_id": "art_0123456789abcdef0123456789abcdef",
  "class_id": "english10_p2",
  "assignment_id": "literary_analysis",
  "student_id": "00107",
  "generation_context": {
    "output_kind": "class_packet_pdf",
    "reason": "initial",
    "predecessor_issuance_id": null
  },
  "class_label": "English 10 Period 2",
  "assignment_snapshot": {
    "schema_version": "2",
    "title": "Coming-of-Age Literary Analysis",
    "updated_at": "2026-07-19T18:00:00+00:00"
  },
  "student_snapshot": {
    "display_name": "Sample Student",
    "last_name": "Student",
    "first_name": "Sample",
    "period": "2"
  },
  "page_count": 2,
  "page_ids": [
    "pg_0123456789abcdef0123456789abcdef",
    "pg_1123456789abcdef0123456789abcdef"
  ],
  "lifecycle": {
    "status": "prepared",
    "revision": 1,
    "created_at": "2026-07-19T18:30:00+00:00",
    "updated_at": "2026-07-19T18:30:00+00:00",
    "issued_at": null,
    "ended_at": null,
    "reason": null,
    "replacement_issuance_id": null
  }
}
```

The assignment snapshot is bounded to schema version, title, and update time.
The student snapshot is bounded to the printed display name, first/last names,
and period. Creation verifies both snapshots against the current canonical
assignment and roster. Later loading does not consult those mutable sources;
the immutable records remain the historical authority.

#### Page schema and contract version 1

```json
{
  "schema_version": "1",
  "page_id": "pg_0123456789abcdef0123456789abcdef",
  "issuance_id": "iss_0123456789abcdef0123456789abcdef",
  "generation_id": "gen_0123456789abcdef0123456789abcdef",
  "artifact_id": "art_0123456789abcdef0123456789abcdef",
  "class_id": "english10_p2",
  "assignment_id": "literary_analysis",
  "student_id": "00107",
  "logical_page": 1,
  "total_pages": 2,
  "page_role": "response_start",
  "created_at": "2026-07-19T18:30:00+00:00"
}
```

Page one is always `response_start`; every later logical page is
`continuation`. The immutable page record—not QR text, a filename, scan order,
source-page number, current packet settings, or a submission manifest—is the
authority for student identity, issuance membership, logical page, total pages,
and continuation meaning. `source_page_number` will identify a page in a
retained scan file; `logical_page` identifies a page in the original student
issuance. They are independent values.

Page records are created exclusively, cannot be overwritten or updated, and
cannot move between issuances. An issuance is written only after all member
pages and acts as their aggregate commit marker. Its controlled lifecycle is:

```text
prepared -> issued
prepared -> cancelled
prepared -> invalidated
issued   -> superseded
issued   -> invalidated
```

Lifecycle writes require the expected revision and atomically replace only the
issuance JSON. Page bytes never change. `cancelled`, `superseded`, and
`invalidated` are terminal and require a reason; supersession also names a
different, already-issued replacement for the same class, assignment, and
student.

Every additional physical copy receives fresh generation, artifact, issuance,
and page IDs. An `additional_copy` has no predecessor. A `regeneration` names a
persisted predecessor with the same class, assignment, and student, but does
not mutate it. The predecessor may be explicitly superseded only after the
replacement is issued.

Because v1 deliberately has no generation or artifact index, generation uses
fresh cryptographically random generation and artifact IDs for every
additional copy; it must not infer reuse from equivalent content or paths.

These generated-page records are not student submissions and do not prove that
work was returned. Observation-backed digital manifests name one exact issuance
while preserving mutable teacher-controlled evidence state. Plain-paper
submissions remain valid without a generation, issuance, page, route, scan, or
evidence record.

PDS2 PDF generation, route registration, retained-source intake, dispatch,
observation persistence, evidence materialization, and issuance-based assembly
are implemented. Scan-review resolution and broader review/CLI migration remain
later boundaries.

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
