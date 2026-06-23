"""Focused tests for QR-aware single-image scan routing."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
import pytest
import qrcode
from qrcode.image.pil import PilImage
from pds_core.scan_failure_metadata import validate_routing_failure_metadata

from quillan.cli import main
import quillan.cli_app.handlers.routing as cli_routing
from quillan.evidence_filing import EvidenceFilingError
from quillan.payloads import build_response_payload

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
UNKNOWN_ASSIGNMENT_ID = "essay_unknown_synthetic"
UNKNOWN_STUDENT_ID = "stu_9999"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(cli_routing, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _write_workspace(
    root: Path,
    *,
    assignment_id: str = ASSIGNMENT_ID,
) -> None:
    class_dir = root / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / assignment_id
    assignment_dir.mkdir(parents=True)

    with (class_dir / "roster.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as roster_file:
        writer = csv.DictWriter(
            roster_file,
            fieldnames=(
                "class_id",
                "student_id",
                "last_name",
                "first_name",
                "period",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "3",
            }
        )

    assignment = {
        "assignment_id": assignment_id,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "standards_profile_id": "synthetic_profile",
        "tagging_mode": "focus",
        "focus_standards": ["W.1"],
        "basic_requirements": {"paragraphs_min": 1},
        "rubric_id": "synthetic_rubric",
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment),
        encoding="utf-8",
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


def _write_qr_image(path: Path, payload: str) -> None:
    assert cv2.imwrite(str(path), _make_qr_image(payload))


def _valid_payload(
    *,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
) -> str:
    return build_response_payload(
        class_id=CLASS_ID,
        assignment_id=assignment_id,
        student_id=student_id,
        page=2,
    )


def _review_metadata(workspace: Path) -> dict[str, object]:
    records = list((workspace / "scans" / "review").glob("*.json"))
    assert len(records) == 1
    loaded = json.loads(records[0].read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    validate_routing_failure_metadata(loaded)
    return loaded


def _assert_no_identity(metadata: dict[str, object]) -> None:
    assert metadata["module"] is None
    assert metadata["payload_page_number"] is None
    assert metadata["class_id"] is None
    assert metadata["assignment_id"] is None
    assert metadata["student_id"] is None


def test_route_scan_decode_qr_successfully_routes_single_image(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _valid_payload()
    source = tmp_path / "synthetic-response.png"
    _write_qr_image(source, payload)
    original_bytes = source.read_bytes()

    result = main(["route-scan", str(source), "--decode-qr"])

    output = capsys.readouterr().out
    retained_files = list((workspace / "scans" / "source").rglob("*.png"))
    routed_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_stu_0001_pg_002.png"
    )
    assert result == 0
    assert len(retained_files) == 1
    assert retained_files[0].read_bytes() == original_bytes
    assert routed_path.read_bytes() == original_bytes
    assert "Routed Quillan response page." in output
    assert "Routed evidence: classes/" in output
    assert not (workspace / "scans" / "review").exists()
    assert not list(workspace.rglob("submission.json"))
    assert not list(workspace.rglob("review.json"))


def test_route_scan_payload_mode_still_works_without_qr_decoding(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "teacher-scan.png"
    source.write_bytes(b"synthetic routed image bytes")

    def fail_decode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("payload mode should not decode QR images")

    monkeypatch.setattr(cli_routing, "decode_qr_payload_from_image_path", fail_decode)

    assert main(["route-scan", str(source), "--payload", _valid_payload()]) == 0
    assert list(
        (
            workspace
            / "classes"
            / CLASS_ID
            / "assignments"
            / ASSIGNMENT_ID
            / "scans"
        ).glob("response_*.png")
    )


def test_route_scan_requires_payload_or_decode_qr(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic-response.png"
    source.write_bytes(b"synthetic")

    with pytest.raises(SystemExit) as error:
        main(["route-scan", str(source)])

    assert error.value.code == 2


def test_route_scan_rejects_payload_and_decode_qr_together(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic-response.png"
    source.write_bytes(b"synthetic")

    with pytest.raises(SystemExit) as error:
        main(["route-scan", str(source), "--payload", "PDS1", "--decode-qr"])

    assert error.value.code == 2


def test_route_scan_decode_qr_blank_image_preserves_decode_failure(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "blank.png"
    blank = np.full((550, 425, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(source), blank)

    result = main(["route-scan", str(source), "--decode-qr"])

    output = capsys.readouterr().out
    metadata = _review_metadata(workspace)
    assert result == 0
    assert metadata["failure_category"] == "payload_missing"
    assert metadata["failure_message"]
    assert metadata["source_filename"] == source.name
    assert metadata["detected_payload"] is None
    _assert_no_identity(metadata)
    assert metadata["module_details"] == {
        "failure_origin": "qr_decode",
        "decode_attempt": None,
    }
    assert not list(workspace.rglob("response_*.png"))
    assert "preserved for review" in output
    assert "Category: payload_missing" in output


def test_route_scan_decode_qr_unsupported_source_type_preserves_failure(
    workspace: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "scan.gif"
    source.write_bytes(b"synthetic")

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "source_type_unsupported"
    assert metadata["source_filename"] == source.name
    assert metadata["detected_payload"] is None
    _assert_no_identity(metadata)
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "qr_decode"
    assert not list(workspace.rglob("response_*.gif"))


def test_route_scan_decode_qr_non_pds_payload_preserves_validation_failure(
    workspace: Path,
    tmp_path: Path,
) -> None:
    payload = "not a pds payload"
    source = tmp_path / "non-pds.png"
    _write_qr_image(source, payload)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert metadata["failure_category"] == "payload_schema_unsupported"
    assert metadata["detected_payload"] == payload
    _assert_no_identity(metadata)
    assert module_details["failure_origin"] == "payload_validation"
    assert not list(workspace.rglob("response_*.png"))


def test_route_scan_decode_qr_wrong_module_preserves_validation_failure(
    workspace: Path,
    tmp_path: Path,
) -> None:
    payload = (
        "PDS1|module=scoreform|class=english12|aid=quiz1|"
        "sid=stu_0001|page=1"
    )
    source = tmp_path / "scoreform.png"
    _write_qr_image(source, payload)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "module_unsupported"
    assert metadata["detected_payload"] == payload
    assert metadata["module"] == "scoreform"
    assert metadata["class_id"] == "english12"
    assert metadata["assignment_id"] == "quiz1"
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 1
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "payload_validation"
    assert module_details["expected_module"] == "quillan"
    assert not list(workspace.rglob("response_*.png"))


@pytest.mark.parametrize(
    ("payload", "reason", "actual_document_type"),
    [
        (
            build_response_payload(
                class_id=CLASS_ID,
                assignment_id=ASSIGNMENT_ID,
                student_id=STUDENT_ID,
                page=2,
            ).replace("|doc=response", ""),
            "document_type_missing",
            None,
        ),
        (
            build_response_payload(
                class_id=CLASS_ID,
                assignment_id=ASSIGNMENT_ID,
                student_id=STUDENT_ID,
                page=2,
            ).replace("doc=response", "doc=cover"),
            "document_type_invalid",
            "cover",
        ),
    ],
)
def test_route_scan_decode_qr_document_type_validation_preserves_identity(
    workspace: Path,
    tmp_path: Path,
    payload: str,
    reason: str,
    actual_document_type: str | None,
) -> None:
    source = tmp_path / f"{reason}.png"
    _write_qr_image(source, payload)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "payload_invalid"
    assert metadata["detected_payload"] == payload
    assert metadata["module"] == "quillan"
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 2
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "payload_validation"
    assert module_details["reason"] == reason
    if actual_document_type is not None:
        assert module_details["actual_document_type"] == actual_document_type
    assert not list(workspace.rglob("response_*.png"))


def test_route_scan_decode_qr_unknown_student_preserves_route_failure(
    workspace: Path,
    tmp_path: Path,
) -> None:
    payload = _valid_payload(student_id=UNKNOWN_STUDENT_ID)
    source = tmp_path / "unknown-student.png"
    _write_qr_image(source, payload)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "student_unknown"
    assert metadata["detected_payload"] == payload
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == UNKNOWN_STUDENT_ID
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "route_planning"
    assert module_details["reason"] == "student_unknown"
    assert not list(workspace.rglob("response_*.png"))


def test_route_scan_decode_qr_unknown_assignment_preserves_route_failure(
    workspace: Path,
    tmp_path: Path,
) -> None:
    payload = _valid_payload(assignment_id=UNKNOWN_ASSIGNMENT_ID)
    source = tmp_path / "unknown-assignment.png"
    _write_qr_image(source, payload)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "assignment_unknown"
    assert metadata["detected_payload"] == payload
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == UNKNOWN_ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "route_planning"
    assert module_details["reason"] == "assignment_unknown"
    assert not list(workspace.rglob("response_*.png"))


def test_route_scan_decode_qr_evidence_filing_failure_is_preserved(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "synthetic-response.png"
    _write_qr_image(source, _valid_payload())

    def fail_filing(*_args: object, **_kwargs: object) -> None:
        raise EvidenceFilingError("Synthetic disk write failure.")

    monkeypatch.setattr(
        cli_routing,
        "file_routed_response_evidence",
        fail_filing,
    )

    result = main(["route-scan", str(source), "--decode-qr"])

    output = capsys.readouterr().out
    metadata = _review_metadata(workspace)
    assert result == 0
    assert metadata["failure_category"] == "evidence_write_failed"
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 2
    assert metadata["module"] == "quillan"
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "evidence_filing"
    assert "could not be filed; preserved for review" in output


def test_route_scan_decode_qr_pdf_conversion_failure_is_preserved(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "synthetic-response.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    monkeypatch.setattr(cli_routing, "iter_pdf_page_images", lambda _source: [])

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == "source_unreadable"
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "pdf_conversion"
    assert not list(workspace.rglob("response_*.pdf"))
