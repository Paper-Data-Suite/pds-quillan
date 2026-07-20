"""Direct CLI coverage for canonical submission page management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import quillan.cli_app.handlers.pages as page_handlers
from quillan.cli_app.main import main
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
TIMESTAMP = "2026-07-13T12:00:00+00:00"


def _evidence(evidence_id: str, page_number: int, role: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "routed_evidence_path": (
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/scans/"
            f"response_{STUDENT_ID}_pg_{page_number:03d}.pdf"
        ),
        "evidence_role": role,
        "evidence_state": "active",
        "duplicate_number": None,
        "created_at": TIMESTAMP,
        "retained_source": None,
        "module_details": {},
    }


def _manifest(*, plain_paper: bool = False) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    expected_pages: int | None = None
    details: dict[str, Any] = {
        "submission_entry_method": "plain_paper_manual"
    }
    if not plain_paper:
        expected_pages = 3
        details = {}
        pages = [
            {
                "page_number": 3,
                "page_state": "missing",
                "selected_evidence_id": None,
                "evidence": [],
            },
            {
                "page_number": 1,
                "page_state": "present",
                "selected_evidence_id": "evidence_001",
                "evidence": [_evidence("evidence_001", 1, "selected")],
            },
            {
                "page_number": 2,
                "page_state": "duplicate",
                "selected_evidence_id": None,
                "evidence": [
                    _evidence("evidence_002a", 2, "candidate"),
                    _evidence("evidence_002b", 2, "candidate"),
                ],
            },
        ]
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": expected_pages,
        "submission_state": "reviewed",
        "pages": pages,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": details,
    }


def _write(root: Path, *, plain_paper: bool = False) -> Path:
    path = submission_manifest_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_submission_manifest(path, _manifest(plain_paper=plain_paper))


def _configure_workspace(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(page_handlers, "resolve_workspace_root", lambda: root)


def test_help_lists_pages_namespace_and_all_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as top_help:
        main(["--help"])
    assert top_help.value.code == 0
    assert "pages" in capsys.readouterr().out

    assert main(["pages"]) == 0
    namespace_help = capsys.readouterr().out
    assert "list" in namespace_help
    assert "exclude" in namespace_help
    assert "restore" in namespace_help
    assert "mark-needs-rescan" in namespace_help

    for command in ("list", "exclude", "restore", "mark-needs-rescan"):
        with pytest.raises(SystemExit) as subcommand_help:
            main(["pages", command, "--help"])
        assert subcommand_help.value.code == 0
        capsys.readouterr()


def test_bare_pages_does_not_resolve_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        page_handlers,
        "resolve_workspace_root",
        lambda: pytest.fail("bare namespace resolved workspace"),
    )
    assert main(["pages"]) == 0


def test_list_is_read_only_and_orders_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path)
    before = path.read_bytes()
    _configure_workspace(monkeypatch, tmp_path)

    assert main(["pages", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = capsys.readouterr().out
    assert output.index("Page 1:") < output.index("Page 2:") < output.index("Page 3:")
    assert "Selected evidence: none" in output
    assert "Present pages: 1" in output
    assert "Missing pages: 1" in output
    assert "Duplicate pages: 1" in output
    assert "Pages lacking selected evidence: 2,3" in output
    assert "Routed path:" in output
    assert path.read_bytes() == before


def test_plain_paper_lists_zero_pages_and_mutations_fail_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, plain_paper=True)
    before = path.read_bytes()
    _configure_workspace(monkeypatch, tmp_path)

    assert main(["pages", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    output = capsys.readouterr().out
    assert "Plain-paper submission: yes" in output
    assert "zero digital pages" in output
    assert "Digital pages: none" in output

    for command in ("exclude", "restore", "mark-needs-rescan"):
        assert main(
            [
                "pages",
                command,
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--page",
                "1",
                "--yes",
            ]
        ) == 1
        assert "Page 1 is not in this submission record" in capsys.readouterr().out
        assert path.read_bytes() == before


def test_missing_manifest_reports_assembly_guidance_without_creating_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _configure_workspace(monkeypatch, tmp_path)
    path = submission_manifest_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert main(["pages", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 1
    assert "Assemble submissions" in capsys.readouterr().out
    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.parametrize("command", ["exclude", "restore", "mark-needs-rescan"])
def test_mutations_require_yes_and_positive_page(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as missing_yes:
        main(
            [
                "pages",
                command,
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--page",
                "1",
            ]
        )
    assert missing_yes.value.code != 0
    assert "--yes" in capsys.readouterr().err

    with pytest.raises(SystemExit) as invalid_page:
        main(
            [
                "pages",
                command,
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--page",
                "0",
                "--yes",
            ]
        )
    assert invalid_page.value.code != 0
    assert "positive integer" in capsys.readouterr().err


def test_cli_mutations_report_transition_and_preserve_submission_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path)
    review = path.with_name("review.json")
    review.write_bytes(b'{"review_state":"in_progress"}\n')
    review_before = review.read_bytes()
    _configure_workspace(monkeypatch, tmp_path)
    args = [CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "--page", "1", "--yes"]

    assert main(["pages", "exclude", *args]) == 0
    excluded_output = capsys.readouterr().out
    assert "Action: excluded" in excluded_output
    assert "Previous state: present" in excluded_output
    assert "Resulting state: excluded from active review" in excluded_output

    assert main(["pages", "restore", *args]) == 0
    restored_output = capsys.readouterr().out
    assert "Action: restored" in restored_output
    assert "Restore source: preserved pre-exclusion metadata" in restored_output

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["submission_state"] == "reviewed"
    assert manifest["created_at"] == TIMESTAMP
    assert review.read_bytes() == review_before


def test_rescan_transition_discards_obsolete_exclusion_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)
    args = [CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "--page", "1", "--yes"]

    assert main(["pages", "exclude", *args]) == 0
    assert main(["pages", "mark-needs-rescan", *args]) == 0
    assert main(["pages", "exclude", *args]) == 0
    assert main(["pages", "restore", *args]) == 0

    page = json.loads(path.read_text(encoding="utf-8"))["pages"][1]
    evidence = page["evidence"][0]
    assert page["page_state"] == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert evidence["evidence_role"] == "candidate"
    assert evidence["evidence_state"] == "needs_rescan"
    assert "quillan_before_page_exclusion" not in evidence["module_details"]
