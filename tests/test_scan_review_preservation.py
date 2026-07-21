from __future__ import annotations

from dataclasses import replace
import copy
from pathlib import Path

import cv2
import numpy as np
import pytest
from pds_core.module_dispatch import RouteDispatchRequest, RouteDispatchSuccess
from pds_core.module_profiles import ModuleProfile
from pds_core.pds2 import parse_pds2_payload
from pds_core.routing_models import ModuleRecordRef, RouteRegistration, RouteResolution
from pds_core.scan_failure_metadata import (
    ROUTING_FAILURE_SCHEMA_VERSION,
    RoutingFailureMetadata,
    RoutingFailureMetadataWriteError,
    load_routing_failure_metadata,
)
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan

from quillan.module_errors import (
    QuillanQrDetectionError,
    QuillanScanReviewPersistenceError,
)
from quillan.pds2_scan_intake import (
    QuillanFailurePersistenceError,
    QuillanScanIntakeSummary,
    QuillanScanPageOutcome,
    QuillanScanSourceResult,
)
from quillan.scan_intake_summary import format_scan_intake_summary
import quillan.scan_review_preservation as preservation
from quillan.scan_review_preservation import (
    preserve_and_attach_quillan_scan_failures,
    preserve_quillan_scan_failures,
)


def _retained(tmp_path: Path) -> tuple[Path, Path, RetainedSourceScan]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "scan.png"
    assert cv2.imwrite(str(source), np.full((10, 10, 3), 255, dtype=np.uint8))
    return workspace, source, retain_source_scan(workspace, source)


def _retained_pdf(tmp_path: Path) -> tuple[Path, Path, RetainedSourceScan]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic retained provenance")
    return workspace, source, retain_source_scan(workspace, source)


def _failed_page(retained: RetainedSourceScan, number: int) -> QuillanScanPageOutcome:
    return QuillanScanPageOutcome(
        number,
        "pre_dispatch_failure",
        retained,
        failure_stage="qr_detection",
        failure_category="payload_missing",
        error=QuillanQrDetectionError("no QR", failure_category="payload_missing"),
    )


