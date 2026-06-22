"""Assignment-level assembly of routed evidence into submission manifests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.storage import assignment_scans_dir
from quillan.submission_assembly import (
    RoutedSubmissionEvidence,
    assemble_submission_manifest,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_manifest_paths import submission_manifest_path

_ROUTED_EVIDENCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^response_(?P<student_id>[A-Za-z0-9_-]+)_pg_"
    r"(?P<page_number>[0-9]+)"
    r"(?:__dup_(?P<duplicate_number>[0-9]+))?"
    r"\.(?P<extension>pdf|png|jpg|jpeg|tif|tiff)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SkippedRoutedEvidenceFile:
    """One assignment scans file excluded from routed-evidence discovery."""

    path: Path
    reason: str


@dataclass(frozen=True, slots=True)
class StudentSubmissionAssemblySummary:
    """Page-state summary for one newly written student manifest."""

    student_id: str
    manifest_path: Path
    missing_pages: tuple[int, ...]
    duplicate_pages: tuple[int, ...]
    needs_rescan_pages: tuple[int, ...]
    excluded_pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AssignmentSubmissionAssemblyResult:
    """Outcome of assembling all routed evidence for one assignment."""

    class_id: str
    assignment_id: str
    written_manifests: tuple[Path, ...]
    skipped_existing_manifests: tuple[Path, ...]
    skipped_files: tuple[SkippedRoutedEvidenceFile, ...]
    students_with_evidence: tuple[str, ...]
    student_summaries: tuple[StudentSubmissionAssemblySummary, ...]


@dataclass(frozen=True, slots=True)
class AssignmentRoutedEvidenceDiscovery:
    """Read-only routed-evidence discovery for one assignment."""

    evidence_by_student: dict[str, list[RoutedSubmissionEvidence]]
    skipped_files: tuple[SkippedRoutedEvidenceFile, ...]


def discover_assignment_routed_evidence(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> dict[str, list[RoutedSubmissionEvidence]]:
    """Discover routed response evidence files grouped by student ID."""
    return _discover_assignment_routed_evidence(
        workspace_root, class_id, assignment_id
    ).evidence_by_student


def discover_assignment_routed_evidence_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentRoutedEvidenceDiscovery:
    """Discover routed evidence plus files excluded from discovery."""
    return _discover_assignment_routed_evidence(
        workspace_root, class_id, assignment_id
    )


def assemble_assignment_submissions(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    expected_pages: int | None = None,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
) -> AssignmentSubmissionAssemblyResult:
    """Assemble manifests for every student with routed assignment evidence.

    ``overwrite=True`` performs full regeneration. It does not merge prior
    review state or preserve prior teacher selections.
    """
    if (
        expected_pages is not None
        and (
            isinstance(expected_pages, bool)
            or not isinstance(expected_pages, int)
            or expected_pages < 1
        )
    ):
        raise ValueError("expected_pages must be a positive integer.")

    discovery = _discover_assignment_routed_evidence(
        workspace_root, class_id, assignment_id
    )
    students = tuple(discovery.evidence_by_student)
    written: list[Path] = []
    skipped_existing: list[Path] = []
    summaries: list[StudentSubmissionAssemblySummary] = []

    for student_id, evidence_items in discovery.evidence_by_student.items():
        manifest_path = submission_manifest_path(
            workspace_root, class_id, assignment_id, student_id
        )
        if manifest_path.exists() and not overwrite:
            skipped_existing.append(manifest_path)
            continue

        written_path = assemble_submission_manifest(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            evidence_items,
            expected_pages=expected_pages,
            overwrite=overwrite,
            created_at=created_at,
            updated_at=updated_at,
        )
        written.append(written_path)
        summaries.append(_summarize_manifest(student_id, written_path))

    return AssignmentSubmissionAssemblyResult(
        class_id=class_id,
        assignment_id=assignment_id,
        written_manifests=tuple(written),
        skipped_existing_manifests=tuple(skipped_existing),
        skipped_files=discovery.skipped_files,
        students_with_evidence=students,
        student_summaries=tuple(summaries),
    )


def _discover_assignment_routed_evidence(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentRoutedEvidenceDiscovery:
    validate_identifier(class_id, "class_id")
    validate_identifier(assignment_id, "assignment_id")
    root = Path(workspace_root).resolve(strict=False)
    scans_dir = assignment_scans_dir(root, class_id, assignment_id)
    if not scans_dir.exists():
        return AssignmentRoutedEvidenceDiscovery({}, ())
    if not scans_dir.is_dir():
        raise NotADirectoryError(
            f"Assignment scans path is not a directory: {scans_dir}"
        )

    grouped: dict[str, list[RoutedSubmissionEvidence]] = {}
    skipped: list[SkippedRoutedEvidenceFile] = []
    try:
        entries = sorted(scans_dir.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        raise

    for path in entries:
        if not path.is_file():
            continue
        match = _ROUTED_EVIDENCE_PATTERN.fullmatch(path.name)
        if match is None:
            skipped.append(
                SkippedRoutedEvidenceFile(
                    path=path,
                    reason=_unmatched_filename_reason(path.name),
                )
            )
            continue

        student_id = match.group("student_id")
        try:
            validate_identifier(student_id, "student_id")
        except IdentifierValidationError as error:
            skipped.append(SkippedRoutedEvidenceFile(path=path, reason=str(error)))
            continue

        page_number = int(match.group("page_number"))
        duplicate_text = match.group("duplicate_number")
        duplicate_number = (
            int(duplicate_text) if duplicate_text is not None else None
        )
        if page_number < 1:
            skipped.append(
                SkippedRoutedEvidenceFile(
                    path=path,
                    reason="page number must be a positive integer",
                )
            )
            continue
        if duplicate_number is not None and duplicate_number < 1:
            skipped.append(
                SkippedRoutedEvidenceFile(
                    path=path,
                    reason="duplicate number must be a positive integer",
                )
            )
            continue

        grouped.setdefault(student_id, []).append(
            RoutedSubmissionEvidence(
                page_number=page_number,
                routed_evidence_path=path.relative_to(root),
                duplicate_number=duplicate_number,
                retained_source_path=None,
                source_scan_id=None,
                source_filename=None,
                source_sha256=None,
                source_page_number=None,
            )
        )

    ordered = {
        student_id: sorted(
            grouped[student_id],
            key=lambda item: (
                item.page_number,
                item.duplicate_number is not None,
                item.duplicate_number or 0,
                str(item.routed_evidence_path).casefold(),
            ),
        )
        for student_id in sorted(grouped)
    }
    return AssignmentRoutedEvidenceDiscovery(ordered, tuple(skipped))


def _unmatched_filename_reason(filename: str) -> str:
    if filename.casefold().startswith("response_"):
        return "malformed routed response evidence filename"
    return "filename does not match routed response evidence convention"


def _summarize_manifest(
    student_id: str, manifest_path: Path
) -> StudentSubmissionAssemblySummary:
    manifest = load_submission_manifest(manifest_path)

    def pages_with_state(state: str) -> tuple[int, ...]:
        return tuple(
            page["page_number"]
            for page in manifest["pages"]
            if page["page_state"] == state
        )

    return StudentSubmissionAssemblySummary(
        student_id=student_id,
        manifest_path=manifest_path,
        missing_pages=pages_with_state("missing"),
        duplicate_pages=pages_with_state("duplicate"),
        needs_rescan_pages=pages_with_state("needs_rescan"),
        excluded_pages=pages_with_state("excluded"),
    )
