"""Tests for the direct printable response packet CLI."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
import pytest

from quillan.cli import main
import quillan.cli_app.handlers.printable_responses as handlers
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)


def command(*extra: str) -> list[str]:
    return ["printable-responses", "generate", CLASS_ID, ASSIGNMENT_ID, *extra]


def test_help_surface_and_bare_namespace_do_not_resolve_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unexpected_resolution() -> Path:
        raise AssertionError("bare namespace resolved the workspace")

    monkeypatch.setattr(handlers, "resolve_workspace_root", unexpected_resolution)
    assert main(["printable-responses"]) == 0
    assert "generate" in capsys.readouterr().out

    for argv, expected in [
        (["--help"], "printable-responses"),
        (["printable-responses", "--help"], "generate"),
        (["printable-responses", "generate", "--help"], "--pages-per-student"),
    ]:
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 0
        assert expected in capsys.readouterr().out


def test_confirmation_and_page_count_are_parser_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_resolution() -> Path:
        raise AssertionError("invalid options resolved the workspace")

    monkeypatch.setattr(handlers, "resolve_workspace_root", unexpected_resolution)
    for argv in [
        command(),
        command("--yes", "--dry-run"),
        command("--yes", "--pages-per-student", "0"),
        ["printable-responses", "generate", CLASS_ID, "--yes"],
    ]:
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code != 0

    assert main(command("--overwrite", "--dry-run")) == 1


def test_dry_run_is_full_preflight_with_no_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_packet_workspace(tmp_path)
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)

    def no_render(*_args: object, **_kwargs: object) -> Path:
        raise AssertionError("dry run called the renderer")

    monkeypatch.setattr(
        "quillan.printable_response_packet.generate_printable_responses_for_roster",
        no_render,
    )
    assert main(command("--pages-per-student", "2", "--dry-run")) == 0

    output = capsys.readouterr().out
    assert "Printable response packet dry run:" in output
    assert "Students: 2" in output
    assert "Pages per student: 2" in output
    assert "Total packet pages: 4" in output
    assert "Existing target: no" in output
    assert "No files were written." in output
    assert str(tmp_path) not in output
    assert not (
        tmp_path / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID / "templates"
    ).exists()


def test_dry_run_reports_existing_target_without_touching_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_packet_workspace(tmp_path)
    packet = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "templates"
        / "printable_response_pages.pdf"
    )
    packet.parent.mkdir(parents=True)
    packet.write_bytes(b"existing synthetic bytes")
    before = packet.stat().st_mtime_ns
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)

    assert main(command("--dry-run")) == 0
    output = capsys.readouterr().out
    assert "Existing target: yes" in output
    assert "--overwrite --yes" in output
    assert packet.read_bytes() == b"existing synthetic bytes"
    assert packet.stat().st_mtime_ns == before


def test_generation_is_noninteractive_and_uses_default_page_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path, roster_path = write_packet_workspace(tmp_path)
    inputs_before = (assignment_path.read_bytes(), roster_path.read_bytes())
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        "builtins.input",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct command prompted for input")
        ),
    )

    assert main(command("--yes")) == 0
    packet = assignment_path.parent / "templates" / "printable_response_pages.pdf"
    assert packet.read_bytes().startswith(b"%PDF")
    assert len(PdfReader(str(packet)).pages) == 2
    assert (assignment_path.read_bytes(), roster_path.read_bytes()) == inputs_before
    output = capsys.readouterr().out
    assert "Pages per student: 1" in output
    assert "Total packet pages: 2" in output
    assert "Action: created" in output
    assert f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/templates/" in output
    assert str(tmp_path) not in output


def test_existing_target_error_and_successful_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path, _ = write_packet_workspace(tmp_path)
    packet = assignment_path.parent / "templates" / "printable_response_pages.pdf"
    packet.parent.mkdir(parents=True)
    packet.write_bytes(b"old synthetic packet")
    before = packet.stat().st_mtime_ns
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)

    assert main(command("--yes")) == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "--overwrite --yes" in output
    assert packet.read_bytes() == b"old synthetic packet"
    assert packet.stat().st_mtime_ns == before

    assert main(command("--overwrite", "--yes")) == 0
    assert packet.read_bytes().startswith(b"%PDF")
    assert "Action: replaced existing packet" in capsys.readouterr().out


def test_missing_assignment_fails_without_creating_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    assert main(command("--dry-run")) == 1
    assert "Error:" in capsys.readouterr().out
    assert not list(tmp_path.rglob("templates"))
