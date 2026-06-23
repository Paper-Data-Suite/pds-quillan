"""Tests for Quillan's internal QR image-decoding layer."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
import pytest
import qrcode
from qrcode.image.pil import PilImage

from quillan.payloads import build_response_payload
from quillan.qr_decode import (
    ImageArray,
    decode_qr_payload_from_image,
    decode_qr_payload_from_image_path,
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


def _response_payload() -> str:
    return build_response_payload(
        class_id="english12_p4_synthetic",
        assignment_id="literary_argument_synthetic",
        student_id="stu_0001",
        page=1,
    )


def test_synthetic_quillan_qr_image_decodes_successfully() -> None:
    payload = _response_payload()

    result = decode_qr_payload_from_image(_make_qr_image(payload))

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.failure_message is None
    assert result.successful_attempt


def test_synthetic_qr_image_path_decodes_successfully(tmp_path: Path) -> None:
    payload = _response_payload()
    source = tmp_path / "synthetic-response.png"
    assert cv2.imwrite(str(source), _make_qr_image(payload))

    result = decode_qr_payload_from_image_path(source)

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.successful_attempt


def test_path_loaded_rgba_png_decodes_successfully(tmp_path: Path) -> None:
    payload = _response_payload()
    source = tmp_path / "synthetic-response-rgba.png"
    bgra_image = cv2.cvtColor(_make_qr_image(payload), cv2.COLOR_BGR2BGRA)
    bgra_image[:, :, 3] = 180
    assert cv2.imwrite(str(source), bgra_image)

    result = decode_qr_payload_from_image_path(source)

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.successful_attempt


def test_synthetic_full_response_page_decodes_successfully() -> None:
    payload = _response_payload()
    page = np.full((2200, 1700, 3), 255, dtype=np.uint8)
    qr_image = cv2.resize(
        _make_qr_image(payload),
        (200, 200),
        interpolation=cv2.INTER_NEAREST,
    )
    page[100:300, 1400:1600] = qr_image

    result = decode_qr_payload_from_image(page)

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.successful_attempt


def test_upper_right_crop_attempt_has_a_diagnostic_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = "synthetic crop fallback"
    expected_crop_shape = (320, 304)

    class CropOnlyDetector:
        def detectAndDecode(
            self,
            image: ImageArray,
        ) -> tuple[str, None, None]:
            decoded = payload if image.shape[:2] == expected_crop_shape else ""
            return decoded, None, None

    monkeypatch.setattr(cv2, "QRCodeDetector", CropOnlyDetector)
    page = np.full((1000, 800, 3), 255, dtype=np.uint8)

    result = decode_qr_payload_from_image(page)

    assert result.payload_text == payload
    assert result.successful_attempt == "crop 1 broad raw"


def test_candidate_level_opencv_error_does_not_prevent_later_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = "synthetic later candidate"

    class LaterSuccessDetector:
        calls = 0

        def detectAndDecode(
            self,
            image: ImageArray,
        ) -> tuple[str, None, None]:
            type(self).calls += 1
            if type(self).calls == 1:
                raise cv2.error("synthetic candidate failure")
            decoded = payload if type(self).calls == 2 else ""
            return decoded, None, None

    monkeypatch.setattr(cv2, "QRCodeDetector", LaterSuccessDetector)

    result = decode_qr_payload_from_image(
        np.full((100, 100, 3), 255, dtype=np.uint8)
    )

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.successful_attempt == "grayscale"


def test_candidate_level_opencv_errors_without_success_report_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AlwaysFailingDetector:
        def detectAndDecode(
            self,
            image: ImageArray,
        ) -> tuple[str, None, None]:
            raise cv2.error("synthetic candidate failure")

    monkeypatch.setattr(cv2, "QRCodeDetector", AlwaysFailingDetector)

    result = decode_qr_payload_from_image(
        np.full((100, 100, 3), 255, dtype=np.uint8)
    )

    assert result.payload_text is None
    assert result.failure_category == "payload_unreadable"
    assert result.failure_message


def test_missing_file_gives_structured_failure(tmp_path: Path) -> None:
    result = decode_qr_payload_from_image_path(tmp_path / "missing.png")

    assert result.payload_text is None
    assert result.failure_category == "source_missing"
    assert result.failure_message
    assert result.successful_attempt is None


def test_unsupported_extension_gives_structured_failure(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-synthetic")

    result = decode_qr_payload_from_image_path(source)

    assert result.payload_text is None
    assert result.failure_category == "source_type_unsupported"


def test_invalid_image_content_gives_structured_failure(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    source.write_text("not an image", encoding="utf-8")

    result = decode_qr_payload_from_image_path(source)

    assert result.payload_text is None
    assert result.failure_category == "source_unreadable"
    assert result.failure_message


def test_blank_image_reports_missing_payload_without_workspace_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))

    result = decode_qr_payload_from_image(
        np.full((550, 425, 3), 255, dtype=np.uint8)
    )

    assert result.payload_text is None
    assert result.failure_category == "payload_missing"
    assert result.failure_message
    assert set(tmp_path.rglob("*")) == before


def test_decoder_returns_arbitrary_nonempty_qr_text_without_validation() -> None:
    payload = "synthetic text that is intentionally not a PDS1 payload"

    result = decode_qr_payload_from_image(_make_qr_image(payload))

    assert result.payload_text == payload
    assert result.failure_category is None
    assert result.successful_attempt
