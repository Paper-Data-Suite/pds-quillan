# Batch Feedback Assembly

Issue #412 adds a teacher-facing distribution layer over existing canonical
student feedback PDFs. It does not change the feedback storage contract.

```text
review
  -> #387 per-student feedback generation/export
  -> submissions/<student_id>/exports/feedback.pdf
  -> #412 batch assembly
       -> feedback_print_packet.pdf
       -> feedback_sharing_bundle.zip
```

## Ownership boundary

The canonical student-facing artifact and provenance remain:

```text
submissions/<student_id>/exports/feedback.pdf
review.json.exports.feedback_pdf
```

Batch output is derived, rebuildable, teacher-facing, multi-student, and safe
to delete. Assembly never generates feedback, changes review state, modifies
canonical records, registers Academic Work, creates Academic Results, publishes
records, contacts Meridian, or calculates grades or proficiency.

#387 owns generating and refreshing canonical per-student exports. #412 only
selects and assembles exports that the existing status contract reports as
current. Missing and stale students are excluded and directed to Batch Feedback
Export.

## Planning and eligibility

`build_feedback_assembly_plan(...)` is read-only. Whole-class planning evaluates
every canonical roster student in canonical order. Selected planning accepts
one or more exact, unique roster `student_id` values and still emits canonical
roster order. Display names are never identifiers.

The plan contains only identities, display labels, requested options, bounded
status/reason codes, canonical workspace-relative source paths, timestamps,
file sizes, digests, and page counts. It contains no student writing, feedback
text, private notes, rationales, observations, evidence paths, scans, or QR
contents.

A source is current only when all of these hold:

- the existing feedback status is `present`;
- the canonical PDF is an ordinary file at the exact canonical path;
- feedback metadata exists and names that path;
- `source_review_updated_at` equals the current valid review timestamp;
- class, assignment, student, and roster identities match; and
- the PDF is readable and contains at least one page.

Symlink, junction, traversal, noncanonical metadata-path, unreadable-PDF, and
identity states fail closed. Planning reads source bytes only to calculate
bounded size/digest/page information and does not retain feedback content.

## Execution and state changes

Execution reloads canonical roster and status, requires the confirmed ordering,
and revalidates every planned current source. After source inspection and
revalidation, one final guarded read pins each accepted PDF by its preview digest
and page count; that final validated byte set is reused for every requested
output. A changed, missing, stale, or replaced source is excluded as
`state_changed`; it is never substituted.

If no current PDFs remain, execution creates nothing and directs the teacher to
Batch Feedback Export. For `both`, print and ZIP output always use one identical
validated student set.

## Outputs

Outputs are installed beneath:

```text
exports/feedback_batches/<YYYYMMDDTHHMMSSZ>/
  feedback_print_packet.pdf
  feedback_sharing_bundle.zip
```

Only requested files are present. Existing batch directories are never
overwritten. Requested artifacts are written and verified in one assignment-
local staging directory, then the complete directory is atomically renamed to
its final identity. A pre-install failure removes staging where safely possible
and never touches source PDFs.

The print packet appends complete source documents in roster order; source
pages remain contiguous. Duplex-safe mode inserts one blank page after an
odd-page student only when another student follows. No trailing blank is added.

The sharing ZIP contains only separate PDF members. Member contents equal the
canonical source bytes. Names use normalized roster display labels, exclude
path components and illegal Windows characters, and add a deterministic exact-
student-ID disambiguator only on collision. The ZIP and print packet are both
sensitive multi-student containers. Neither is appropriate to send wholesale
to one student.

## CLI

```powershell
quillan assemble-feedback-batch <class_id> <assignment_id> `
  --whole-class --output print --dry-run

quillan assemble-feedback-batch <class_id> <assignment_id> `
  --student-id <student_id> --student-id <student_id> `
  --output bundle --yes

quillan assemble-feedback-batch <class_id> <assignment_id> `
  --whole-class --output both --duplex-safe --yes
```

Exactly one scope and exactly one execution boundary are required. `--dry-run`
performs complete planning without creating `feedback_batches/`, output files,
or staging files. Direct CLI execution never opens a file or folder.

## Teacher menu

Assignment Review Actions exposes `G. Prepare Feedback for Printing / Sharing`
adjacent to `F. Batch Feedback Export`. The flow is scope, output, optional
duplex mode, one preview, one confirmation, assembly, and result. Cancellation
before confirmation writes nothing. After success the teacher may open the
primary artifact or output folder through Quillan's workspace-contained output
opener.

## Release boundary

This workflow ships in Quillan v0.10.1 with `pypdf>=5,<7` as a runtime
dependency. The installed-wheel gate creates two current canonical feedback
PDFs, exercises dry-run and both-mode CLI assembly outside the source checkout,
checks packet order and ZIP source-byte equality, and proves canonical records
and academic/publication state remain unchanged. Because #412 does not change
PDS2, routing, scan intake, response-page generation, physical evidence,
review, or publication semantics, v0.10.0 physical-paper acceptance remains
applicable and is not repeated.
