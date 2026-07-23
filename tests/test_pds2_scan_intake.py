from __future__ import annotations

from pathlib import Path
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import cast

import pytest
import cv2
import numpy as np
from pds_core.module_dispatch import (
    ModuleRouteHandlingError,
    RouteDispatchFailure,
    RouteDispatchRequest,
    RouteDispatchSuccess,
)
from pds_core.module_profiles import ModuleProfile, ModuleRegistry
from pds_core.pds2 import Pds2PayloadError, parse_pds2_payload
from pds_core.routing_models import ModuleRecordRef, RouteRegistration, RouteResolution
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan as core_retain_source_scan
from pypdf import PdfWriter

import quillan.pds2_scan_intake as intake
from quillan.module_errors import QuillanScanPreflightError, QuillanScanRegistryError
from quillan.qr_decode import QrPayloadDetectionResult
from quillan.printable_response_records import page_role_for_logical_page
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)


def _handler(*_args: object) -> object:
    return object()


def registry() -> ModuleRegistry:
    return ModuleRegistry((ModuleProfile(
        module_id="quillan", display_name="Quillan",
        supported_core_routing_contract_versions=frozenset({"1"}),
        supported_qr_schemas=frozenset({"PDS2"}),
        supported_route_registration_schema_versions=frozenset({"1"}),
        dispatchable_route_statuses=frozenset({"active"}), route_handler=_handler,
    ),))


def _valid_quillan_result(
    request: RouteDispatchRequest,
) -> QuillanResponsePageDispatchResult:
    retained = request.retained_source
    result = QuillanResponsePageDispatchResult(
        route_id=request.locator.route_id,
        page_id="pg_11111111111111111111111111111111",
        issuance_id="iss_22222222222222222222222222222222",
        generation_id="gen_33333333333333333333333333333333",
        artifact_id="art_44444444444444444444444444444444",
        class_id=request.locator.class_id,
        assignment_id=request.locator.work_id,
        student_id="student_1",
        logical_page=1,
        total_pages=1,
        page_role=page_role_for_logical_page(1),
        source_scan_id=retained.source_scan_id,
        source_filename=retained.source_filename,
        source_page_number=request.source_page_number,
        retained_source_path=retained.retained_source_path,
        retained_source_relative_path=retained.retained_source_relative_path,
        source_sha256=retained.source_sha256,
        intake_timestamp=retained.intake_timestamp,
        intake_date=retained.intake_date,
    )
    return validate_quillan_response_page_dispatch_result(result)


def test_supported_extensions_are_exact() -> None:
    assert intake.SUPPORTED_SCAN_EXTENSIONS == frozenset({".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"})


