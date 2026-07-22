"""Read-only assignment submission and routed-evidence status."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from pds_core.identifiers import validate_identifier

from quillan.assignment_submission_assembly import (
    SkippedRoutedEvidenceFile,
    discover_assignment_routed_evidence_status,
)
from quillan.record_context import (
    ReviewLoadingPolicy,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
    student_record_paths,
)
from quillan.response_page_observations import QuillanResponsePageObservation
from quillan.work_paths import _is_link_like, quillan_work_ref


@dataclass(frozen=True, slots=True)
class PageStatusSummary:
    """Read-only status for one manifest page."""

    page_number: int
    page_state: str
    selected_evidence_id: str | None
    evidence_count: int
    evidence_roles: tuple[str, ...]
    evidence_states: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StudentSubmissionStatus:
    """Read-only submission status for one student."""

    student_id: str
    manifest_path: Path | None
    submission_state: str | None
    pages: tuple[PageStatusSummary, ...]
    missing_pages: tuple[int, ...]
    duplicate_pages: tuple[int, ...]
    needs_rescan_pages: tuple[int, ...]
    excluded_pages: tuple[int, ...]
    unselected_present_pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AssignmentSubmissionStatus:
    """Read-only submission and routed-evidence status for one assignment."""

    class_id: str
    assignment_id: str
    students_with_manifests: tuple[str, ...]
    students_with_routed_evidence: tuple[str, ...]
    students_without_manifests: tuple[str, ...]
    unassembled_routed_files: tuple[Path, ...]
    unused_duplicate_routed_files: tuple[Path, ...]
    skipped_routed_files: tuple[SkippedRoutedEvidenceFile, ...]
    student_statuses: tuple[StudentSubmissionStatus, ...]


def list_assignment_submission_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    expected_pages: int | None = None,
) -> AssignmentSubmissionStatus:
    """Return read-only submission/evidence status for one assignment."""
    validate_identifier(class_id, "class_id")
    validate_identifier(assignment_id, "assignment_id")
    _validate_expected_pages(expected_pages)

    work_ref = quillan_work_ref(class_id, assignment_id)
    assignment_context = load_quillan_assignment_context(workspace_root, work_ref)
    root = assignment_context.paths.workspace_root
    manifests = _load_assignment_manifests(
        root, class_id, assignment_id
    )
    discovery = discover_assignment_routed_evidence_status(
        root, class_id, assignment_id
    )

    manifest_students = tuple(manifests)
    routed_students = tuple(discovery.evidence_by_student)
    students_without_manifests = tuple(
        student_id
        for student_id in routed_students
        if student_id not in manifests
    )
    assembled_paths = {
        _resolved_evidence_path(root, item["routed_evidence_path"])
        for _, manifest in manifests.values()
        for page in manifest["pages"]
        for item in page["evidence"]
    }
    unassembled: list[Path] = []
    unused_duplicates: list[Path] = []
    for student_id, items in discovery.evidence_by_student.items():
        for item in items:
            path = _resolved_evidence_path(root, item.routed_evidence_path)
            if path in assembled_paths:
                continue
            unassembled.append(path)
    unassembled_routed_files = tuple(
        sorted(unassembled, key=lambda path: str(path).casefold())
    )
    unused_duplicate_routed_files = tuple(
        sorted(unused_duplicates, key=lambda path: str(path).casefold())
    )

    statuses = [
        _summarize_manifest(student_id, path, manifest)
        for student_id, (path, manifest) in manifests.items()
    ]
    statuses.extend(
        _summarize_routed_only_student(
            student_id,
            discovery.evidence_by_student[student_id],
            expected_pages,
        )
        for student_id in students_without_manifests
    )
    statuses.sort(key=lambda status: status.student_id)

    return AssignmentSubmissionStatus(
        class_id=class_id,
        assignment_id=assignment_id,
        students_with_manifests=manifest_students,
        students_with_routed_evidence=routed_students,
        students_without_manifests=students_without_manifests,
        unassembled_routed_files=unassembled_routed_files,
        unused_duplicate_routed_files=unused_duplicate_routed_files,
        skipped_routed_files=discovery.skipped_files,
        student_statuses=tuple(statuses),
    )


def _load_assignment_manifests(
    root: Path,
    class_id: str,
    assignment_id: str,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    work_ref = quillan_work_ref(class_id, assignment_id)
    assignment_context = load_quillan_assignment_context(root, work_ref)
    submissions_dir = assignment_context.paths.submissions_dir
    if not os.path.lexists(submissions_dir):
        return {}
    if _is_link_like(submissions_dir) or not submissions_dir.is_dir():
        raise NotADirectoryError(
            "Assignment submissions path is not an ordinary non-link directory: "
            f"{submissions_dir}"
        )

    manifests: dict[str, tuple[Path, dict[str, Any]]] = {}
    for student_dir in sorted(
        submissions_dir.iterdir(), key=lambda path: path.name.casefold()
    ):
        student_id = student_dir.name
        validate_identifier(student_id, "student_id")
        if _is_link_like(student_dir) or not student_dir.is_dir():
            raise NotADirectoryError(
                f"Invalid direct student submission child: {student_dir}"
            )
        manifest_path = student_record_paths(
            root, work_ref, student_id
        ).submission_manifest_path
        if not os.path.lexists(manifest_path):
            continue
        context = load_quillan_student_review_context(
            root,
            work_ref,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
        manifest = mutable_json_copy(context.submission)
        manifests[student_id] = (manifest_path, manifest)
    return manifests


def _validate_manifest_identity(
    manifest: dict[str, Any],
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    path: Path,
) -> None:
    expected = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, value in expected.items():
        if manifest[field] != value:
            raise ValueError(
                f"Manifest identity mismatch at {path}: field '{field}' "
                f"is {manifest[field]!r}, expected {value!r}."
            )


def _summarize_manifest(
    student_id: str,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> StudentSubmissionStatus:
    pages = tuple(
        PageStatusSummary(
            page_number=page["page_number"],
            page_state=page["page_state"],
            selected_evidence_id=page["selected_evidence_id"],
            evidence_count=len(page["evidence"]),
            evidence_roles=tuple(
                item["evidence_role"] for item in page["evidence"]
            ),
            evidence_states=tuple(
                item["evidence_state"] for item in page["evidence"]
            ),
        )
        for page in sorted(
            manifest["pages"], key=lambda page: page["page_number"]
        )
    )
    return _student_status(
        student_id=student_id,
        manifest_path=manifest_path,
        submission_state=manifest["submission_state"],
        pages=pages,
    )


def _summarize_routed_only_student(
    student_id: str,
    evidence_items: tuple[QuillanResponsePageObservation, ...],
    expected_pages: int | None,
) -> StudentSubmissionStatus:
    routed_page_numbers = {item.logical_page for item in evidence_items}
    missing_pages = (
        tuple(
            page_number
            for page_number in range(1, expected_pages + 1)
            if page_number not in routed_page_numbers
        )
        if expected_pages is not None
        else ()
    )
    return StudentSubmissionStatus(
        student_id=student_id,
        manifest_path=None,
        submission_state=None,
        pages=(),
        missing_pages=missing_pages,
        duplicate_pages=(),
        needs_rescan_pages=(),
        excluded_pages=(),
        unselected_present_pages=(),
    )


def _student_status(
    *,
    student_id: str,
    manifest_path: Path,
    submission_state: str,
    pages: tuple[PageStatusSummary, ...],
) -> StudentSubmissionStatus:
    def pages_with_state(state: str) -> tuple[int, ...]:
        return tuple(
            page.page_number for page in pages if page.page_state == state
        )

    return StudentSubmissionStatus(
        student_id=student_id,
        manifest_path=manifest_path,
        submission_state=submission_state,
        pages=pages,
        missing_pages=pages_with_state("missing"),
        duplicate_pages=pages_with_state("duplicate"),
        needs_rescan_pages=pages_with_state("needs_rescan"),
        excluded_pages=pages_with_state("excluded"),
        unselected_present_pages=tuple(
            page.page_number
            for page in pages
            if page.page_state == "present"
            and page.selected_evidence_id is None
        ),
    )


def _validate_expected_pages(expected_pages: int | None) -> None:
    if (
        expected_pages is not None
        and (
            isinstance(expected_pages, bool)
            or not isinstance(expected_pages, int)
            or expected_pages < 1
        )
    ):
        raise ValueError("expected_pages must be a positive integer.")


def _resolved_evidence_path(root: Path, value: str | Path) -> Path:
    return Path(os.path.abspath(root / Path(value)))
