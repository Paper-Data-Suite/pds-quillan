"""Teacher-controlled submission page/evidence management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.submission_manifest import (
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    update_quillan_submission_manifest,
)
from quillan.plain_paper_submission import is_plain_paper_submission
from quillan.submission_guidance import missing_submission_guidance
from quillan.record_context import (
    canonical_workspace_root,
    MissingSubmissionError,
    QuillanRecordContextError,
    ReviewLoadingPolicy,
    QuillanStudentReviewContext,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.work_paths import quillan_work_ref

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
    action: str
    previous_page_state: str
    page_state: str
    previous_selected_evidence_id: str | None
    selected_evidence_id: str | None
    evidence_count: int
    updated_at: str
    restore_source: str | None = None


@dataclass(frozen=True, slots=True)
class SubmissionEvidenceStatus:
    """Immutable manifest-only status for one evidence record."""

    evidence_id: str
    evidence_role: str
    evidence_state: str
    routed_evidence_path: str
    duplicate_number: int | None
    retained_source_present: bool
    pre_exclusion_role: str | None
    pre_exclusion_state: str | None


@dataclass(frozen=True, slots=True)
class SubmissionPageStatus:
    """Immutable manifest-only status for one logical submission page."""

    page_number: int
    page_state: str
    selected_evidence_id: str | None
    evidence: tuple[SubmissionEvidenceStatus, ...]


@dataclass(frozen=True, slots=True)
class SubmissionPageContext:
    """Read-only page-management context for one canonical submission."""

    class_id: str
    assignment_id: str
    student_id: str
    manifest_path: Path
    manifest_relative_path: str
    submission_state: str
    expected_pages: int | None
    plain_paper: bool
    plain_paper_entry_method: str | None
    created_at: str
    updated_at: str
    pages: tuple[SubmissionPageStatus, ...]
    present_count: int
    missing_count: int
    duplicate_count: int
    needs_rescan_count: int
    excluded_count: int
    pages_without_selected_evidence: tuple[int, ...]


def load_submission_page_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> SubmissionPageContext:
    """Load one student's canonical manifest without inspecting evidence files."""
    path, manifest, _ = _load_manifest(
        workspace_root, class_id, assignment_id, student_id
    )
    pages = tuple(
        SubmissionPageStatus(
            page_number=int(page["page_number"]),
            page_state=str(page["page_state"]),
            selected_evidence_id=(
                str(page["selected_evidence_id"])
                if page["selected_evidence_id"] is not None
                else None
            ),
            evidence=tuple(_evidence_status(item) for item in _evidence_items(page)),
        )
        for page in sorted(
            cast(list[dict[str, Any]], manifest["pages"]),
            key=lambda item: int(item["page_number"]),
        )
    )
    root = canonical_workspace_root(workspace_root)
    try:
        relative_path = Path(os.path.abspath(path)).relative_to(root).as_posix()
    except (OSError, ValueError):
        relative_path = str(path)
    details = cast(dict[str, Any], manifest["module_details"])
    return SubmissionPageContext(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        manifest_path=path,
        manifest_relative_path=relative_path,
        submission_state=str(manifest["submission_state"]),
        expected_pages=cast(int | None, manifest["expected_pages"]),
        plain_paper=is_plain_paper_submission(manifest),
        plain_paper_entry_method=cast(str | None, details.get("submission_entry_method")),
        created_at=str(manifest["created_at"]),
        updated_at=str(manifest["updated_at"]),
        pages=pages,
        present_count=_state_count(pages, "present"),
        missing_count=_state_count(pages, "missing"),
        duplicate_count=_state_count(pages, "duplicate"),
        needs_rescan_count=_state_count(pages, "needs_rescan"),
        excluded_count=_state_count(pages, "excluded"),
        pages_without_selected_evidence=tuple(
            page.page_number for page in pages if page.selected_evidence_id is None
        ),
    )


def exclude_submission_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Exclude one page from active review without deleting evidence."""
    manifest_path, manifest, page, record_context = _load_page(
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
    return _write_result(
        workspace_root,
        manifest_path,
        updated,
        updated_page,
        previous_page=page,
        action="excluded",
        record_context=record_context,
    )


def restore_excluded_submission_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Return one excluded page to the active review set when unambiguous."""
    manifest_path, manifest, page, record_context = _load_page(
        workspace_root, class_id, assignment_id, student_id, page_number
    )
    if page["page_state"] != "excluded":
        raise SubmissionPageManagementError(
            f"Page {page_number} is not currently excluded from active review."
        )

    updated = deepcopy(manifest)
    updated_page = _page_by_number(updated, page_number)
    evidence = _evidence_items(updated_page)
    used_preserved_state = any(_has_preserved_state(item) for item in evidence)
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
    return _write_result(
        workspace_root,
        manifest_path,
        updated,
        updated_page,
        previous_page=page,
        action="restored",
        record_context=record_context,
        restore_source=(
            "preserved pre-exclusion metadata"
            if used_preserved_state
            else "legacy fallback"
        ),
    )


