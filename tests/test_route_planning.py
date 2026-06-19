"""Tests for decoded Quillan response-page route planning."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from quillan.route_planning import (
    DecodedResponsePage,
    RouteFailure,
    RoutePlan,
    plan_decoded_response_page_route,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    class_dir = tmp_path / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)

    with (class_dir / "roster.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as roster_file:
        writer = csv.DictWriter(
            roster_file,
            fieldnames=(
                "class_id",
                "student_id",
                "last_name",
                "first_name",
                "period",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "3",
            }
        )

    assignment = {
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "standards_profile_id": "synthetic_profile",
        "tagging_mode": "focus",
        "focus_standards": ["W.1"],
        "basic_requirements": {"paragraphs_min": 1},
        "rubric_id": "synthetic_rubric",
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def decoded_page() -> DecodedResponsePage:
    return DecodedResponsePage(
        module="quillan",
        document_type="response",
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        page_number=2,
        raw_payload=(
            "PDS1|module=quillan|class=english12_p3_synthetic|"
            "aid=essay_01_synthetic|sid=00107|page=2|doc=response"
        ),
    )


def _failure(result: RoutePlan | RouteFailure) -> RouteFailure:
    assert isinstance(result, RouteFailure)
    return result


def test_valid_decoded_page_returns_expected_route_plan(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    result = plan_decoded_response_page_route(workspace, decoded_page)

    assert result == RoutePlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        page_number=2,
        assignment_config_path=(
            workspace
            / "classes"
            / CLASS_ID
            / "assignments"
            / ASSIGNMENT_ID
            / "assignment.json"
        ),
        roster_path=workspace / "classes" / CLASS_ID / "roster.csv",
        routed_evidence_dir=(
            workspace
            / "classes"
            / CLASS_ID
            / "assignments"
            / ASSIGNMENT_ID
            / "scans"
        ),
        student_submission_dir=(
            workspace
            / "classes"
            / CLASS_ID
            / "assignments"
            / ASSIGNMENT_ID
            / "submissions"
            / STUDENT_ID
        ),
    )
    assert result.student_id == "00107"


@pytest.mark.parametrize(
    ("changes", "category"),
    [
        ({"module": "scoreform"}, "module_unsupported"),
        ({"document_type": None}, "payload_invalid"),
        ({"document_type": "cover"}, "payload_invalid"),
        ({"class_id": None}, "payload_invalid"),
        ({"class_id": "../unsafe"}, "identifier_invalid"),
        ({"assignment_id": None}, "payload_invalid"),
        ({"student_id": None}, "payload_invalid"),
        ({"page_number": 0}, "payload_invalid"),
        ({"page_number": True}, "payload_invalid"),
    ],
)
def test_invalid_decoded_values_return_structured_failure(
    workspace: Path,
    decoded_page: DecodedResponsePage,
    changes: dict[str, Any],
    category: str,
) -> None:
    result = plan_decoded_response_page_route(
        workspace,
        replace(decoded_page, **changes),
    )

    assert _failure(result).failure_category == category


def test_optional_page_number_may_be_absent(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    result = plan_decoded_response_page_route(
        workspace,
        replace(decoded_page, page_number=None),
    )

    assert isinstance(result, RoutePlan)
    assert result.page_number is None


def test_unknown_class_returns_class_unknown(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    result = plan_decoded_response_page_route(
        workspace,
        replace(decoded_page, class_id="unknown_class"),
    )

    assert _failure(result).failure_category == "class_unknown"


def test_missing_roster_returns_processing_error(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    (workspace / "classes" / CLASS_ID / "roster.csv").unlink()

    result = plan_decoded_response_page_route(workspace, decoded_page)

    failure = _failure(result)
    assert failure.failure_category == "processing_error"
    assert failure.module_details["reason"] == "roster_missing"


def test_unknown_assignment_returns_assignment_unknown(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    result = plan_decoded_response_page_route(
        workspace,
        replace(decoded_page, assignment_id="unknown_assignment"),
    )

    assert _failure(result).failure_category == "assignment_unknown"


def test_invalid_assignment_config_returns_processing_error(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    assignment_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment_path.write_text("{}", encoding="utf-8")

    result = plan_decoded_response_page_route(workspace, decoded_page)

    failure = _failure(result)
    assert failure.failure_category == "processing_error"
    assert failure.module_details["reason"] == "assignment_config_invalid"


def test_assignment_class_mismatch_returns_route_mismatch(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    assignment_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment["class_ids"] = ["different_class"]
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")

    result = plan_decoded_response_page_route(workspace, decoded_page)

    assert _failure(result).failure_category == "route_mismatch"


def test_assignment_id_mismatch_returns_route_mismatch(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    assignment_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment["assignment_id"] = "different_assignment"
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")

    result = plan_decoded_response_page_route(workspace, decoded_page)

    assert _failure(result).failure_category == "route_mismatch"


def test_unknown_student_returns_student_unknown(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    result = plan_decoded_response_page_route(
        workspace,
        replace(decoded_page, student_id="00999"),
    )

    assert _failure(result).failure_category == "student_unknown"


def test_planner_does_not_write_or_create_scan_directories(
    workspace: Path,
    decoded_page: DecodedResponsePage,
) -> None:
    before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))

    result = plan_decoded_response_page_route(workspace, decoded_page)

    after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
    assert isinstance(result, RoutePlan)
    assert after == before
    assert not (workspace / "scans").exists()
    assert not result.routed_evidence_dir.exists()
    assert not result.student_submission_dir.exists()