def test_pre_retention_failure_writes_no_review_record(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    result = QuillanScanSourceResult(
        source, source.name, "image", None, (), ("quillan",), RuntimeError("preflight")
    )
    batch = preserve_quillan_scan_failures(tmp_path, result)
    assert batch.persisted == ()
    assert batch.failures == ()
    assert not (tmp_path / "scans" / "review").exists()


def test_public_persistence_rejects_nonexistent_workspace_without_creation(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    source = tmp_path / "scan.png"
    result = QuillanScanSourceResult(
        source, source.name, "image", None, (), ("quillan",), RuntimeError("preflight")
    )
    with pytest.raises(QuillanScanReviewPersistenceError):
        preserve_quillan_scan_failures(missing, result)
    assert not missing.exists()


def test_page_failure_is_written_with_exact_core_v2_schema_and_reloads(tmp_path: Path) -> None:
    workspace, source, retained = _retained(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "image", retained, (_failed_page(retained, 1),), ("quillan",)
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    record = attached.pages[0].review_record
    assert record is not None
    assert record.retained_source is retained
    assert record.metadata.schema_version == ROUTING_FAILURE_SCHEMA_VERSION == "2"
    assert record.metadata.source_page_number == 1
    assert record.metadata.retained_source_path == retained.retained_source_relative_path
    assert record.metadata_path == workspace / record.metadata_relative_path
    assert load_routing_failure_metadata(workspace, record.failure_id) == record.metadata
    assert not (workspace / "scans" / "review" / "resolutions").exists()


def test_partial_persistence_keeps_successful_page_attached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source, retained = _retained_pdf(tmp_path)
    result = QuillanScanSourceResult(
        source,
        source.name,
        "pdf",
        retained,
        (_failed_page(retained, 1), _failed_page(retained, 2)),
        ("quillan",),
    )
    real_write = preservation.write_routing_failure_metadata  # type: ignore[attr-defined]
    calls = 0

    def sometimes_fail(root: Path, metadata: object) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RoutingFailureMetadataWriteError("synthetic write failure")
        return real_write(root, metadata)  # type: ignore[arg-type]

    monkeypatch.setattr(preservation, "write_routing_failure_metadata", sometimes_fail)
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    assert attached.pages[0].review_record is not None
    assert attached.pages[0].review_error is None
    assert attached.pages[1].review_record is None
    assert isinstance(attached.pages[1].review_error, QuillanFailurePersistenceError)
    assert isinstance(
        attached.pages[1].review_error.error,
        QuillanScanReviewPersistenceError,
    )
    assert len(tuple((workspace / "scans" / "review").glob("*.json"))) == 1


def test_collision_exhaustion_returns_typed_occurrence_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source, retained = _retained(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "image", retained, (_failed_page(retained, 1),), ("quillan",)
    )
    monkeypatch.setattr(
        "quillan.scan_review_preservation.os.path.lexists",
        lambda _path: True,
    )
    batch = preserve_quillan_scan_failures(workspace, result)
    assert batch.persisted == ()
    assert len(batch.failures) == 1
    assert "unique routing failure ID" in str(batch.failures[0].error)


def test_retained_source_level_failure_gets_scan_scoped_record(tmp_path: Path) -> None:
    workspace, source, retained = _retained_pdf(tmp_path)
    result = QuillanScanSourceResult(
        source,
        source.name,
        "pdf",
        retained,
        (),
        ("quillan",),
        RuntimeError("page enumeration failed"),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    assert attached.scan_review_record is not None
    assert attached.scan_review_record.metadata.scope == "scan"
    assert attached.scan_review_record.source_page_number is None
    assert attached.scan_review_record.retained_source is retained
    text = format_scan_intake_summary(
        QuillanScanIntakeSummary((attached,), ("quillan",))
    )
    assert attached.scan_review_record.metadata_relative_path in text


@pytest.mark.parametrize("verification_failure", ["wrong_path", "reload_raises", "reload_differs"])
def test_possibly_durable_path_survives_public_attachments_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verification_failure: str,
) -> None:
    workspace, source, retained = _retained(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "image", retained,
        (_failed_page(retained, 1),), ("quillan",),
    )
    real_write = preservation.write_routing_failure_metadata  # type: ignore[attr-defined]
    real_load = preservation.load_routing_failure_metadata  # type: ignore[attr-defined]

    def write(root: Path, metadata: RoutingFailureMetadata) -> Path:
        written = real_write(root, metadata)
        if verification_failure == "wrong_path":
            return root / "wrong" / written.name
        return written

    def load(root: Path, failure_id: str) -> RoutingFailureMetadata:
        if verification_failure == "reload_raises":
            raise RuntimeError("synthetic reload failure")
        metadata = real_load(root, failure_id)
        if verification_failure == "reload_differs":
            return replace(metadata, failure_message="different after reload")
        return metadata

    monkeypatch.setattr(preservation, "write_routing_failure_metadata", write)
    monkeypatch.setattr(preservation, "load_routing_failure_metadata", load)
    batch = preserve_quillan_scan_failures(workspace, result)
    assert batch.persisted == ()
    assert len(batch.failures) == 1
    durable = batch.failures[0].durable_path
    assert durable is not None
    assert durable.is_file()

    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    occurrence = attached.pages[0].review_error
    assert occurrence is not None
    assert occurrence.durable_path is not None
    assert occurrence.durable_path.is_file()
    summary = QuillanScanIntakeSummary((attached,), ("quillan",))
    text = format_scan_intake_summary(summary)
    assert "Review persistence failed" in text
    assert "Possibly durable path:" in text
    assert str(occurrence.durable_path) in text


def test_partial_persistence_preserves_second_pages_possibly_durable_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source, retained = _retained_pdf(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "pdf", retained,
        (_failed_page(retained, 1), _failed_page(retained, 2)), ("quillan",),
    )
    real_write = preservation.write_routing_failure_metadata  # type: ignore[attr-defined]

    def wrong_after_second_write(
        root: Path, metadata: RoutingFailureMetadata
    ) -> Path:
        written = real_write(root, metadata)
        if metadata.source_page_number == 2:
            return root / "wrong" / written.name
        return written

    monkeypatch.setattr(
        preservation, "write_routing_failure_metadata", wrong_after_second_write
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    assert attached.pages[0].review_record is not None
    assert attached.pages[0].review_error is None
    assert attached.pages[1].review_record is None
    assert attached.pages[1].review_error is not None
    durable = attached.pages[1].review_error.durable_path
    assert durable is not None and durable.is_file()
    text = format_scan_intake_summary(
        QuillanScanIntakeSummary((attached,), ("quillan",))
    )
    assert str(durable) in text


def test_source_level_possibly_durable_path_survives_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source, retained = _retained_pdf(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "pdf", retained, (), ("quillan",),
        RuntimeError("page enumeration failed"),
    )
    monkeypatch.setattr(
        preservation,
        "load_routing_failure_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic source reload failure")
        ),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    occurrence = attached.scan_review_error
    assert occurrence is not None
    assert occurrence.source_page_number is None
    assert occurrence.durable_path is not None
    assert occurrence.durable_path.is_file()
    text = format_scan_intake_summary(
        QuillanScanIntakeSummary((attached,), ("quillan",))
    )
    assert "Source review persistence failed:" in text
    assert str(occurrence.durable_path) in text


def test_routing_review_record_rejects_adversarial_contract_changes(tmp_path: Path) -> None:
    workspace, source, retained = _retained(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "image", retained,
        (_failed_page(retained, 1),), ("quillan",),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    record = attached.pages[0].review_record
    assert record is not None
    def tampered(field_name: str, value: object) -> RoutingFailureMetadata:
        metadata = copy.copy(record.metadata)
        object.__setattr__(metadata, field_name, value)
        return metadata

    adversarial_metadata = (
        tampered("schema_version", "1"),
        tampered("source_filename", "other.png"),
        tampered("source_scan_id", "scan_other"),
        tampered("source_sha256", "b" * 64),
        tampered("retained_source_path", "scans/source/other.png"),
        tampered("source_page_number", 2),
    )
    for metadata in adversarial_metadata:
        with pytest.raises(ValueError):
            replace(record, metadata=metadata)
    with pytest.raises(ValueError):
        replace(record, metadata_path=workspace / "elsewhere" / f"{record.failure_id}.json")
    with pytest.raises(ValueError):
        replace(record, metadata_relative_path=f"elsewhere/{record.failure_id}.json")


def test_successful_page_rejects_review_attachments(tmp_path: Path) -> None:
    workspace, source, retained = _retained(tmp_path)
    failed = QuillanScanSourceResult(
        source, source.name, "image", retained,
        (_failed_page(retained, 1),), ("quillan",),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, failed)
    record = attached.pages[0].review_record
    assert record is not None
    locator = parse_pds2_payload(
        "PDS2|m=quillan|c=class_1|w=work_1|"
        "r=rt_0123456789abcdef0123456789abcdef"
    )
    request = RouteDispatchRequest(locator, retained, 1)
    profile = ModuleProfile(
        "quillan", "Quillan", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), lambda *_args: object(),
    )
    registration = RouteRegistration(
        "1", locator,
        ModuleRecordRef("quillan", "response_page", "synthetic", "1"),
        "2026-07-20T00:00:00+00:00", "active", "fallback", {},
    )
    outcome = RouteDispatchSuccess(
        request,
        profile,
        RouteResolution(locator, registration, workspace, workspace, workspace),
        object(),
    )
    success = QuillanScanPageOutcome(
        1, "dispatch_success", retained,
        raw_payload_text="PDS2 synthetic", locator=locator, decode_method="raw",
        dispatch_request=request, dispatch_outcome=outcome,
    )
    with pytest.raises(ValueError):
        replace(success, review_record=record)
    occurrence = QuillanFailurePersistenceError(
        1,
        "core_dispatch",
        QuillanScanReviewPersistenceError("synthetic persistence failure"),
    )
    with pytest.raises(ValueError):
        replace(success, review_error=occurrence)


def test_enumerated_source_rejects_scan_scoped_review_attachment(tmp_path: Path) -> None:
    workspace, source, retained = _retained_pdf(tmp_path)
    source_failure = QuillanScanSourceResult(
        source, source.name, "pdf", retained, (), ("quillan",),
        RuntimeError("enumeration failed"),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, source_failure)
    assert attached.scan_review_record is not None
    with pytest.raises(ValueError):
        QuillanScanSourceResult(
            source, source.name, "pdf", retained,
            (_failed_page(retained, 1),), ("quillan",),
            scan_review_record=attached.scan_review_record,
        )


def test_review_occurrence_origin_and_batch_keys_must_agree(tmp_path: Path) -> None:
    workspace, source, retained = _retained(tmp_path)
    result = QuillanScanSourceResult(
        source, source.name, "image", retained,
        (_failed_page(retained, 1),), ("quillan",),
    )
    attached = preserve_and_attach_quillan_scan_failures(workspace, result)
    record = attached.pages[0].review_record
    assert record is not None
    with pytest.raises(ValueError):
        replace(record, origin="wrong_origin")
    wrong_origin = QuillanFailurePersistenceError(
        1,
        "wrong_origin",
        QuillanScanReviewPersistenceError("synthetic persistence failure"),
    )
    with pytest.raises(ValueError):
        replace(attached.pages[0], review_record=None, review_error=wrong_origin)
    duplicate_failure = QuillanFailurePersistenceError(
        1,
        "qr_detection",
        QuillanScanReviewPersistenceError("synthetic persistence failure"),
    )
    with pytest.raises(ValueError):
        preservation.QuillanFailurePersistenceBatch(
            (), (duplicate_failure, duplicate_failure)
        )
