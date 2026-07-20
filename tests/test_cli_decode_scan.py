"""Focused tests for the decode-only scan diagnostic CLI command."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
import pytest
import qrcode
from qrcode.image.pil import PilImage

from quillan.cli import main
from tests.pds1_scan_test_support import build_response_payload

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"


def _make_qr_image(payload: str, *, box_size: int = 8) -> NDArray[np.uint8]:
    qr = qrcode.QRCode[PilImage](
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
        image_factory=PilImage,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    rgb_image = image.get_image().convert("RGB")
    return cast(
        NDArray[np.uint8],
        cv2.cvtColor(np.asarray(rgb_image), cv2.COLOR_RGB2BGR),
    )


def _write_qr_image(path: Path, payload: str) -> None:
    assert cv2.imwrite(str(path), _make_qr_image(payload))


def _valid_payload() -> str:
    return build_response_payload(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        page=2,
    )


def test_decode_scan_valid_quillan_response_image_prints_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _valid_payload()
    source = tmp_path / "synthetic-response.png"
    _write_qr_image(source, payload)

    result = main(["decode-scan", str(source)])

    output = capsys.readouterr().out
    assert result == 0
    assert "Quillan scan decode diagnostic" in output
    assert f"Source: {source}" in output
    assert "QR decode: success" in output
    assert "Decode attempt:" in output
    assert f"Payload: {payload}" in output
    assert "Payload validation: success" in output
    assert "Module: quillan" in output
    assert "Document type: response" in output
    assert f"Class ID: {CLASS_ID}" in output
    assert f"Assignment ID: {ASSIGNMENT_ID}" in output
    assert f"Student ID: {STUDENT_ID}" in output
    assert "Page number: 2" in output


def test_decode_scan_hide_payload_suppresses_raw_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _valid_payload()
    source = tmp_path / "synthetic-response.png"
    _write_qr_image(source, payload)

    result = main(["decode-scan", str(source), "--hide-payload"])

    output = capsys.readouterr().out
    assert result == 0
    assert payload not in output
    assert "Payload: hidden" in output
    assert "Payload validation: success" in output
    assert f"Class ID: {CLASS_ID}" in output
    assert f"Student ID: {STUDENT_ID}" in output


def test_decode_scan_blank_image_exits_two_and_reports_decode_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "blank.png"
    blank = np.full((550, 425, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(source), blank)

    result = main(["decode-scan", str(source)])

    output = capsys.readouterr().out
    assert result == 2
    assert "QR decode: failed" in output
    assert "Category: payload_missing" in output


def test_decode_scan_unsupported_source_type_exits_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic\n%%EOF\n")

    result = main(["decode-scan", str(source)])

    output = capsys.readouterr().out
    assert result == 2
    assert "QR decode: failed" in output
    assert "Category: source_type_unsupported" in output


def test_decode_scan_non_pds1_qr_exits_three(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = "not a pds payload"
    source = tmp_path / "non-pds.png"
    _write_qr_image(source, payload)

    result = main(["decode-scan", str(source)])

    output = capsys.readouterr().out
    assert result == 3
    assert "QR decode: success" in output
    assert f"Payload: {payload}" in output
    assert "Payload validation: failed" in output
    assert "Category: payload_schema_unsupported" in output


def test_decode_scan_wrong_module_exits_three_and_reports_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = (
        "PDS1|module=scoreform|class=english12|aid=quiz1|"
        "sid=stu_0001|page=1"
    )
    source = tmp_path / "scoreform.png"
    _write_qr_image(source, payload)

    result = main(["decode-scan", str(source)])

    output = capsys.readouterr().out
    assert result == 3
    assert "Payload validation: failed" in output
    assert "Category: module_unsupported" in output
    assert "Module: scoreform" in output
    assert "Class ID: english12" in output
    assert "Assignment ID: quiz1" in output
    assert "Student ID: stu_0001" in output
    assert "Page number: 1" in output


def test_decode_scan_does_not_resolve_or_mutate_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _valid_payload()
    source = tmp_path / "synthetic-response.png"
    _write_qr_image(source, payload)
    before_paths = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert main(["decode-scan", str(source)]) == 0
    after_success = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert main(["decode-scan", str(tmp_path / "missing.png")]) == 2
    after_failure = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert after_success == before_paths
    assert after_failure == before_paths
    assert not (tmp_path / "scans").exists()
    assert not (tmp_path / "classes").exists()
    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.rglob("response_*.png"))


def test_decode_scan_help_documents_decode_only_behavior(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["decode-scan", "--help"])

    output = capsys.readouterr().out
    assert error.value.code == 0
    assert "decode-scan" in output
    assert "without routing" in output
    assert "--hide-payload" in output
