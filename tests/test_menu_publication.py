"""Teacher-menu tests for explicit Quillan publication management."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import quillan.assignment_workflows as assignment_workflows
import quillan.publication_menu as menu
from quillan.academic_result_publication import (
    publish_quillan_academic_results,
)
from quillan.assignment_picker import AssignmentChoice
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_academic_result_publication import _registered_manifest


def _choice(tmp_path: Path) -> AssignmentChoice:
    return AssignmentChoice(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        title="Unit Essay",
        path=tmp_path / "assignment.json",
    )


def _patch_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(menu, "resolve_workspace_root", lambda: tmp_path)
    import quillan.menu as root_menu

    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)


def _patch_assignment_sequence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    choices = iter((_choice(tmp_path), None))
    monkeypatch.setattr(
        menu,
        "_prompt_publication_assignment_choice",
        lambda _root: next(choices),
    )


def test_publication_assignment_selection_does_not_require_roster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[bool] = []

    def list_classes(
        _root: Path,
        *,
        require_roster: bool = True,
    ) -> tuple[SimpleNamespace, ...]:
        seen.append(require_roster)
        return (SimpleNamespace(class_id=CLASS_ID),)

    monkeypatch.setattr(menu, "list_class_folders", list_classes)
    monkeypatch.setattr(
        menu,
        "available_assignments",
        lambda _root, _class_id: (_choice(tmp_path),),
    )
    responses = iter(("1", "1"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    selected = menu._prompt_publication_assignment_choice(tmp_path)

    assert selected == _choice(tmp_path)
    assert seen == [False]


def test_publication_menu_requires_typed_publish_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registered_manifest(tmp_path)
    _patch_shell(monkeypatch, tmp_path)
    _patch_assignment_sequence(monkeypatch, tmp_path)
    called = False

    def publish(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("publish must not run without PUBLISH confirmation")

    monkeypatch.setattr(menu, "publish_quillan_academic_results", publish)
    responses = iter(("4", "NOPE", "9"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert menu.launch_academic_result_publication_menu() == 0
    assert called is False


def test_publication_menu_withdrawal_does_not_echo_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    _patch_shell(monkeypatch, tmp_path)
    _patch_assignment_sequence(monkeypatch, tmp_path)
    reason = "SECRET-MENU-WITHDRAWAL-REASON"
    responses = iter(
        (
            "7",
            published.publication.publication_id,
            reason,
            "WITHDRAW",
            "9",
        )
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert menu.launch_academic_result_publication_menu() == 0

    output = capsys.readouterr().out
    assert reason not in output
    assert "Operation: withdraw" in output
    assert "Withdrawn: yes" in output


def test_assignment_management_routes_option_seven_to_publication_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = 0

    def launch() -> int:
        nonlocal called
        called += 1
        return 0

    monkeypatch.setattr(menu, "launch_academic_result_publication_menu", launch)
    import quillan.menu as root_menu

    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)
    responses = iter(("7", "B"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert assignment_workflows.launch_assignment_menu() == 0
    assert called == 1
