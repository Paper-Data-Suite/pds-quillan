"""Issue #412 teacher-menu feedback assembly coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.batch_feedback_assembly import (
    FeedbackAssemblyPlan,
    FeedbackAssemblyResult,
    FeedbackAssemblyStudentPlan,
)
from quillan.generated_output_opening import OpenedGeneratedOutput
from quillan.cli import main
from quillan.review_work_queue import (
    AssignmentReviewWorkQueue,
    ReviewWorkQueueItem,
    WORK_QUEUE_CATEGORIES,
)
import quillan.review_menu as review_menu
from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen
from tests.test_menu_export_actions import (
    _enter_assignment_review_actions,
    _exit_assignment_review_actions_to_main,
    _write_workspace,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _plan() -> FeedbackAssemblyPlan:
    return FeedbackAssemblyPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="whole_class",
        output="print",
        duplex_safe=False,
        roster_count=2,
        items=(
            FeedbackAssemblyStudentPlan(
                student_id="001",
                display_name="Avery Rivera",
                status="current",
                reason_code="current",
                source_relative_path="classes/c/a/001/exports/feedback.pdf",
                review_updated_at="2026-09-20T20:00:00+00:00",
                source_review_updated_at="2026-09-20T20:00:00+00:00",
                source_size=100,
                source_sha256="a" * 64,
                source_page_count=1,
            ),
            FeedbackAssemblyStudentPlan(
                student_id="002",
                display_name="Jordan Smith",
                status="stale",
                reason_code="feedback_pdf_stale",
                source_relative_path="classes/c/a/002/exports/feedback.pdf",
                review_updated_at="2026-09-20T20:01:00+00:00",
                source_review_updated_at="2026-09-20T20:00:00+00:00",
                source_size=None,
                source_sha256=None,
                source_page_count=None,
            ),
        ),
    )


def _result() -> FeedbackAssemblyResult:
    return FeedbackAssemblyResult(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="whole_class",
        output="print",
        duplex_safe=False,
        selected_count=2,
        included_student_ids=("001",),
        exclusions=(),
        print_packet_relative_path="classes/c/work/a/exports/feedback_batches/x/feedback_print_packet.pdf",
        sharing_bundle_relative_path=None,
        print_packet_page_count=1,
        sharing_bundle_pdf_count=None,
    )


def _queue() -> AssignmentReviewWorkQueue:
    items = (
        ReviewWorkQueueItem(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id="001",
            display_name="Avery Rivera",
            category="complete",
            reason_code="feedback_export_current",
            warnings=(),
        ),
        ReviewWorkQueueItem(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id="002",
            display_name="Jordan Smith",
            category="complete",
            reason_code="feedback_export_current",
            warnings=(),
        ),
    )
    return AssignmentReviewWorkQueue(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=items,
        counts=tuple(
            (category, sum(item.category == category for item in items))
            for category in WORK_QUEUE_CATEGORIES
        ),
        unrostered_student_ids=(),
        warnings=(),
    )


def test_menu_cancellation_after_preview_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        review_menu, "build_feedback_assembly_plan", lambda *a, **k: _plan()
    )
    monkeypatch.setattr(
        review_menu,
        "execute_feedback_assembly",
        lambda *a, **k: calls.append("execute"),
    )
    answers = iter(["1", "1", "n", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    review_menu._menu_feedback_assembly(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert calls == []
    assert "canceled; no files were written" in capsys.readouterr().out


def test_menu_selected_students_use_numbered_canonical_ids_in_input_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    executed: list[FeedbackAssemblyPlan] = []
    queue = _queue()

    monkeypatch.setattr(review_menu, "_load_review_work_queue", lambda *a: queue)

    def build(*args: object, **kwargs: object) -> FeedbackAssemblyPlan:
        captured.update(kwargs)
        return FeedbackAssemblyPlan(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            assignment_title="Synthetic Essay",
            scope="selected",
            output="bundle",
            duplex_safe=False,
            roster_count=2,
            items=_plan().items,
        )

    monkeypatch.setattr(review_menu, "build_feedback_assembly_plan", build)
    monkeypatch.setattr(
        review_menu,
        "execute_feedback_assembly",
        lambda root, plan: executed.append(plan),
    )
    answers = iter(["2", "2,1", "2", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    review_menu._menu_feedback_assembly(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert captured["scope"] == "selected"
    assert captured["student_ids"] == ("002", "001")
    assert "Jordan Smith" not in captured["student_ids"]
    assert "Avery Rivera" not in captured["student_ids"]
    assert executed == []
    output = capsys.readouterr().out
    assert "Feedback Batch Assembly Preview" in output
    assert "canceled; no files were written" in output


@pytest.mark.menu_density_workflow("feedback batch assembly")
def test_menu_previews_once_executes_once_and_opens_with_safe_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    plan = _plan()
    result = _result()
    executed: list[FeedbackAssemblyPlan] = []
    opened: list[str] = []
    monkeypatch.setattr(
        review_menu, "build_feedback_assembly_plan", lambda *a, **k: plan
    )
    def execute(root: Path, value: FeedbackAssemblyPlan) -> FeedbackAssemblyResult:
        executed.append(value)
        return result

    def open_folder(root: Path, path: str) -> OpenedGeneratedOutput:
        opened.append(path)
        return OpenedGeneratedOutput(
            Path(path), "classes/c/work/a/exports/feedback_batches/x"
        )

    monkeypatch.setattr(review_menu, "execute_feedback_assembly", execute)
    monkeypatch.setattr(review_menu, "open_generated_output_folder", open_folder)
    recorder = MenuScreenRecorder(
        _enter_assignment_review_actions()
        + ["g", "1", "1", "n", "yes", "2"]
        + _exit_assignment_review_actions_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    assert executed == [plan]
    assert opened == [result.print_packet_relative_path]
    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Feedback Batch Assembly Preview",
        required_text=("Ready: 1", "Excluded: 1", "feedback_pdf_stale"),
        forbidden_parent_text="5. View full diagnostic dashboard",
        parent_heading="Assignment Review Actions",
        result_heading="Feedback Batch Assembly Result",
        unrelated_previous_text="Assembly needed:",
    )
    assert "Opened output folder" in output