@pytest.mark.parametrize("name", ["scan.bmp", "scan.gif", "scan.webp", "scan"])
def test_source_preflight_rejects_unsupported_types(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(b"x")
    with pytest.raises(QuillanScanPreflightError):
        intake.validate_scan_source(source)


def test_folder_reuses_one_injected_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "input"
    folder.mkdir()
    for name in ("b.jpg", "A.png"):
        (folder / name).write_bytes(b"scan")
    supplied = registry()
    seen: list[ModuleRegistry] = []
    def fake_process(path: str | Path, *, workspace_root: Path, registry: ModuleRegistry | None = None) -> intake.QuillanScanSourceResult:
        assert registry is not None
        seen.append(registry)
        source = Path(path)
        return intake.QuillanScanSourceResult(source, source.name, "image", None, (), registry.module_ids(), RuntimeError("synthetic"))
    monkeypatch.setattr(intake, "process_quillan_scan_source", fake_process)
    summary = intake.process_quillan_scan_folder(folder, workspace_root=tmp_path, registry=supplied)
    assert [x.source_filename for x in summary.source_results] == ["A.png", "b.jpg"]
    assert seen == [supplied, supplied]


@pytest.mark.parametrize("second_boundary", ["disappeared", "link_like", "unreadable"])
def test_folder_contains_second_preflight_race_and_preserves_registry_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second_boundary: str,
) -> None:
    folder = tmp_path / "input"
    folder.mkdir()
    first = folder / "a.png"
    second = folder / "b.png"
    image = np.full((8, 8, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(first), image)
    assert cv2.imwrite(str(second), image)
    supplied = registry()
    expected_ids = supplied.module_ids()
    real_validate = intake.validate_scan_source
    retained_calls: list[Path] = []

    def raced_validate(path: str | Path) -> Path:
        selected = Path(path)
        if selected.name == first.name:
            if second_boundary == "disappeared":
                first.unlink(missing_ok=True)
            raise QuillanScanPreflightError(
                f"synthetic second-boundary {second_boundary} failure"
            )
        return real_validate(path)

    def retain(root: Path, selected: Path) -> RetainedSourceScan:
        retained_calls.append(selected)
        return core_retain_source_scan(root, selected)

    def successful_dispatch(
        root: Path,
        retained: RetainedSourceScan,
        *,
        registry: ModuleRegistry,
        source_path: Path | None = None,
    ) -> intake.QuillanScanSourceResult:
        assert source_path is not None
        locator = parse_pds2_payload(
            "PDS2|m=quillan|c=class_1|w=work_1|"
            "r=rt_0123456789abcdef0123456789abcdef"
        )
        request = RouteDispatchRequest(locator, retained, 1)
        registration = RouteRegistration(
            "1",
            locator,
            ModuleRecordRef("quillan", "response_page", "synthetic", "1"),
            "2026-07-20T00:00:00+00:00",
            "active",
            "synthetic fallback",
            {},
        )
        outcome = RouteDispatchSuccess(
            request,
            registry.require("quillan"),
            RouteResolution(locator, registration, root, root, root),
            object(),
        )
        page = intake.QuillanScanPageOutcome(
            1,
            "dispatch_success",
            retained,
            raw_payload_text="PDS2 synthetic",
            locator=locator,
            decode_method="synthetic",
            dispatch_request=request,
            dispatch_outcome=outcome,
        )
        return intake.QuillanScanSourceResult(
            source_path,
            source_path.name,
            "image",
            retained,
            (page,),
            registry.module_ids(),
        )

    monkeypatch.setattr(intake, "validate_scan_source", raced_validate)
    monkeypatch.setattr(intake, "retain_source_scan", retain)
    monkeypatch.setattr(intake, "dispatch_retained_quillan_scan", successful_dispatch)
    monkeypatch.setattr(
        "quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures",
        lambda _root, result: result,
    )
    summary = intake.process_quillan_scan_folder(
        folder, workspace_root=tmp_path, registry=supplied
    )
    assert len(summary.source_results) == 2
    assert summary.source_results[0].retained_source is None
    assert summary.source_results[0].source_error is not None
    assert summary.source_results[0].registry_module_ids == expected_ids
    assert summary.source_results[1].complete_success
    assert summary.source_results[1].registry_module_ids == expected_ids
    assert retained_calls == [second]


def test_pds1_classification_never_recovers_partial_locator() -> None:
    error = Pds2PayloadError("unsupported")
    assert intake.classify_pds2_payload_error("PDS1|class=x|student=y", error) == "payload_schema_unsupported"


@pytest.mark.parametrize(
    "raw",
    (
        "PDS1|",
        "PDS1|student=001",
        "PDS1|assignment=essay|student=001|page=1",
        "PDS1|duplicate=one|duplicate=two",
        "PDS1|student=%2E%2E%2Fescape",
        "PDS1|student=private_student|assignment=private_assignment",
    ),
)
def test_pds1_like_text_is_rejected_before_locator_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    monkeypatch.setattr(
        intake, "retained_source_page_count", lambda *_args, **_kwargs: 1
    )
    monkeypatch.setattr(
        intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: QrPayloadDetectionResult(raw, "raw"),
    )

    def forbidden_dispatch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Core dispatch must not receive an unsupported schema")

    monkeypatch.setattr(intake, "dispatch_routes", forbidden_dispatch)
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    page = result.pages[0]
    assert page.failure_category == "payload_schema_unsupported"
    assert page.failure_stage == "payload_parsing"
    assert page.locator is None
    assert page.dispatch_request is None
    assert page.dispatch_outcome is None
    assert not (tmp_path / "classes").exists()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("PDS1|x=y", "payload_schema_unsupported"),
        ("PDS3|x=y", "payload_schema_unsupported"),
        ("OMR1|x=y", "payload_schema_unsupported"),
        ("arbitrary raw text, not a route payload", "payload_invalid"),
        ("hello", "payload_invalid"),
        ("|m=quillan", "payload_invalid"),
        (" PDS1|x=y", "payload_invalid"),
        ("PDS 1|x=y", "payload_invalid"),
    ],
)
def test_payload_classification_distinguishes_declared_schema_from_arbitrary_text(
    payload: str,
    expected: str,
) -> None:
    assert intake.classify_pds2_payload_error(
        payload, Pds2PayloadError("synthetic parse rejection")
    ) == expected


