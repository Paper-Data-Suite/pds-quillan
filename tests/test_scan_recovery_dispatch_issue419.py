"""Issue #419 Slice 2: exact read-only Core dispatch for retained recovery."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from pds_core.module_dispatch import (
    RouteDispatchRequest,
    RouteDispatchSuccess,
    dispatch_route,
)
from pds_core.module_profiles import ModuleRegistry
from pds_core.routes import route_registration_path

import quillan.pds2_scan_intake as intake
import quillan.scan_recovery_dispatch as recovery_dispatch
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from quillan.pds_module import get_module_profile
from quillan.scan_recovery_dispatch import (
    ScanRecoveryDispatchError,
    dispatch_prepared_scan_recovery,
)
from quillan.scan_recovery_preflight import prepare_scan_review_recovery
from quillan.scan_review_resolution import resolve_scan_review_item
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _registry() -> ModuleRegistry:
    """Install the real Quillan Core profile without global entry-point discovery."""
    return ModuleRegistry((get_module_profile(),))


def test_exact_core_dispatch_does_not_decode_qr_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    before = _files(root)

    def no_qr(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("QR decoding must not run for manual recovery")

    monkeypatch.setattr(intake, "detect_qr_payload", no_qr)
    result = dispatch_prepared_scan_recovery(root, prepared, registry=_registry())

    assert result.prepared == prepared
    assert type(result.request) is RouteDispatchRequest
    assert type(result.success) is RouteDispatchSuccess
    assert result.request.locator == locator
    assert result.request.retained_source == retained
    assert result.request.source_page_number == 1
    assert result.success.request == result.request
    assert result.page_result.page_id == target.record_id
    assert result.page_result.student_id == "00107"
    assert result.page_result.source_scan_id == retained.source_scan_id
    assert _files(root) == before


def test_historical_route_reuse_dispatches_without_new_resolution(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    historical = resolve_scan_review_item(
        root,
        FAILURE_ID,
        action="route_selected",
        route_locator=locator,
        target=target,
    )
    prepared = prepare_scan_review_recovery(root, FAILURE_ID, use_recorded_route=True)
    before = _files(root)

    result = dispatch_prepared_scan_recovery(root, prepared, registry=_registry())

    assert result.prepared.route_origin == "recorded"
    assert result.prepared.historical_resolution_id == historical.resolution_id
    assert result.page_result.route_id == locator.route_id
    assert _files(root) == before


def test_stale_prepared_source_is_rejected_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    retained.retained_source_path.write_bytes(b"tampered after preview")

    def do_not_dispatch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Core should not dispatch stale retained bytes")

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", do_not_dispatch)
    with pytest.raises(ScanRecoveryDispatchError, match="preflight no longer passes"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_removed_registered_route_is_rejected_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    route_registration_path(root, locator).unlink()

    def do_not_dispatch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Core should not run when the registration disappears")

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", do_not_dispatch)
    with pytest.raises(ScanRecoveryDispatchError, match="preflight no longer passes"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_foreign_only_registry_fails_without_routing(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    with pytest.raises(ScanRecoveryDispatchError, match="dispatch registry"):
        dispatch_prepared_scan_recovery(root, prepared, registry=ModuleRegistry())


def test_core_rejects_incompatible_route_status(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    incompatible_profile = replace(
        get_module_profile(), dispatchable_route_statuses=frozenset({"inactive"})
    )
    before = _files(root)
    with pytest.raises(ScanRecoveryDispatchError, match="Core rejected"):
        dispatch_prepared_scan_recovery(
            root, prepared, registry=ModuleRegistry((incompatible_profile,))
        )
    assert _files(root) == before


def test_tampered_dispatch_page_identity_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    original = dispatch_route

    def wrong_student(
        workspace_root: str | Path, registry: ModuleRegistry, request: RouteDispatchRequest
    ) -> RouteDispatchSuccess:
        success = original(workspace_root, registry, request)
        return replace(
            success,
            module_result=replace(
                cast(QuillanResponsePageDispatchResult, success.module_result),
                student_id="other_student",
            ),
        )

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", wrong_student)
    with pytest.raises(ScanRecoveryDispatchError, match="immutable page authority"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_tampered_dispatch_request_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    original = dispatch_route

    def wrong_request(
        workspace_root: str | Path, registry: ModuleRegistry, request: RouteDispatchRequest
    ) -> RouteDispatchSuccess:
        success = original(workspace_root, registry, request)
        different = RouteDispatchRequest(
            locator=success.request.locator,
            retained_source=success.request.retained_source,
            source_page_number=2,
        )
        return replace(success, request=different)

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", wrong_request)
    with pytest.raises(ScanRecoveryDispatchError, match="request or resolved route"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_tampered_dispatch_result_type_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    original = dispatch_route

    def wrong_type(
        workspace_root: str | Path, registry: ModuleRegistry, request: RouteDispatchRequest
    ) -> RouteDispatchSuccess:
        return replace(
            original(workspace_root, registry, request), module_result=object()
        )

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", wrong_type)
    with pytest.raises(ScanRecoveryDispatchError, match="exact Quillan response-page"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_detects_retained_source_change_during_core_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    original = dispatch_route

    def change_source(
        workspace_root: str | Path, registry: ModuleRegistry, request: RouteDispatchRequest
    ) -> RouteDispatchSuccess:
        success = original(workspace_root, registry, request)
        retained.retained_source_path.write_bytes(b"changed while Core dispatched")
        return success

    monkeypatch.setattr(recovery_dispatch, "dispatch_route", change_source)
    with pytest.raises(ScanRecoveryDispatchError, match="changed during Core dispatch"):
        dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_requires_exact_prepared_preview(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)
    with pytest.raises(ScanRecoveryDispatchError, match="exact prepared"):
        dispatch_prepared_scan_recovery(
            root, object(), registry=_registry()  # type: ignore[arg-type]
        )


def test_pdf_recovery_dispatches_only_the_requested_physical_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(
        tmp_path, extension=".pdf", physical_page=2
    )
    import quillan.scan_recovery_preflight as preflight

    # Slice 2 dispatch consumes original page identity; it does not render
    # PDF pages or run QR detection. Page-count integration was Slice 1.
    monkeypatch.setattr(
        preflight, "retained_source_page_count", lambda *_a, **_k: 3
    )
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    before = _files(root)
    result = dispatch_prepared_scan_recovery(root, prepared, registry=_registry())
    assert result.request.retained_source.source_scan_id == retained.source_scan_id
    assert result.request.source_page_number == 2
    assert result.page_result.source_page_number == 2
    assert _files(root) == before
