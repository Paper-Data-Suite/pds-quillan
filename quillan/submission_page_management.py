"""Teacher-controlled submission page/evidence management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
    write_submission_manifest,
)

_PRESERVED_EXCLUSION_KEY = "quillan_before_page_exclusion"


class SubmissionPageManagementError(ValueError):
    """Raised when a page-management action cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class ManagedSubmissionPage:
    """A concise result for one managed submission page."""

    manifest_path: Path
    class_id: str
    assignment_id: str
    student_id: str
    page_number: int
    page_state: str
    selected_evidence_id: str | None
    evidence_count: int


def exclude_submission_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Exclude one page from active review without deleting evidence."""
    manifest_path, manifest, page = _load_page(
        workspace_root, class_id, assignment_id, student_id, page_number
    )
    if page["page_state"] == "excluded":
        raise SubmissionPageManagementError(
            f"Page {page_number} is already excluded from active review."
        )

    updated = deepcopy(manifest)
    updated_page = _page_by_number(updated, page_number)
    updated_page["page_state"] = "excluded"
    updated_page["selected_evidence_id"] = None
    for evidence in _evidence_items(updated_page):
        _preserve_evidence_state_before_exclusion(evidence)
    return _write_result(manifest_path, updated, updated_page)


def restore_excluded_submission_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Return one excluded page to the active review set when unambiguous."""
    manifest_path, manifest, page = _load_page(
        workspace_root, class_id, assignment_id, student_id, page_number
    )
    if page["page_state"] != "excluded":
        raise SubmissionPageManagementError(
            f"Page {page_number} is not currently excluded from active review."
        )

    updated = deepcopy(manifest)
    updated_page = _page_by_number(updated, page_number)
    evidence = _evidence_items(updated_page)
    updated_page["selected_evidence_id"] = None
    if not evidence:
        updated_page["page_state"] = "missing"
    else:
        for item in evidence:
            _restore_evidence_state_after_exclusion(
                item,
                default_role="selected" if len(evidence) == 1 else "candidate",
                default_state="active",
            )
        selected_ids = [
            str(item["evidence_id"])
            for item in evidence
            if item["evidence_role"] == "selected"
        ]
        if len(selected_ids) > 1:
            raise SubmissionPageManagementError(
                "Restore canceled because multiple evidence records would be selected."
            )
        updated_page["selected_evidence_id"] = (
            selected_ids[0] if selected_ids else None
        )
        updated_page["page_state"] = _restored_page_state(evidence)
    return _write_result(manifest_path, updated, updated_page)


def mark_submission_page_needs_rescan(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Mark one page as needing a corrected scan without deleting evidence."""
    manifest_path, manifest, page = _load_page(
        workspace_root, class_id, assignment_id, student_id, page_number
    )
    if page["page_state"] == "needs_rescan":
        raise SubmissionPageManagementError(
            f"Page {page_number} is already marked as needing rescan."
        )

    updated = deepcopy(manifest)
    updated_page = _page_by_number(updated, page_number)
    updated_page["page_state"] = "needs_rescan"
    updated_page["selected_evidence_id"] = None
    for evidence in _evidence_items(updated_page):
        evidence["evidence_role"] = "candidate"
        evidence["evidence_state"] = "needs_rescan"
    return _write_result(manifest_path, updated, updated_page)


def _load_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    _validate_identity(class_id, assignment_id, student_id)
    if (
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
    ):
        raise SubmissionPageManagementError("Page number must be a positive integer.")
    path = submission_manifest_path(
        workspace_root, class_id, assignment_id, student_id
    )
    try:
        manifest = load_submission_manifest(path)
    except (SubmissionManifestError, OSError) as error:
        raise SubmissionPageManagementError(
            f"Could not load submission record: {error}"
        ) from error
    if (
        manifest["class_id"] != class_id
        or manifest["assignment_id"] != assignment_id
        or manifest["student_id"] != student_id
    ):
        raise SubmissionPageManagementError(
            "Submission record identity does not match the selected student."
        )
    return path, manifest, _page_by_number(manifest, page_number)


def _page_by_number(manifest: dict[str, Any], page_number: int) -> dict[str, Any]:
    pages = cast(list[dict[str, Any]], manifest["pages"])
    for page in pages:
        if page["page_number"] == page_number:
            return page
    raise SubmissionPageManagementError(
        f"Page {page_number} is not in this submission record."
    )


def _evidence_items(page: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], page["evidence"])


def _preserve_evidence_state_before_exclusion(evidence: dict[str, Any]) -> None:
    module_details = _module_details(evidence)
    module_details.setdefault(
        _PRESERVED_EXCLUSION_KEY,
        {
            "evidence_role": evidence["evidence_role"],
            "evidence_state": evidence["evidence_state"],
        },
    )
    evidence["evidence_role"] = "excluded"
    evidence["evidence_state"] = "excluded"


def _restore_evidence_state_after_exclusion(
    evidence: dict[str, Any],
    *,
    default_role: str,
    default_state: str,
) -> None:
    preserved = _module_details(evidence).pop(_PRESERVED_EXCLUSION_KEY, None)
    if isinstance(preserved, dict):
        role = preserved.get("evidence_role")
        state = preserved.get("evidence_state")
        evidence["evidence_role"] = role if isinstance(role, str) else default_role
        evidence["evidence_state"] = state if isinstance(state, str) else default_state
    else:
        evidence["evidence_role"] = default_role
        evidence["evidence_state"] = default_state


def _module_details(evidence: dict[str, Any]) -> dict[str, Any]:
    module_details = evidence.get("module_details")
    if not isinstance(module_details, dict):
        module_details = {}
        evidence["module_details"] = module_details
    return module_details


def _restored_page_state(evidence: list[dict[str, Any]]) -> str:
    evidence_states = {item["evidence_state"] for item in evidence}
    if evidence_states & {"needs_rescan", "damaged"}:
        return "needs_rescan"
    if len(evidence) > 1:
        return "duplicate"
    return "present"


def _write_result(
    manifest_path: Path, manifest: dict[str, Any], page: dict[str, Any]
) -> ManagedSubmissionPage:
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    try:
        validate_submission_manifest(manifest)
        write_submission_manifest(manifest_path, manifest, overwrite=True)
    except (SubmissionManifestError, SubmissionManifestPathError, OSError) as error:
        raise SubmissionPageManagementError(
            f"Page change was not saved: {error}"
        ) from error
    return ManagedSubmissionPage(
        manifest_path=manifest_path,
        class_id=str(manifest["class_id"]),
        assignment_id=str(manifest["assignment_id"]),
        student_id=str(manifest["student_id"]),
        page_number=int(page["page_number"]),
        page_state=str(page["page_state"]),
        selected_evidence_id=(
            str(page["selected_evidence_id"])
            if page["selected_evidence_id"] is not None
            else None
        ),
        evidence_count=len(page["evidence"]),
    )


def _validate_identity(class_id: str, assignment_id: str, student_id: str) -> None:
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
        validate_identifier(student_id, "student_id")
    except IdentifierValidationError as error:
        raise SubmissionPageManagementError(str(error)) from error