def test_arbitrary_qr_text_is_preserved_as_invalid_payload_in_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    raw = "arbitrary raw text, not a route payload"
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: QrPayloadDetectionResult(raw, "raw"),
    )
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    page = result.pages[0]
    assert page.raw_payload_text == raw
    assert page.failure_category == "payload_invalid"
    assert page.failure_stage == "payload_parsing"


def test_unexpected_qr_runtime_is_wrapped_as_page_local_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    original = RuntimeError("programming failure")
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: (_ for _ in ()).throw(original),
    )
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    page = result.pages[0]
    assert page.terminal_category == "pre_dispatch_failure"
    assert page.failure_stage == "qr_detection"
    assert page.failure_category == "payload_unreadable"
    assert page.error is not None and page.error.__cause__ is original


def test_corrupted_exact_detector_result_is_contained_and_later_page_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    corrupted = QrPayloadDetectionResult("PDS2", "raw")
    object.__setattr__(corrupted, "decode_method", None)
    detections = iter(
        (corrupted, QrPayloadDetectionResult(None, None, RuntimeError("missing")))
    )
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(intake, "detect_qr_payload", lambda _image: next(detections))
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    assert len(result.pages) == 2
    assert result.pages[0].failure_stage == "qr_detection"
    assert result.pages[1].failure_stage == "qr_detection"


@pytest.mark.parametrize(
    "payload",
    [
        "PDS2|m=bad module|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef",
        "PDS2|m=quillan|c=bad class|w=work_1|r=rt_0123456789abcdef0123456789abcdef",
        "PDS2|m=quillan|c=class_1|w=bad work|r=rt_0123456789abcdef0123456789abcdef",
        "PDS2|m=quillan|c=class_1|w=work_1|r=bad route",
    ],
)
def test_identifier_parse_failures_use_exception_chain(payload: str) -> None:
    with pytest.raises(Pds2PayloadError) as caught:
        parse_pds2_payload(payload)
    assert intake.classify_pds2_payload_error(payload, caught.value) == "identifier_invalid"


@pytest.mark.parametrize("filename", ["scan.png", "six-pages.pdf"])
def test_file_intake_retains_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str) -> None:
    source = tmp_path / filename
    source.write_bytes(b"synthetic scan")
    calls: list[Path] = []
    retained_path = tmp_path / "retained" / filename
    event = RetainedSourceScan(
        "scan_synthetic", filename, "a" * 64, retained_path,
        f"retained/{filename}", datetime(2026, 7, 20, tzinfo=timezone.utc),
        date(2026, 7, 20),
    )
    def fake_retain(_root: Path, selected: Path) -> RetainedSourceScan:
        calls.append(selected)
        return event
    def fake_dispatch(_root: Path, retained_source: RetainedSourceScan, *, registry: ModuleRegistry, source_path: Path | None = None) -> intake.QuillanScanSourceResult:
        assert retained_source is event
        assert source_path == source
        source_type: intake.SourceType = "pdf" if filename.endswith(".pdf") else "image"
        return intake.QuillanScanSourceResult(source, filename, source_type, event, (), registry.module_ids(), RuntimeError("synthetic page-count stop"))
    monkeypatch.setattr(intake, "retain_source_scan", fake_retain)
    monkeypatch.setattr(intake, "dispatch_retained_quillan_scan", fake_dispatch)
    monkeypatch.setattr("quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures", lambda _root, result: result)
    intake.process_quillan_scan_source(source, workspace_root=tmp_path, registry=registry())
    assert calls == [source]


