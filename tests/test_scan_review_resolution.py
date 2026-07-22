"""Focused tests for Quillan scan review discovery and resolution."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import (
    ModuleRecordRef,
    ModuleWorkRef,
    RouteLocator,
    RouteRegistration,
)
from pds_core.scan_failure_metadata import RoutingFailureMetadata, write_routing_failure_metadata
from pds_core.scan_resolution_metadata import (
    scan_resolution_metadata_from_dict,
)

from quillan.scan_review_resolution import (
    ScanReviewResolutionError,
    discover_scan_review_route_options,
    discover_scan_review_items,
    resolve_scan_review_item,
)
import quillan.scan_review_resolution as scan_review_resolution
from tests.test_route_handler import route_context

FAILURE_ID = "failure_20260711T120000000000Z_a1b2c3d4e5f6"


def test_route_option_discovery_propagates_unexpected_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "routes"
    directory.mkdir()
    (directory / "route_0123456789abcdef.json").write_text(
        "{}", encoding="utf-8"
    )
    monkeypatch.setattr(
        scan_review_resolution,
        "module_routes_dir",
        lambda *_args, **_kwargs: directory,
    )
    monkeypatch.setattr(
        scan_review_resolution,
        "validate_route_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("unexpected programming failure")
        ),
    )

    with pytest.raises(RuntimeError, match="unexpected programming failure"):
        discover_scan_review_route_options(
            tmp_path, "english12_p3", "essay_01"
        )


def _write_failure(
    root: Path,
    *,
    failure_id: str = FAILURE_ID,
    stage: str = "quillan_route_review",
    module_id: str = "quillan",
    scoped: bool = True,
) -> Path:
    return write_routing_failure_metadata(
        root,
        RoutingFailureMetadata(
            schema_version="2",
            failure_id=failure_id,
            scope="page",
            stage=stage if scoped else "qr_detection",
            created_at="2026-07-11T12:00:00+00:00",
            failure_category="payload_missing",
            failure_message="No QR payload was found.",
            source_filename="teacher_scan.pdf",
            route_locator=(
                RouteLocator(
                    "PDS2",
                    ModuleWorkRef(module_id, "english12_p3", "essay_01"),
                    "route_a1b2c3d4e5f6",
                )
                if scoped
                else None
            ),
            target=None,
            module_details=(
                {"failure_origin": "qr_decode"}
                if scoped
                else {
                    "failure_owner": "quillan",
                    "failure_origin": "qr_detection",
                }
            ),
            source_scan_id="scan_001",
            source_sha256="a" * 64,
            retained_source_path="scans/source/2026-07-11/teacher_scan.pdf",
            review_copy_path="scans/review/teacher_scan_page_2.pdf",
            source_page_number=2,
            detected_payload=None,
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
        module_id="scoreform",
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
        ("mixed_assignment", "resolved", "other"),
        ("evidence_filed", "resolved", "evidence_filed"),
        ("dismissed_duplicate", "resolved", "dismissed_duplicate"),
        ("other", "resolved", "other"),
        ("defer", "deferred", "deferred"),
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
    evidence_path = None
    if action == "evidence_filed":
        evidence = (
            tmp_path
            / "classes"
            / "english12_p3"
            / "modules"
            / "quillan"
            / "work"
            / "essay_01"
            / "handled"
            / "teacher_scan.pdf"
        )
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b"evidence")
        evidence_path = evidence.relative_to(tmp_path).as_posix()

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
    assert metadata.schema_version == "2"
    # Core-v2 no-final-route actions intentionally do not copy a failure route.
    assert metadata.route_locator is None
    assert metadata.target is None
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


def _write_routed_failure(
    root: Path,
) -> tuple[RouteLocator, ModuleRecordRef, RouteRegistration]:
    resolution, _ = route_context(root)
    write_route_registration(root, resolution.registration)
    registration = resolution.registration
    write_routing_failure_metadata(
        root,
        RoutingFailureMetadata(
            schema_version="2",
            failure_id=FAILURE_ID,
            scope="page",
            stage="dispatch",
            created_at="2026-07-11T12:00:00+00:00",
            failure_category="route_mismatch",
            failure_message="Teacher routing decision required.",
            source_filename="teacher_scan.pdf",
            source_scan_id="scan_001",
            source_sha256="a" * 64,
            retained_source_path="scans/source/2026-07-21/teacher_scan.pdf",
            review_copy_path=None,
            source_page_number=1,
            detected_payload="PDS2",
            route_locator=registration.locator,
            target=registration.target,
            module_details={"failure_owner": "quillan"},
        ),
    )
    return registration.locator, registration.target, registration


def test_route_selected_requires_explicit_registered_locator_and_target(
    tmp_path: Path,
) -> None:
    locator, target, _ = _write_routed_failure(tmp_path)
    with pytest.raises(ScanReviewResolutionError, match="requires an exact"):
        resolve_scan_review_item(tmp_path, FAILURE_ID, action="route_selected")

    result = resolve_scan_review_item(
        tmp_path,
        FAILURE_ID,
        action="route_selected",
        route_locator=locator,
        target=target,
    )
    assert result.resolution_action == "route_selected"


def test_route_corrected_requires_a_changed_registered_route(tmp_path: Path) -> None:
    locator, target, registration = _write_routed_failure(tmp_path)
    corrected_locator = RouteLocator(
        "PDS2",
        locator.work,
        "route_ffffffffffffffffffffffffffffffff",
    )
    corrected_registration = replace(
        registration,
        locator=corrected_locator,
        target=target,
    )
    write_route_registration(tmp_path, corrected_registration)

    result = resolve_scan_review_item(
        tmp_path,
        FAILURE_ID,
        action="route_corrected",
        route_locator=corrected_locator,
        target=target,
    )
    assert result.resolution_action == "route_corrected"


def test_strict_core_loader_skips_duplicate_keys_without_hiding_sibling(
    tmp_path: Path,
) -> None:
    valid = _write_failure(tmp_path)
    duplicate_path = valid.with_name(
        "failure_20260711T120002000000Z_c1b2c3d4e5f6.json"
    )
    text = valid.read_text(encoding="utf-8").replace(
        '"failure_id":',
        '"failure_id": "failure_20260711T120002000000Z_c1b2c3d4e5f6",\n  "failure_id":',
        1,
    )
    duplicate_path.write_text(text, encoding="utf-8")

    discovery = discover_scan_review_items(tmp_path)
    assert [item.failure_id for item in discovery.items] == [FAILURE_ID]
    assert any("invalid JSON" in warning for warning in discovery.warnings)
