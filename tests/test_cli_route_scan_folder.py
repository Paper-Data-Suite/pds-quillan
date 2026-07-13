"""Focused tests for folder-based QR scan intake."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
from pds_core.scan_failure_metadata import validate_routing_failure_metadata
import pytest
import qrcode
from qrcode.image.pil import PilImage

from quillan.cli import main
import quillan.cli_app.handlers.routing as cli_routing
from quillan.payloads import build_response_payload
from quillan.pdf_pages import PdfPageConversionError, PdfPageConversionFailure
from quillan.pdf_pages import PdfPageImage
from quillan.routing_review import RoutingReviewError

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
SECOND_ASSIGNMENT_ID = "memoir_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
UNKNOWN_STUDENT_ID = "stu_9999"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(cli_routing, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _write_workspace(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    assignments_dir = class_dir / "assignments"
    assignments_dir.mkdir(parents=True)

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

    for assignment_id in (ASSIGNMENT_ID, SECOND_ASSIGNMENT_ID):
        assignment_dir = assignments_dir / assignment_id
        assignment_dir.mkdir()
        assignment = {
            "schema_version": "2",
            "module": "quillan",
            "record_type": "assignment",
            "assignment_id": assignment_id,
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


def _write_qr_image(path: Path, payload: str) -> None:
    assert cv2.imwrite(str(path), _make_qr_image(payload))


def _blank_image(path: Path) -> None:
    blank = np.full((550, 425, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(path), blank)


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
            / "assignments"
            / ASSIGNMENT_ID
            / "scans"
        ).glob("response_*.png")
    )


def test_route_scan_decode_qr_folder_routes_supported_images_in_order(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _write_qr_image(folder / "b_scan.png", _valid_payload(student_id=SECOND_STUDENT_ID))
    _write_qr_image(folder / "A_scan.png", _valid_payload(student_id=STUDENT_ID))

    result = main(["route-scan", str(folder), "--decode-qr"])

    output = capsys.readouterr().out
    assert result == 0
    assert len(_routed_pngs(workspace)) == 2
    assert output.index("Source 1: A_scan.png") < output.index("Source 2: b_scan.png")
    assert "Sources processed: 2" in output
    assert "Pages attempted: 2" in output
    assert "Routed: 2" in output
    assert "Skipped unsupported files: 0" in output
    assert (
        f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}  "
        "(2 routed pages)"
    ) in output


def test_route_scan_decode_qr_folder_prints_sorted_assembly_targets(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _write_qr_image(
        folder / "memoir.png",
        _valid_payload(assignment_id=SECOND_ASSIGNMENT_ID),
    )
    _write_qr_image(folder / "essay.png", _valid_payload())

    assert main(["route-scan", str(folder), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    first_command = f"- quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}"
    second_command = (
        f"- quillan assemble-submissions {CLASS_ID} {SECOND_ASSIGNMENT_ID}"
    )
    assert "Next steps:" in output
    assert first_command in output
    assert second_command in output
    assert output.index(first_command) < output.index(second_command)
    assert not list(workspace.rglob("submission.json"))


def test_route_scan_decode_qr_folder_processes_supported_pdfs(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    source = folder / "responses.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(_make_qr_image(_valid_payload())),
    )

    assert main(["route-scan", str(folder), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Sources processed: 1" in output
    assert "Pages attempted: 1" in output
    assert "Routed: 1" in output


def test_route_scan_decode_qr_folder_skips_unsupported_files(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _write_qr_image(folder / "response.jpg", _valid_payload())
    (folder / "notes.txt").write_text("ignore me", encoding="utf-8")
    (folder / "Thumbs.db").write_bytes(b"synthetic")

    assert main(["route-scan", str(folder), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Skipped unsupported files: 2" in output


def test_route_scan_decode_qr_folder_empty_returns_clear_error(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()

    assert main(["route-scan", str(folder), "--decode-qr"]) == 1

    output = capsys.readouterr().out
    assert f"Error: no supported scan files found in folder: {folder}" in output
    assert not _routed_pngs(workspace)


def test_route_scan_payload_mode_rejects_folder(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()

    assert main(["route-scan", str(folder), "--payload", _valid_payload()]) == 1

    output = capsys.readouterr().out
    assert "--payload route-scan mode requires a source file" in output
    assert not _routed_pngs(workspace)


def test_route_scan_decode_qr_folder_preserved_failure_continues(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _blank_image(folder / "blank.png")
    _write_qr_image(folder / "valid.png", _valid_payload())

    assert main(["route-scan", str(folder), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    metadata = _review_metadata_records(workspace)
    assert len(_routed_pngs(workspace)) == 1
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "payload_missing"
    assert "Sources processed: 2" in output
    assert "Routed: 1" in output
    assert "Preserved for review: 1" in output
    assert "Review required: yes" in output
    assert "- payload_missing: 1" in output
    assert (
        "You may assemble submissions for routed evidence now, but "
        "preserved failures should be reviewed before treating the batch "
        "as complete."
    ) in output
    assert f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}" in output


def test_route_scan_decode_qr_folder_pdf_conversion_failure_continues(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    bad_pdf = folder / "bad.pdf"
    good_pdf = folder / "good.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4\nbad\n%%EOF\n")
    good_pdf.write_bytes(b"%PDF-1.4\ngood\n%%EOF\n")

    def convert(source: Path) -> list[PdfPageImage]:
        if source.name == "bad.pdf":
            raise PdfPageConversionError(
                PdfPageConversionFailure(
                    failure_category="source_unreadable",
                    failure_message="Synthetic conversion failure.",
                    module_details={"failure_origin": "pdf_conversion"},
                )
            )
        return _pdf_pages(_make_qr_image(_valid_payload()))

    monkeypatch.setattr(cli_routing, "iter_pdf_page_images", convert)

    assert main(["route-scan", str(folder), "--decode-qr"]) == 0

    output = capsys.readouterr().out
    metadata = _review_metadata_records(workspace)
    assert len(_routed_pngs(workspace)) == 1
    assert len(metadata) == 1
    assert metadata[0]["failure_category"] == "source_unreadable"
    assert "Sources processed: 2" in output
    assert "Routed: 1" in output
    assert "Preserved for review: 1" in output
    assert "- source_unreadable: 1" in output


def test_route_scan_decode_qr_folder_unpreserved_failure_exits_one(
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _blank_image(folder / "blank.png")
    _write_qr_image(folder / "valid.png", _valid_payload())

    def fail_preservation(*_args: object, **_kwargs: object) -> object:
        raise RoutingReviewError("Synthetic preservation failure.")

    monkeypatch.setattr(
        cli_routing,
        "preserve_decode_failure_for_review",
        fail_preservation,
    )

    assert main(["route-scan", str(folder), "--decode-qr"]) == 1

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Sources processed: 2" in output
    assert "Routed: 1" in output
    assert "Failed: 1" in output
    assert "- review_preservation_failed: 1" in output
