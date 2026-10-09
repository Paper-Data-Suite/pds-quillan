# Issue #419 Slice 9 — installed scan-recovery acceptance

## Scope and release status

Qualify the Issue #419 recovery pipeline from the **exact installed Quillan
0.10.5 candidate wheel** against the authenticated **released PDS Core 0.6.4
wheel**, outside the Quillan source checkout. This slice does not bump a release
version, publish a wheel, or alter any teacher workspace. The repository release
validator also invokes this same installed program at its 0.6.4 endpoint only.

The synthetic installed test (`scripts/verify_installed_issue419_recovery.py`)
uses installed public constructors for printable response pages, an issued
lifecycle, route registration, Core-retained source and schema-v2 routing
failure. It imports no `tests` helpers and requires all Quillan/Core imports to
originate from a distribution environment outside the repository.

## Installed qualification matrix

1. Show correct installed package versions and entry points. Refuse source-tree imports.
2. Read-only CLI inventory and explicit registered-route preflight; reject mutation
   without `--yes` without changing any file.
3. Recover a retained failed physical PNG page without QR guessing; establish
   canonical observation and evidence, submission membership, and Open Evidence.
4. Retry the same recovery; retain the observation ID and preserve all bytes.
5. Preserve a teacher's `needs_rescan` decision instead of reselecting evidence.
6. Discover an old Core `resolved` route as `evidence_missing`, not completed.
7. Refuse a wrong historical resolution ID, then replay the exact original route,
   verify the selected evidence and preserve resolution JSON byte-for-byte.
8. Exercise the installed Scan Review menu's B/Back, declined confirmation, and
   confirmed replay without changing an already-complete submission.
9. Refuse replay of a superseded historical route decision.
10. Assemble recovered evidence as a candidate without changing a previously
    selected page; distinguish `selection_needed` from `ready_for_review`.
11. Inject an assembly interruption, verify durable observation only, retry to
    complete, then detect tampered evidence and retained-source bytes fail-closed.

This is noninteractive **synthetic qualification**, not real-school-paper or
print/scanner physical acceptance. No identifiers or student artifacts from a
teacher's actual workspace are read.

## Dedicated run against a built candidate wheel (PowerShell)

First build the candidate wheel in a separate artifact directory using the
existing development environment:

```powershell
$artifacts = "$HOME\Downloads\quillan-issue419-candidate"
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
python -m build --wheel --outdir $artifacts
```

Then run from the repository root, substituting the path to your authenticated
released Core 0.6.4 wheel:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_issue419_wheel_acceptance.ps1 `
  -Python python `
  -PdsCore064Wheel "C:\path\to\pds_core-0.6.4-py3-none-any.whl" `
  -QuillanWheel "$HOME\Downloads\quillan-issue419-candidate\quillan-0.10.5-py3-none-any.whl"
```

The runner authenticates Core's known exact wheel hash before installing it,
creates an isolated temporary virtual environment, installs the exact Quillan
wheel, checks dependencies and runs the synthetic harness from outside the
checkout. It deletes only its validated temporary root.

## Repository validation

```powershell
python -m pytest -q tests/test_issue419_installed_acceptance.py `
  tests/test_scan_recovery_cli_issue419.py `
  tests/test_scan_recovery_menu_issue419.py `
  tests/test_scan_recovery_historical_issue419.py `
  tests/test_scan_recovery_completion_issue419.py
python -m ruff check scripts/verify_installed_issue419_recovery.py `
  tests/test_issue419_installed_acceptance.py
python -m mypy scripts/verify_installed_issue419_recovery.py
```

Run the installed acceptance in addition to, not instead of, the repository
quality gates and current release candidate validation. Do not claim Issue #419
installed acceptance passed until the exact-wheel run emits `"status": "PASS"`.