def test_folder_with_four_selected_files_retains_four_times(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    for name in ("a.png", "b.jpg", "c.tif", "d.pdf"):
        (folder / name).write_bytes(b"synthetic")
    calls: list[Path] = []
    def fake_retain(_root: Path, selected: Path) -> RetainedSourceScan:
        calls.append(selected)
        return RetainedSourceScan(
            f"scan_{selected.stem}", selected.name, "b" * 64,
            tmp_path / "retained" / selected.name, f"retained/{selected.name}",
            datetime(2026, 7, 20, tzinfo=timezone.utc), date(2026, 7, 20),
        )
    def fake_dispatch(_root: Path, event: RetainedSourceScan, *, registry: ModuleRegistry, source_path: Path | None = None) -> intake.QuillanScanSourceResult:
        assert source_path is not None
        kind: intake.SourceType = "pdf" if source_path.suffix == ".pdf" else "image"
        return intake.QuillanScanSourceResult(source_path, source_path.name, kind, event, (), registry.module_ids(), RuntimeError("synthetic"))
    monkeypatch.setattr(intake, "retain_source_scan", fake_retain)
    monkeypatch.setattr(intake, "dispatch_retained_quillan_scan", fake_dispatch)
    monkeypatch.setattr("quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures", lambda _root, result: result)
    intake.process_quillan_scan_folder(folder, workspace_root=tmp_path, registry=registry())
    assert len(calls) == 4


def test_pdf_page_two_loading_failure_does_not_suppress_page_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = RetainedSourceScan(
        "scan_synthetic",
        source.name,
        "a" * 64,
        tmp_path / "scans" / "source" / "retained.pdf",
        "scans/source/retained.pdf",
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        date(2026, 7, 20),
    )
    loaded: list[int] = []
    payload = "PDS2|m=quillan|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef"

    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 3)

    def load(_retained: RetainedSourceScan, page: int, **_kwargs: object) -> np.ndarray:
        loaded.append(page)
        if page == 2:
            raise RuntimeError("page two conversion")
        return np.full((10, 10, 3), 255, dtype=np.uint8)

    monkeypatch.setattr(intake, "load_retained_page_for_qr", load)
    monkeypatch.setattr(intake, "detect_qr_payload", lambda _image: QrPayloadDetectionResult(payload, "raw"))
    monkeypatch.setattr(
        intake,
        "dispatch_routes",
        lambda _root, _registry, requests: tuple(
            RouteDispatchFailure(request, RuntimeError("expected Core failure"))
            for request in requests
        ),
    )
    result = intake.dispatch_retained_quillan_scan(
        tmp_path,
        retained,
        registry=registry(),
        source_path=source,
    )
    assert loaded == [1, 2, 3]
    assert [page.terminal_category for page in result.pages] == [
        "core_dispatch_failure",
        "pre_dispatch_failure",
        "core_dispatch_failure",
    ]
    assert result.pages[1].failure_stage == "source_page_loading"


def test_unexpected_qr_exception_is_page_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = RetainedSourceScan(
        "scan_synthetic", source.name, "a" * 64,
        tmp_path / "scans" / "source" / "retained.pdf",
        "scans/source/retained.pdf",
        datetime(2026, 7, 20, tzinfo=timezone.utc), date(2026, 7, 20),
    )
    calls = 0
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8))

    def detect(_image: object) -> QrPayloadDetectionResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("detector exploded")
        return QrPayloadDetectionResult(None, None, RuntimeError("missing"))

    monkeypatch.setattr(intake, "detect_qr_payload", detect)
    result = intake.dispatch_retained_quillan_scan(tmp_path, retained, registry=registry(), source_path=source)
    assert calls == 2
    assert result.pages[0].failure_stage == "qr_detection"
    assert result.pages[0].failure_category == "payload_unreadable"


def test_reordered_core_outcomes_make_every_page_an_integration_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = RetainedSourceScan(
        "scan_synthetic", source.name, "a" * 64,
        tmp_path / "scans" / "source" / "retained.pdf",
        "scans/source/retained.pdf",
        datetime(2026, 7, 20, tzinfo=timezone.utc), date(2026, 7, 20),
    )
    payload = "PDS2|m=quillan|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8))
    monkeypatch.setattr(intake, "detect_qr_payload", lambda _image: QrPayloadDetectionResult(payload, "raw"))

    def reordered(_root: Path, _registry: ModuleRegistry, requests: tuple[object, ...]) -> tuple[RouteDispatchFailure, ...]:
        first, second = requests
        assert hasattr(first, "locator") and hasattr(second, "locator")
        return (
            RouteDispatchFailure(second, RuntimeError("second")),  # type: ignore[arg-type]
            RouteDispatchFailure(first, RuntimeError("first")),  # type: ignore[arg-type]
        )

    monkeypatch.setattr(intake, "dispatch_routes", reordered)
    result = intake.dispatch_retained_quillan_scan(tmp_path, retained, registry=registry(), source_path=source)
    assert [page.terminal_category for page in result.pages] == [
        "quillan_integration_failure",
        "quillan_integration_failure",
    ]
    assert all(page.dispatch_outcome is not None for page in result.pages)


