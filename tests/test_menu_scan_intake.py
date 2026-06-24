"""Tests for the teacher-facing QR scan intake menu workflow."""

from __future__ import annotations

from collections.abc import Iterator
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

from quillan.cli import main
import quillan.cli_app.handlers.routing as cli_routing
from quillan.payloads import build_response_payload
from quillan.pdf_pages import PdfPageImage

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(cli_routing, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _menu_input(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _write_workspace(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / ASSIGNMENT_ID
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
        "assignment_id": ASSIGNMENT_ID,
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


def _valid_payload(
    *,
    student_id: str = STUDENT_ID,
    page: int = 2,
) -> str:
    return build_response_payload(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
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


def _blank_image() -> NDArray[np.uint8]:
    return np.full((550, 425, 3), 255, dtype=np.uint8)


def _pdf_pages(*images: object) -> list[PdfPageImage]:
    return [
        PdfPageImage(page_number=page_number, image=image)
        for page_number, image in enumerate(images, start=1)
    ]


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


def test_main_menu_exposes_scan_intake_option(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "4. Scan Intake / Route Paper Responses" in output


def test_menu_scan_intake_empty_input_cancels(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["4", "  ", "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Scan Intake / Route Paper Responses" in output
    assert "Scan intake canceled. No scan files were routed." in output
    assert "Goodbye." in output


def test_menu_scan_intake_invalid_path_does_not_create_review_metadata(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_source = workspace / "missing-scan.pdf"
    _menu_input(monkeypatch, ["4", str(missing_source), "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert f"Error: scan source does not exist: {missing_source}" in output
    assert not (workspace / "scans" / "review").exists()


def test_menu_scan_intake_with_quoted_qr_image_routes_and_prints_next_step(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "synthetic response.png"
    _write_qr_image(source, _valid_payload())
    original_bytes = source.read_bytes()
    _menu_input(monkeypatch, ["4", f'  "{source}"  ', "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert source.read_bytes() == original_bytes
    assert "Scan intake summary" in output
    assert "Sources processed: 1" in output
    assert "Pages attempted: 1" in output
    assert "Routed: 1" in output
    assert "Review required: no" in output
    assert "Run submission assembly for newly routed evidence:" in output
    assert f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}" in output
    assert not list(workspace.rglob("submission.json"))
    assert not list(workspace.rglob("review.json"))


def test_menu_scan_intake_pdf_uses_existing_qr_page_intake(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "responses.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload(student_id=STUDENT_ID, page=1)),
            _make_qr_image(_valid_payload(student_id=SECOND_STUDENT_ID, page=2)),
        ),
    )
    _menu_input(monkeypatch, ["4", str(source), "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 2
    assert "Processing PDF:" in output
    assert "Pages attempted: 2" in output
    assert "Routed: 2" in output
    assert (
        f"quillan assemble-submissions {CLASS_ID} {ASSIGNMENT_ID}  "
        "(2 routed pages)"
    ) in output


def test_menu_scan_intake_mixed_pdf_prints_review_warning(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mixed.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    monkeypatch.setattr(
        cli_routing,
        "iter_pdf_page_images",
        lambda _source: _pdf_pages(
            _make_qr_image(_valid_payload()),
            _blank_image(),
        ),
    )
    _menu_input(monkeypatch, ["4", str(source), "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Routed: 1" in output
    assert "Preserved for review: 1" in output
    assert "Review required: yes" in output
    assert "- payload_missing: 1" in output
    assert (
        "preserved failures should be reviewed before treating the batch "
        "as complete."
    ) in output


def test_menu_scan_intake_folder_processes_supported_files_and_skips_unsupported(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    _write_qr_image(folder / "response.png", _valid_payload())
    (folder / "notes.txt").write_text("ignore me", encoding="utf-8")
    _menu_input(monkeypatch, ["4", str(folder), "", "7"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Processing folder:" in output
    assert "Sources processed: 1" in output
    assert "Skipped unsupported files: 1" in output
