"""Import-isolated direct printable-response handler tests."""

from argparse import Namespace
from pathlib import Path

from pypdf import PdfReader
import pytest

import quillan.cli_app.handlers.printable_responses as handlers
from quillan.printable_response_generation import PrintableResponseGenerationError
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)


def args(**overrides: object) -> Namespace:
    values = {
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "pages_per_student": 1,
        "overwrite": False,
        "yes": False,
        "dry_run": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_confirmation_rules_do_not_resolve_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "resolve_workspace_root",
        lambda: (_ for _ in ()).throw(AssertionError("resolved workspace")),
    )
    assert handlers.handle_printable_responses_generate(args()) == 1
    assert handlers.handle_printable_responses_generate(
        args(overwrite=True, dry_run=True)
    ) == 1


def test_direct_dry_run_is_nonmutating_and_aggregate_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_packet_workspace(tmp_path)
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    before = set(tmp_path.rglob("*"))
    assert handlers.handle_printable_responses_generate(
        args(dry_run=True, pages_per_student=2)
    ) == 0
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Planned issuances: 2" in output
    assert "Planned routes: 4" in output
    assert "No files were written." in output
    assert str(tmp_path) not in output
    assert set(tmp_path.rglob("*")) == before


def test_direct_generation_never_opens_and_reports_verified_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path, _ = write_packet_workspace(tmp_path)
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        "builtins.input",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct generation prompted or opened")
        ),
    )
    assert handlers.handle_printable_responses_generate(args(yes=True)) == 0
    packet = assignment_path.parent / "templates" / "printable_response_pages.pdf"
    assert len(PdfReader(str(packet)).pages) == 2
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Created routes: 2" in output
    assert "Verified routes: 2" in output
    assert "Installed: yes" in output


def test_existing_output_requires_overwrite_and_regenerates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment_path, _ = write_packet_workspace(tmp_path)
    packet = assignment_path.parent / "templates" / "printable_response_pages.pdf"
    packet.parent.mkdir(parents=True)
    packet.write_bytes(b"old synthetic packet")
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    assert handlers.handle_printable_responses_generate(args(yes=True)) == 1
    assert packet.read_bytes() == b"old synthetic packet"
    assert handlers.handle_printable_responses_generate(
        args(yes=True, overwrite=True)
    ) == 0
    assert packet.read_bytes().startswith(b"%PDF")


def test_direct_governed_packet_error_is_clean_and_never_opens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_packet_workspace(tmp_path)
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        handlers,
        "plan_printable_response_packet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PrintableResponseGenerationError("synthetic governed planning failure")
        ),
    )
    assert handlers.handle_printable_responses_generate(args(yes=True)) == 1
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Error: synthetic governed planning failure" in output
    assert "Traceback" not in output
    assert not list(tmp_path.rglob("*.pdf"))
