"""Tests for direct Academic Work Registration CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.academic_work as handlers
from quillan.work_paths import quillan_work_paths


def _assignment() -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": "essay1",
        "title": "Unit Essay",
        "class_ids": ["class1"],
        "writing_type": "literary_analysis",
        "student_prompt": "Analyze the text.",
        "standards_profile_id": "ela_profile",
        "focus_standard_ids": ["njsls-ela:W.AW.9-10.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_4_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."},
                {"value": 2, "label": "Approaching", "description": "Approaching."},
                {"value": 3, "label": "Meeting", "description": "Meeting."},
                {"value": 4, "label": "Exceeding", "description": "Exceeding."},
            ],
        },
        "basic_requirements": {},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-08-01T00:00:00+00:00",
        "module_details": {},
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    paths = quillan_work_paths(tmp_path, "class1", "essay1")
    paths.work_root.mkdir(parents=True)
    paths.assignment_path.write_text(json.dumps(_assignment()), encoding="utf-8")
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _identity() -> list[str]:
    return ["--class-id", "class1", "--assignment-id", "essay1"]


def test_academic_work_help_surface(capsys: pytest.CaptureFixture[str]) -> None:
    for argv, expected in [
        (["--help"], "academic-work"),
        (["academic-work", "--help"], "register"),
        (["academic-work", "show", "--help"], "--class-id"),
        (["academic-work", "register", "--help"], "--academic-intent"),
        (["academic-work", "update", "--help"], "--expected-current-revision"),
    ]:
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 0
        captured = capsys.readouterr()
        assert expected in captured.out + captured.err


def test_show_register_replay_and_update(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["academic-work", "show", *_identity()]) == 1
    assert "registration status: not registered" in capsys.readouterr().out

    register = [
        "academic-work",
        "register",
        *_identity(),
        "--academic-intent",
        "formative",
        "--lifecycle",
        "planned",
    ]
    assert main(register) == 0
    first = capsys.readouterr().out
    assert "disposition: created" in first
    assert "registration revision: 1" in first
    assert "contract_version=2" in first

    assert main(register) == 0
    assert "disposition: existing" in capsys.readouterr().out

    update = [
        "academic-work",
        "update",
        *_identity(),
        "--academic-intent",
        "summative",
        "--lifecycle",
        "active",
        "--expected-current-revision",
        "1",
    ]
    assert main(update) == 0
    updated = capsys.readouterr().out
    assert "disposition: updated" in updated
    assert "registration revision: 2" in updated
    assert main(["academic-work", "show", *_identity()]) == 0
    shown = capsys.readouterr().out
    assert "academic intent: summative" in shown
    assert "lifecycle: active" in shown


def test_register_never_silently_updates(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(
        [
            "academic-work",
            "register",
            *_identity(),
            "--academic-intent",
            "formative",
            "--lifecycle",
            "planned",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        [
            "academic-work",
            "register",
            *_identity(),
            "--academic-intent",
            "summative",
            "--lifecycle",
            "planned",
        ]
    ) == 1
    captured = capsys.readouterr()
    assert "Error: academic-work registration failed" in captured.err
    assert "use the update service" in captured.err


def test_cli_rejects_invalid_vocabulary_and_revision(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as invalid_intent:
        main(
            [
                "academic-work",
                "register",
                *_identity(),
                "--academic-intent",
                "exam",
                "--lifecycle",
                "active",
            ]
        )
    assert invalid_intent.value.code == 2
    capsys.readouterr()

    with pytest.raises(SystemExit) as invalid_revision:
        main(
            [
                "academic-work",
                "update",
                *_identity(),
                "--academic-intent",
                "summative",
                "--lifecycle",
                "active",
                "--expected-current-revision",
                "0",
            ]
        )
    assert invalid_revision.value.code == 2


def test_cli_rejects_duplicate_and_unknown_options(workspace: Path) -> None:
    with pytest.raises(SystemExit) as duplicate:
        main(
            [
                "academic-work",
                "show",
                *_identity(),
                "--class-id",
                "class1",
            ]
        )
    assert duplicate.value.code == 2

    with pytest.raises(SystemExit) as unknown:
        main(["academic-work", "show", *_identity(), "--mystery", "value"])
    assert unknown.value.code == 2


def test_missing_assignment_fails_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    result = main(
        [
            "academic-work",
            "register",
            *_identity(),
            "--academic-intent",
            "formative",
            "--lifecycle",
            "active",
        ]
    )
    assert result == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert "Error: academic-work registration failed" in captured.err
    assert not (tmp_path / "registry").exists()
