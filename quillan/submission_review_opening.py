"""Open selected evidence for one student submission review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quillan.evidence_opening import EvidenceOpeningError, open_workspace_evidence
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)


class SubmissionReviewOpeningError(Exception):
    """Raised when a student submission cannot be opened for review."""


@dataclass(frozen=True, slots=True)
class OpenedSubmissionReview:
    """Information about a student submission evidence file opened for review."""

    class_id: str
    assignment_id: str
    student_id: str
    manifest_path: Path
    manifest_relative_path: str
    page_number: int
    evidence_id: str
    evidence_path: Path
    evidence_relative_path: str
    submission_state: str
    page_state: str


def open_student_submission_for_review(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> OpenedSubmissionReview:
    """Open the single selected routed evidence file for one submission."""
    try:
        resolved_workspace_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    except (OSError, RuntimeError, SubmissionManifestPathError) as error:
        raise SubmissionReviewOpeningError(str(error)) from error

    if not manifest_path.exists():
        raise SubmissionReviewOpeningError(
            "Submission manifest does not exist for "
            f"class={class_id}, assignment={assignment_id}, student={student_id}."
        )

    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise SubmissionReviewOpeningError(
            f"Could not load submission manifest: {error}"
        ) from error

    _validate_manifest_identity(
        manifest,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    page, selected_id = _find_selected_page(manifest)
    evidence = next(
        (
            candidate
            for candidate in page["evidence"]
            if candidate["evidence_id"] == selected_id
        ),
        None,
    )
    if evidence is None:
        raise SubmissionReviewOpeningError(
            f"Selected evidence ID '{selected_id}' was not found on "
            f"page {page['page_number']}."
        )

    try:
        opened = open_workspace_evidence(
            resolved_workspace_root,
            evidence["routed_evidence_path"],
        )
        manifest_relative_path = manifest_path.resolve(strict=False).relative_to(
            resolved_workspace_root
        ).as_posix()
    except (EvidenceOpeningError, OSError, RuntimeError, ValueError) as error:
        raise SubmissionReviewOpeningError(
            f"Could not open selected evidence: {error}"
        ) from error

    return OpenedSubmissionReview(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        manifest_path=manifest_path,
        manifest_relative_path=manifest_relative_path,
        page_number=page["page_number"],
        evidence_id=selected_id,
        evidence_path=opened.evidence_path,
        evidence_relative_path=opened.evidence_relative_path,
        submission_state=manifest["submission_state"],
        page_state=page["page_state"],
    )


def _validate_manifest_identity(
    manifest: dict[str, Any],
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    requested = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, expected in requested.items():
        actual = manifest[field]
        if actual != expected:
            raise SubmissionReviewOpeningError(
                f"Submission manifest {field} is {actual!r}, expected {expected!r}."
            )


def _find_selected_page(
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    selected = [
        (page, page["selected_evidence_id"])
        for page in manifest["pages"]
        if page["selected_evidence_id"] is not None
    ]
    if not selected:
        raise SubmissionReviewOpeningError(
            "Submission has no selected evidence to open. Use status listing "
            "to inspect missing, duplicate, needs-rescan, or unselected evidence."
        )
    if len(selected) > 1:
        raise SubmissionReviewOpeningError(
            "Submission has multiple selected evidence files; open-submission "
            "currently requires exactly one selected evidence file."
        )

    page, selected_id = selected[0]
    return page, selected_id
