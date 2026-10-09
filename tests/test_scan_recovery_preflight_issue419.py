"""Issue #419 Slice 1: read-only retained-page recovery preflight."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef, RouteLocator
from pds_core.scan_failure_metadata import (
    RoutingFailureMetadata,
    write_routing_failure_metadata,
)
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan

import quillan.scan_recovery_preflight as recovery
from quillan.scan_recovery_preflight import (
    ScanRecoveryPreflightError,
    prepare_scan_review_recovery,
)
from quillan.scan_review_resolution import resolve_scan_review_item
from tests.test_route_handler import route_context

FAILURE_ID = "failure_20260711T120000000000Z_a1b2c3d4e5f6"


def _fixture(
    tmp_path: Path,
    *,
    extension: str = ".png",
    physical_page: int = 1,
    scoped: bool = False,
    issuance_status: str = "issued",
) -> tuple[Path, RetainedSourceScan, RouteLocator, ModuleRecordRef]:
    root = tmp_path / "workspace"
    root.mkdir()
    resolution, _ = route_context(root, status=issuance_status)
    write_route_registration(root, resolution.registration)
    source = tmp_path / f"actual_scan{extension}"
    if extension == ".png":
        Image.new("RGB", (30, 20), "white").save(source)
    else:
        source.write_bytes(b"%PDF-1.4 synthetic test PDF")
    retained = retain_source_scan(root, source)
    write_routing_failure_metadata(
        root,
        RoutingFailureMetadata(
            schema_version="2",
            failure_id=FAILURE_ID,
            scope="page",
            stage="dispatch" if scoped else "qr_detection",
            created_at="2026-07-11T12:00:00+00:00",
            failure_category="route_mismatch" if scoped else "payload_missing",
            failure_message="Scan could not be routed.",
            source_filename=retained.source_filename,
            source_scan_id=retained.source_scan_id,
            source_sha256=retained.source_sha256,
            retained_source_path=retained.retained_source_relative_path,
            review_copy_path=None,
            source_page_number=physical_page,
            detected_payload=None,
            route_locator=resolution.locator if scoped else None,
            target=resolution.registration.target if scoped else None,
            module_details={
                "failure_owner": "quillan",
                "failure_origin": "core_dispatch" if scoped else "qr_detection",
            },
        ),
    )
    return root, retained, resolution.locator, resolution.registration.target


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_unreadable_qr_can_prepare_exact_route_without_writing(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    before = _files(root)

    result = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )

    assert result.failure_id == FAILURE_ID
    assert result.route_origin == "explicit"
    assert result.historical_resolution_id is None
    assert result.source_page_number == result.source_page_count == 1
    assert result.retained_source == retained
    assert result.student_id == "00107"
    assert result.logical_page == 1
    assert result.page_id == target.record_id
    assert result.route_locator == locator
    assert _files(root) == before


def test_historical_route_decision_is_preparable_without_writes(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    old = resolve_scan_review_item(
        root,
        FAILURE_ID,
        action="route_selected",
        route_locator=locator,
        target=target,
    )
    before = _files(root)

    result = prepare_scan_review_recovery(root, FAILURE_ID, use_recorded_route=True)

    assert result.route_origin == "recorded"
    assert result.historical_resolution_id == old.resolution_id
    assert result.route_locator == locator
    assert result.retained_source.source_scan_id == retained.source_scan_id
    assert _files(root) == before


def test_recorded_route_requires_latest_route_decision(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)
    with pytest.raises(ScanRecoveryPreflightError, match="not a reusable route"):
        prepare_scan_review_recovery(root, FAILURE_ID, use_recorded_route=True)


def test_route_inputs_are_explicit_and_mutually_exclusive(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    with pytest.raises(ScanRecoveryPreflightError, match="must be supplied together"):
        prepare_scan_review_recovery(root, FAILURE_ID, route_locator=locator)
    with pytest.raises(ScanRecoveryPreflightError, match="cannot be combined"):
        prepare_scan_review_recovery(
            root,
            FAILURE_ID,
            route_locator=locator,
            target=target,
            use_recorded_route=True,
        )


def test_retained_bytes_must_match_original_hash(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    retained.retained_source_path.write_bytes(b"corrupted")
    before = _files(root)
    with pytest.raises(ScanRecoveryPreflightError, match="SHA-256"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )
    assert _files(root) == before


def test_missing_retained_source_is_not_recreated(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    retained.retained_source_path.unlink()
    before = _files(root)
    with pytest.raises(ScanRecoveryPreflightError, match="retained source"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )
    assert _files(root) == before


def test_image_has_only_physical_page_one(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path, physical_page=2)
    with pytest.raises(ScanRecoveryPreflightError, match="source and page"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )


def test_pdf_page_count_is_checked_without_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(
        tmp_path, extension=".pdf", physical_page=3
    )
    monkeypatch.setattr(recovery, "retained_source_page_count", lambda *_a, **_k: 2)
    with pytest.raises(ScanRecoveryPreflightError, match="exceeds retained"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )


def test_unissued_page_cannot_be_recovered(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path, issuance_status="prepared")
    with pytest.raises(ScanRecoveryPreflightError, match="not currently issued"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )


def test_wrong_target_rejected(tmp_path: Path) -> None:
    root, _, locator, _ = _fixture(tmp_path)
    wrong = ModuleRecordRef("quillan", "response_page", "page_wrong", "1")
    with pytest.raises(ScanRecoveryPreflightError, match="exact registration"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=wrong
        )


def test_scoped_failure_cannot_cross_assignment(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path, scoped=True)
    wrong = RouteLocator(
        "PDS2", ModuleWorkRef("quillan", locator.class_id, "other_work"),
        locator.route_id,
    )
    with pytest.raises(ScanRecoveryPreflightError, match="crosses"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=wrong, target=target
        )


def test_recovery_preflight_rejects_symlinked_retained_page(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(retained.retained_source_path.read_bytes())
    retained.retained_source_path.unlink()
    try:
        retained.retained_source_path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Creating a symlink requires additional OS privileges")
    with pytest.raises(ScanRecoveryPreflightError, match="source and page"):
        prepare_scan_review_recovery(
            root, FAILURE_ID, route_locator=locator, target=target
        )


def test_non_quillan_failure_is_not_recoverable(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    # A missing/incorrect failure ID must fail rather than silently choosing
    # another retained page or falling back to a route guess.
    with pytest.raises(ScanRecoveryPreflightError, match="No unique valid"):
        prepare_scan_review_recovery(
            root, "failure_other", route_locator=locator, target=target
        )
