"""Grammar-independent QR detection coverage used by retained PDS2 intake."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
import pytest
import qrcode
from qrcode.image.pil import PilImage

from quillan.qr_decode import (
    ImageArray,
    QrDetectionFailure,
    QrPayloadDetectionResult,
    decode_qr_payload_from_image,
    decode_qr_payload_from_image_path,
    detect_qr_payload,
)


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


def _pds2_payload() -> str:
    return "PDS2|m=quillan|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef"


def test_synthetic_pds2_qr_image_decodes_successfully() -> None:
    payload = _pds2_payload()
    result = decode_qr_payload_from_image(_make_qr_image(payload))
    assert result.raw_payload_text == payload
    assert result.error is None
    assert result.decode_method


def test_synthetic_qr_image_path_decodes_successfully(tmp_path: Path) -> None:
    payload = _pds2_payload()
    source = tmp_path / "synthetic-response.png"
    assert cv2.imwrite(str(source), _make_qr_image(payload))
    result = decode_qr_payload_from_image_path(source)
    assert result.raw_payload_text == payload
    assert result.error is None


def test_path_loaded_rgba_png_decodes_successfully(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-response-rgba.png"
    bgra_image = cv2.cvtColor(_make_qr_image(_pds2_payload()), cv2.COLOR_BGR2BGRA)
    bgra_image[:, :, 3] = 180
    assert cv2.imwrite(str(source), bgra_image)
    assert decode_qr_payload_from_image_path(source).raw_payload_text == _pds2_payload()


def test_full_page_upper_right_qr_decodes_successfully() -> None:
    page = np.full((2200, 1700, 3), 255, dtype=np.uint8)
    qr_image = cv2.resize(_make_qr_image(_pds2_payload()), (200, 200), interpolation=cv2.INTER_NEAREST)
    page[100:300, 1400:1600] = qr_image
    assert decode_qr_payload_from_image(page).raw_payload_text == _pds2_payload()


def test_upper_right_crop_attempt_has_diagnostic_label(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_crop_shape = (320, 304)

    class CropOnlyDetector:
        def detectAndDecode(self, image: ImageArray) -> tuple[str, None, None]:
            return ("synthetic crop fallback" if image.shape[:2] == expected_crop_shape else "", None, None)

    monkeypatch.setattr(cv2, "QRCodeDetector", CropOnlyDetector)
    result = detect_qr_payload(np.full((1000, 800, 3), 255, dtype=np.uint8))
    assert result.raw_payload_text == "synthetic crop fallback"
    assert result.decode_method == "crop 1 broad raw"


def test_candidate_opencv_failure_does_not_prevent_later_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class LaterSuccessDetector:
        calls = 0

        def detectAndDecode(self, _image: ImageArray) -> tuple[str, None, None]:
            type(self).calls += 1
            if type(self).calls == 1:
                raise cv2.error("synthetic candidate failure")
            return ("later candidate" if type(self).calls == 2 else "", None, None)

    monkeypatch.setattr(cv2, "QRCodeDetector", LaterSuccessDetector)
    result = detect_qr_payload(np.full((100, 100, 3), 255, dtype=np.uint8))
    assert result.raw_payload_text == "later candidate"
    assert result.decode_method == "grayscale"


def test_all_candidate_opencv_errors_report_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    class AlwaysFailingDetector:
        def detectAndDecode(self, _image: ImageArray) -> tuple[str, None, None]:
            raise cv2.error("synthetic candidate failure")

    monkeypatch.setattr(cv2, "QRCodeDetector", AlwaysFailingDetector)
    result = detect_qr_payload(np.full((100, 100, 3), 255, dtype=np.uint8))
    assert result.raw_payload_text is None
    assert result.failure_category == "payload_unreadable"


def test_unexpected_internal_runtime_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_image: ImageArray) -> object:
        raise RuntimeError("programming failure")

    monkeypatch.setattr("quillan.qr_decode._qr_candidate_images", fail)
    with pytest.raises(RuntimeError, match="programming failure"):
        detect_qr_payload(np.full((100, 100, 3), 255, dtype=np.uint8))


@pytest.mark.parametrize(
    ("raw", "method", "error"),
    [
        ("", "raw", None),
        (object(), "raw", None),
        ("payload", None, None),
        ("payload", "raw", RuntimeError("contradiction")),
        (None, None, None),
        (None, object(), RuntimeError("failure")),
        (None, None, object()),
    ],
)
def test_detection_result_rejects_impossible_states(
    raw: object,
    method: object,
    error: object,
) -> None:
    with pytest.raises(ValueError):
        QrPayloadDetectionResult(raw, method, error)  # type: ignore[arg-type]


def test_invalid_image_returns_typed_failure() -> None:
    result = detect_qr_payload(object())
    assert isinstance(result.error, QrDetectionFailure)
    assert result.failure_category == "source_unreadable"


def test_blank_image_reports_missing_payload() -> None:
    result = detect_qr_payload(np.full((100, 100, 3), 255, dtype=np.uint8))
    assert result.raw_payload_text is None
    assert result.failure_category == "payload_missing"


def test_detector_returns_arbitrary_non_pds2_text_without_validation() -> None:
    payload = "arbitrary raw text, not a route payload"
    assert detect_qr_payload(_make_qr_image(payload)).raw_payload_text == payload


def test_candidate_attempt_order_is_bounded_and_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, ...]] = []

    class EmptyDetector:
        def detectAndDecode(self, image: ImageArray) -> tuple[str, None, None]:
            calls.append(image.shape)
            return "", None, None

    monkeypatch.setattr(cv2, "QRCodeDetector", EmptyDetector)
    result = detect_qr_payload(np.full((100, 80, 3), 255, dtype=np.uint8))
    assert result.failure_category == "payload_missing"
    assert 1 < len(calls) < 100
    assert calls[0] == (100, 80, 3)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("missing.png", "source_missing"), ("scan.pdf", "source_type_unsupported")],
)
def test_image_path_structured_failures(tmp_path: Path, name: str, expected: str) -> None:
    source = tmp_path / name
    if name.endswith(".pdf"):
        source.write_bytes(b"%PDF-synthetic")
    assert decode_qr_payload_from_image_path(source).failure_category == expected


def test_invalid_image_content_reports_unreadable(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    source.write_text("not an image", encoding="utf-8")
    assert decode_qr_payload_from_image_path(source).failure_category == "source_unreadable"
