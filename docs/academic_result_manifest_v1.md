# Quillan Academic Result Manifest v1

## Purpose and ownership

`quillan_academic_result_manifest_v1` is Quillan's immutable, producer-owned
representation of one record-set revision of writing-review results for one
managed assignment. Its record type is `quillan_academic_result_manifest`; its
producer module and `work.module_id` are `quillan`.

Quillan publishes producer-native writing-review evidence and ratings. Core
registers and verifies publication envelopes. Meridian or another authorized
consumer applies grading/reporting policy. A Quillan native rating scale is not
a Meridian proficiency scale unless an explicit downstream versioned mapping
policy says so.

The module is a pure contract: it performs no workspace, registry, catalog,
artifact, roster, or standards-library I/O and calculates no proficiency,
Grade, missing-work state, or portfolio policy. Construction belongs to #361;
privacy projection is defined by
[Quillan Publication Projection Policy v1](publication_projection_policy_v1.md);
revision, correction, and withdrawal behavior is defined by
[Quillan Publication Revision Policy](publication_revision_policy.md); explicit
assignment eligibility and Core registration are defined by
[Quillan Academic Work Registration](academic_work_registration.md); and manifest
generation/publication integration remains #361–#364.

## Exact schema

Every object has exactly the listed keys. Unknown keys are invalid. Nullable
fields remain present with JSON `null`.

```text
manifest
  record_type, contract_version, producer_module_id, generated_at
  record_set { record_set_id, revision }
  work { module_id, class_id, work_id }
  source_snapshot { relative_path, sha256, contract_version }
  assignment
    assignment_id, title, writing_type, student_prompt
    standards_profile_id, focus_standard_ids[]
    review_unit { type, singular_label, plural_label }
    rating_scale { scale_id, levels[] { value, label, description } }
    basic_requirements
      { paragraphs_min, paragraphs_max, word_count_min, word_count_max,
        required_elements[] }
    minimum_requirement_policy { allow_return_without_full_review }
  students[]
    student_id
    source_snapshot
      submission { relative_path, sha256, contract_version }
      review { relative_path, sha256, contract_version }
    submission
      class_id, assignment_id, student_id
      submission_state, entry_method, expected_pages, digital_provenance
    review
      class_id, assignment_id, student_id
      review_state, minimum_requirement_outcome, review_units[]
      overall_standard_ratings[], feedback
```

`record_set_id` is a safe identifier and `revision` a positive non-Boolean
integer. This identity describes the whole frozen record set; it is not a native
schema version, review state, Core registration revision, publication identity,
series head, or package version. v1 defines no “latest” inference.

Work identity is `(module_id, class_id, work_id)`. `work_id` equals
`assignment.assignment_id`; all represented student sources agree with this
work and their `student_id`.

Identifier domains remain distinct. Record-set, work, assignment, student, and
retained-scan identities use the shared path-safe PDS identifier contract.
Assignment `review_unit.type` uses Quillan's native assignment type grammar.
Standards profile IDs, rating-scale IDs, Focus Standard IDs, and review-local
unit/observation/comment IDs preserve bounded nonempty native text. In
particular, a durable standard such as `njsls-ela:RL.CR.9-10.1` is preserved
exactly; it is not passed through the path-safe identifier grammar, normalized,
or rewritten.

## Exact source lineage

Sources are relative to the exact managed work root. Canonical POSIX spelling is
required; absolute and drive-qualified paths, backslashes, empty/dot components,
and traversal are prohibited. Digests are exactly 64 lowercase hex characters.

| Source | Required path | Native contract |
|---|---|---:|
| Assignment | `assignment.json` | `2` |
| Submission | `submissions/<student_id>/submission.json` | `1` |
| Review | `submissions/<student_id>/review.json` | `2` |

Snapshots bind exact producer bytes. They differ from Core Academic Work
Registration `source_records` and a Core Publication Record `source_record`.
They are never authorization to open records, submissions, scans, evidence, or
feedback. Native children do not acquire fabricated Core record IDs.

