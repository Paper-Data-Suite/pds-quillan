# Release Process

Classification: **active authority** for v0.9.0.

1. Reconcile a clean branch with `origin/main` and record the exact starting
   commit.
2. Authenticate `pds_core-0.6.0-py3-none-any.whl` with SHA-256
   `be28c061b38463ef59ebc328ed1aa443767fe7f2c626babb769c2d8e5932f308`.
3. Run source pytest, Ruff, strict mypy, compileall, `pip check`, documentation,
   release compatibility, diff hygiene, and `run_tests.ps1`.
4. Build exactly `quillan-0.9.0-py3-none-any.whl` and
   `quillan-0.9.0.tar.gz`; run Twine and archive inspection.
5. Install the exact Core wheel and each Quillan artifact into separate clean
   environments outside the source checkout. Run ordinary installed acceptance,
   the full wheel producer lifecycle, and the lighter sdist smoke.
6. Persist the tested pair byte-for-byte into a new empty external directory and
   record exact sizes and SHA-256 values. Do not rebuild a second pair.
7. Generate v0.9.0 synthetic visual evidence outside the repository and rehearse
   the teacher menu/CLI publication lifecycle.
8. Submit the complete pre-staging report for qualification review. Automation
   leaves physical acceptance pending and release authorization not granted.
9. After merge, repeat authoritative qualification from exact reconciled `main`
   into a fresh external directory. Pre-merge artifacts are not authoritative.
10. The owner performs [physical acceptance](physical_acceptance_v0.9.0.md) with
    the exact final wheel and explicitly binds authorization to the commit,
    Quillan hashes, Core hash, automated result, visual result, and physical result.
11. Only after `RELEASE AUTHORIZATION: GRANTED` may the authorized commit be tagged
    `v0.9.0`, the tag pushed, and a GitHub Release created with the already-tested
    wheel and sdist. Do not publish to a package index.
12. Download and reverify the released assets, clean-install them with exact Core
    0.6.0, and repeat profile/import/side-effect, producer-lifecycle, and sdist
    smoke checks before closing the release issue.

Run the pre-merge candidate gate with:

```powershell
.\scripts\validate_release_candidate.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -PdsCoreWheel C:\path\to\pds_core-0.6.0-py3-none-any.whl `
  -ArtifactOutputDirectory C:\new-external\quillan-0.9.0-candidate
```

The release-preparation PR references issue #366 with `Refs #366` or
`Part of #366`; it does not close the issue.
