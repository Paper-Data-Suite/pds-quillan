from __future__ import annotations

from pathlib import Path

import pytest

from quillan.review_status_display import (
    feedback_export_status,
    review_progress_status,
    review_status_label,
)


@pytest.mark.parametrize(
    ("state", "label"),
    [
        ("not_started", "not started"),
        ("requirements_checked", "requirements checked"),
        ("returned_without_full_review", "returned without full standards review"),
        ("observations_in_progress", "observations in progress"),
        ("observations_complete", "observations complete"),
        ("ratings_complete", "ratings complete"),
        ("feedback_composed", "feedback composed"),
        ("ready_for_export", "ready for export"),
        ("exported", "exported"),
    ],
)
def test_review_status_label(state: str, label: str) -> None:
    assert review_status_label({"review_state": state}) == label


@pytest.mark.parametrize(
    ("state", "observations", "ratings", "feedback"),
    [
        ("not_started", False, False, False),
        ("requirements_checked", False, False, False),
        ("observations_in_progress", False, False, False),
        ("observations_complete", True, False, False),
        ("ratings_complete", True, True, False),
        ("feedback_composed", True, True, True),
        ("ready_for_export", True, True, True),
        ("exported", True, True, True),
    ],
)
def test_review_progress_status_treats_later_states_as_complete(
    state: str,
    observations: bool,
    ratings: bool,
    feedback: bool,
) -> None:
    status = review_progress_status({"review_state": state})

    assert status.observations_complete is observations
    assert status.ratings_complete is ratings
    assert status.feedback_composed is feedback


def test_review_progress_status_treats_returned_work_as_not_applicable() -> None:
    status = review_progress_status({"review_state": "returned_without_full_review"})

    assert status.is_returned_without_full_review is True
    assert status.observations_complete is False
    assert status.ratings_complete is False
    assert status.feedback_composed is False
    assert status.observations_status_label == (
        "not applicable - returned without full standards review"
    )
    assert status.ratings_status_label == (
        "not applicable - returned without full standards review"
    )
    assert status.feedback_status_label == (
        "not applicable - returned without full standards review"
    )


def test_review_progress_status_exported_uses_export_metadata() -> None:
    status = review_progress_status(
        {
            "review_state": "returned_without_full_review",
            "exports": {
                "feedback_pdf": {
                    "path": "feedback.pdf",
                    "generated_at": "2026-07-08T17:35:00+00:00",
                }
            },
        }
    )

    assert status.review_state == "returned_without_full_review"
    assert status.exported is True
    assert status.is_returned_without_full_review is True


def test_feedback_export_status_uses_latest_metadata_timestamp(tmp_path: Path) -> None:
    pdf = tmp_path / "feedback.pdf"
    markdown = tmp_path / "feedback.md"
    pdf.write_bytes(b"pdf")
    markdown.write_text("feedback", encoding="utf-8")
    record = {
        "exports": {
            "feedback_pdf": {
                "path": "feedback.pdf",
                "generated_at": "2026-07-08T17:30:00+00:00",
            },
            "feedback_markdown": {
                "path": "feedback.md",
                "generated_at": "2026-07-08T17:35:00+00:00",
            },
        }
    }

    assert feedback_export_status(tmp_path, record) == (
        "PDF + Markdown exported 2026-07-08T17:35:00+00:00"
    )


def test_feedback_export_status_warns_when_metadata_file_is_missing(
    tmp_path: Path,
) -> None:
    record = {
        "exports": {
            "feedback_pdf": {
                "path": "missing.pdf",
                "generated_at": "2026-07-08T17:35:00+00:00",
            },
            "feedback_markdown": None,
        }
    }

    assert feedback_export_status(tmp_path, record) == (
        "metadata exists, but export file is missing"
    )