@pytest.mark.parametrize("batch", [None, [], (), (object(),), (object(), object(), object())])
def test_malformed_core_batch_gives_every_request_page_a_terminal_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch: object,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = RetainedSourceScan(
        "scan_synthetic", source.name, "a" * 64,
        tmp_path / "scans" / "source" / "retained.pdf",
        "scans/source/retained.pdf",
        datetime(2026, 7, 20, tzinfo=timezone.utc), date(2026, 7, 20),
    )
    payload = "PDS2|m=quillan|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8))
    monkeypatch.setattr(intake, "detect_qr_payload", lambda _image: QrPayloadDetectionResult(payload, "raw"))
    monkeypatch.setattr(intake, "dispatch_routes", lambda *_args, **_kwargs: batch)
    result = intake.dispatch_retained_quillan_scan(tmp_path, retained, registry=registry(), source_path=source)
    assert len(result.pages) == 2
    assert all(page.terminal_category == "quillan_integration_failure" for page in result.pages)


def test_actual_six_page_pdf_is_retained_once_and_enumerated_from_retained_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "six-pages.pdf"
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=40, height=40)
    with source.open("wb") as output:
        writer.write(output)
    calls: list[Path] = []

    def retain(root: Path, selected: Path) -> RetainedSourceScan:
        calls.append(selected)
        return core_retain_source_scan(root, selected)

    monkeypatch.setattr(intake, "retain_source_scan", retain)
    monkeypatch.setattr(
        "quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures",
        lambda _root, result: result,
    )
    result = intake.process_quillan_scan_source(source, workspace_root=tmp_path, registry=registry())
    assert calls == [source]
    assert result.retained_source is not None
    assert len(result.pages) == 6
    assert [page.source_page_number for page in result.pages] == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("external_change", ["delete", "mutate"])
