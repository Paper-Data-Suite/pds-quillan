# v0.9.0 Release Checklist

Classification: **acceptance procedure**. No final release evidence is claimed
until the corresponding event occurs.

## Pre-merge

- [x] Starting `main` and branch reconciled; exact commit recorded.
- [x] Runtime dependency remains exactly `pds-core>=0.6,<0.7`.
- [x] Released Core 0.6.0 wheel filename and SHA-256 authenticated.
- [x] Version-bearing runtime, CLI, tooling, documentation, and tests identify
      Quillan 0.9.0 while v0.8.9 history remains unchanged.
- [x] Routing, publication, reader, privacy, artifact, and consumer-neutrality
      contracts are covered by focused audit tests.
- [ ] Full source, static, documentation, development-install, artifact,
      installed-lifecycle, visual, and menu/CLI qualification complete.
- [ ] Exact pre-merge wheel/sdist sizes and SHA-256 values recorded in the
      reviewed #366 pre-staging qualification report.
- [ ] Complete pre-staging report reviewed.

## Post-merge and owner gates

- [ ] Exact reconciled final `main` commit recorded and requalified from scratch.
- [ ] Final visual acceptance complete using the exact final wheel.
- [ ] Owner-only physical cases A, B, and C recorded as `PASS`,
      `PASS WITH DOCUMENTED LIMITATION`, or `FAIL`.
- [ ] Owner release authorization explicitly says `RELEASE AUTHORIZATION: GRANTED`
      and binds the exact commit and all artifact hashes.
- [ ] Only after authorization: tag `v0.9.0`, push tag, create GitHub Release,
      upload the tested artifacts, and record hashes. No package-index publication.
- [ ] Downloaded release assets pass clean-install, profile/import/no-side-effect,
      producer-lifecycle, and sdist-smoke verification.
- [ ] Only after all preceding gates: close #366, #355, and the milestone.

Before owner authorization there is no tag, GitHub Release, upload, publication,
deployment, or issue closure.
