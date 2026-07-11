"""Tests for Quillan routing failure preservation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest
from pds_core.scan_failure_metadata import (
    ROUTING_FAILURE_CATEGORIES,
    validate_routing_failure_metadata,
)

from quillan.evidence_filing import (
    EvidenceFilingError,
    RetainedSourceScan,
)
from quillan.payload_validation import (
    ResponsePayloadValidationFailure,
    decoded_payload_to_response_page,
)
from quillan.qr_decode import QrImageDecodeResult
from quillan.route_planning import (
    DecodedResponsePage,
    RouteFailure,
    RoutePlan,
    plan_decoded_response_page_route,
)
from quillan.routing_review import (
    RoutingReviewError,
    preserve_decode_failure_for_review,
    preserve_evidence_filing_error_for_review,
    preserve_payload_validation_failure_for_review,
    preserve_route_failure_for_review,
    preserve_routing_failure_for_review,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
CREATED_AT = datetime(2026, 6, 19, 23, 59, 1, 123456, tzinfo=timezone.utc)
SOURCE_SHA256 = "a" * 64
RAW_PAYLOAD = (
    "PDS1|module=quillan|class=english12_p3_synthetic|"
    "aid=essay_01_synthetic|sid=00107|page=2|doc=response"
)


def _read_metadata(path: Path) -> dict[str, object]:
    metadata = cast(
        dict[str, object],
        json.loads(path.read_text(encoding="utf-8")),
    )
    validate_routing_failure_metadata(metadata)
    return metadata


def _route_failure(workspace: Path) -> RouteFailure:
    result = plan_decoded_response_page_route(
        workspace,
        DecodedResponsePage(
            module="quillan",
            document_type="response",
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id=STUDENT_ID,
            page_number=2,
            raw_payload=RAW_PAYLOAD,
        ),
    )
    assert isinstance(result, RouteFailure)
    return result


def _route_plan(workspace: Path) -> RoutePlan:
    assignment_dir = (
        workspace / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID
    )
    return RoutePlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        page_number=2,
        assignment_config_path=assignment_dir / "assignment.json",
        roster_path=workspace / "classes" / CLASS_ID / "roster.csv",
        routed_evidence_dir=assignment_dir / "scans",
        student_submission_dir=assignment_dir / "submissions" / STUDENT_ID,
    )


def test_writes_shared_metadata_only_under_scans_review(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Teacher Scan.pdf"
    source.write_bytes(b"original source remains untouched")
    original_bytes = source.read_bytes()

    record = preserve_routing_failure_for_review(
        tmp_path,
        failure_category="payload_invalid",
        failure_message="Decoded payload is invalid.",
        source_filename=source.name,
        detected_payload="not-a-valid-payload",
        module_details={"reason": "syntax"},
        created_at=CREATED_AT,
    )

    assert record.failure_metadata_path.parent == (
        tmp_path / "scans" / "review"
    ).resolve()
    assert record.failure_metadata_relative_path == (
        f"scans/review/{record.failure_id}.json"
    )
    assert re.fullmatch(
        r"failure_20260619T235901123456Z_[0-9a-f]{12}",
        record.failure_id,
    )
    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["schema_version"] == "1"
    assert metadata["scope"] == "page"
    assert metadata["stage"] == "quillan_route_review"
    assert metadata["failure_id"] == record.failure_id
    assert metadata["module_details"] == {"reason": "syntax"}
    assert record.failure_metadata_path.read_bytes().endswith(b"\n")
    assert source.read_bytes() == original_bytes
    assert not (tmp_path / "scans" / "source").exists()
    assert not (tmp_path / "classes").exists()
    assert not list(tmp_path.rglob("submission.json"))


def test_review_directory_is_created_only_when_failure_is_preserved(
    tmp_path: Path,
) -> None:
    assert not (tmp_path / "scans").exists()

    with pytest.raises(RoutingReviewError, match="source_filename"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="payload_invalid",
            failure_message="Invalid.",
            source_filename="../unsafe.pdf",
            created_at=CREATED_AT,
        )

    assert not (tmp_path / "scans").exists()


def test_shared_writer_refuses_failure_id_collision(tmp_path: Path) -> None:
    preserve_routing_failure_for_review(
        tmp_path,
        failure_category="payload_invalid",
        failure_message="Invalid.",
        source_filename="scan.pdf",
        created_at=CREATED_AT,
    )

    with pytest.raises(RoutingReviewError, match="already exists"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="payload_invalid",
            failure_message="Invalid.",
            source_filename="scan.pdf",
            created_at=CREATED_AT,
        )


def test_failure_metadata_filenames_are_unique_for_distinct_failures(
    tmp_path: Path,
) -> None:
    first = preserve_routing_failure_for_review(
        tmp_path,
        failure_category="payload_invalid",
        failure_message="Invalid.",
        source_filename="scan.pdf",
        detected_payload="first",
        created_at=CREATED_AT,
    )
    second = preserve_routing_failure_for_review(
        tmp_path,
        failure_category="payload_invalid",
        failure_message="Invalid.",
        source_filename="scan.pdf",
        detected_payload="second",
        created_at=CREATED_AT,
    )

    assert first.failure_metadata_path != second.failure_metadata_path
    records = sorted((tmp_path / "scans" / "review").glob("*.json"))
    assert records == sorted(
        [first.failure_metadata_path, second.failure_metadata_path]
    )
    for record in records:
        validate_routing_failure_metadata(
            json.loads(record.read_text(encoding="utf-8"))
        )


def test_preserves_route_failure_fields_without_replanning(
    tmp_path: Path,
) -> None:
    failure = _route_failure(tmp_path)

    record = preserve_route_failure_for_review(
        tmp_path,
        route_failure=failure,
        source_filename="batch.pdf",
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["failure_category"] == "class_unknown"
    assert metadata["failure_message"] == failure.failure_message
    assert metadata["module"] == "quillan"
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["detected_payload"] == RAW_PAYLOAD
    assert metadata["payload_page_number"] == 2
    expected_details: dict[str, object] = {
        "failure_origin": "route_planning",
    }
    expected_details.update(failure.module_details)
    assert metadata["module_details"] == expected_details


def test_decode_failure_adapter_preserves_null_identity(
    tmp_path: Path,
) -> None:
    record = preserve_decode_failure_for_review(
        tmp_path,
        decode_result=QrImageDecodeResult(
            payload_text=None,
            failure_category="payload_missing",
            failure_message="No QR payload could be decoded.",
        ),
        source_filename="blank.png",
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["failure_category"] == "payload_missing"
    assert metadata["failure_message"] == "No QR payload could be decoded."
    assert metadata["source_filename"] == "blank.png"
    assert metadata["module"] is None
    assert metadata["detected_payload"] is None
    assert metadata["payload_page_number"] is None
    assert metadata["class_id"] is None
    assert metadata["assignment_id"] is None
    assert metadata["student_id"] is None
    assert metadata["module_details"] == {
        "failure_origin": "qr_decode",
        "decode_attempt": None,
    }


def test_payload_validation_failure_adapter_preserves_parsed_identity(
    tmp_path: Path,
) -> None:
    payload = RAW_PAYLOAD.replace("doc=response", "doc=cover")
    failure = decoded_payload_to_response_page(payload)
    assert isinstance(failure, ResponsePayloadValidationFailure)

    record = preserve_payload_validation_failure_for_review(
        tmp_path,
        failure=failure,
        source_filename="wrong-doc.png",
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["failure_category"] == "payload_invalid"
    assert metadata["module"] == "quillan"
    assert metadata["detected_payload"] == payload
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 2
    assert metadata["module_details"] == {
        "failure_origin": "payload_validation",
        "reason": "document_type_invalid",
        "field": "doc",
        "expected_document_type": "response",
        "actual_document_type": "cover",
    }


def test_route_failure_adapter_accepts_retained_source_provenance(
    tmp_path: Path,
) -> None:
    retained_path = (
        tmp_path / "scans" / "source" / "2026-06-19" / "retained.pdf"
    )
    retained_path.parent.mkdir(parents=True)
    retained_path.write_bytes(b"retained")
    retained = RetainedSourceScan(
        source_scan_id="scan_20260619",
        source_filename="batch.pdf",
        source_sha256=SOURCE_SHA256,
        retained_source_path=retained_path.resolve(),
        retained_source_relative_path=(
            "scans/source/2026-06-19/retained.pdf"
        ),
        intake_timestamp=CREATED_AT,
        intake_date=CREATED_AT.date(),
    )

    record = preserve_route_failure_for_review(
        tmp_path,
        route_failure=_route_failure(tmp_path),
        source_filename="batch.pdf",
        retained_source=retained,
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["source_scan_id"] == "scan_20260619"
    assert metadata["source_sha256"] == SOURCE_SHA256
    assert metadata["retained_source_path"] == (
        "scans/source/2026-06-19/retained.pdf"
    )
    assert record.retained_source_relative_path == (
        "scans/source/2026-06-19/retained.pdf"
    )


def test_pre_retention_failure_allows_absent_provenance(
    tmp_path: Path,
) -> None:
    record = preserve_routing_failure_for_review(
        tmp_path,
        failure_category="source_retention_failed",
        failure_message="Source could not be retained.",
        source_filename="batch.pdf",
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["source_scan_id"] is None
    assert metadata["source_sha256"] is None
    assert metadata["retained_source_path"] is None
    assert record.retained_source_relative_path is None


@pytest.mark.parametrize("field_name", ["retained_source_path", "review_copy_path"])
def test_rejects_provenance_paths_outside_workspace(
    tmp_path: Path,
    field_name: str,
) -> None:
    outside = tmp_path.parent / "outside.pdf"
    retained_source_path = (
        outside if field_name == "retained_source_path" else None
    )
    review_copy_path = outside if field_name == "review_copy_path" else None

    with pytest.raises(RoutingReviewError, match="inside the workspace"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="processing_error",
            failure_message="Failed.",
            source_filename="batch.pdf",
            created_at=CREATED_AT,
            retained_source_path=retained_source_path,
            review_copy_path=review_copy_path,
        )

    assert not (tmp_path / "scans").exists()


def test_normalizes_workspace_relative_paths_to_posix(tmp_path: Path) -> None:
    record = preserve_routing_failure_for_review(
        tmp_path,
        failure_category="processing_error",
        failure_message="Failed.",
        source_filename="batch.pdf",
        retained_source_path=Path("scans") / "source" / "retained.pdf",
        review_copy_path=Path("scans") / "review" / "problem.pdf",
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["retained_source_path"] == "scans/source/retained.pdf"
    assert metadata["review_copy_path"] == "scans/review/problem.pdf"
    assert record.review_copy_relative_path == "scans/review/problem.pdf"
    assert not (tmp_path / "scans" / "review" / "problem.pdf").exists()


@pytest.mark.parametrize(
    "category",
    [
        "payload_invalid",
        "module_unsupported",
        "identifier_invalid",
        "class_unknown",
        "assignment_unknown",
        "student_unknown",
        "route_mismatch",
        "processing_error",
        "evidence_write_failed",
    ],
)
def test_accepts_required_shared_failure_categories(
    tmp_path: Path,
    category: str,
) -> None:
    assert category in ROUTING_FAILURE_CATEGORIES
    record = preserve_routing_failure_for_review(
        tmp_path,
        failure_category=category,
        failure_message=f"Synthetic {category} failure.",
        source_filename=f"{category}.pdf",
        created_at=CREATED_AT,
    )
    assert record.failure_category == category


def test_rejects_custom_failure_category_before_writes(
    tmp_path: Path,
) -> None:
    with pytest.raises(RoutingReviewError, match="shared"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="quillan_custom_failure",
            failure_message="Custom.",
            source_filename="batch.pdf",
            created_at=CREATED_AT,
        )

    assert not (tmp_path / "scans").exists()


def test_evidence_filing_error_adapter_preserves_route_context(
    tmp_path: Path,
) -> None:
    plan = _route_plan(tmp_path)
    record = preserve_evidence_filing_error_for_review(
        tmp_path,
        error=EvidenceFilingError("Disk write failed."),
        route_plan=plan,
        source_filename="batch.pdf",
        module_details={"operation": "copy_routed_evidence"},
        created_at=CREATED_AT,
    )

    metadata = _read_metadata(record.failure_metadata_path)
    assert metadata["failure_category"] == "evidence_write_failed"
    assert metadata["failure_message"] == "Disk write failed."
    assert metadata["module"] == "quillan"
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 2
    assert metadata["module_details"] == {
        "failure_origin": "evidence_filing",
        "operation": "copy_routed_evidence",
    }
    assert not plan.routed_evidence_dir.exists()
    assert not plan.student_submission_dir.exists()
    assert not (tmp_path / "scans" / "source").exists()


def test_invalid_metadata_does_not_leave_partial_json(tmp_path: Path) -> None:
    with pytest.raises(RoutingReviewError, match="source_sha256"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="processing_error",
            failure_message="Failed.",
            source_filename="batch.pdf",
            source_sha256="not-a-sha256",
            created_at=CREATED_AT,
        )

    assert not list(tmp_path.rglob("*.json"))


def test_naive_timestamp_is_rejected_before_writes(tmp_path: Path) -> None:
    with pytest.raises(RoutingReviewError, match="timezone-aware"):
        preserve_routing_failure_for_review(
            tmp_path,
            failure_category="processing_error",
            failure_message="Failed.",
            source_filename="batch.pdf",
            created_at=CREATED_AT.replace(tzinfo=None),
        )

    assert not (tmp_path / "scans").exists()