def test_external_original_change_after_retention_does_not_change_retained_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    external_change: str,
) -> None:
    source = tmp_path / "scan.png"
    original = np.full((30, 30, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(source), original)
    expected = source.read_bytes()
    original_dispatch = intake.dispatch_retained_quillan_scan

    def dispatch(
        root: Path,
        retained: RetainedSourceScan,
        *,
        registry: ModuleRegistry,
        source_path: Path | None = None,
    ) -> intake.QuillanScanSourceResult:
        if external_change == "delete":
            source.unlink()
        else:
            source.write_bytes(b"mutated external original")
        return original_dispatch(root, retained, registry=registry, source_path=source_path)

    monkeypatch.setattr(intake, "dispatch_retained_quillan_scan", dispatch)
    monkeypatch.setattr(
        "quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures",
        lambda _root, result: result,
    )
    result = intake.process_quillan_scan_source(source, workspace_root=tmp_path, registry=registry())
    assert result.retained_source is not None
    assert result.retained_source.retained_source_path.read_bytes() == expected
    assert len(result.pages) == 1


def test_actual_four_file_folder_retains_each_selected_child_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    image = np.full((12, 12, 3), 255, dtype=np.uint8)
    for name in ("a.png", "b.jpg", "c.tif"):
        assert cv2.imwrite(str(folder / name), image)
    writer = PdfWriter()
    writer.add_blank_page(width=20, height=20)
    with (folder / "d.pdf").open("wb") as output:
        writer.write(output)
    calls: list[Path] = []

    def retain(root: Path, selected: Path) -> RetainedSourceScan:
        calls.append(selected)
        return core_retain_source_scan(root, selected)

    def stop_after_retention(
        _root: Path,
        retained: RetainedSourceScan,
        *,
        registry: ModuleRegistry,
        source_path: Path | None = None,
    ) -> intake.QuillanScanSourceResult:
        assert source_path is not None
        source_type: intake.SourceType = "pdf" if source_path.suffix == ".pdf" else "image"
        return intake.QuillanScanSourceResult(
            source_path, source_path.name, source_type, retained, (),
            registry.module_ids(), RuntimeError("synthetic post-retention stop"),
        )

    monkeypatch.setattr(intake, "retain_source_scan", retain)
    monkeypatch.setattr(intake, "dispatch_retained_quillan_scan", stop_after_retention)
    monkeypatch.setattr(
        "quillan.scan_review_preservation.preserve_and_attach_quillan_scan_failures",
        lambda _root, result: result,
    )
    summary = intake.process_quillan_scan_folder(folder, workspace_root=tmp_path, registry=registry())
    assert [path.name for path in calls] == ["a.png", "b.jpg", "c.tif", "d.pdf"]
    assert summary.retained_source_count == 4
    assert all(
        result.retained_source is not None
        and result.retained_source.retained_source_path.is_file()
        for result in summary.source_results
    )


def test_mixed_module_success_keeps_foreign_result_opaque_and_ordered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mixed.pdf"
    source.write_bytes(b"%PDF synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    foreign_profile = ModuleProfile(
        "foreign", "Foreign", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), _handler,
    )
    mixed_registry = ModuleRegistry((foreign_profile, registry().require("quillan")))
    payloads = iter((
        "PDS2|m=foreign|c=class_1|w=work_1|r=rt_11111111111111111111111111111111",
        "PDS2|m=quillan|c=class_1|w=work_1|r=rt_22222222222222222222222222222222",
    ))
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(intake, "load_retained_page_for_qr", lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8))
    monkeypatch.setattr(intake, "detect_qr_payload", lambda _image: QrPayloadDetectionResult(next(payloads), "raw"))

    class OpaqueForeignResult:
        def __getattribute__(self, name: str) -> object:
            raise AssertionError(f"foreign result attribute accessed: {name}")

    foreign_result = OpaqueForeignResult()

    def resolution(request: RouteDispatchRequest) -> RouteResolution:
        locator = request.locator
        registration = RouteRegistration(
            "1", locator,
            ModuleRecordRef(locator.module_id, "response_page", "synthetic", "1"),
            "2026-07-20T00:00:00+00:00", "active", "synthetic fallback", {},
        )
        return RouteResolution(locator, registration, tmp_path, tmp_path, tmp_path)

    def dispatch(
        _root: Path,
        selected: ModuleRegistry,
        requests: tuple[RouteDispatchRequest, ...],
    ) -> tuple[RouteDispatchSuccess, ...]:
        foreign_request, quillan_request = requests
        quillan_result = _valid_quillan_result(quillan_request)
        return (
            RouteDispatchSuccess(
                foreign_request, selected.require("foreign"),
                resolution(foreign_request), foreign_result,
            ),
            RouteDispatchSuccess(
                quillan_request, selected.require("quillan"),
                resolution(quillan_request), quillan_result,
            ),
        )

    monkeypatch.setattr(intake, "dispatch_routes", dispatch)
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=mixed_registry, source_path=source
    )
    assert [page.locator.module_id for page in result.pages if page.locator] == [
        "foreign", "quillan"
    ]
    assert all(page.terminal_category == "dispatch_success" for page in result.pages)
    foreign_outcome = result.pages[0].dispatch_outcome
    assert isinstance(foreign_outcome, RouteDispatchSuccess)
    assert foreign_outcome.module_result is foreign_result