## Assignment and native rating scale

The student prompt is intentionally included and bounded to 20,000 characters.
The snapshot preserves Focus Standard order, standards profile, review-unit
labels, recognized basic requirements, minimum-return policy, and assignment-
local scale order. The exact assignment digest binds all remaining native state.

Level values are strict native integers; Booleans, floats, strings, and numeric
coercion are prohibited. Values need not be consecutive or start at one. Every
present observation and overall rating is first validated as a non-Boolean
integer and then matched to one copied level value. No
percentage, threshold, mastery label, Grade, global default scale, or Meridian
mapping is inferred. Overall ratings are teacher-entered judgments and are never
calculated from observations.

## Student and submission meaning

Students are unique and sorted by `student_id`; names, email, guardian,
accommodation, demographic, and unrelated roster fields are absent. A projection
may include a student only with represented canonical submission schema 1 and
review schema 2 records. Roster presence creates no entry. Absence from
`students[]` means no represented result—not zero, missing, failed, excused,
incomplete, submitted, or unreviewed.

`submission_state` and `review_state` remain separate. `entry_method` is
`pds2_response_pages` or `plain_paper_manual`. Plain paper requires
`expected_pages=null` and `digital_provenance=null`; no digital identity or
evidence is fabricated.

PDS2 requires positive `expected_pages` and:

```text
digital_provenance
  issuance_id, generation_id, artifact_id, expected_page_ids[]
  evidence_references[]
    page_id, evidence_id, observation_id, route_id
    issuance_id, generation_id, artifact_id
    source_page_number, source_scan_id, source_sha256
    routed_evidence_sha256
```

Identity fields must agree with their envelope. Locator paths, retained-source
paths, filenames, and QR payloads are excluded. The
[publication projection policy](publication_projection_policy_v1.md) restricts
evidence references to authoritative selected evidence; candidate, unselected
replacement, excluded, and unselected duplicate evidence are not published.
Withholding cannot be interpreted as weak or missing academic evidence.
Discovery is not access.

PDS2 typed identities use the current native Quillan forms:

```text
issuance_id    iss_<32 lowercase hexadecimal characters>
generation_id  gen_<32 lowercase hexadecimal characters>
artifact_id    art_<32 lowercase hexadecimal characters>
page_id        pg_<32 lowercase hexadecimal characters>
evidence_id    obs_<32 lowercase hexadecimal characters>
observation_id obs_<32 lowercase hexadecimal characters>
route_id       rt_<32 lowercase hexadecimal characters>
```

Within one evidence reference, `evidence_id` equals `observation_id`, matching
the submission contract's selected response-page observation identity. Every
reference carries complete retained-source provenance: a valid `source_scan_id`,
positive non-Boolean `source_page_number`, and exact lowercase `source_sha256`.
Partial retained-source tuples are invalid. The manifest deliberately omits
`source_filename`, `retained_source_path`, and `routed_evidence_path`.

Across references, one `(source_scan_id, source_page_number)` cannot identify
contradictory `page_id` values, and one `source_scan_id` cannot identify
contradictory `source_sha256` values. Repeated references remain valid when both
relationships are consistent.

## Review, observations, ratings, and non-scores

`review_state` is exactly one of `not_started`, `requirements_checked`,
`returned_without_full_review`, `observations_in_progress`,
`observations_complete`, `ratings_complete`, `feedback_composed`,
`ready_for_export`, or `exported`. Arrays, timestamps, comments, and exports do
not infer it. `exported` is not stronger performance. None is a Grade.

Minimum-requirement outcome separately preserves `status`, explicit return flag,
nullable `updated_at`, and teacher-note publication state. Status is
`not_checked`, `met`, `unmet_continue_review`, or
`returned_without_full_review`; return status, flag, and review state agree.
Individual checks remain outside v1. The publication projection policy permits
only a narrow configured-unmet view in the separate returned-work feedback
artifact; it does not add individual requirement checks to this manifest.

