# Quillan Publication Projection Policy v1

## Purpose and ownership

`quillan_publication_projection_v1` is Quillan's producer-owned privacy floor for
publication projections derived from validated assignment, submission, and review
records.

The policy answers one narrow question:

```text
which already-valid Quillan-native values may cross the producer publication boundary?
```

It does not answer:

```text
who may discover a publication
who may inspect a student-level manifest
who may open student work
who may receive a feedback artifact
which result affects a Grade
which artifact belongs in a Portfolio
```

The governing separation is:

```text
native field exists
  != field is publication-approved
  != Core discovery authorizes manifest inspection
  != manifest inspection authorizes source access
  != source identity authorizes artifact retrieval
  != producer projection authorizes disclosure to a recipient
```

Quillan owns the producer projection and its closed allowlists. Core owns
publication envelopes and integrity verification. Application/deployment policy owns
authorization. Meridian and Vitrine may narrow Quillan output for their own purposes
but may not broaden it.

## Relationship to Academic Result Manifest v1

The policy is designed for `quillan_academic_result_manifest_v1` without changing
that contract's exact JSON key set.

The manifest already has the public value object:

```text
PublishedText
  disposition = absent | withheld | included
  text
```

This policy decides those dispositions for privacy-sensitive native text.

The distinction is normative:

```text
absent    = no source text exists
withheld  = source text exists but is not publication-approved
included  = source text exists and explicit Quillan policy approves publication
```

`withheld` must never be converted to an empty string, placeholder, low rating,
missing evidence, failed requirement, or other academic state.

The policy module is pure and side-effect free. It does not read workspace files,
load rosters or standards, inspect Core registry state, open evidence, hash files,
write manifests, publish through Core, or apply consumer policy.

## Policy identity

Stable policy version:

```text
quillan_publication_projection_v1
```

The policy version is independent from:

- assignment schema version;
- submission schema version;
- review schema version;
- Academic Result Manifest contract version;
- record-set revision;
- Core registration revision;
- Core Publication Record identity or schema;
- package version;
- Meridian policy;
- and Vitrine Profile policy.

Historical and revision consequences of material policy changes are defined by
[Quillan Publication Revision Policy](publication_revision_policy.md).

## Closed allowlist

The publication rule is:

```text
publish only declared fields and declared text selections
```

The rejected rule is:

```text
publish everything except fields currently known to be secret
```

Unknown native fields and future schema extensions do not become public
implicitly. `publication_field_disposition()` is intentionally closed and fails on
an undeclared field rather than defaulting it to allowed.

There is no caller-controlled privacy bypass such as:

```text
include_private
teacher_mode
admin_mode
include_all
debug
```

A downstream consumer may suppress more. It cannot use a role or audience setting
to widen the canonical Quillan projection.

## Observation rationales

Native source:

```text
review.json.review_units[].standard_observations[].rationale
```

The observation's structured academic state remains distinct from its text:

```text
standard_id
applicable
evidence_present
rating
include_in_feedback
updated_at
```

An existing rationale is `included` only when both are true:

```text
review.feedback.include_review_unit_observations == true
```

and

```text
observation_id is explicitly listed for the same standard_id in
review.feedback.standard_feedback[].included_observation_ids
```

Otherwise an existing rationale is `withheld`.

No source rationale produces `absent`.

The observation-level `include_in_feedback` flag is intentionally not sufficient by
itself. Current Quillan feedback export selects observation content through the
global observation-feedback switch plus the same-standard selected-observation ID
set. The publication policy preserves that existing behavior rather than inventing
a second selection model.

## Overall Focus Standard rationales

Native source:

```text
review.json.overall_standard_ratings[].rationale
```

Overall ratings are teacher-entered native results. Their publication meaning is
separate from whether the rationale text is student-facing.

First apply:

```text
review.feedback.include_overall_standard_ratings
```

If the global setting is false, any existing rationale is `withheld`.

When matching `feedback.standard_feedback` exists, current Quillan semantics use:

```text
include_overall_rating
include_overall_rationale
```

The rationale is included only when both select it through the per-standard feedback
record.

When no per-standard feedback record exists, Quillan's existing feedback exporter
falls back to:

```text
overall_standard_ratings[].include_in_feedback
```

The projection policy preserves that fallback. It does not invent a stricter or
looser replacement rule.

A missing rationale is always `absent`.

## Feedback comments

Native source:

```text
review.json.feedback.standard_feedback[].comments[]
```

Only a comment with:

```text
include_in_feedback == true
```

may appear in the public feedback-comment collection.

A selected comment publishes the exact text copied into `review.json`. An unselected
comment is omitted from the public collection rather than represented with its
private text.

The projection never publishes reusable-comment provenance or live reusable-comment
state, including:

```text
source
reusable_comment_id
save_for_reuse
comment_set_id
module_details
```

A reusable comment selected into a review is already a stable copied native
snapshot. Publication must not look up the source comment set again.

## Minimum-requirement outcome

Assignment-level basic requirements are ordinary assignment context:

```text
paragraphs_min
paragraphs_max
word_count_min
word_count_max
required_elements
minimum_requirement_policy
```

