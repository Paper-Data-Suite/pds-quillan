# v0.10.1 Candidate Acceptance Checklist

Classification: **active #412 patch-release procedure**.

## Preparation

- [x] Candidate identity is Quillan `0.10.1`.
- [x] Runtime dependency remains `pds-core>=0.6.2,<0.7`.
- [x] `pypdf>=5,<7` is a bounded runtime dependency.
- [x] Historical v0.10.0 installed and physical evidence remains unchanged.
- [ ] Core 0.6.2 and 0.6.3 exact wheels authenticated.
- [ ] Full source/static/documentation gates pass.
- [ ] Exactly one v0.10.1 wheel/sdist pair built.
- [ ] Twine and artifact inspection pass.
- [ ] Candidate filenames, lengths, and SHA-256 values recorded.

## Installed acceptance

- [ ] Core 0.6.2 isolated install passes.
- [ ] Core 0.6.3 isolated install passes.
- [ ] No source checkout or `PYTHONPATH` shadowing.
- [ ] Installed `quillan` console entry point verified.
- [ ] Existing routing/publication/module-operation/class-set gates pass.
- [ ] Whole-class feedback assembly dry-run creates nothing.
- [ ] Installed print packet preserves roster order.
- [ ] Installed sharing ZIP preserves source PDF bytes.
- [ ] Canonical records and academic/publication state remain unchanged.
- [ ] Exact tested wheel/sdist persisted outside the repository.

## Physical boundary

- [x] No #412 change intentionally touches the v0.10.0 physical-paper boundary.
- [ ] Reconfirm implementation diff did not invalidate that conclusion.
- [ ] If invalidated, rerun affected physical acceptance before authorization.

## Authority

- [ ] Reconciled release commit qualified.
- [ ] Installed acceptance passed against exact recorded bytes.
- [ ] Artifact hashes recorded.
- [ ] Owner explicitly authorized `v0.10.1`.
- [ ] Tag and repository release use those exact artifacts.

Do not upload to an external package index without separate explicit
authorization.

This checklist does not itself authorize a tag, GitHub Release, upload,
publication, or deployment.
