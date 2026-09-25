"""Regression coverage for the installed #415 acceptance program."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from quillan.resubmission_inbox import build_assignment_resubmission_inbox
from quillan.submission_evidence_resolution import (
    select_submission_evidence_candidate,
)
from quillan.submission_review_opening import open_exact_verified_submission_evidence
from quillan.review_record_paths import review_record_path
from scripts.verify_installed_resubmission_inbox import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _prepare,
)


def test_installed_acceptance_fixture_exercises_rescan_and_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original, candidate = _prepare(tmp_path)
    inbox = build_assignment_resubmission_inbox(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert len(inbox.items) == 1
    assert inbox.items[0].temporal_classification == "new_after_feedback"
    assert original.routed_evidence_sha256 == candidate.routed_evidence_sha256
    review = json.loads(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert review["exports"]["feedback_pdf"]["module_details"] == {
        "source_selected_evidence_fingerprint": review["exports"][
            "feedback_markdown"
        ]["module_details"]["source_selected_evidence_fingerprint"]
    }
    opened_paths: list[Path] = []
    monkeypatch.setattr(
        "quillan.evidence_opening.open_local_path",
        lambda path: opened_paths.append(path) or path,
    )
    for evidence in (original, candidate):
        opened = open_exact_verified_submission_evidence(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            page_number=1,
            evidence_id=evidence.observation_id,
        )
        assert opened.evidence_id == evidence.observation_id
    assert len(opened_paths) == 2

    select_submission_evidence_candidate(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        1,
        candidate.observation_id,
        timestamp="2026-09-24T12:00:00+00:00",
    )
    assert not build_assignment_resubmission_inbox(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ).items


def test_candidate_validator_invokes_installed_resubmission_acceptance() -> None:
    source = Path("scripts/validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "verify_installed_resubmission_inbox.py" in source
    assert "Installed resubmission inbox Core $CoreVersion" in source
    assert "'--expected-quillan-version', '0.10.3'" in source