Review units have unique IDs and positive increasing sequences. Each contains
at most one observation per assignment Focus Standard. Observations preserve
`applicable`, nullable `evidence_present`, nullable `rating`, feedback inclusion,
timestamp, and rationale publication state. Non-applicable observations require
null evidence/rating. Applicable with `evidence_present=false` does not imply a
low rating; a null rating is not a numeric sentinel.

Every represented review unit's `unit_type` equals the assignment-configured
review-unit type used by the native workflow. A standard-feedback entry may
include only observation IDs whose observations carry that entry's exact
`standard_id`.

Overall ratings contain only represented teacher judgments. A missing standard
has no entry. `ratings_complete` does not manufacture entries. Consequently the
lowest native rating, no overall rating, returned without full review, review not
at ratings, not-applicable observation, and applicable observation without
evidence remain distinct.

## Feedback and privacy boundary

`PublishedText` is `{ disposition, text }`, where disposition is `absent`,
`withheld`, or `included`. Text is nonempty and bounded only when included and is
otherwise null. This distinguishes absent source text from deliberate redaction.
The value object has no default disposition and neither its constructor, mapping
parser, validator, nor serializer examines native source text or promotes text to
`included`. The
[publication projection policy](publication_projection_policy_v1.md) chooses
the disposition explicitly; the existence of a rationale, note, or comment in
`review.json` is not permission to publish it.

Feedback preserves global and per-standard inclusion choices, selected
observation IDs, and bounded included comment records. Observation/overall
rationales, minimum-outcome notes, and comment text use `PublishedText`; the
publication projection policy includes, withholds, or omits them without changing
educational meaning.
Reusable-comment source/provenance fields are not part of the public comment
object. Individual requirement checks and detailed evidence disclosure remain
bounded by the publication projection policy and later artifact-reader contracts.

Always excluded: `private_notes`, roster display data, live reusable-comment
state, arbitrary `module_details`, exception/debug text, diagnostics, absolute or
private paths, and feedback PDF/Markdown metadata. Derived exports prove neither
ratings nor completion, publication/Grade eligibility, or proficiency.

The contract deliberately contains no workspace projection helper or default
mapping from native review text. It can represent withheld/absent text without a
placeholder or empty string, while the publication projection policy owns the
allow/deny decision and later generation workflows retain responsibility for
applying it.

## Immutability, canonical JSON, and fixture

Models are frozen and slotted; collections are defensively copied tuples.
Validation rejects unsafe identities/paths, invalid timestamps/digests,
Booleans in integer fields, controlled-vocabulary errors, duplicates, ordering
errors, identity disagreement, scale mismatches, contradictions, and fabricated
plain-paper provenance. JSON decoding also rejects malformed UTF-8/JSON,
duplicate keys at every depth, and nonfinite numbers.

Canonical JSON is UTF-8 with sorted keys, two-space indentation, finite numbers,
UTC timestamps ending `Z`, and exactly one trailing newline. The normative
fixture is
`tests/fixtures/publication/quillan_academic_result_manifest_v1.json`.
It demonstrates a native `0, 2, 4` scale, genuine lowest and missing ratings,
applicability distinctions, PDS2 lineage, bounded/withheld text, and plain-paper
return without digital fabrication. It parses and reserializes byte-exactly.

## Future capability and consumers

The later profile is expected to advertise only `standards_ratings`. Review-unit
observations are not automatically Core `criterion_scores` or Meridian values.
No points, question evidence, multiple attempts, moderated/criterion scores, or
intervention capability is claimed.

An authorized consumer must verify canonical Core state plus exact manifest path
and SHA-256, parse through Quillan, preserve native meaning and missingness, and
only afterward apply an explicit versioned consumer policy.
