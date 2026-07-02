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
from quillan.submission_guidance import missing_submission_guidance


class SubmissionReviewOpeningError(Exception):
    """Raised when a student submission cannot be opened for review."""


@dataclass(frozen=True, slots=True)
class SelectedSubmissionEvidencePage:
    """Selected evidence metadata for one logical submission page."""

    page_number: int
    evidence_id: str
    evidence_relative_path: str
    page_state: str


@dataclass(frozen=True, slots=True)
class OpenedSubmissionEvidencePage:
    """Information about one submission evidence file opened for review."""

    page_number: int
    evidence_id: str
    evidence_path: Path
    evidence_relative_path: str
    page_state: str


@dataclass(frozen=True, slots=True)
class OpenedSubmissionReview:
    """Information about student submission evidence opened for review."""

    class_id: str
    assignment_id: str
    student_id: str
    manifest_path: Path
    manifest_relative_path: str
    submission_state: str
    opened_pages: tuple[OpenedSubmissionEvidencePage, ...]

    @property
    def page_number(self) -> int:
        return self.opened_pages[0].page_number

    @property
    def evidence_id(self) -> str:
        return self.opened_pages[0].evidence_id

    @property
    def evidence_path(self) -> Path:
        return self.opened_pages[0].evidence_path

    @property
    def evidence_relative_path(self) -> str:
        return self.opened_pages[0].evidence_relative_path

    @property
    def page_state(self) -> str:
        return self.opened_pages[0].page_state


def open_student_submission_for_review(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    page_number: int | None = None,
) -> OpenedSubmissionReview:
    """Open selected routed evidence files for one submission."""
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
        raise SubmissionReviewOpeningError(missing_submission_guidance())

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
    selected_pages = selected_submission_evidence_pages(
        manifest,
        page_number=page_number,
    )

    try:
        manifest_relative_path = manifest_path.resolve(strict=False).relative_to(
            resolved_workspace_root
        ).as_posix()
    except (EvidenceOpeningError, OSError, RuntimeError, ValueError) as error:
        raise SubmissionReviewOpeningError(
            f"Could not resolve submission manifest path: {error}"
        ) from error

    opened_pages: list[OpenedSubmissionEvidencePage] = []
    for selected_page in selected_pages:
        try:
            opened = open_workspace_evidence(
                resolved_workspace_root,
                selected_page.evidence_relative_path,
            )
        except (EvidenceOpeningError, OSError, RuntimeError, ValueError) as error:
            raise SubmissionReviewOpeningError(
                "Could not open selected evidence for "
                f"page {selected_page.page_number} "
                f"({selected_page.evidence_relative_path}): {error}"
            ) from error
        opened_pages.append(
            OpenedSubmissionEvidencePage(
                page_number=selected_page.page_number,
                evidence_id=selected_page.evidence_id,
                evidence_path=opened.evidence_path,
                evidence_relative_path=opened.evidence_relative_path,
                page_state=selected_page.page_state,
            )
        )

    return OpenedSubmissionReview(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        manifest_path=manifest_path,
        manifest_relative_path=manifest_relative_path,
        submission_state=manifest["submission_state"],
        opened_pages=tuple(opened_pages),
    )


def selected_submission_evidence_pages(
    manifest: dict[str, Any],
    *,
    page_number: int | None = None,
) -> tuple[SelectedSubmissionEvidencePage, ...]:
    """Return selected evidence pages in ascending logical page order."""
    pages = manifest["pages"]
    if page_number is not None:
        matching_page = next(
            (page for page in pages if page["page_number"] == page_number),
            None,
        )
        if matching_page is None:
            raise SubmissionReviewOpeningError(
                f"Submission page {page_number} does not exist."
            )
        selected = _selected_evidence_page(matching_page)
        if selected is None:
            raise SubmissionReviewOpeningError(
                f"Submission page {page_number} has no selected evidence to open "
                f"(page state: {matching_page['page_state']})."
            )
        return (selected,)

    selected_pages = [
        selected
        for page in pages
        if (selected := _selected_evidence_page(page)) is not None
    ]
    if not selected_pages:
        raise SubmissionReviewOpeningError(
            "Submission has no selected evidence to open. Use status listing "
            "to inspect missing, duplicate, needs-rescan, or unselected evidence."
        )
    return tuple(sorted(selected_pages, key=lambda page: page.page_number))


def _selected_evidence_page(
    page: dict[str, Any],
) -> SelectedSubmissionEvidencePage | None:
    selected_id = page["selected_evidence_id"]
    if selected_id is None:
        return None
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
    return SelectedSubmissionEvidencePage(
        page_number=page["page_number"],
        evidence_id=selected_id,
        evidence_relative_path=evidence["routed_evidence_path"],
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
