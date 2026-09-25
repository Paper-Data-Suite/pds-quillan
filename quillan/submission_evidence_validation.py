"""Shared immutable submission-evidence validation and selection identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from quillan.response_page_observations import QuillanResponsePageObservation


class SubmissionEvidenceValidationError(ValueError):
    """Raised when manifest evidence contradicts its source observation."""


def expected_evidence_projection(
    observation: QuillanResponsePageObservation,
    *,
    duplicate_number: int | None,
    evidence_role: str,
    evidence_state: str,
) -> dict[str, Any]:
    """Build the complete canonical evidence projection for one observation."""
    return {
        "evidence_id": observation.observation_id,
        "routed_evidence_path": observation.routed_evidence_path,
        "evidence_role": evidence_role,
        "evidence_state": evidence_state,
        "duplicate_number": duplicate_number,
        "created_at": observation.created_at,
        "retained_source": {
            "source_scan_id": observation.source_scan_id,
            "source_filename": observation.source_filename,
            "source_sha256": observation.source_sha256,
            "retained_source_path": observation.retained_source_path,
            "source_page_number": observation.source_page_number,
        },
        "module_details": {
            "observation_id": observation.observation_id,
            "page_id": observation.page_id,
            "route_id": observation.route_id,
            "issuance_id": observation.issuance_id,
            "generation_id": observation.generation_id,
            "artifact_id": observation.artifact_id,
            "logical_page": observation.logical_page,
            "total_pages": observation.total_pages,
            "page_role": observation.page_role,
            "routed_evidence_sha256": observation.routed_evidence_sha256,
            "routed_evidence_kind": observation.routed_evidence_kind,
        },
    }


def validate_evidence_observation_projection(
    evidence: dict[str, Any],
    observation: QuillanResponsePageObservation,
) -> None:
    """Validate every immutable observation and retained-source projection field."""
    try:
        expected = expected_evidence_projection(
            observation,
            duplicate_number=cast(int | None, evidence["duplicate_number"]),
            evidence_role=str(evidence["evidence_role"]),
            evidence_state=str(evidence["evidence_state"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SubmissionEvidenceValidationError(
            "Evidence is missing required projection fields."
        ) from error
    for field in (
        "evidence_id",
        "routed_evidence_path",
        "created_at",
        "retained_source",
    ):
        if evidence.get(field) != expected[field]:
            raise SubmissionEvidenceValidationError(
                f"Evidence {field} contradicts its immutable observation."
            )
    actual_details = evidence.get("module_details")
    if not isinstance(actual_details, dict):
        raise SubmissionEvidenceValidationError(
            "Evidence module_details must be an object."
        )
    for field, expected_value in expected["module_details"].items():
        if actual_details.get(field) != expected_value:
            raise SubmissionEvidenceValidationError(
                "Evidence immutable module details contradict its observation."
            )


def evidence_matches_observation(
    evidence: dict[str, Any],
    observation: QuillanResponsePageObservation,
) -> bool:
    """Return whether evidence passes the shared full projection contract."""
    try:
        validate_evidence_observation_projection(evidence, observation)
    except SubmissionEvidenceValidationError:
        return False
    return True


def selected_evidence_fingerprint(manifest: dict[str, Any]) -> str:
    """Fingerprint only the ordered authoritative evidence selection."""
    pages = cast(list[dict[str, Any]], manifest["pages"])
    projection = [
        {
            "page_number": int(page["page_number"]),
            "selected_evidence_id": cast(str | None, page["selected_evidence_id"]),
        }
        for page in sorted(pages, key=lambda item: int(item["page_number"]))
    ]
    canonical = json.dumps(
        projection,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "SubmissionEvidenceValidationError",
    "evidence_matches_observation",
    "expected_evidence_projection",
    "selected_evidence_fingerprint",
    "validate_evidence_observation_projection",
]
