"""CLI parser and handler coverage for review workflow state."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import review_workflow as handlers


@pytest.mark.parametrize(
    "argv",
    [["--help"], ["review-workflow", "--help"], ["review-workflow", "set-state", "--help"]],
)
def test_review_workflow_help_succeeds(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 0


def test_bare_namespace_prints_help_without_resolving_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: pytest.fail("resolved"))
    assert main(["review-workflow"]) == 0
    assert "set-state" in capsys.readouterr().out


def test_yes_is_required_before_workspace_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: pytest.fail("resolved"))
    with pytest.raises(SystemExit) as error:
        main([
            "review-workflow", "set-state", "class_1", "assignment_1", "student_1",
            "--state", "not_started",
        ])
    assert error.value.code == 2


def test_handler_is_direct_and_prints_service_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from quillan.review_workflow_state import UpdatedReviewWorkflowState

    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: Path("workspace"))
    monkeypatch.setattr(
        handlers,
        "set_review_workflow_state",
        lambda *args: UpdatedReviewWorkflowState(
            "class_1", "assignment_1", "student_1", Path("review.json"),
            "classes/class_1/review.json", None, "not_started", True,
            "2026-07-13T13:00:00+00:00",
        ),
    )
    assert main([
        "review-workflow", "set-state", "class_1", "assignment_1", "student_1",
        "--state", "not_started", "--yes",
    ]) == 0
    output = capsys.readouterr().out
    assert "Updated review workflow state:" in output
    assert "Previous workflow state: no review record" in output
