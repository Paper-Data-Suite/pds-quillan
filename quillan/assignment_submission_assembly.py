"""Assignment-level observation discovery and issuance-based assembly."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final

from pds_core.identifiers import validate_identifier

from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    list_quillan_page_observations,
)
from quillan.submission_observation_assembly import (
    AssembledQuillanSubmission,
    QuillanSubmissionAssemblyFailure,
    assemble_quillan_submission_manifests,
)

_MAPPING_PROXY_TYPE: Final[type[object]] = type(MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class SkippedRoutedEvidenceFile:
    """Compatibility diagnostic; orphan evidence is never discovered."""

    path: Path
    reason: str

    def __post_init__(self) -> None:
        _canonical_absolute_path(self.path, "skipped evidence path")
        if type(self.reason) is not str or not self.reason.strip():
            raise ValueError("Skipped evidence reason must be nonempty text.")


@dataclass(frozen=True, slots=True)
class StudentSubmissionAssemblySummary:
    student_id: str
    manifest_path: Path
    missing_pages: tuple[int, ...]
    duplicate_pages: tuple[int, ...]
    needs_rescan_pages: tuple[int, ...]
    excluded_pages: tuple[int, ...]
    status: str

    def __post_init__(self) -> None:
        validate_identifier(self.student_id, "student_id")
        _canonical_absolute_path(self.manifest_path, "manifest_path")
        if self.status not in {"created", "updated", "unchanged"}:
            raise ValueError("Unsupported student summary status.")
        groups = (
            self.missing_pages,
            self.duplicate_pages,
            self.needs_rescan_pages,
            self.excluded_pages,
        )
        for values in groups:
            _page_tuple(values)
        flattened = tuple(value for values in groups for value in values)
        if len(set(flattened)) != len(flattened):
            raise ValueError("Student summary page-state tuples must be disjoint.")


@dataclass(frozen=True, slots=True)
class AssignmentSubmissionAssemblyResult:
    class_id: str
    assignment_id: str
    written_manifests: tuple[Path, ...]
    skipped_existing_manifests: tuple[Path, ...]
    skipped_files: tuple[SkippedRoutedEvidenceFile, ...]
    students_with_evidence: tuple[str, ...]
    student_summaries: tuple[StudentSubmissionAssemblySummary, ...]
    assembled: tuple[AssembledQuillanSubmission, ...]
    failures: tuple[QuillanSubmissionAssemblyFailure, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.class_id, "class_id")
        validate_identifier(self.assignment_id, "assignment_id")
        for name, values, member_type in (
            ("written_manifests", self.written_manifests, Path),
            ("skipped_existing_manifests", self.skipped_existing_manifests, Path),
            ("skipped_files", self.skipped_files, SkippedRoutedEvidenceFile),
            ("students_with_evidence", self.students_with_evidence, str),
            ("student_summaries", self.student_summaries, StudentSubmissionAssemblySummary),
            ("assembled", self.assembled, AssembledQuillanSubmission),
            ("failures", self.failures, QuillanSubmissionAssemblyFailure),
        ):
            if type(values) is not tuple or any(
                not isinstance(item, Path)
                if member_type is Path
                else type(item) is not member_type
                for item in values
            ):
                raise ValueError(f"{name} must be an exact member tuple.")
        for paths in (self.written_manifests, self.skipped_existing_manifests):
            for path in paths:
                _canonical_absolute_path(path, "manifest path")
            if len(set(paths)) != len(paths) or paths != tuple(sorted(paths, key=lambda item: item.as_posix())):
                raise ValueError("Manifest paths must be unique and deterministically ordered.")
        if set(self.written_manifests) & set(self.skipped_existing_manifests):
            raise ValueError("Written and unchanged manifest paths must be disjoint.")
        if self.students_with_evidence != tuple(sorted(set(self.students_with_evidence))):
            raise ValueError("students_with_evidence must be unique and sorted.")
        if tuple(item.student_id for item in self.student_summaries) != tuple(
            sorted(item.student_id for item in self.student_summaries)
        ):
            raise ValueError("Student summaries must be deterministically ordered.")
        if tuple(item.student_id for item in self.assembled) != tuple(
            sorted(item.student_id for item in self.assembled)
        ):
            raise ValueError("Assembled results must be deterministically ordered.")
        failure_keys = tuple(
            (item.student_id or "", item.issuance_ids, item.observation_ids)
            for item in self.failures
        )
        if failure_keys != tuple(sorted(failure_keys)):
            raise ValueError("Assembly failures must be deterministically ordered.")
        assembled_targets = {(item.student_id, item.issuance_id) for item in self.assembled}
        failure_targets = {
            (item.student_id, issuance_id)
            for item in self.failures
            if item.student_id is not None
            for issuance_id in item.issuance_ids
        }
        if assembled_targets & failure_targets:
            raise ValueError("A student issuance cannot be both assembled and failed.")
        expected_summaries = tuple(
            (
                item.student_id,
                item.manifest_path,
                item.missing_pages,
                item.duplicate_pages,
                item.needs_rescan_pages,
                item.excluded_pages,
                item.status,
            )
            for item in self.assembled
        )
        actual_summaries = tuple(
            (
                item.student_id,
                item.manifest_path,
                item.missing_pages,
                item.duplicate_pages,
                item.needs_rescan_pages,
                item.excluded_pages,
                item.status,
            )
            for item in self.student_summaries
        )
        if actual_summaries != expected_summaries:
            raise ValueError("Student summaries must exactly represent assembled results.")
        expected_written = tuple(
            item.manifest_path for item in self.assembled if item.status in {"created", "updated"}
        )
        expected_unchanged = tuple(
            item.manifest_path for item in self.assembled if item.status == "unchanged"
        )
        if self.written_manifests != expected_written or self.skipped_existing_manifests != expected_unchanged:
            raise ValueError("Compatibility manifest paths contradict assembled statuses.")


@dataclass(frozen=True, slots=True)
class AssignmentRoutedEvidenceDiscovery:
    """Compatibility name for observation-authoritative discovery."""

    evidence_by_student: Mapping[str, tuple[QuillanResponsePageObservation, ...]]
    skipped_files: tuple[SkippedRoutedEvidenceFile, ...]

    def __post_init__(self) -> None:
        if type(self.evidence_by_student) is not _MAPPING_PROXY_TYPE:
            raise ValueError("evidence_by_student must be an immutable mapping.")
        if type(self.skipped_files) is not tuple or any(
            type(item) is not SkippedRoutedEvidenceFile for item in self.skipped_files
        ):
            raise ValueError("skipped_files must be an exact tuple.")
        keys = tuple(self.evidence_by_student)
        if keys != tuple(sorted(keys)):
            raise ValueError("Evidence student groups must be deterministically ordered.")
        seen: set[str] = set()
        for student_id, observations in self.evidence_by_student.items():
            validate_identifier(student_id, "student_id")
            if type(observations) is not tuple or any(
                type(item) is not QuillanResponsePageObservation
                or item.student_id != student_id
                for item in observations
            ):
                raise ValueError("Evidence groups must contain exact matching observations.")
            ids = tuple(item.observation_id for item in observations)
            if len(set(ids)) != len(ids) or seen.intersection(ids):
                raise ValueError("Grouped observation IDs must be unique.")
            seen.update(ids)
            observation_keys = tuple(
                _observation_sort_key(item) for item in observations
            )
            if observation_keys != tuple(sorted(observation_keys)):
                raise ValueError("Evidence groups must be deterministically ordered.")


def discover_assignment_routed_evidence(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Mapping[str, tuple[QuillanResponsePageObservation, ...]]:
    """Group strict observation records by their stored student identity."""
    return discover_assignment_routed_evidence_status(
        workspace_root, class_id, assignment_id
    ).evidence_by_student


def discover_assignment_routed_evidence_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentRoutedEvidenceDiscovery:
    """Discover observations only; routed evidence filenames are never parsed."""
    observations = list_quillan_page_observations(
        Path(workspace_root), class_id, assignment_id
    )
    grouped: dict[str, list[QuillanResponsePageObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.student_id, []).append(observation)
    return AssignmentRoutedEvidenceDiscovery(
        MappingProxyType(
            {
                student_id: tuple(grouped[student_id])
                for student_id in sorted(grouped)
            }
        ),
        (),
    )


def assemble_assignment_submissions(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
) -> AssignmentSubmissionAssemblyResult:
    """Assemble every observed student without caller-supplied page identity."""
    timestamp = updated_at if updated_at is not None else created_at
    root = Path(workspace_root)
    observations = list_quillan_page_observations(root, class_id, assignment_id)
    result = assemble_quillan_submission_manifests(
        root,
        class_id,
        assignment_id,
        timestamp=timestamp,
    )
    written = tuple(
        item.manifest_path
        for item in result.assembled
        if item.status in {"created", "updated"}
    )
    unchanged = tuple(
        item.manifest_path for item in result.assembled if item.status == "unchanged"
    )
    summaries = tuple(
        StudentSubmissionAssemblySummary(
            student_id=item.student_id,
            manifest_path=item.manifest_path,
            missing_pages=item.missing_pages,
            duplicate_pages=item.duplicate_pages,
            needs_rescan_pages=item.needs_rescan_pages,
            excluded_pages=item.excluded_pages,
            status=item.status,
        )
        for item in result.assembled
    )
    return AssignmentSubmissionAssemblyResult(
        class_id=class_id,
        assignment_id=assignment_id,
        written_manifests=written,
        skipped_existing_manifests=unchanged,
        skipped_files=(),
        students_with_evidence=tuple(sorted({item.student_id for item in observations})),
        student_summaries=summaries,
        assembled=result.assembled,
        failures=result.failures,
    )


def _canonical_absolute_path(value: object, field_name: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or Path(os.path.abspath(value)) != value:
        raise ValueError(f"{field_name} must be a canonical absolute Path.")
    return value


def _page_tuple(values: object) -> tuple[int, ...]:
    if type(values) is not tuple or any(
        type(value) is not int or isinstance(value, bool) or value < 1 for value in values
    ):
        raise ValueError("Page summaries must be exact positive-integer tuples.")
    if values != tuple(sorted(set(values))):
        raise ValueError("Page summaries must be unique and sorted.")
    return values


def _observation_sort_key(
    observation: QuillanResponsePageObservation,
) -> tuple[str, int, str, str, int, str]:
    return (
        observation.issuance_id,
        observation.logical_page,
        observation.created_at,
        observation.source_scan_id,
        observation.source_page_number,
        observation.observation_id,
    )


__all__ = [
    "AssignmentRoutedEvidenceDiscovery",
    "AssignmentSubmissionAssemblyResult",
    "SkippedRoutedEvidenceFile",
    "StudentSubmissionAssemblySummary",
    "assemble_assignment_submissions",
    "discover_assignment_routed_evidence",
    "discover_assignment_routed_evidence_status",
]
