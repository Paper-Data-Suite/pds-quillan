# Issue #416 Slice 6 — installed scan-path qualification harness

This slice adds the dedicated installed-wheel acceptance program:

```text
scripts/verify_installed_issue416_scan_paths.py
```

The harness is intended to run outside the source checkout with:

- the exact Quillan patch candidate wheel; and
- the exact PDS Core 0.6.4 candidate/released wheel.

It verifies in one synthetic deep workspace:

1. fresh Core 0.6.4 long external filename retention uses the bounded writer;
2. Quillan accepts that fresh provenance;
3. fresh retained PDF page count and rendering succeed;
4. a synthetic historical Core 0.6.3 long retained filename remains valid;
5. the historical PDF is page-counted and rendered from retained bytes;
6. a historical retained image is decoded from retained bytes;
7. newly materialized Quillan routed evidence uses the bounded observation-ID leaf;
8. a legacy Quillan routed-evidence observation remains readable without rename;
9. historical retained bytes remain unchanged; and
10. Windows `LongPathsEnabled`, when readable, has the same value before and
    after the run.

The harness emits only privacy-minimal qualification evidence: package
versions, PASS markers, filename/path lengths, the configured evidence-leaf
bound, and the before/after machine-policy value. It does not print scan bytes,
QR payloads, student identities, teacher usernames, or temporary file paths.

## Current release-gate status

Core 0.6.4 is still on the Core #226 candidate branch rather than the released
default line. Therefore this slice deliberately does **not** yet:

- bump Quillan from 0.10.3 to 0.10.4;
- rewrite the existing v0.10.3 release harness;
- authenticate a final Core 0.6.4 wheel; or
- claim final installed qualification.

Once Core 0.6.4 is published/authenticated, the next release-preparation slice
can wire this program into `validate_release_candidate.ps1`, move Quillan to
0.10.4, update release metadata/changelog documentation, and run the exact
installed-wheel matrix.
