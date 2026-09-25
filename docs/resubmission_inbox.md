# Resubmission / Rescan Review

Classification: **active Quillan v0.10.3 workflow contract**.

## Purpose

`Assignment Review Actions -> 8. Review resubmissions / rescans` is a focused
teacher inbox for successfully routed page evidence that still needs an
evidence-selection decision. It answers which students and logical pages have
new evidence without requiring the teacher to open every submission or
interpret the full diagnostic dashboard.

The same read model is available noninteractively:

```powershell
quillan resubmission-inbox <class_id> <assignment_id> --format text
quillan resubmission-inbox <class_id> <assignment_id> --format json
```

JSON uses `record_type: quillan_assignment_resubmission_inbox` and
`schema_version: 1`. It contains canonical identities and timestamps but no
absolute paths or student writing.

## What qualifies

For an assembled logical page, an item is actionable when an active candidate
or replacement observation is strictly newer than the current selected
observation. If there is no selection, every active candidate remains
actionable. Excluded, damaged, or otherwise inactive evidence is not an active
candidate.

This differs deliberately from `page_state == duplicate`. Duplicate is a
structural diagnostic: a page may retain several historical evidence records
after the teacher has selected the latest one. The inbox includes only newer
unresolved evidence, so older retained candidates do not remain pending merely
because the page remains structurally duplicate.

Exact retries resolve to the existing observation identity and therefore do
not create a second item. A later physical intake has a distinct canonical
observation identity and remains discoverable even when its bytes match an
earlier scan.

## Awaiting assembly and attention

A strictly verified later observation not yet represented in an existing
student digital manifest appears as `awaiting assembly`. When no manifest
exists, Quillan requires more than one observation for the same logical page
and treats only observations after the earliest as rescan signals. Ordinary
first intake before initial assembly is therefore not a resubmission item.
Opening the inbox never assembles evidence.
The teacher must choose the explicit assembly action, after which the inbox is
rebuilt from canonical state.

Quillan fails closed when it cannot establish the candidate relationship. An
invalid manifest or review with an established rescan signal, an unrostered
identity, a plain-paper/digital
conflict, an unsupported issuance relationship, or a selected/candidate record
that does not match a strictly verified observation appears as bounded
`attention required` state. Resolution actions are unavailable for that item.

Strict observation discovery continues to validate canonical identity,
workspace containment, non-link paths, routed-evidence size and SHA-256,
retained-source provenance, and page/issuance relationships. Inbox menu
positions, display names, filenames, and timestamps are never authoritative
identity.

## Chronology and terminology

Chronology comes from the canonical observation `created_at`, which is the
stable physical-intake timestamp. It orders candidates by timestamp with
evidence identity as a stable tie-breaker; it never decides which evidence
wins.

Classification is bounded:

- `new after feedback` means the evidence timestamp is later than the latest
  valid feedback-export `generated_at` recorded by Quillan;
- `new after recorded review activity` is used only when no feedback export
  exists and the evidence is later than `review.updated_at`;
- `additional scanned evidence` is the neutral fallback;
- `awaiting assembly` means the verified observation is not yet incorporated;
- `attention required` means Quillan could not safely derive an actionable
  relationship.

These labels do not say the writing changed. Quillan performs no OCR,
handwriting comparison, image diff, semantic comparison, or revision-quality
judgment.

## Explicit resolution

The detail screen can open the current selection and exact candidate through a
fresh exact-evidence service. Each open re-reads class, assignment, student,
page, and observation identity; validates the complete immutable manifest
projection including retained-source provenance and module details; and
re-verifies routed bytes, size, SHA-256, and retained-source provenance before
calling the local opener. Opening is read-only and does not mark evidence seen
or resolved. The detail remains open after either image is opened so both can
be compared before a decision. Inbox rows include the candidate scan timestamp
to distinguish multiple rescans for the same page.

`Use new scan as selected evidence` requires confirmation. The evidence
resolution service re-reads and strictly verifies the current canonical state,
then revision-guards one manifest update:

- the chosen active newer candidate becomes the one selected evidence record;
- the previous selection becomes retained active candidate evidence;
- no evidence bytes, observation, route, retained source, or provenance record
  is deleted;
- teacher ratings, observations, comments, notes, requirements, rationale, and
  review completion are unchanged.

`Keep current evidence and dismiss new candidate` also requires confirmation.
It changes only the candidate role/state to excluded. The observation and all
evidence/provenance bytes remain retained. Dismissal is unavailable when the
page has no authoritative selection, preventing all usable evidence from being
excluded. Back, cancel, image opening, and inbox visitation perform no writes.

With several rescans, selecting an intermediate candidate leaves any strictly
newer candidates pending. Selecting the newest candidate leaves older evidence
retained but removes it from the ordinary inbox. A later physical intake makes
the page appear again.

## Feedback freshness

New feedback export metadata records a deterministic fingerprint of the
ordered `(page_number, selected_evidence_id)` projection. Candidate routing,
assembly, or dismissal may advance `submission.json.updated_at`, but does not
change this fingerprint and therefore does not stale feedback. Explicitly
selecting different authoritative evidence changes the fingerprint and makes
earlier feedback stale. Feedback freshness also checks `review.updated_at`.
Stale means the teacher should review and export again; Quillan does not alter
judgments or rewrite feedback.

## Fresh read architecture

The inbox reuses `AssignmentReviewReadContext`, introduced by #414. One fresh
redraw performs one assignment load, one roster load, and one strict grouped
observation discovery/hash pass. Student manifests and optional reviews are
loaded once from the already validated assignment context. Summary counts,
rows, candidate detail identities, and chronology are projections of that one
read.

The context is discarded before the next action. After assembly, selection,
dismissal, review navigation, evidence opening, feedback export, or refresh,
the inbox is rebuilt. There is no `inbox.json`, persistent cache, database,
index, seen flag, or manually maintained revision list.

## Related workflows

- The full diagnostic dashboard continues to report structural page state,
  including duplicates.
- Scan Review continues to handle routing/intake failures, not successful
  rescans.
- The #383 review queue retains its existing categories. A completed review may
  independently have pending resubmission evidence.
- Plain-paper submissions remain evidence-less and are never silently converted
  to digital submissions.
