"""Focused tests for Quillan scan review discovery and resolution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pds_core.scan_failure_metadata import RoutingFailureMetadata, write_routing_failure_metadata
from pds_core.scan_resolution_metadata import (
    scan_resolution_metadata_from_dict,
)

from quillan.scan_review_resolution import (
    ScanReviewResolutionError,
    discover_scan_review_items,
    resolve_scan_review_item,
)

FAILURE_ID = "failure_20260711T120000000000Z_a1b2c3d4e5f6"


def _write_failure(
    root: Path,
    *,
    failure_id: str = FAILURE_ID,
    stage: str = "quillan_route_review",
) -> Path:
    return write_routing_failure_metadata(
        root,
        RoutingFailureMetadata(
            schema_version="1",
            failure_id=failure_id,
            scope="page",
            stage=stage,
            created_at="2026-07-11T12:00:00+00:00",
            failure_category="payload_missing",
            failure_message="No QR payload was found.",
            source_filename="teacher_scan.pdf",
            module_details={"failure_origin": "qr_decode"},
            module="quillan",
            source_scan_id="scan_001",
            source_sha256="a" * 64,
            retained_source_path="scans/source/2026-07-11/teacher_scan.pdf",
            review_copy_path="scans/review/teacher_scan_page_2.pdf",
            source_page_number=2,
            detected_payload=None,
            payload_page_number=None,
            class_id="english12_p3",
            assignment_id="essay_01",
            student_id="stu_001",
        ),
    )


def test_discovery_lists_valid_quillan_items_and_skips_bad_or_other_records(
    tmp_path: Path,
) -> None:
    _write_failure(tmp_path)
    _write_failure(
        tmp_path,
        failure_id="failure_20260711T120001000000Z_b1b2c3d4e5f6",
        stage="scoreform_route_review",
    )
    malformed = tmp_path / "scans" / "review" / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")

    result = discover_scan_review_items(tmp_path)

    assert [item.failure_id for item in result.items] == [FAILURE_ID]
    assert result.items[0].display_status == "unresolved"
    assert result.items[0].retained_source_path == (
        "scans/source/2026-07-11/teacher_scan.pdf"
    )
    assert len(result.warnings) == 1


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_action"),
    [
        ("rescan_needed", "resolved", "rescan_needed"),
        ("cannot_route", "resolved", "cannot_route"),
        ("mixed_assignment", "resolved", "mixed_assignment"),
        ("evidence_filed", "resolved", "evidence_filed"),
        ("dismissed_duplicate", "resolved", "dismissed_duplicate"),
        ("other", "resolved", "other"),
        ("defer", "deferred", "other"),
    ],
)
def test_resolution_actions_write_shared_metadata(
    tmp_path: Path,
    action: str,
    expected_status: str,
    expected_action: str,
) -> None:
    _write_failure(tmp_path)
    message = "Teacher decision." if action == "other" else None
    evidence_path = "handled/teacher_scan.pdf" if action == "evidence_filed" else None

    result = resolve_scan_review_item(
        tmp_path,
        FAILURE_ID,
        action=action,
        message=message,
        evidence_path=evidence_path,
        resolved_at=datetime(2026, 7, 11, 13, 0, tzinfo=timezone.utc),
    )

    loaded = json.loads(result.resolution_metadata_path.read_text(encoding="utf-8"))
    metadata = scan_resolution_metadata_from_dict(loaded)
    assert metadata.failure_id == FAILURE_ID
    assert metadata.resolution_status == expected_status
    assert metadata.resolution_action == expected_action
    assert metadata.retained_source_path == "scans/source/2026-07-11/teacher_scan.pdf"
    assert (metadata.class_id, metadata.assignment_id, metadata.student_id) == (
        "english12_p3",
        "essay_01",
        "stu_001",
    )
    assert metadata.resolution_evidence_path == evidence_path


def test_resolved_is_hidden_and_deferred_remains_visible(tmp_path: Path) -> None:
    failure_path = _write_failure(tmp_path)
    before = failure_path.read_bytes()
    resolve_scan_review_item(tmp_path, FAILURE_ID, action="defer")

    deferred = discover_scan_review_items(tmp_path)
    assert deferred.items[0].display_status == "deferred"

    resolve_scan_review_item(tmp_path, FAILURE_ID, action="rescan_needed")

    assert discover_scan_review_items(tmp_path).items == ()
    included = discover_scan_review_items(tmp_path, include_resolved=True)
    assert included.items[0].display_status == "resolved"
    assert failure_path.read_bytes() == before


@pytest.mark.parametrize(
    ("action", "message", "evidence_path"),
    [
        ("unsupported", "Decision", None),
        ("other", None, None),
        ("rescan_needed", None, "outside.pdf"),
        ("evidence_filed", None, "../outside.pdf"),
        ("evidence_filed", None, "C:/outside.pdf"),
    ],
)
def test_resolution_rejects_invalid_inputs(
    tmp_path: Path,
    action: str,
    message: str | None,
    evidence_path: str | None,
) -> None:
    _write_failure(tmp_path)
    with pytest.raises(ScanReviewResolutionError):
        resolve_scan_review_item(
            tmp_path,
            FAILURE_ID,
            action=action,
            message=message,
            evidence_path=evidence_path,
        )


def test_resolution_rejects_missing_failure(tmp_path: Path) -> None:
    with pytest.raises(ScanReviewResolutionError, match="No valid Quillan"):
        resolve_scan_review_item(
            tmp_path,
            "failure_missing",
            action="cannot_route",
        )
