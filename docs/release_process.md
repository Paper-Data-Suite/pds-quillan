# Release Process

Classification: **active authority**.

1. Begin from the approved baseline with a clean tree and use synthetic data.
2. Supply the released PDS Core 0.5.0 wheel explicitly to the release validator.
3. Run source tests, Ruff, mypy without incremental state, documentation and
   parser drift checks, repository hard-cutover checks, and `git diff --check`.
4. Build exactly `quillan-0.8.9-py3-none-any.whl` and
   `quillan-0.8.9.tar.gz`; run Twine and archive inspection.
5. Install wheel and sdist into separate clean environments outside the source
   directory. Verify dependency health, metadata, import origins, entry points,
   CLI help/version, menu smoke, module discovery, and the installed synthetic
   workflow.
   The validator then copies that exact tested pair byte-for-byte to a new or
   empty persistent directory outside the repository and proves source/copy
   SHA-256 equality. Do not rebuild a separate persistent pair.
6. Generate the synthetic visual matrix outside the repository and record
   hashes, dimensions, page counts, QR decoding, and layout decisions.
7. The owner performs [physical acceptance](physical_acceptance_v0.8.9.md) and
   records the decision against the exact candidate.
8. Only after explicit owner authorization may a separate action tag, publish,
   deploy, or close release issues.

Run the automated candidate gate with:

```powershell
.\scripts\validate_release_candidate.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -PdsCoreWheel C:\path\to\pds_core-0.5.0-py3-none-any.whl `
  -ArtifactOutputDirectory C:\path\outside\repository\quillan-0.8.9-candidate
```
