# v0.8.9 Physical Acceptance

Classification: **acceptance procedure**. This procedure is owner-only and must
use synthetic data. Do not commit scans, generated packets, or workspaces.

Record candidate commit; Quillan wheel filename/hash; Core wheel
filename/version/hash/origin; Python and OS; printer/scanner make and model;
print scaling and paper size; scan DPI, color mode, simplex/duplex, and source
format; Poppler version; date; and tester.

## A. Golden loop

Generate from the final wheel for two synthetic students with leading-zero IDs
and two pages each. Print at documented scaling, add harmless marks, scan all
four pages as one PDF, route it, and verify one retained source, four dispatched
pages, four observations, routed evidence, two complete submissions, evidence
opening, dashboard, and status output.

## B. Duplicate and missing page

In a fresh synthetic work area, scan page 1 twice and omit page 2. Verify the
duplicate remains a candidate, page 2 remains missing, no winner is chosen, and
teacher page-management actions remain available.

## C. Regeneration and mixed issuance

Generate an original and regenerated issuance, then scan one page from each for
the same student. Verify both locators, distinct immutable identities, refusal
to assemble a contradictory mixed issuance, and a visible conflict or
post-dispatch occurrence.

Record exactly `PASS`, `PASS WITH DOCUMENTED LIMITATION`, or `FAIL`. A limitation
must state the symptom, scenario, workaround, release impact, and follow-up issue.

## Superseded Owner Acceptance Record — 2026-07-23

This record remains evidence for the exact artifacts named below. It does not
cover the current replacement artifacts because subsequent release-blocking
runtime corrections changed packaged bytes.

**Owner/tester:** Stephen Severino
**Candidate implementation commit:** `84ceb28d13a410ecbded9d0f33c17ae192cb31b6`
**Physical acceptance result:** `PASS`

### Authoritative artifacts

* Wheel: `quillan-0.8.9-py3-none-any.whl`
* Wheel SHA-256: `041bf1f451b16d225b7f74ffa8af77a72d91bdfdd36bb55e312cd9a6c23a7485`
* Source distribution: `quillan-0.8.9.tar.gz`
* Source-distribution SHA-256: `b27151152ed1962a286fbf674a7b10146787adb69cb123ae985d103ccac593ae`
* Visual-evidence ZIP SHA-256: `2418dd0ff83f62a31f26211798b5c300ffe62c626aefe9914bed26ea8b919c43`

### Owner-observed behavior

The owner performed an owner-defined physical and normal-use acceptance test.

The following behavior was confirmed:

* printed-page QR decoding functioned correctly;
* PDS2 route resolution and routing functioned correctly;
* routed evidence was recorded correctly;
* Quillan’s core physical-paper workflow remained intact after the PDS2 conversion;
* the minimum-requirements workflow supported consecutive requirement updates without returning to the parent action menu after each entry;
* Focus Standard feedback configuration opened on a cleared, focused child screen without retaining irrelevant parent-menu content.

No release-blocking defect was observed in the exercised workflow.

## Current Candidate Record — 2026-07-23

**Owner/tester:** Stephen Severino
**Candidate implementation commit:** `c3e57db5e0e175e61ce988e0681375d7b76ce861`
**Automated release-candidate validation:** `PASS`
**Physical acceptance result:** `PASS`
**Release authorization:** `GRANTED`

### Physical environment

* Acceptance date: July 23, 2026
* Operating system: Windows 11
* Python: 3.14.1, in a clean virtual environment outside the source repository
* Printer: Brother HL-L2350DW
* Scanner: Epson ES-50
* Print scaling: Actual Size
* Paper size: Letter
* Scan resolution: 200 DPI
* Scan color mode: grayscale
* Scan mode: simplex
* Scan source format: PDF
* Poppler: 25.07.0

### Exact replacement artifacts

* Wheel: `quillan-0.8.9-py3-none-any.whl`
* Wheel SHA-256: `67536b7266770816e7d5732752167f1b77e23767ba48f34d98af48bbee7ade91`
* Source distribution: `quillan-0.8.9.tar.gz`
* Source-distribution SHA-256: `6ad8201224343f08edb7a6fc41d8ea6316a1ce4c95992eeeea9f96af94cb6dcd`
* PDS Core 0.5.0 wheel SHA-256: `336676fa4b72e2b4094f654e77b5746b0d6670946cb4c5d3022c4c0be7963400`

The wheel hash was verified before physical testing. `pip check` passed, and
the installed CLI reported `quillan 0.8.9`.

The authoritative validator passed source tests, Ruff, mypy, documentation,
artifact inspection, Twine, separate clean wheel and sdist installation, and
installed acceptance. CI push run `30046233133` and pull-request run
`30046236657` passed on Windows and Ubuntu with Python 3.11, 3.12, 3.13, and
3.14.

### Current owner-observed behavior

Case A, the golden loop, passed for two synthetic students with leading-zero
IDs and two pages each. Packet generation, physical printing and scanning, PDF
intake, retained-source creation, page dispatch, immutable observations, routed
evidence, complete submission assembly, evidence opening, dashboard output,
and student status output all behaved correctly.

Case B, the duplicate-and-missing-page scenario, passed. The duplicate page 1
remained a candidate, omitted page 2 remained visibly missing, no winner was
selected automatically, and teacher page-management actions remained
available.

Case C, regeneration and mixed issuance, passed using the explicit overwrite
workflow after preserving the original packet. Both QR locators resolved,
issuance identities remained distinct, contradictory pages did not form a
valid complete submission, and the conflict or post-dispatch condition was
visibly surfaced.

No release-blocking issue was observed. The owner explicitly authorizes release
of the exact wheel and source distribution recorded above.

### Deferred work

A future grading and reporting module may require a shared assignment manifest or assignment-subscription contract. That integration is outside the scope of Quillan v0.8.9 and does not block this release.
