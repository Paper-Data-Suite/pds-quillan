# v0.10.0 Release Process

Classification: **active authority for the v0.10.0 candidate**.

Issue #393 owns candidate construction plus installed and physical class-set
acceptance. Issue #394 owns the final skeptical workflow/release audit. Neither
issue grants release authorization merely because automation passes.

## Candidate construction

1. Reconcile a clean branch with `origin/main` and record the starting commit.
2. Authenticate both supported Core endpoint wheels:
   - `pds_core-0.6.2-py3-none-any.whl`
   - `pds_core-0.6.3-py3-none-any.whl`
3. Run source pytest, Ruff, strict mypy, compileall, `pip check`,
   documentation, release compatibility, `run_tests.ps1`, and diff hygiene.
4. Build exactly one pair:
   - `quillan-0.10.0-py3-none-any.whl`
   - `quillan-0.10.0.tar.gz`
5. Run Twine and archive inspection on that pair.
6. Install the **same wheel bytes** in isolated Core 0.6.2 and Core 0.6.3
   environments outside the checkout.
7. Verify independently:
   - console/application entry point;
   - Core routing profile;
   - publication-producer profile and lifecycle;
   - module-operations profile;
   - attention;
   - readiness;
   - installed class-set workflow;
   - final publication/withdrawal state;
   - mixed foreign-route isolation.
8. Run the sdist smoke without rebuilding the candidate pair.
9. Persist the exact tested pair to a new empty external directory and record
   filenames, byte lengths, and SHA-256 values.
10. Prepare physical acceptance from the persisted exact wheel.

A rebuilt wheel has a new identity. Any installed or physical evidence tied to
previous bytes is invalid for the rebuilt candidate.

## Core endpoint policy

Runtime compatibility remains exactly:

```text
pds-core>=0.6.2,<0.7
```

Core 0.6.2 is the minimum supported endpoint and Core 0.6.3 is the current
qualification endpoint for this milestone. Core 0.6.0 remains historical v0.9.0
release evidence only.

## Physical acceptance

Use [v0.10.0 Physical Acceptance](physical_acceptance_v0.10.0.md).

Physical acceptance means real generated paper is printed, physically marked,
scanned, retained through Core, decoded/routed, assembled, and reviewed through
the exact installed candidate. Generated PDFs, rendered images, or mocked scan
bytes are not substitutes for physical evidence.

No raw scans, generated PDFs, candidate wheels, workspaces, or venvs are
committed.

## Pre-merge and post-merge authority

The preparation PR should say `Refs #393` or `Part of #393`; normally it must
not auto-close #393 because squash merge changes commit identity.

After merge:

1. reconcile exact `main == origin/main`;
2. record the merged commit;
3. rebuild one fresh v0.10.0 pair;
4. rerun authoritative installed qualification;
5. persist exact bytes externally;
6. perform owner physical acceptance against that exact wheel;
7. bind the result to commit and hashes;
8. close #393 only if no acceptance blocker remains.

#394 then audits the final workflow and release boundary. If #394 requires a
packaged-byte change, affected #393 installed/physical acceptance must be
repeated.

## Release authority

#393 does not tag, publish, deploy, or grant final release authorization.

No tag or GitHub Release may be created until the later release decision is
explicitly authorized. Do not publish Quillan to a package index.