The manifest separately preserves the aggregate native minimum-requirement outcome.

### Outcome teacher note

Native source:

```text
review.json.minimum_requirement_outcome.teacher_note
```

Quillan's current returned-work workflow requires a nonempty note when all three
returned signals agree:

```text
status = returned_without_full_review
returned_without_full_review = true
review_state = returned_without_full_review
```

The existing student feedback exporter renders this note as the student's Return
Note. Therefore the exact returned-work outcome note is `included`.

For other statuses, including:

```text
met
unmet_continue_review
not_checked
```

an existing outcome note is `withheld`. The generic field name `teacher_note` does
not itself establish publication permission.

A missing note is `absent`.

Contradictory returned status, flag, and review state fail closed.

### Individual requirement checks

Academic Result Manifest v1 does not contain an individual requirement-check array,
and this policy does not add one.

The complete native fields remain outside the structured academic-result manifest:

```text
requirement_check_id
requirement_key
label
expected
met
teacher_note
updated_at
module_details
```

The existing returned-work feedback artifact may present a narrower student-facing
view of configured checks that are actually unmet. That derived artifact may use:

```text
label
expected
optional teacher_note
```

It must not turn requirement-check IDs, module details, arbitrary checks, or internal
timestamps into public structured result data.

## PDS2 evidence policy

Quillan submission records distinguish:

```text
candidate
selected
replacement
excluded
```

A PDS2 evidence record is eligible for Academic Result Manifest provenance only when
these native facts agree:

```text
page.selected_evidence_id == evidence.evidence_id
AND
evidence.evidence_role == selected
```

Contradiction fails closed.

Candidate, unselected replacement, excluded, and unselected duplicate evidence are
not published. A page with no selected evidence contributes no evidence reference.

### Allowed selected-evidence provenance

The current manifest's bounded PDS2 reference fields are:

```text
page_id
evidence_id
observation_id
route_id
issuance_id
generation_id
artifact_id
source_page_number
source_scan_id
source_sha256
routed_evidence_sha256
```

They are provenance and integrity references only. They are not paths, URLs,
capability tokens, authorization grants, or instructions to bypass the Quillan
reader.

### Prohibited evidence information

Do not publish:

```text
routed_evidence_path
retained_source_path
source_filename
QR payload
raw route payload
scan-intake diagnostics
routing failure details
duplicate_number
candidate evidence lists
excluded evidence lists
replacement history
quillan_before_page_exclusion
arbitrary module_details
private absolute paths
```

Raw retained scans are not direct Academic Result Manifest artifacts.

Optional native review-unit locators such as `page_number` and `evidence_id` remain
outside Academic Result Manifest v1. Publishing an observation does not turn the
review record into a source-navigation API.

Plain-paper submissions retain:

```text
expected_pages = null
digital_provenance = null
```

and never receive fabricated PDS2 identity.

## Native files and derived artifacts

The canonical files:

```text
assignment.json
submission.json
review.json
```

remain source-only. A consumer must not expose a native file merely because it can
locate it.

`review.json.private_notes` are prohibited. The prohibition includes unnecessary
existence leakage such as:

```text
has_private_notes
private_note_count
private_notes_redacted = true
```

Class-wide and standards-wide reports are not individual student artifacts merely
because one student appears in them.

### Structured feedback

A future structured feedback reader may return only content approved by this policy.
It must not return complete `review.json`, unselected comments, withheld rationales,
private notes, or arbitrary requirement history.

### Feedback PDF and Markdown

The existing PDF and Markdown exports are derived student-facing artifacts, not
canonical review state. Their existence or metadata in `review.json.exports` does
not grant publication or access permission.

A later artifact reader may expose an exact feedback export only after verifying its
relationship, source/projection provenance, applicable historical state, and
separate artifact-access authorization.

### Original student work

A later student-work artifact projection may resolve only producer-confirmed selected
evidence. It must not fall back to candidate evidence, duplicate alternatives,
excluded evidence, unrelated replacement history, complete retained scans, another
student's pages, or arbitrary source bytes.

Artifact resolution belongs to #364, not this policy module.

## Discovery is not authorization

Core publication discovery supplies bounded candidate metadata and exact publication
integrity information. It does not establish authority to inspect student-level
manifest contents or underlying artifacts.

The intended flow is:

```text
discover candidate publication through Core
-> reload canonical Core publication state
-> evaluate compatibility
-> establish authorization for exact student/work/purpose
-> verify exact manifest path and SHA-256
-> parse through Quillan's public contract
-> return only the bounded authorized projection
```

The access gates remain distinct:

```text
authorized manifest/result lookup
  != authorized feedback-artifact lookup
  != authorized student-work lookup
  != authorized underlying source resolution
```

A manifest identifier, source digest, route ID, page ID, or scan ID does not by
itself authorize any later lookup.

Ordinary denial must not unnecessarily reveal private-note existence, hidden
feedback text, candidate/duplicate evidence counts, retained-scan paths, or another
student's submission details.

## Producer and consumer ownership

Quillan owns:

- native educational semantics;
- projection version and field allowlists;
- privacy-sensitive text disposition;
- selected-evidence eligibility;
- prohibited producer fields;
- and later public-reader behavior.

