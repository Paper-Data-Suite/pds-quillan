# v0.10.5 Release Process

Classification: **active authority for the v0.10.5 #417 patch candidate**.

Issue #417 expands assignment-local reporting and streamlines teacher review
continuation/navigation. It does not change PDS2 routing, physical scan intake,
publication schemas, assignment/review schemas, or the runtime Core dependency
range.

Passing automation does not itself grant tag or GitHub Release authority.

## Core release identities

Runtime compatibility remains:

```text
pds-core>=0.6.2,<0.7
```

Quillan v0.10.5 qualification uses three exact released Core endpoints:

```text
pds_core-0.6.2-py3-none-any.whl
SHA-256 b9d5de7d467d18716f415da87f359e940603d9c738a3a9ae9309272ebe78a848

pds_core-0.6.3-py3-none-any.whl
SHA-256 98d7596ce0eed26e4d56a17bbbbd644db3014259b56a45783a173fe8237af5e5

pds_core-0.6.4-py3-none-any.whl
SHA-256 48cea9317f2967bdc0f2d4c14349a56677c7c3f8211f0f33978ccb1a1c75859b
release commit 152d1c65064c4f8fe55249ff2ca3379d7c4d6ccb
```

The released Core 0.6.4 bytes supersede the pre-release #226 handoff wheel used
during Quillan v0.10.4 qualification. Historical v0.10.4 evidence remains
historical and is not rewritten.

## Exact candidate construction

1. Reconcile the release commit with `origin/main` and require a clean tree.
2. Authenticate released Core 0.6.2, 0.6.3, and 0.6.4 wheels.
3. Run the repository development gate once.
4. Build exactly one `quillan-0.10.5-py3-none-any.whl` and
   `quillan-0.10.5.tar.gz`.
5. Run Twine and archive inspection against that exact pair.
6. Reuse the same Quillan wheel bytes in isolated Core 0.6.2, 0.6.3, and 0.6.4
   environments outside the checkout.
7. Run the established installed application, producer, module-operations,
   class-set, release-edge, selected-review, and resubmission gates at each
   endpoint.
8. Run `verify_installed_issue417_acceptance.py` at each Core endpoint to prove
   the five-artifact reporting packet, BOM-aware Unicode CSV boundary,
   privacy/non-mutation contract, and shared B/M/Q review navigation from the
   installed wheel.
9. Under released Core 0.6.4, also rerun
   `verify_installed_issue416_scan_paths.py` as historical path-safety
   regression coverage.
10. Install the exact Quillan sdist with released Core 0.6.4 and run the
    installed smoke.
11. Persist the exact tested Quillan pair outside the repository and record
    filenames, lengths, and SHA-256 values.

A rebuild has a different artifact identity and invalidates installed evidence
for the previous bytes.

## #417 installed acceptance

The active installed contract is
[v0.10.5 Installed Reporting and Review Acceptance](v0.10.5_installed_reporting_review_acceptance.md).

The harness must prove from an installed, source-isolated wheel that:

- one assignment reporting operation creates exactly the three CSVs, the
  consolidated Assignment Review PDF, and the Assignment Results JSON;
- all three spreadsheet CSVs begin with exactly one UTF-8 BOM and preserve
  Unicode student/standard text without mojibake;
- private teacher notes, rating rationale, and the assignment prompt do not leak
  into the reporting packet;
- canonical assignment, roster, submission, review, and standards files are not
  modified by reporting;
- the JSON inventory sees the other four generated artifacts;
- the installed review menu has no numbered Back display and uses the shared
  `B. Back`, `M. Main Menu`, `Q. Quit` navigation signals.

## Historical release evidence

Quillan v0.10.4 was released on 2026-10-01. Its #416 installed scan-path
acceptance remains historical evidence for provenance/path compatibility and
retains the exact pre-release Core #226 handoff identity it originally tested.

The v0.10.3 resubmission-inbox, v0.10.2 selected-review read, v0.10.1
batch-feedback, and v0.10.0 class-set/physical acceptance documents likewise
remain historical evidence for unchanged boundaries.

Issue #417 does not change physical packet generation, QR routing, retained scan
intake, or evidence decoding, so the v0.10.0 owner-operated physical-paper
acceptance is not repeated as a v0.10.5 release gate.

## Release authority

After exact-candidate qualification, an owner must explicitly authorize the
v0.10.5 release. Only then may the normal process create/push tag `v0.10.5` and
make the exact qualified wheel/sdist available in the repository release
channel.

Do not upload Quillan to an external package index without separate explicit
authorization.
