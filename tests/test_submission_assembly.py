"""Public submission assembly boundary is observation-authoritative."""

from quillan.submission_assembly import (
    assemble_quillan_submission_manifests,
    merge_submission_manifest_observations,
)


def test_public_boundary_exposes_observation_assembly_only() -> None:
    assert callable(assemble_quillan_submission_manifests)
    assert callable(merge_submission_manifest_observations)