@pytest.mark.parametrize(
    ("failure_module", "later_modules"),
    [("quillan", ("foreign", "quillan")), ("foreign", ("quillan", "quillan"))],
)
def test_expected_core_failure_is_followed_by_two_ordered_successes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_module: str,
    later_modules: tuple[str, str],
) -> None:
    source = tmp_path / "three-pages.pdf"
    source.write_bytes(b"%PDF synthetic retained source")
    retained = core_retain_source_scan(tmp_path, source)
    foreign_profile = ModuleProfile(
        "foreign", "Foreign", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), _handler,
    )
    supplied = ModuleRegistry((foreign_profile, registry().require("quillan")))
    modules = (failure_module, *later_modules)
    payloads = iter(
        f"PDS2|m={module_id}|c=class_1|w=work_1|r=rt_{number * 32}"
        for module_id, number in zip(modules, "123", strict=True)
    )
    dispatch_calls: list[tuple[RouteDispatchRequest, ...]] = []
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(
        intake,
        "load_retained_page_for_qr",
        lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: QrPayloadDetectionResult(next(payloads), "raw"),
    )

    def resolution(request: RouteDispatchRequest) -> RouteResolution:
        locator = request.locator
        registration = RouteRegistration(
            "1",
            locator,
            ModuleRecordRef(locator.module_id, "response_page", "synthetic", "1"),
            "2026-07-20T00:00:00+00:00",
            "active",
            "synthetic fallback",
            {},
        )
        return RouteResolution(locator, registration, tmp_path, tmp_path, tmp_path)

    def result_for(request: RouteDispatchRequest) -> QuillanResponsePageDispatchResult:
        return _valid_quillan_result(request)

    expected_error = ModuleRouteHandlingError("expected Core route failure")

    def dispatch(
        _root: Path,
        selected: ModuleRegistry,
        requests: tuple[RouteDispatchRequest, ...],
    ) -> tuple[RouteDispatchFailure | RouteDispatchSuccess, ...]:
        dispatch_calls.append(requests)
        outcomes: list[RouteDispatchFailure | RouteDispatchSuccess] = [
            RouteDispatchFailure(requests[0], expected_error)
        ]
        for request in requests[1:]:
            module_result = (
                result_for(request)
                if request.locator.module_id == "quillan"
                else object()
            )
            outcomes.append(
                RouteDispatchSuccess(
                    request,
                    selected.require(request.locator.module_id),
                    resolution(request),
                    module_result,
                )
            )
        return tuple(outcomes)

    monkeypatch.setattr(intake, "dispatch_routes", dispatch)
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=supplied, source_path=source
    )
    assert len(dispatch_calls) == 1
    assert [request.source_page_number for request in dispatch_calls[0]] == [1, 2, 3]
    assert [page.source_page_number for page in result.pages] == [1, 2, 3]
    assert [page.terminal_category for page in result.pages] == [
        "core_dispatch_failure", "dispatch_success", "dispatch_success"
    ]
    failure = result.pages[0].dispatch_outcome
    assert isinstance(failure, RouteDispatchFailure)
    assert failure.error is expected_error
    assert all(page.retained_source is retained for page in result.pages)

    from quillan.scan_review_preservation import (
        preserve_and_attach_quillan_scan_failures,
    )

    attached = preserve_and_attach_quillan_scan_failures(tmp_path, result)
    summary = intake.QuillanScanIntakeSummary((attached,), supplied.module_ids())
    assert summary.core_dispatch_failure_count == 1
    assert summary.dispatch_success_count == 2
    assert attached.pages[0].review_record is not None
    assert attached.pages[1].review_record is None
    assert attached.pages[2].review_record is None


