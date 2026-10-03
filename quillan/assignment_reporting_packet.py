"""Coherent assignment reporting-packet orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from quillan.assignment_reporting_snapshot import (
    AssignmentReportingSnapshotError,
    build_assignment_reporting_snapshot,
)
from quillan.assignment_results_manifest_export import (
    AssignmentResultsManifestExportError,
    ExportedAssignmentResultsManifest,
    assignment_results_manifest_export_path,
    export_assignment_results_manifest_from_snapshot,
)
from quillan.assignment_review_report_export import (
    AssignmentReviewReportExportError,
    ExportedAssignmentReviewReport,
    assignment_review_report_export_path,
    export_assignment_review_report_from_snapshot,
)
from quillan.class_summary_export import (
    ClassSummaryExportError,
    ExportedClassSummary,
    class_summary_export_path,
    export_class_review_summary_from_snapshot,
)
from quillan.standards_summary_export import (
    ExportedStandardsSummary,
    StandardsSummaryExportError,
    export_standards_summary_from_snapshot,
    standards_summary_export_path,
)
from quillan.student_performance_summary_export import (
    ExportedStudentPerformanceSummary,
    StudentPerformanceSummaryExportError,
    export_student_performance_summary_from_snapshot,
    student_performance_summary_export_path,
)


class AssignmentReportingPacketError(Exception):
    """Raised when a complete assignment reporting packet cannot be generated."""

    def __init__(
        self,
        message: str,
        *,
        completed_relative_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.completed_relative_paths = completed_relative_paths


@dataclass(frozen=True, slots=True)
class ExportedAssignmentReportingPacket:
    """Five assignment-local reports generated from one immutable snapshot."""

    class_id: str
    assignment_id: str
    generated_at: str
    student_performance_summary: ExportedStudentPerformanceSummary
    class_summary: ExportedClassSummary
    standards_summary: ExportedStandardsSummary
    assignment_review_report: ExportedAssignmentReviewReport
    assignment_results_manifest: ExportedAssignmentResultsManifest

    @property
    def relative_paths(self) -> tuple[str, ...]:
        """Return packet artifacts in canonical generation order."""
        return (
            self.student_performance_summary.summary_relative_path,
            self.class_summary.summary_relative_path,
            self.standards_summary.summary_relative_path,
            self.assignment_review_report.report_relative_path,
            self.assignment_results_manifest.manifest_relative_path,
        )


def export_assignment_reporting_packet(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    generated_at: datetime | str | None = None,
) -> ExportedAssignmentReportingPacket:
    """Generate the canonical five-file packet from one reporting snapshot."""
    normalized_generated_at = _normalize_timestamp(generated_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise AssignmentReportingPacketError(str(error)) from error

    targets = (
        student_performance_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        ),
        class_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        ),
        standards_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        ),
        assignment_review_report_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        ),
        assignment_results_manifest_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        ),
    )

    if not overwrite:
        conflicts = tuple(path for path in targets if path.exists())
        if conflicts:
            rendered = ", ".join(
                _relative(path, snapshot.workspace_root)
                for path in conflicts
            )
            raise AssignmentReportingPacketError(
                "Reporting packet was not generated because existing report "
                f"artifacts would be replaced: {rendered}. "
                "Use overwrite=True only when replacement is deliberate."
            )

    completed: list[str] = []
    try:
        student_performance = export_student_performance_summary_from_snapshot(
            snapshot,
            overwrite=overwrite,
            created_at=normalized_generated_at,
        )
        completed.append(student_performance.summary_relative_path)

        class_summary = export_class_review_summary_from_snapshot(
            snapshot,
            overwrite=overwrite,
            created_at=normalized_generated_at,
        )
        completed.append(class_summary.summary_relative_path)

        standards_summary = export_standards_summary_from_snapshot(
            snapshot,
            overwrite=overwrite,
            created_at=normalized_generated_at,
        )
        completed.append(standards_summary.summary_relative_path)

        review_report = export_assignment_review_report_from_snapshot(
            snapshot,
            overwrite=overwrite,
            created_at=normalized_generated_at,
        )
        completed.append(review_report.report_relative_path)

        results_manifest = export_assignment_results_manifest_from_snapshot(
            snapshot,
            overwrite=overwrite,
            generated_at=normalized_generated_at,
        )
        completed.append(results_manifest.manifest_relative_path)
    except (
        StudentPerformanceSummaryExportError,
        ClassSummaryExportError,
        StandardsSummaryExportError,
        AssignmentReviewReportExportError,
        AssignmentResultsManifestExportError,
        OSError,
    ) as error:
        raise AssignmentReportingPacketError(
            "Reporting packet generation stopped before all artifacts were "
            f"completed: {error}",
            completed_relative_paths=tuple(completed),
        ) from error

    return ExportedAssignmentReportingPacket(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        generated_at=normalized_generated_at,
        student_performance_summary=student_performance,
        class_summary=class_summary,
        standards_summary=standards_summary,
        assignment_review_report=review_report,
        assignment_results_manifest=results_manifest,
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            root.resolve(strict=False)
        ).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.name


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise AssignmentReportingPacketError(
                "generated_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise AssignmentReportingPacketError(
            "generated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise AssignmentReportingPacketError(
            "generated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssignmentReportingPacketError(
            "generated_at must be a timezone-aware ISO 8601 string."
        )
    return value
