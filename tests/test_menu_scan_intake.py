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
from quillan.intake_assembly import IntakeAssemblyTarget
from quillan.menu import handle_scan_post_route_menu
from quillan.menu_navigation import QuitQuillan, ReturnToMainMenu
from quillan.payloads import build_response_payload
from quillan.pdf_pages import PdfPageImage
from quillan.submission_status import AssignmentSubmissionStatus

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


def _post_route_target() -> IntakeAssemblyTarget:
    return IntakeAssemblyTarget(CLASS_ID, ASSIGNMENT_ID, 1)


def _assignment_status(
    *,
    manifests: tuple[str, ...] = (),
    routed: tuple[str, ...] = (STUDENT_ID,),
    unassembled: tuple[Path, ...] = (),
) -> AssignmentSubmissionStatus:
    return AssignmentSubmissionStatus(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        students_with_manifests=manifests,
        students_with_routed_evidence=routed,
        students_without_manifests=tuple(
            student_id for student_id in routed if student_id not in manifests
        ),
        unassembled_routed_files=unassembled,
        unused_duplicate_routed_files=(),
        skipped_routed_files=(),
        student_statuses=(),
    )


def test_post_route_menu_pre_assembly_wording(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(),
    )
    _menu_input(monkeypatch, ["b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert "Scan Intake / Route Paper Responses" in output
    assert "Submission records are required before review." in output
    assert "Assemble submissions now" in output
    assert "View submission status" in output


def test_post_route_menu_recomputes_status_after_assembly(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statuses = iter(
        [
            _assignment_status(),
            _assignment_status(
                manifests=(STUDENT_ID,),
                routed=(STUDENT_ID,),
            ),
        ]
    )
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: next(statuses),
    )
    monkeypatch.setattr(
        "quillan.menu.assemble_assignment_submissions",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "quillan.menu.print_assignment_submission_assembly",
        lambda *_args, **_kwargs: print("Assembly complete."),
    )
    clear_calls: list[str] = []
    monkeypatch.setattr(
        "quillan.menu.clear_screen",
        lambda: clear_calls.append("clear"),
    )
    _menu_input(monkeypatch, ["1", "", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert clear_calls == ["clear", "clear"]
    assert "Assemble Submissions" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Press Enter to return to the post-route menu..." in output
    after_assembly = output.split("Assembly complete.", maxsplit=1)[1]
    assert "Submission records have been assembled" in after_assembly
    assert "ready for review" in after_assembly
    assert "Submission records are required before review." not in after_assembly
    assert "Assemble submissions now" not in after_assembly
    assert "Reassemble submissions" in after_assembly


def test_post_route_menu_ready_state_offers_review(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_targets: list[tuple[Path, str, str]] = []

    def fake_launch_review(root: Path, class_id: str, assignment_id: str) -> int:
        reviewed_targets.append((root, class_id, assignment_id))
        return 0

    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(
            manifests=(STUDENT_ID,),
            routed=(STUDENT_ID,),
        ),
    )
    monkeypatch.setattr(
        "quillan.review_menu.launch_assignment_review_actions",
        fake_launch_review,
    )
    _menu_input(monkeypatch, ["2", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert "Review student work" in output
    assert reviewed_targets == [(workspace, CLASS_ID, ASSIGNMENT_ID)]


def test_post_route_menu_partial_state_wording(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(
            manifests=(STUDENT_ID,),
            routed=(STUDENT_ID, SECOND_STUDENT_ID),
            unassembled=(workspace / "unassembled.png",),
        ),
    )
    _menu_input(monkeypatch, ["b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert "Some submission records have been assembled" in output
    assert "routed evidence still needs assembly" in output
    assert "Assemble remaining submissions" in output
    assert "Review student work" in output


def test_post_route_menu_view_status_uses_existing_status_output(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(),
    )
    clear_calls: list[str] = []
    monkeypatch.setattr(
        "quillan.menu.clear_screen",
        lambda: clear_calls.append("clear"),
    )
    _menu_input(monkeypatch, ["2", "", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert clear_calls == ["clear", "clear"]
    assert "Submission Status" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Press Enter to return to the post-route menu..." in output
    status_heading_index = output.index("Submission Status")
    status_report_index = output.index(
        f"Submission status for assignment {ASSIGNMENT_ID}"
    )
    assert status_heading_index < status_report_index
    assert "Students with routed evidence: 1" in output
    after_status = output.split(
        "Press Enter to return to the post-route menu...",
        maxsplit=1,
    )[1]
    assert "Scan Intake / Route Paper Responses" in after_status
    assert "Submission records are required before review." in after_status


def test_post_route_ready_state_reassemble_uses_clean_action_screen(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(
            manifests=(STUDENT_ID,),
            routed=(STUDENT_ID,),
        ),
    )
    monkeypatch.setattr(
        "quillan.menu.assemble_assignment_submissions",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "quillan.menu.print_assignment_submission_assembly",
        lambda *_args, **_kwargs: print("Reassembly complete."),
    )
    clear_calls: list[str] = []
    monkeypatch.setattr(
        "quillan.menu.clear_screen",
        lambda: clear_calls.append("clear"),
    )
    _menu_input(monkeypatch, ["3", "", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert clear_calls == ["clear", "clear"]
    assert "Assemble Submissions" in output
    assert "Reassembly complete." in output
    assert "Press Enter to return to the post-route menu..." in output


def test_post_route_partial_state_assemble_remaining_uses_clean_action_screen(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(
            manifests=(STUDENT_ID,),
            routed=(STUDENT_ID, SECOND_STUDENT_ID),
            unassembled=(workspace / "unassembled.png",),
        ),
    )
    monkeypatch.setattr(
        "quillan.menu.assemble_assignment_submissions",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "quillan.menu.print_assignment_submission_assembly",
        lambda *_args, **_kwargs: print("Remaining submissions assembled."),
    )
    clear_calls: list[str] = []
    monkeypatch.setattr(
        "quillan.menu.clear_screen",
        lambda: clear_calls.append("clear"),
    )
    _menu_input(monkeypatch, ["1", "", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert clear_calls == ["clear", "clear"]
    assert "Assemble Submissions" in output
    assert "Remaining submissions assembled." in output
    assert "Some submission records have been assembled" in output


def test_post_route_review_action_clears_before_launching_review(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def fake_clear_screen() -> None:
        events.append("clear")

    def fake_launch_review(_root: Path, _class_id: str, _assignment_id: str) -> int:
        events.append("review")
        return 0

    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(
            manifests=(STUDENT_ID,),
            routed=(STUDENT_ID,),
        ),
    )
    monkeypatch.setattr("quillan.menu.clear_screen", fake_clear_screen)
    monkeypatch.setattr(
        "quillan.review_menu.launch_assignment_review_actions",
        fake_launch_review,
    )
    _menu_input(monkeypatch, ["2", "b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    assert events == ["clear", "review", "clear"]


def test_post_route_menu_back_returns(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(),
    )
    _menu_input(monkeypatch, ["b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])


def test_post_route_menu_main_menu_navigation_is_unchanged(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(),
    )
    _menu_input(monkeypatch, ["m"])

    with pytest.raises(ReturnToMainMenu):
        handle_scan_post_route_menu(workspace, [_post_route_target()])


def test_post_route_menu_quit_navigation_is_unchanged(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        lambda *_args, **_kwargs: _assignment_status(),
    )
    _menu_input(monkeypatch, ["q"])

    with pytest.raises(QuitQuillan):
        handle_scan_post_route_menu(workspace, [_post_route_target()])


def test_post_route_menu_status_error_falls_back_safely(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_status_error(*_args: object, **_kwargs: object) -> None:
        raise ValueError("synthetic status failure")

    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        raise_status_error,
    )
    _menu_input(monkeypatch, ["b"])

    handle_scan_post_route_menu(workspace, [_post_route_target()])

    output = capsys.readouterr().out
    assert "Submission status could not be loaded." in output
    assert "Error: synthetic status failure" in output
    assert "Try assembling submissions" in output
    assert "Return to Scan Intake" in output
    assert "Traceback" not in output


def test_post_route_multi_target_lists_status_labels(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_target = IntakeAssemblyTarget("english12_p4_synthetic", ASSIGNMENT_ID, 1)

    def status_for_target(
        _workspace: Path,
        class_id: str,
        _assignment_id: str,
    ) -> AssignmentSubmissionStatus:
        if class_id == CLASS_ID:
            return _assignment_status()
        return AssignmentSubmissionStatus(
            class_id=class_id,
            assignment_id=ASSIGNMENT_ID,
            students_with_manifests=(STUDENT_ID,),
            students_with_routed_evidence=(STUDENT_ID,),
            students_without_manifests=(),
            unassembled_routed_files=(),
            unused_duplicate_routed_files=(),
            skipped_routed_files=(),
            student_statuses=(),
        )

    monkeypatch.setattr(
        "quillan.menu.list_assignment_submission_status",
        status_for_target,
    )
    _menu_input(monkeypatch, ["b"])

    handle_scan_post_route_menu(workspace, [_post_route_target(), second_target])

    output = capsys.readouterr().out
    assert f"Class: {CLASS_ID}; Assignment: {ASSIGNMENT_ID} - needs assembly" in output
    assert (
        "Class: english12_p4_synthetic; "
        f"Assignment: {ASSIGNMENT_ID} - ready for review"
    ) in output


def test_review_student_work_exposes_scan_intake_option(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["2", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "2. Scan Intake / Route Paper Responses" in output


def test_menu_scan_intake_empty_input_cancels(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["2", "2", "  ", "", "3", "6"])

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
    _menu_input(monkeypatch, ["2", "2", str(missing_source), "", "b", "3", "6"])

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
    _menu_input(monkeypatch, ["2", "2", f'  "{source}"  ', "", "b", "3", "6"])

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
    _menu_input(monkeypatch, ["2", "2", str(source), "", "b", "3", "6"])

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
    _menu_input(monkeypatch, ["2", "2", str(source), "", "b", "3", "6"])

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
    _menu_input(monkeypatch, ["2", "2", str(folder), "", "b", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert len(_routed_pngs(workspace)) == 1
    assert "Processing folder:" in output
    assert "Sources processed: 1" in output
    assert "Skipped unsupported files: 1" in output
