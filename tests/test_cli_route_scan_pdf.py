"""Focused tests for QR-aware PDF page scan routing."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from pds_core.scan_failure_metadata import validate_routing_failure_metadata
import pytest
import qrcode
from qrcode.image.pil import PilImage

from quillan.cli import main
import quillan.cli_app.handlers.routing as cli_routing
from quillan.evidence_filing import EvidenceFilingError
from quillan.evidence_filing import file_routed_response_evidence
from quillan.payloads import build_response_payload
from quillan.pdf_pages import PdfPageConversionError, PdfPageConversionFailure
from quillan.pdf_pages import PdfPageImage
from quillan.route_planning import RoutePlan

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
UNKNOWN_ASSIGNMENT_ID = "essay_unknown_synthetic"
UNKNOWN_STUDENT_ID = "stu_9999"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(cli_routing, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _write_workspace(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    assignment_dir = class_dir / "modules" / "quillan" / "work" / ASSIGNMENT_ID
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
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": SECOND_STUDENT_ID,
                "last_name": "Patel",
                "first_name": "Mina",
                "period": "3",
            }
        )

    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["njsls-ela:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
        "module_details": {},
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment),
        encoding="utf-8",
    )


def _source_pdf(tmp_path: Path) -> Path:
    source = tmp_path / "responses.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    return source


def _valid_payload(
    *,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
    page: int = 2,
) -> str:
    return build_response_payload(
        class_id=CLASS_ID,
        assignment_id=assignment_id,
        student_id=student_id,
        page=page,
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


def _blank_image() -> NDArray[np.uint8]:
    return np.full((550, 425, 3), 255, dtype=np.uint8)


def _pdf_pages(*images: object) -> list[PdfPageImage]:
    return [
        PdfPageImage(page_number=page_number, image=image)
        for page_number, image in enumerate(images, start=1)
    ]


def _review_metadata_records(workspace: Path) -> list[dict[str, object]]:
    records = sorted((workspace / "scans" / "review").glob("*.json"))
    loaded_records: list[dict[str, object]] = []
    for record in records:
        loaded = json.loads(record.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        validate_routing_failure_metadata(loaded)
        loaded_records.append(loaded)
    return loaded_records


def _routed_pngs(workspace: Path) -> list[Path]:
    return sorted(
        (
            workspace
            / "classes"
            / CLASS_ID
            / "modules"
            / "quillan"
            / "work"
            / ASSIGNMENT_ID
            / "scans"
        ).glob("response_*.png")
    )


def test_route_scan_decode_qr_pdf_routes_each_valid_page(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source_pdf(tmp_path)
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload(student_id=STUDENT_ID, page=1)),
            _make_qr_image(_valid_payload(student_id=SECOND_STUDENT_ID, page=2)),
        ),
    )

    result = main(["route-scan", str(source), "--decode-qr"])

    output = capsys.readouterr().out
    routed = _routed_pngs(workspace)
    assert result == 0
    assert len(routed) == 2
    assert {path.suffix for path in routed} == {".png"}
    assert not list(workspace.rglob("response_*.pdf"))
    assert not _review_metadata_records(workspace)
    assert "Scan intake summary" in output
    assert "Sources processed: 1" in output
    assert "Pages attempted: 2" in output
    assert "Routed: 2" in output
    assert (
        f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}  "
        "(2 routed pages)"
    ) in output
    assert not list(workspace.rglob("submission.json"))
    assert not list(workspace.rglob("review.json"))


def test_route_scan_decode_qr_pdf_preserves_blank_page_and_continues(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source_pdf(tmp_path)
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload()),
            _blank_image(),
        ),
    )

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    metadata = _review_metadata_records(workspace)
    assert len(_routed_pngs(workspace)) == 1
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "payload_missing"
    assert metadata[0]["source_page_number"] == 2
    assert metadata[0]["detected_payload"] is None
    assert metadata[0]["student_id"] is None
    assert "Preserved for review: 1" in output


def test_route_scan_decode_qr_pdf_preserves_payload_validation_failure(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)
    bad_payload = "not a pds payload"
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload()),
            _make_qr_image(bad_payload),
        ),
    )

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(_routed_pngs(workspace)) == 1
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "payload_schema_unsupported"
    assert metadata[0]["detected_payload"] == bad_payload
    assert metadata[0]["source_page_number"] == 2


def test_route_scan_decode_qr_pdf_preserves_route_planning_failure(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)
    unknown_student_payload = _valid_payload(student_id=UNKNOWN_STUDENT_ID)
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload()),
            _make_qr_image(unknown_student_payload),
        ),
    )

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(_routed_pngs(workspace)) == 1
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "student_unknown"
    assert metadata[0]["detected_payload"] == unknown_student_payload
    assert metadata[0]["student_id"] == UNKNOWN_STUDENT_ID
    assert metadata[0]["payload_page_number"] == 2
    assert metadata[0]["source_page_number"] == 2


def test_route_scan_decode_qr_pdf_conversion_failure_is_preserved_once(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)

    def fail_conversion(_source: Path) -> list[PdfPageImage]:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="source_unreadable",
                failure_message="Synthetic conversion failure.",
                module_details={"failure_origin": "pdf_conversion"},
            )
        )

    monkeypatch.setattr(cli_routing, "iter_pdf_page_images", fail_conversion)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "source_unreadable"
    assert metadata[0]["source_page_number"] is None
    assert metadata[0]["module_details"] == {"failure_origin": "pdf_conversion"}
    assert not _routed_pngs(workspace)


def test_route_scan_decode_qr_pdf_zero_pages_is_preserved(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)
    monkeypatch.setattr(cli_routing, "iter_pdf_page_images", lambda _source: [])

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "source_unreadable"
    assert not _routed_pngs(workspace)


def test_route_scan_decode_qr_pdf_evidence_failure_is_preserved(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload()),
            _make_qr_image(_valid_payload(student_id=SECOND_STUDENT_ID, page=3)),
        ),
    )
    def fail_first_page(workspace_root: str | Path, **kwargs: Any) -> object:
        route_plan = cast(RoutePlan, kwargs["route_plan"])
        if route_plan.student_id == STUDENT_ID:
            raise EvidenceFilingError("Synthetic disk write failure.")
        return file_routed_response_evidence(workspace_root, **kwargs)

    monkeypatch.setattr(cli_routing, "file_routed_response_evidence", fail_first_page)

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "evidence_write_failed"
    assert metadata[0]["source_page_number"] == 1
    assert metadata[0]["student_id"] == STUDENT_ID
    assert len(_routed_pngs(workspace)) == 1


def test_route_scan_decode_qr_pdf_later_pages_process_after_failures(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source_pdf(tmp_path)
    non_pds_payload = "not a pds payload"
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _blank_image(),
            _make_qr_image(_valid_payload()),
            _make_qr_image(non_pds_payload),
        ),
    )

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    metadata = _review_metadata_records(workspace)
    categories = [record["failure_category"] for record in metadata]
    assert len(_routed_pngs(workspace)) == 1
    assert categories == ["payload_missing", "payload_schema_unsupported"]
    assert [record["source_page_number"] for record in metadata] == [1, 3]
    assert "Scan intake summary" in output
    assert "Pages attempted: 3" in output
    assert "Routed: 1" in output
    assert "Preserved for review: 2" in output
    assert (
        "You may assemble submissions for routed evidence now, but "
        "preserved failures should be reviewed before treating the batch "
        "as complete."
    ) in output
    assert f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}" in output


def test_route_scan_payload_mode_does_not_process_pdf_pages(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)

    def fail_pdf_conversion(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("payload mode should not convert PDF pages")

    monkeypatch.setattr(cli_routing, "iter_pdf_page_images", fail_pdf_conversion)

    assert main(["route-scan", str(source), "--payload", _valid_payload()]) == 0
    assert list(workspace.rglob("response_*.pdf"))
    assert not list(workspace.rglob("response_*.png"))


def test_route_scan_decode_qr_pdf_unknown_assignment_preserves_identity(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path)
    payload = _valid_payload(assignment_id=UNKNOWN_ASSIGNMENT_ID)
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(_make_qr_image(payload)),
    )

    assert main(["route-scan", str(source), "--decode-qr"]) == 0

    metadata = _review_metadata_records(workspace)
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "assignment_unknown"
    assert metadata[0]["assignment_id"] == UNKNOWN_ASSIGNMENT_ID
    assert metadata[0]["source_page_number"] == 1
