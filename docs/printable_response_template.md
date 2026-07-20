# Printable Response Packet Contract

Quillan generates one combined class-packet PDF at:

```text
classes/<class_id>/modules/quillan/work/<assignment_id>/templates/printable_response_pages.pdf
```

Each actual operation creates one fresh generation ID and artifact ID, one
issuance per roster student, and one immutable page ID plus one Core route ID
per physical page. Continuation pages share their student's issuance but never
share page or route identity. Roster order, including leading-zero student IDs,
is preserved.

## PDS2 route and QR

The QR contains only Core's canonical locator serialization:

```text
PDS2|m=quillan|c=<class_id>|w=<assignment_id>|r=<route_id>
```

The locator resolves a Core-owned active route registration whose target is:

```text
ModuleRecordRef(
    module_id="quillan",
    record_kind="response_page",
    record_id=<page_id>,
    contract_version="1",
)
```

The registration timestamp equals the immutable page timestamp. Its diagnostic
details are exactly `issuance_id`, `logical_page`, and `total_pages`; its human
fallback is:

```text
Quillan | class=<class_id> | assignment=<assignment_id> | student=<student_id> | page=<logical_page>/<total_pages> | page_id=<page_id>
```

Student, issuance, page, logical-page, generation, artifact, and record-path
meaning is not encoded in the QR. The immutable response-page record supplies
that meaning after Core resolves the locator.

## Page layout

Pages are US Letter portrait with printer-safe margins. Each page displays the
assignment title, immutable student display name and student ID, class label and
class ID, assignment ID, `Page X of N`, full page ID, and full route ID. The QR
uses medium error correction and a four-module quiet border. The lined writing
area remains clear of the QR and diagnostics. Prompts, standards, scales, review
settings, and submission, scan, or evidence state are never printed.

Logical page number describes the intended page within one issuance.
`source_page_number`, used by later scan intake, describes a page in a scanned
source file and is not interchangeable with logical page number.

## Managed transaction

Generation revalidates assignment and roster SHA-256 fingerprints, selects
unambiguous predecessors, allocates fresh identities with bounded collision
retries, and preflights every record, route, output, and temporary destination.
It then writes page records and prepared issuances, writes and reload-verifies
one immutable Core route per page, renders a same-directory temporary PDF from
the immutable records and verified routes, transitions new issuances to
`issued`, and atomically installs the PDF. Only after installation are named
predecessors superseded.

No Core route is deleted, overwritten, repointed, or reused. Record failures
before route creation cancel prepared issuances. Failures after any route may
exist invalidate the new issuances while retaining page records and routes.
Predecessor-supersession failure is an installed partial failure: the new PDF
and issued records remain installed and the unresolved lineage is reported.

`--overwrite` authorizes replacement of only the canonical PDF. It never
authorizes identity, record, route, or lifecycle reuse. Concurrent output
changes prevent installation.

## Dry run and interfaces

`plan_printable_response_packet(...)` is the public aggregate dry-run boundary.
It validates canonical inputs, counts students, issuances, pages, routes, and
predecessors, fingerprints sources, and reports output existence. It allocates
no IDs and creates no directory, record, route, temporary file, or PDF.

The direct command is noninteractive and never opens files:

```text
quillan printable-responses generate <class_id> <assignment_id> [--pages-per-student N] [--overwrite] (--yes | --dry-run)
```

Only the teacher menu may offer to open an installed PDF or its folder, and
opening remains an explicit choice.

PDS1 generation has been removed. PDS1 scan interpretation remains a separate,
later migration boundary; this contract does not claim installed module-profile
registration, a route handler, PDS2 scan dispatch, retained-source intake,
evidence assembly, submission-schema migration, or plain-paper changes.
