"""Issue #384 menu integration tests for class-set student navigation."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

import quillan.review_menu as review_menu
from quillan.plain_paper_submission import create_plain_paper_submission
from quillan.review_record_paths import review_record_path
from quillan.review_student_navigation import (
    ReviewStudentNavigation,
    build_review_student_navigation,
)
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    TIMESTAMP,
    _review_record,
    _write_workspace,
)


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: tuple[str, ...]) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)


def test_next_student_moves_directly_without_picker_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("n", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert f"Student: Avery Rivera ({STUDENT_ID})" in output
    assert f"Student: Mina Patel ({SECOND_STUDENT_ID})" in output
    assert "Position: 1 of 2" in output
    assert f"N. Next student — Mina Patel ({SECOND_STUDENT_ID})" in output
    assert "Position: 2 of 2" in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
    assert "Select Student/Submission" not in output
    assert _snapshot(tmp_path) == before


def test_previous_student_moves_directly_in_roster_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("p", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Position: 2 of 2" in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
    assert "Position: 1 of 2" in output
    assert f"N. Next student — Mina Patel ({SECOND_STUDENT_ID})" in output


def test_next_needing_review_uses_same_forward_queue_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("w", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert (
        f"W. Next student needing review — Mina Patel ({SECOND_STUDENT_ID})"
        in output
    )
    assert "Position: 2 of 2" in output
    assert "W. Next student needing review — none later in roster" in output


def test_final_student_boundaries_are_visible_and_do_not_wrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "N. Next student — none (final roster student)" in output
    assert "W. Next student needing review — none later in roster" in output
    assert "Position: 2 of 2" in output


def test_navigation_rebuilds_from_current_queue_on_every_root_redraw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(tmp_path, monkeypatch)
    calls: list[str] = []

    def recording_builder(
        workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
    ) -> ReviewStudentNavigation:
        calls.append(student_id)
        return build_review_student_navigation(
            workspace_root, class_id, assignment_id, student_id
        )

    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation",
        recording_builder,
    )
    _inputs(monkeypatch, ("n", "p", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    assert calls == [STUDENT_ID, SECOND_STUDENT_ID, STUDENT_ID]


def test_existing_review_actions_keep_their_numbers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    for expected in (
        "1. Open submission evidence",
        "2. View current review details",
        "3. Review minimum requirements",
        "4. Review units and Focus Standard observations",
        "5. Overall Focus Standard ratings",
        "6. Compose Focus Standard feedback",
        "7. Manage submission pages",
        "8. Add teacher note",
        "9. Update review workflow state",
        "10. Export student feedback",
        "11. Refresh summary",
    ):
        assert expected in output


def test_canceled_teacher_note_is_not_written_or_carried_to_next_student(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("8", "b", "", "n", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Add note canceled." in output
    assert "Position: 2 of 2" in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
    assert _snapshot(tmp_path) == before


def test_routed_evidence_awaiting_assembly_root_keeps_navigation_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    synthetic_status = SimpleNamespace(
        student_statuses=(
            SimpleNamespace(
                student_id=SECOND_STUDENT_ID,
                manifest_path=None,
            ),
        )
    )
    monkeypatch.setattr(
        review_menu,
        "_load_submission_status",
        lambda *_args, **_kwargs: synthetic_status,
    )
    _inputs(monkeypatch, ("p", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert (
        "This student has routed evidence, but the review-ready submission record "
        "has not been assembled yet."
    ) in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
    assert "Position: 1 of 2" in output
    assert _snapshot(tmp_path) == before


def test_unrostered_selected_student_fails_closed_for_class_set_navigation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from quillan.review_student_navigation import ReviewStudentNavigationError

    _prepare(tmp_path, monkeypatch)
    diagnostic_student_id = "stu_unrostered_diagnostic"
    monkeypatch.setattr(
        review_menu,
        "_print_review_summary",
        lambda *_args, **_kwargs: print(f"Student: {diagnostic_student_id}"),
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ReviewStudentNavigationError("student is outside the canonical roster")
        ),
    )
    monkeypatch.setattr(
        review_menu,
        "_load_submission_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "plan_plain_paper_submission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("student is not rostered")
        ),
    )
    _inputs(monkeypatch, ("n", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, diagnostic_student_id
    ) == 0

    output = capsys.readouterr().out
    assert "Class-set navigation unavailable:" in output
    assert "Class-set navigation: unavailable" in output
    assert "Class-set navigation is unavailable for this selected student." in output
    assert "Position: 1 of 2" not in output
    assert "Position: 2 of 2" not in output


def test_completed_child_write_is_reflected_by_fresh_navigation_redraw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dataclasses import replace

    _prepare(tmp_path, monkeypatch)
    marker = tmp_path / "synthetic-explicit-child-write"
    real_builder = build_review_student_navigation
    calls: list[bool] = []

    def state_sensitive_builder(
        workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
    ) -> ReviewStudentNavigation:
        navigation = real_builder(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        changed = marker.exists()
        calls.append(changed)
        if not changed:
            return navigation
        return replace(
            navigation,
            current=replace(
                navigation.current,
                category="complete",
                reason_code="current_feedback_export_present",
            ),
            needs_work_count=max(0, navigation.needs_work_count - 1),
        )

    def explicit_child_write(*_args: object, **_kwargs: object) -> None:
        marker.write_text("saved", encoding="utf-8")

    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation",
        state_sensitive_builder,
    )
    monkeypatch.setattr(review_menu, "_menu_add_review_note", explicit_child_write)
    _inputs(monkeypatch, ("8", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert calls == [False, True]
    assert "Work state: minimum requirements pending" in output
    assert "Work state: complete" in output
    assert marker.read_text(encoding="utf-8") == "saved"


def test_unavailable_final_next_action_does_not_wrap_to_first_student(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("n", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "No next roster student; this is the final roster student." in output
    assert output.count("Position: 2 of 2") == 2
    assert "Position: 1 of 2" not in output


def test_plain_paper_student_participates_in_adjacent_navigation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    created = create_plain_paper_submission(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        SECOND_STUDENT_ID,
        created_at=TIMESTAMP,
    )
    manifest = json.loads(created.submission_manifest_path.read_text(encoding="utf-8"))
    assert manifest["module_details"]["submission_entry_method"] == "plain_paper_manual"
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("p", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Position: 2 of 2" in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
    assert "Position: 1 of 2" in output
    assert _snapshot(tmp_path) == before


def test_completed_teacher_note_save_is_retained_once_when_navigation_follows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    first_review_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    second_review_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    )
    record = _review_record()
    record["private_notes"] = []
    first_review_path.parent.mkdir(parents=True, exist_ok=True)
    first_review_path.write_text(json.dumps(record), encoding="utf-8")
    assert not second_review_path.exists()
    _inputs(monkeypatch, ("8", "Saved exactly once.", "", "n", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    persisted = json.loads(first_review_path.read_text(encoding="utf-8"))
    assert [note["text"] for note in persisted["private_notes"]] == [
        "Saved exactly once."
    ]
    assert not second_review_path.exists()
    output = capsys.readouterr().out
    assert "Position: 2 of 2" in output
    assert f"P. Previous student — Avery Rivera ({STUDENT_ID})" in output