@pytest.mark.parametrize(
    "contradiction",
    [
        "wrong_profile_module",
        "wrong_resolution_locator",
        "wrong_registration_locator",
        "wrong_target_module",
        "unsupported_resolution",
        "unsupported_registration",
        "fake_profile",
        "fake_resolution",
        "fake_registration",
        "fake_target",
    ],
)
def test_core_success_contradiction_persists_locator_but_never_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contradiction: str,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic retained source")
    retained = core_retain_source_scan(tmp_path, source)
    payload = (
        "PDS2|m=quillan|c=class_1|w=work_1|"
        "r=rt_0123456789abcdef0123456789abcdef"
    )
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        intake,
        "load_retained_page_for_qr",
        lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: QrPayloadDetectionResult(payload, "raw"),
    )

    def dispatch(
        _root: Path,
        selected: ModuleRegistry,
        requests: tuple[RouteDispatchRequest, ...],
    ) -> tuple[RouteDispatchSuccess]:
        request = requests[0]
        locator = request.locator
        other_locator = parse_pds2_payload(
            "PDS2|m=quillan|c=other_class|w=work_1|"
            "r=rt_0123456789abcdef0123456789abcdef"
        )
        target: object = ModuleRecordRef(
            "quillan", "response_page", "synthetic", "1"
        )
        registration_locator = (
            other_locator if contradiction == "wrong_registration_locator" else locator
        )
        if contradiction == "wrong_target_module":
            target = ModuleRecordRef("foreign", "response_page", "synthetic", "1")
        elif contradiction == "fake_target":
            target = SimpleNamespace(module_id="quillan")
        registration: object = RouteRegistration(
            "1", registration_locator, cast(ModuleRecordRef, target),
            "2026-07-20T00:00:00+00:00", "active", "fallback", {},
        )
        if contradiction == "unsupported_registration":
            registration = object()
        elif contradiction == "fake_registration":
            registration = SimpleNamespace(locator=locator, target=target)
        resolution_locator = (
            other_locator if contradiction == "wrong_resolution_locator" else locator
        )
        resolution: object = RouteResolution(
            resolution_locator,
            cast(RouteRegistration, registration),
            tmp_path,
            tmp_path,
            tmp_path,
        )
        if contradiction == "unsupported_resolution":
            resolution = object()
        elif contradiction == "fake_resolution":
            resolution = SimpleNamespace(locator=locator, registration=registration)
        profile: object = selected.require("quillan")
        if contradiction == "wrong_profile_module":
            profile = ModuleProfile(
                "foreign", "Foreign", frozenset({"1"}), frozenset({"PDS2"}),
                frozenset({"1"}), frozenset({"active"}), _handler,
            )
        elif contradiction == "fake_profile":
            profile = SimpleNamespace(module_id="quillan")
        return (
            RouteDispatchSuccess(
                request,
                cast(ModuleProfile, profile),
                cast(RouteResolution, resolution),
                object(),
            ),
        )

    monkeypatch.setattr(intake, "dispatch_routes", dispatch)
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    page = result.pages[0]
    assert page.terminal_category == "quillan_integration_failure"
    assert page.failure_stage == "core_outcome_validation"
    assert page.locator is not None

    from quillan.scan_review_preservation import (
        preserve_and_attach_quillan_scan_failures,
    )

    attached = preserve_and_attach_quillan_scan_failures(tmp_path, result)
    record = attached.pages[0].review_record
    assert record is not None
    assert record.metadata.route_locator == page.locator
    assert record.metadata.target is None


def test_quillan_result_failure_may_persist_fully_validated_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic retained source")
    retained = core_retain_source_scan(tmp_path, source)
    payload = (
        "PDS2|m=quillan|c=class_1|w=work_1|"
        "r=rt_0123456789abcdef0123456789abcdef"
    )
    target = ModuleRecordRef("quillan", "response_page", "synthetic", "1")
    monkeypatch.setattr(intake, "retained_source_page_count", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        intake,
        "load_retained_page_for_qr",
        lambda *_args, **_kwargs: np.zeros((4, 4, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        intake,
        "detect_qr_payload",
        lambda _image: QrPayloadDetectionResult(payload, "raw"),
    )

    def dispatch(
        _root: Path,
        selected: ModuleRegistry,
        requests: tuple[RouteDispatchRequest, ...],
    ) -> tuple[RouteDispatchSuccess]:
        request = requests[0]
        registration = RouteRegistration(
            "1", request.locator, target,
            "2026-07-20T00:00:00+00:00", "active", "fallback", {},
        )
        resolution = RouteResolution(
            request.locator, registration, tmp_path, tmp_path, tmp_path
        )
        return (
            RouteDispatchSuccess(
                request, selected.require("quillan"), resolution, object()
            ),
        )

    monkeypatch.setattr(intake, "dispatch_routes", dispatch)
    result = intake.dispatch_retained_quillan_scan(
        tmp_path, retained, registry=registry(), source_path=source
    )
    assert result.pages[0].failure_stage == "quillan_result_validation"

    from quillan.scan_review_preservation import (
        preserve_and_attach_quillan_scan_failures,
    )

    attached = preserve_and_attach_quillan_scan_failures(tmp_path, result)
    record = attached.pages[0].review_record
    assert record is not None
    assert record.metadata.target == target


def test_public_dispatch_rejects_malformed_boundary_arguments(
    tmp_path: Path,
) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic")
    retained = core_retain_source_scan(tmp_path, source)
    with pytest.raises(QuillanScanPreflightError):
        intake.dispatch_retained_quillan_scan(
            tmp_path, cast(RetainedSourceScan, object()), registry=registry()
        )
    with pytest.raises(QuillanScanRegistryError):
        intake.dispatch_retained_quillan_scan(
            tmp_path, retained, registry=cast(ModuleRegistry, object())
        )
    with pytest.raises(QuillanScanPreflightError):
        intake.dispatch_retained_quillan_scan(
            tmp_path,
            retained,
            registry=registry(),
            source_path=cast(Path, "scan.png"),
        )
