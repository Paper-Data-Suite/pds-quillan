# v0.10.4 Release Process

Classification: **active authority for the v0.10.4 #416 patch candidate**.

Issue #416 owns historical Core retained-source provenance compatibility,
path-independent retained PDF/image decoding, bounded new routed-evidence leaves,
legacy routed-evidence read compatibility, Windows/deep-path installed
qualification, and the Quillan patch needed to unblock Core #226.

Passing automation does not itself grant tag or GitHub Release authority.

## Core handoff identity

Quillan v0.10.4 qualification uses released Core 0.6.2, released Core 0.6.3,
and the exact Core 0.6.4 #226 candidate built from:

```text
2e47734  refresh released consumer compatibility
```

Authenticated handoff artifacts:

```text
pds_core-0.6.4-py3-none-any.whl
SHA-256 201e651f4b9aad0bfeb1565b37f425982513f2fb616b86a8835a10f4dcd7db62

pds_core-0.6.4.tar.gz
SHA-256 8faa892a1e665d3d7dea1ad800ca5e03ffa235ef3b0fda224e8e96f5664aae6e
```

The Quillan release validator authenticates the exact wheel bytes. Core 0.6.4
remains unpublished until the compatible Quillan patch is released and Core
#226 completes its final released-consumer matrix.

Runtime compatibility remains `pds-core>=0.6.2,<0.7`; Core 0.6.4 is a
qualification endpoint, not the new runtime floor.

## Exact candidate construction

1. Reconcile the release commit with `origin/main` and require a clean tree.
2. Authenticate Core 0.6.2, Core 0.6.3, and the exact Core 0.6.4 #226 wheel.
3. Run the repository development gate once.
4. Build exactly one `quillan-0.10.4-py3-none-any.whl` and
   `quillan-0.10.4.tar.gz`.
5. Run Twine and archive inspection against that exact pair.
6. Reuse the same Quillan wheel bytes in isolated Core 0.6.2, 0.6.3, and 0.6.4
   environments outside the checkout.
7. Run established installed application, producer, module-operations,
   class-set, release-edge, selected-review, and resubmission acceptance at each
   endpoint.
8. Under Core 0.6.4, additionally run
   `verify_installed_issue416_scan_paths.py`.
9. Install the exact Quillan sdist with the authenticated Core 0.6.4 candidate
   and run the installed smoke.
10. Persist the exact tested Quillan pair outside the repository and record
    filenames, lengths, and SHA-256 values.

A rebuild has a different artifact identity and invalidates installed evidence
for the previous bytes.

## Historical release evidence

Quillan v0.10.3 was released on 2026-09-25. Its resubmission-inbox acceptance
remains historical evidence for #415. The v0.10.2 selected-review read
acceptance, v0.10.1 batch-feedback acceptance, and v0.10.0 class-set/physical
acceptance remain historical evidence for their unchanged boundaries.

Issue #416 crosses retained-source and routed-evidence execution boundaries.
The old v0.10.0 physical-paper evidence is historical context, not proof of
#416 path safety. The replacement evidence is the Windows/deep-path installed
scan-processing acceptance documented in
[v0.10.4 Installed Scan-Path Acceptance](v0.10.4_installed_scan_path_acceptance.md).

## Release authority

After exact-candidate qualification, an owner must explicitly authorize the
v0.10.4 release. Only then may the normal process create/push tag `v0.10.4` and
make the exact qualified wheel/sdist available in the repository release
channel.

The released and authenticated Quillan 0.10.4 wheel is then supplied back to
Core #226 for its final released-consumer matrix.

Do not upload Quillan to an external package index without separate explicit
authorization.
