"""Issue #382 tests for ephemeral teacher class/assignment context."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from quillan.assignment_picker import (
    prompt_assignment_choice,
    prompt_assignment_choice_for_class,
)
from quillan.menu_context import (
    MenuSessionContext,
    exact_assignment_choice,
    print_session_context,
    revalidate_menu_context,
)
import quillan.menu as menu
import quillan.review_menu as review_menu
from quillan.menu_navigation import ReturnToMainMenu
from tests.menu_screen_recorder import MenuScreenRecorder


CLASS_ID = "english12_p3_synthetic"
OTHER_CLASS_ID = "english12_p4_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
OTHER_ASSIGNMENT_ID = "essay_02_synthetic"


def _assignment(assignment_id: str, title: str) -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": title,
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
        "basic_requirements": {},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": "2026-08-20T00:00:00+00:00",
        "updated_at": "2026-08-20T00:00:00+00:00",
        "module_details": {},
    }


def _write_class(root: Path, class_id: str) -> None:
    class_dir = root / "classes" / class_id
    class_dir.mkdir(parents=True, exist_ok=True)
    with (class_dir / "roster.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("class_id", "student_id", "last_name", "first_name", "period"))
        writer.writerow((class_id, "student_001", "Student", "Synthetic", "3"))


def _write_assignment(
    root: Path,
    class_id: str,
    assignment_id: str,
    title: str,
) -> Path:
    document = _assignment(assignment_id, title)
    document["class_ids"] = [class_id]
    path = (
        root
        / "classes"
        / class_id
        / "modules"
        / "quillan"
        / "work"
        / assignment_id
        / "assignment.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    _write_class(tmp_path, CLASS_ID)
    _write_class(tmp_path, OTHER_CLASS_ID)
    _write_assignment(tmp_path, CLASS_ID, ASSIGNMENT_ID, "Shared Title")
    _write_assignment(tmp_path, CLASS_ID, OTHER_ASSIGNMENT_ID, "Shared Title")
    return tmp_path


def test_context_invariants_and_class_change() -> None:
    with pytest.raises(ValueError, match="requires class"):
        MenuSessionContext(assignment_id=ASSIGNMENT_ID)

    context = MenuSessionContext()
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID

    context.activate_class(OTHER_CLASS_ID)
    assert context.class_id == OTHER_CLASS_ID
    assert context.assignment_id is None


def test_workspace_binding_preserves_same_root_and_clears_changed_root(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    context = MenuSessionContext()

    assert context.bind_workspace(first) is False
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    assert context.bind_workspace(first / ".") is False
    assert context.assignment_id == ASSIGNMENT_ID

    assert context.bind_workspace(second) is True
    assert context.class_id is None
    assert context.assignment_id is None


def test_exact_assignment_identity_never_falls_back_to_matching_title(
    workspace: Path,
) -> None:
    choice = exact_assignment_choice(workspace, CLASS_ID, ASSIGNMENT_ID)
    assert choice is not None
    assert choice.assignment_id == ASSIGNMENT_ID

    choice.path.unlink()
    assert exact_assignment_choice(workspace, CLASS_ID, ASSIGNMENT_ID) is None
    other = exact_assignment_choice(workspace, CLASS_ID, OTHER_ASSIGNMENT_ID)
    assert other is not None
    assert other.title == "Shared Title"


def test_stale_assignment_fails_closed_and_retains_valid_class(
    workspace: Path,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    choice = exact_assignment_choice(workspace, CLASS_ID, ASSIGNMENT_ID)
    assert choice is not None
    choice.path.unlink()

    result = revalidate_menu_context(context, workspace)

    assert result.assignment is None
    assert result.message is not None
    assert "no longer a valid canonical assignment" in result.message
    assert context.class_id == CLASS_ID
    assert context.assignment_id is None


def test_stale_class_fails_closed_and_clears_assignment(workspace: Path) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    (workspace / "classes" / CLASS_ID / "roster.csv").unlink()

    result = revalidate_menu_context(context, workspace)

    assert result.assignment is None
    assert result.message is not None
    assert context.class_id is None
    assert context.assignment_id is None


def test_assignment_in_class_picker_does_not_prompt_for_class(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    responses = iter(("1",))

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)

    choice = prompt_assignment_choice_for_class(workspace, CLASS_ID)

    assert choice is not None
    assert choice.assignment_id == ASSIGNMENT_ID
    assert prompts == ["Select assignment: "]


def test_review_assignment_selection_reuses_active_context_without_prompts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    prompts: list[str] = []
    responses = iter(("1", "1"))

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)

    first = review_menu._select_review_assignment(workspace, context)
    assert first is not None
    assert prompts == ["Select class: ", "Select assignment: "]
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID

    prompts.clear()
    second = review_menu._select_review_assignment(workspace, context)
    assert second is not None
    assert second.assignment_id == ASSIGNMENT_ID
    assert prompts == []


def test_class_only_review_context_requires_only_assignment_prompt(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_class(CLASS_ID)
    prompts: list[str] = []

    def choose_first_assignment(prompt: str = "") -> str:
        prompts.append(prompt)
        return "1"

    monkeypatch.setattr("builtins.input", choose_first_assignment)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)

    choice = review_menu._select_review_assignment(workspace, context)

    assert choice is not None
    assert prompts == ["Select assignment: "]
    assert context.assignment_id == ASSIGNMENT_ID


def test_context_rendering_shows_exact_ids_and_current_title(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)

    print_session_context(context)

    output = capsys.readouterr().out
    assert "Active context" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID} - Shared Title" in output


def test_context_reads_do_not_write_workspace(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    files_before = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)

    assert revalidate_menu_context(context, workspace).assignment is not None
    print_session_context(context)
    capsys.readouterr()

    files_after = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    assert files_after == files_before


def test_known_review_handoff_updates_context_only_for_exact_valid_target(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    called: list[tuple[Path, str, str]] = []

    def record_launch(root: Path, class_id: str, assignment_id: str) -> int:
        called.append((root, class_id, assignment_id))
        return 0

    monkeypatch.setattr(
        review_menu,
        "_launch_assignment_review_actions",
        record_launch,
    )

    result = review_menu.launch_assignment_review_actions(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        session_context=context,
    )

    assert result == 0
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID
    assert called == [(workspace, CLASS_ID, ASSIGNMENT_ID)]


def test_invalid_known_review_handoff_does_not_replace_existing_context(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    monkeypatch.setattr(
        review_menu,
        "_launch_assignment_review_actions",
        lambda *_args: pytest.fail("invalid target must not launch review"),
    )

    result = review_menu.launch_assignment_review_actions(
        workspace,
        OTHER_CLASS_ID,
        "missing_assignment",
        session_context=context,
    )

    assert result == 1
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID
    assert "not a valid canonical assignment" in capsys.readouterr().out


def test_context_switch_cancellation_preserves_previous_pair(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    responses = iter(("2", "b", "b"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(review_menu, "_workspace_root", lambda: workspace)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("quillan.menu.pause_for_user", lambda: None)

    review_menu._manage_active_context(context)

    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID


def test_clear_assignment_retains_class_for_next_selection(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    responses = iter(("3", "b"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(review_menu, "_workspace_root", lambda: workspace)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("quillan.menu.pause_for_user", lambda: None)

    review_menu._manage_active_context(context)

    assert context.class_id == CLASS_ID
    assert context.assignment_id is None



def test_recorder_context_prompt_cost_matches_issue_382_targets(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    recorder = MenuScreenRecorder(["1", "1", "1", "1", "1"])
    recorder.install(monkeypatch)

    before = len(recorder.prompts)
    assert review_menu._select_review_assignment(workspace, context) is not None
    first_prompts = recorder.prompts[before:]
    assert [item.prompt for item in first_prompts] == [
        "Select class: ",
        "Select assignment: ",
    ]

    before = len(recorder.prompts)
    assert review_menu._select_review_assignment(workspace, context) is not None
    assert recorder.prompts[before:] == []

    context.clear_assignment()
    before = len(recorder.prompts)
    assert review_menu._select_review_assignment(workspace, context) is not None
    assert [item.prompt for item in recorder.prompts[before:]] == [
        "Select assignment: ",
    ]

    context.clear_selection()
    before = len(recorder.prompts)
    assert review_menu._select_review_assignment(workspace, context) is not None
    assert [item.prompt for item in recorder.prompts[before:]] == [
        "Select class: ",
        "Select assignment: ",
    ]


def test_standalone_source_picker_does_not_mutate_active_session_context(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    responses = iter(("1", "2"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)

    source = prompt_assignment_choice(workspace)

    assert source is not None
    assert source.assignment_id == OTHER_ASSIGNMENT_ID
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID


def test_return_to_main_menu_reuses_same_session_context(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MenuSessionContext()
    context.bind_workspace(workspace)
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    responses = iter(("2", "q"))
    seen: list[MenuSessionContext] = []

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr(
        "pds_core.workspace.resolve_workspace_root", lambda: workspace
    )

    def return_to_main(received: MenuSessionContext | None = None) -> None:
        assert received is context
        seen.append(received)
        raise ReturnToMainMenu

    monkeypatch.setattr(menu, "launch_review_student_work_menu", return_to_main)

    result = menu.launch_menu(
        lambda: 0,
        lambda _path: 0,
        lambda: 0,
        lambda: 0,
        context,
    )

    assert result == 0
    assert seen == [context]
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID
