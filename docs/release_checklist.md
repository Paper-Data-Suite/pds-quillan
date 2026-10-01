# v0.10.4 Candidate Acceptance Checklist

Classification: **active #416 patch-release procedure**.

## Preparation

- [x] Candidate identity is Quillan `0.10.4`.
- [x] Runtime dependency remains `pds-core>=0.6.2,<0.7`.
- [x] Core 0.6.2 and 0.6.3 released endpoint contracts remain authenticated.
- [x] Core 0.6.4 #226 handoff candidate was built from `2e47734`.
- [x] Core 0.6.4 wheel SHA-256 is `201e651f4b9aad0bfeb1565b37f425982513f2fb616b86a8835a10f4dcd7db62`.
- [x] Core 0.6.4 sdist SHA-256 is `8faa892a1e665d3d7dea1ad800ca5e03ffa235ef3b0fda224e8e96f5664aae6e`.
- [x] Pre-release #416 installed characterization passed against those Core
  0.6.4 wheel bytes before the Quillan version bump.
- [ ] Full source/static/documentation gate passes from the v0.10.4 candidate.
- [ ] Exactly one v0.10.4 wheel/sdist pair is built and inspected.
- [ ] Candidate filenames, lengths, and SHA-256 values are recorded.

## Issue #416 source acceptance

- [x] Historical Core identity is validated from persisted provenance.
- [x] Retained PDFs are read as bytes before Poppler processing.
- [x] Retained images are read as bytes before OpenCV decoding.
- [x] New routed-evidence leaves use bounded observation identity.
- [x] Legacy routed-evidence paths remain readable without migration.
- [x] Legacy observation/evidence replay remains idempotent without rewriting.
- [x] Contradictory legacy/bounded duplicate evidence fails closed.

## Installed acceptance

- [ ] Core 0.6.2 isolated install passes with exact Quillan 0.10.4 wheel.
- [ ] Core 0.6.3 isolated install passes with exact Quillan 0.10.4 wheel.
- [ ] Core 0.6.4 #226 candidate isolated install passes with exact Quillan 0.10.4 wheel.
- [ ] No source-checkout or `PYTHONPATH` shadowing.
- [ ] Existing installed application/producer/operations/class-set/release-edge
  gates pass at all three endpoints.
- [ ] Selected-review and resubmission acceptance pass at all three endpoints.
- [ ] Fresh Core 0.6.4 provenance and PDF processing pass.
- [ ] Historical Core 0.6.3 provenance, PDF processing, and image processing pass.
- [ ] New routed-evidence filename remains bounded.
- [ ] Legacy routed evidence remains readable without migration.
- [ ] Windows path policy remains unchanged.
- [ ] Exact tested wheel/sdist is persisted outside the repository.

## Package/release gate

- [ ] Full pytest, Ruff, strict mypy, documentation, and diff hygiene pass.
- [ ] wheel and sdist build.
- [ ] `twine check` and archive inspection pass.
- [ ] clean-wheel qualification passes.
- [ ] clean-sdist installation/smoke passes.
- [ ] release compatibility audit passes.

## Authority and Core handback

- [ ] Reconciled v0.10.4 release commit qualified.
- [ ] Quillan artifact hashes recorded.
- [ ] Owner explicitly authorized `v0.10.4`.
- [ ] Tag and repository release use those exact artifacts.
- [ ] Released Quillan 0.10.4 wheel identity handed back to Core #226.
- [ ] Core #226 final released-consumer matrix replaces Quillan 0.10.3 with
  authenticated Quillan 0.10.4.

This checklist does not itself authorize a tag, GitHub Release, external
package-index upload, publication, or deployment.
