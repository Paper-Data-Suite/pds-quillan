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

## Owner Acceptance Record — 2026-07-23

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

### Deferred work

A future grading and reporting module may require a shared assignment manifest or assignment-subscription contract. That integration is outside the scope of Quillan v0.8.9 and does not block this release.
