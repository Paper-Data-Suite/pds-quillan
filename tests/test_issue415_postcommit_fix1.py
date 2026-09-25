"""Post-commit reconciliation tests for issue #415."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import quillan.submission_evidence_resolution as resolution_module
from quillan.assignment_summary_context import feedback_status
from quillan.resubmission_inbox import _rescan_signal_pages
from quillan.response_page_observations import QuillanResponsePageObservation
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_evidence_resolution import (
    SubmissionEvidenceResolutionError,
    select_submission_evidence_candidate,
)
from quillan.submission_evidence_validation import selected_evidence_fingerprint
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from tests.test_resubmission_inbox_issue415 import _prepare_initial_and_rescan


def _write_legacy_feedback(
    tmp_path: Path,
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    feedback_path: Path,
) -> dict[str, Any]:
    review = build_empty_review_record(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        created_at="2026-09-17T12:00:00+00:00",
    )
    review["updated_at"] = "2026-09-18T12:00:00+00:00"
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_bytes(b"legacy feedback")
    review["exports"]["feedback_pdf"] = {
        "path": feedback_path.relative_to(tmp_path).as_posix(),
        "generated_at": "2026-09-18T12:00:00+00:00",
        "source_review_updated_at": "2026-09-18T12:00:00+00:00",
        "module_details": {},
    }
    write_review_record(
        review_record_path(tmp_path, class_id, assignment_id, student_id),
        review,
    )
    return review


def test_legacy_v0102_feedback_is_current_until_selection_then_stale(
    tmp_path: Path,
) -> None:
    resolution, first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    before = load_submission_manifest(manifest_path)
    before_fingerprint = selected_evidence_fingerprint(before)
    feedback_path = manifest_path.parent / "exports" / "feedback.pdf"
    review = _write_legacy_feedback(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.work_id,
        student_id=first.observation.student_id,
        feedback_path=feedback_path,
    )
    assert feedback_status(
        tmp_path,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=before_fingerprint,
    )[1] == "present"

    select_submission_evidence_candidate(
        tmp_path,
        identity.class_id,
        identity.work_id,
        first.observation.student_id,
        1,
        second.observation.observation_id,
        timestamp="2026-09-24T12:00:00+00:00",
    )

    bound_review = json.loads(
        review_record_path(
            tmp_path,
            identity.class_id,
            identity.work_id,
            first.observation.student_id,
        ).read_text(encoding="utf-8")
    )
    assert bound_review["exports"]["feedback_pdf"]["module_details"] == {
        "source_selected_evidence_fingerprint": before_fingerprint
    }
    after = load_submission_manifest(manifest_path)
    assert selected_evidence_fingerprint(after) != before_fingerprint
    assert feedback_status(
        tmp_path,
        bound_review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(after),
    )[1] == "stale"


def test_failed_manifest_selection_after_legacy_binding_leaves_feedback_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    before = load_submission_manifest(manifest_path)
    before_fingerprint = selected_evidence_fingerprint(before)
    feedback_path = manifest_path.parent / "exports" / "feedback.pdf"
    _write_legacy_feedback(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.work_id,
        student_id=first.observation.student_id,
        feedback_path=feedback_path,
    )

    def fail_manifest_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic manifest write failure")

    monkeypatch.setattr(
        resolution_module,
        "update_quillan_submission_manifest",
        fail_manifest_write,
    )
    with pytest.raises(SubmissionEvidenceResolutionError, match="was not saved"):
        select_submission_evidence_candidate(
            tmp_path,
            identity.class_id,
            identity.work_id,
            first.observation.student_id,
            1,
            second.observation.observation_id,
        )

    unchanged = load_submission_manifest(manifest_path)
    assert selected_evidence_fingerprint(unchanged) == before_fingerprint
    rebound_review = json.loads(
        review_record_path(
            tmp_path,
            identity.class_id,
            identity.work_id,
            first.observation.student_id,
        ).read_text(encoding="utf-8")
    )
    assert rebound_review["exports"]["feedback_pdf"]["module_details"] == {
        "source_selected_evidence_fingerprint": before_fingerprint
    }
    assert feedback_status(
        tmp_path,
        rebound_review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=before_fingerprint,
    )[1] == "present"


def test_rescan_signal_pages_report_only_actual_duplicate_pages() -> None:
    observations = cast(
        tuple[QuillanResponsePageObservation, ...],
        (
            SimpleNamespace(logical_page=1),
            SimpleNamespace(logical_page=2),
            SimpleNamespace(logical_page=2),
            SimpleNamespace(logical_page=3),
        ),
    )
    assert _rescan_signal_pages(observations) == (2,)
