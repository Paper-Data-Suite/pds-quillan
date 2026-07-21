"""Real PDS2 QR workflow coverage for the parse-only CLI service."""

from pathlib import Path

import cv2

from quillan.cli_app.handlers.decoding import decode_retained_pds2_scan
from tests.test_qr_decode import _make_qr_image


def test_real_pds2_qr_is_retained_decoded_and_parsed(tmp_path: Path) -> None:
    payload = "PDS2|m=quillan|c=class_1|w=work_1|r=rt_0123456789abcdef0123456789abcdef"
    source = tmp_path / "response.png"
    assert cv2.imwrite(str(source), _make_qr_image(payload))
    result = decode_retained_pds2_scan(source, workspace_root=tmp_path)
    assert len(result) == 1
    assert result[0].raw_payload_text == payload
    assert result[0].locator is not None
    assert result[0].locator.module_id == "quillan"
    assert len(tuple((tmp_path / "scans" / "source").rglob("*.png"))) == 1