Core owns:

- Academic Work and publication envelopes;
- exact manifest-path and digest binding;
- publication-series state;
- compatibility metadata;
- and rebuildable discovery catalogs.

The application/deployment layer owns actual actor, purpose, and source/artifact
authorization.

Meridian owns grading/reporting policy after authorized producer parsing.

Vitrine owns portfolio Candidate/Selection/Profile policy after authorized producer
parsing.

Neither consumer may broaden this producer privacy floor.

## Synthetic examples

These examples are illustrative policy inputs only. They are not workspace records,
manifest fixtures, authorization examples, or permission grants.

### Selected observation rationale

Given validated native feedback state:

```text
include_review_unit_observations = true
standard_id = njsls-ela:RL.CR.9-10.1
observation_id = observation_0001
included_observation_ids for that same standard = [observation_0001]
rationale = "The claim is supported by a precise quotation."
```

the publication decision is:

```text
PublishedText(
  disposition = included,
  text = "The claim is supported by a precise quotation."
)
```

If the observation ID is not selected for that same standard, the same existing
rationale becomes:

```text
PublishedText(disposition = withheld, text = null)
```

### Overall rationale withheld by per-standard feedback

Given:

```text
include_overall_standard_ratings = true
overall_standard_ratings[].include_in_feedback = true
standard_feedback.include_overall_rating = true
standard_feedback.include_overall_rationale = false
rationale = "The response is consistent but needs more developed analysis."
```

the numeric native rating remains result data, while the rationale decision is:

```text
PublishedText(disposition = withheld, text = null)
```

### Returned-work note and requirement detail

Given:

```text
status = returned_without_full_review
returned_without_full_review = true
review_state = returned_without_full_review
outcome teacher_note = "Add the missing textual evidence and resubmit."
configured requirement_key = required_elements:textual evidence
check.met = false
```

the outcome note is `included`. A separate returned-work feedback artifact may show
that configured unmet check's `label`, `expected`, and optional `teacher_note`; it
must not show the check ID, module details, or internal timestamp.

### Selected PDS2 evidence

Given one page with:

```text
selected_evidence_id = obs_00000000000000000000000000000001
```

and one same-page evidence record with:

```text
evidence_id = obs_00000000000000000000000000000001
evidence_role = selected
```

that evidence record is eligible to contribute the bounded `EvidenceReference`
provenance fields. A different candidate, replacement, excluded, or duplicate
alternative on the same page is not eligible, and the IDs themselves do not
authorize source or artifact access.

## Decision matrix

| Native content | Academic Result Manifest v1 | Separate artifact projection | Rule |
| --- | --- | --- | --- |
| overall Focus Standard rating | included native result | may appear in feedback | preserve assignment-local scale |
| overall rationale | conditional `PublishedText` | conditional | current global/per-standard feedback selection |
| review-unit observation | included structured meaning | conditional | rationale separately gated |
| observation rationale | conditional `PublishedText` | conditional | global switch + same-standard selected observation |
| selected feedback comment | included | feedback | exact copied review text only |
| unselected feedback comment | omitted | omitted | no private text leakage |
| minimum outcome | included native state | return feedback when applicable | preserve non-score semantics |
| returned-work outcome note | `included` | included in return feedback | existing student-facing return contract |
| other outcome note | `withheld` when present | not automatically exposed | teacher-note name is insufficient |
| individual requirement checks | omitted | returned-work minimum view only | configured unmet checks only |
| selected PDS2 evidence | bounded provenance | possible student-work source | exact selected evidence only |
| candidate/duplicate/excluded evidence | omitted | prohibited fallback | selection does not broaden |
| `private_notes` | prohibited | prohibited | no existence leakage |
| feedback export path/metadata | omitted | internal resolution input | metadata is not permission |
| raw retained scan | omitted | prohibited direct | separate sanitized contract required |
| class report | omitted | prohibited as individual artifact | multi-student data |

## Downstream boundaries

### Revision, correction, and withdrawal

[Quillan Publication Revision Policy](publication_revision_policy.md) defines
immutable producer revision identity, exact replay, correction history, historical
reversion, and the producer rules that later Core supersession/withdrawal workflows
must preserve.

### #361 — immutable manifest generation

Loads and validates authoritative native records, applies this pure policy, constructs
Academic Result Manifest v1, binds exact source bytes, and writes immutable manifest
revisions.

### #364 — consumer-neutral reader

Implements bounded authorized manifest/result and artifact lookup. It must not broaden
this policy or use private-native-file fallback.

The Core upgrade, Academic Work Registration, producer profile, Core publication, and
end-to-end integration remain assigned to their existing milestone issues.

## Non-goals

This policy does not:

- change Academic Result Manifest v1's JSON schema;
- generate or write manifests;
- allocate record-set revisions;
- upgrade the Core dependency;
- register Academic Work;
- publish through Core;
- open submissions or retained scans;
- generate new teacher feedback;
- mutate native review records;
- create an authorization system;
- define recipient/audience redaction;
- calculate Grades or proficiency;
- or select Portfolio artifacts.
