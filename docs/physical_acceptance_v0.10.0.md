# v0.10.0 Physical Acceptance

Classification: **owner-only #393 post-merge acceptance procedure**.

Run this checklist only against the exact persisted
`quillan-0.10.0-py3-none-any.whl` that passed authoritative installed
qualification. Record the final commit, Quillan wheel/sdist SHA-256, Core wheel
identity, Python/platform, tester/date, printer, scanner, resolution, color
mode, sidedness, paper size, and scaling.

Use synthetic classroom identities and writing only. Do not commit raw scans,
generated PDFs, candidate artifacts, or physical evidence files.

For each case record exactly:

```text
PASS
PASS WITH DOCUMENTED LIMITATION
FAIL
```

A limitation records symptom, scenario, reproduction, classification,
workaround, release impact, and follow-up issue if needed.

## Case A — representative class-set golden loop

1. Generate a small multi-student class packet from the exact installed wheel.
2. Print it on real paper.
3. Physically mark/fill representative response pages.
4. Scan the returned paper.
5. Retain source bytes through Core.
6. Decode/resolve exact PDS2 page and route identity.
7. Dispatch to Quillan.
8. Verify immutable observation/evidence provenance.
9. Assemble submissions.
10. Enter explicit teacher review state.
11. Exercise queue, student navigation, and Continue Review.
12. Export feedback.
13. Verify class completion/export status.

Result: `PENDING OWNER`

## Case B — duplicate and missing page

Physically return a duplicate page while omitting an expected page.

Confirm:

- duplicate evidence remains a candidate;
- missing remains missing;
- no winner or completeness is inferred;
- explicit page-management/recovery remains available;
- provenance survives teacher resolution.

Result: `PENDING OWNER`

## Case C — regeneration and mixed issuance

Generate original and regenerated packets for the same synthetic work. Physically
mix pages from the two issuance sets.

Confirm:

- issuance identities remain distinct;
- page/route identities remain distinct;
- contradictory mixed issuance cannot silently assemble as one authoritative
  submission;
- recovery remains explicit.

Result: `PENDING OWNER`

## Case D — foreign/mixed routing isolation

Where meaningful without implementing future Suite-owned intake, include valid
Quillan PDS2 pages and a foreign/unsupported synthetic route in the retained
physical source.

Confirm:

- Quillan pages still dispatch normally;
- foreign ownership remains foreign;
- Quillan never claims the foreign route;
- foreign failure does not corrupt Quillan evidence;
- retained-source provenance remains intact.

If the current physical toolchain cannot create a meaningful foreign page
without implementing the future Suite coordinator, record that exact boundary
and rely on the installed synthetic mixed-routing proof. Do not fabricate a
physical Suite-intake PASS.

Result: `PENDING OWNER`

## Failure classification

Classify every failure as one of:

```text
software-contract failure
physical/environment dependency
operator/procedure error
documented limitation
```

Printer scaling, scanner crop/contrast/orientation, Poppler availability,
driver behavior, and damaged paper are physical/environment considerations; do
not silently waive them.

## #393 completion record

```text
final commit: PENDING
Quillan wheel SHA-256: PENDING
Quillan sdist SHA-256: PENDING
Core wheel/version used for physical acceptance: PENDING
automated installed qualification: PENDING
physical case A: PENDING OWNER
physical case B: PENDING OWNER
physical case C: PENDING OWNER
physical case D / boundary: PENDING OWNER
physical acceptance: PENDING OWNER
READY FOR #394: NO
```

Automation must never replace `PENDING OWNER` with PASS.

#393 does not grant final release authorization, tag v0.10.0, create a GitHub
Release, or publish to a package index.
