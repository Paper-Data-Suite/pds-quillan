from pathlib import Path

import pytest

import quillan.cli_app.handlers.decoding as decoding
from quillan.cli_app.parser import build_parser
from quillan.qr_decode import QrPayloadDetectionResult


def test_decode_scan_accepts_image_or_pdf_source_path() -> None:
    args = build_parser().parse_args(["decode-scan", "scan.pdf"])
    assert args.source_file.name == "scan.pdf"
    assert args.hide_payload is False


def test_decode_only_contains_unexpected_qr_error_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    payload = (
        "PDS2|m=quillan|c=class_1|w=work_1|"
        "r=rt_0123456789abcdef0123456789abcdef"
    )
    calls = 0

    def detect(_image: object) -> QrPayloadDetectionResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("programming failure")
        return QrPayloadDetectionResult(payload, "raw")

    monkeypatch.setattr(decoding, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(decoding, "load_retained_page_for_qr", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(decoding, "detect_qr_payload", detect)
    pages = decoding.decode_retained_pds2_scan(source, workspace_root=tmp_path)
    assert len(pages) == 2
    assert pages[0].failure_category == "payload_unreadable"
    assert isinstance(pages[0].error, RuntimeError)
    assert pages[1].locator is not None


def test_decode_only_contains_corrupted_detector_result_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    payload = (
        "PDS2|m=quillan|c=class_1|w=work_1|"
        "r=rt_0123456789abcdef0123456789abcdef"
    )
    corrupted = QrPayloadDetectionResult(payload, "raw")
    object.__setattr__(corrupted, "error", RuntimeError("corrupted result"))
    detections = iter((corrupted, QrPayloadDetectionResult(payload, "raw")))
    monkeypatch.setattr(decoding, "retained_source_page_count", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(decoding, "load_retained_page_for_qr", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(decoding, "detect_qr_payload", lambda _image: next(detections))
    pages = decoding.decode_retained_pds2_scan(source, workspace_root=tmp_path)
    assert len(pages) == 2
    assert pages[0].failure_category == "payload_unreadable"
    assert pages[1].locator is not None