def mark_submission_page_needs_rescan(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> ManagedSubmissionPage:
    """Mark one page as needing a corrected scan without deleting evidence."""
    manifest_path, manifest, page, record_context = _load_page(
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
        _module_details(evidence).pop(_PRESERVED_EXCLUSION_KEY, None)
        evidence["evidence_role"] = "candidate"
        evidence["evidence_state"] = "needs_rescan"
    return _write_result(
        workspace_root,
        manifest_path,
        updated,
        updated_page,
        previous_page=page,
        action="marked needs rescan",
        record_context=record_context,
    )


def _load_page(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
) -> tuple[Path, dict[str, Any], dict[str, Any], QuillanStudentReviewContext]:
    _validate_identity(class_id, assignment_id, student_id)
    if (
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
    ):
        raise SubmissionPageManagementError("Page number must be a positive integer.")
    path, manifest, record_context = _load_manifest(
        workspace_root, class_id, assignment_id, student_id
    )
    return path, manifest, _page_by_number(manifest, page_number), record_context


def _load_manifest(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> tuple[Path, dict[str, Any], QuillanStudentReviewContext]:
    _validate_identity(class_id, assignment_id, student_id)
    try:
        context = load_quillan_student_review_context(
            workspace_root,
            quillan_work_ref(class_id, assignment_id),
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError as error:
        raise SubmissionPageManagementError(missing_submission_guidance()) from error
    except (QuillanRecordContextError, OSError) as error:
        raise SubmissionPageManagementError(
            f"Could not load submission record: {error}"
        ) from error
    path = context.paths.submission_manifest_path
    return path, mutable_json_copy(context.submission), context


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
    module_details[_PRESERVED_EXCLUSION_KEY] = {
        "evidence_role": evidence["evidence_role"],
        "evidence_state": evidence["evidence_state"],
    }
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


def _has_preserved_state(evidence: dict[str, Any]) -> bool:
    preserved = evidence.get("module_details", {}).get(_PRESERVED_EXCLUSION_KEY)
    return isinstance(preserved, dict) and (
        isinstance(preserved.get("evidence_role"), str)
        or isinstance(preserved.get("evidence_state"), str)
    )


def _evidence_status(evidence: dict[str, Any]) -> SubmissionEvidenceStatus:
    details = cast(dict[str, Any], evidence["module_details"])
    preserved = details.get(_PRESERVED_EXCLUSION_KEY)
    preserved_dict = preserved if isinstance(preserved, dict) else {}
    return SubmissionEvidenceStatus(
        evidence_id=str(evidence["evidence_id"]),
        evidence_role=str(evidence["evidence_role"]),
        evidence_state=str(evidence["evidence_state"]),
        routed_evidence_path=str(evidence["routed_evidence_path"]),
        duplicate_number=cast(int | None, evidence["duplicate_number"]),
        retained_source_present=evidence["retained_source"] is not None,
        pre_exclusion_role=cast(str | None, preserved_dict.get("evidence_role")),
        pre_exclusion_state=cast(str | None, preserved_dict.get("evidence_state")),
    )


def _state_count(pages: tuple[SubmissionPageStatus, ...], state: str) -> int:
    return sum(page.page_state == state for page in pages)


def _restored_page_state(evidence: list[dict[str, Any]]) -> str:
    evidence_states = {item["evidence_state"] for item in evidence}
    if evidence_states & {"needs_rescan", "damaged"}:
        return "needs_rescan"
    if len(evidence) > 1:
        return "duplicate"
    return "present"


def _write_result(
    workspace_root: str | Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    page: dict[str, Any],
    *,
    previous_page: dict[str, Any],
    action: str,
    record_context: QuillanStudentReviewContext,
    restore_source: str | None = None,
) -> ManagedSubmissionPage:
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    try:
        validate_submission_manifest(manifest)
        update_quillan_submission_manifest(record_context, manifest)
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
        action=action,
        previous_page_state=str(previous_page["page_state"]),
        page_state=str(page["page_state"]),
        previous_selected_evidence_id=(
            str(previous_page["selected_evidence_id"])
            if previous_page["selected_evidence_id"] is not None
            else None
        ),
        selected_evidence_id=(
            str(page["selected_evidence_id"])
            if page["selected_evidence_id"] is not None
            else None
        ),
        evidence_count=len(page["evidence"]),
        updated_at=str(manifest["updated_at"]),
        restore_source=restore_source,
    )


def _validate_identity(class_id: str, assignment_id: str, student_id: str) -> None:
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
        validate_identifier(student_id, "student_id")
    except IdentifierValidationError as error:
        raise SubmissionPageManagementError(str(error)) from error
