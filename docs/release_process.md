# Quillan v0.10.6 Release Process — Issue #421

## Boundary

Quillan v0.10.6 adopts Core v0.6.5 publication reader-support metadata and includes
completed scan recovery (#419). The public `quillan_academic_result_manifest_v1`
and `quillan_academic_result_reader_v1` contracts are **unchanged**. The runtime
floor is `pds-core>=0.6.5,<0.7`, with no sibling runtime dependencies or migration.

Reader metadata is not authorization, not consumer adapter approval, and not a
compatibility promise for any future reader-contract change. Meridian #111 and
Vitrine #103 independently decide adapter compatibility against the declared
reader contract rather than a producer package-version allowlist.

## Exact released Core dependency

- `pds_core-0.6.5-py3-none-any.whl`
- SHA-256: `9ace75f17b23b7f0ed6a709d531af5120db43d0325b4148d26f2d6ba1d4b3c18`
- Release source commit: `64da9d2e4884ffe78a020aed87b1d5b9500927ad`

## Short candidate gate

1. Reconcile the merged Issue #421 source commit and require a clean checkout.
2. Reuse passing CI source checks, rather than rerunning the full suite. CI includes
   pytest, Ruff, strict mypy, documentation and compatibility checks.
3. Authenticate released Core 0.6.5 by exact filename, embedded metadata and SHA-256.
4. Build **one** Quillan 0.10.6 wheel/sdist pair and inspect its metadata, provider
   entry points and archive contents; run Twine check.
5. In **one** source-isolated venv, install the exact Core wheel and exact Quillan
   wheel, run `pip check`, and qualify: the reader declaration and actual reader,
   representative publication/installed application workflow, and Issue #419
   synthetic scan recovery.
6. Persist exactly the qualified pair outside the repository with SHA-256 hashes,
   source commit and Core identity recorded.
7. Only after owner authorization create the tag/GitHub Release. No external
   package-index upload without distinct authorization.

Run with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/validate_release_candidate.ps1 `
  -PdsCore065Wheel "$HOME\Downloads\pds_core-0.6.5-py3-none-any.whl" `
  -ArtifactOutputDirectory "$HOME\Downloads\quillan-v0.10.6-qualified" `
  -SkipRepositoryDevelopmentChecks
```

Historical v0.10.5, v0.10.4, and older acceptance records are retained as
historic evidence and are **not** repeated against obsolete Core endpoints.
Physical paper/QR testing is not repeated because the physical contract did not change.

This acceptance qualifies producer behavior, not the completeness of Meridian/Vitrine
consumer-side #111/#103 upgrades.
