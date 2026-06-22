"""Tests for read-only assignment submission status."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import quillan.cli
from quillan.cli import main
from quillan.submission_assembly import (
    RoutedSubmissionEvidence,
    build_submission_manifest,
)
from quillan.submission_manifest import SubmissionManifestError
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_status import list_assignment_submission_status

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
TIMESTAMP = "2026-06-22T12:00:00+00:00"


def _assignment_dir(workspace: Path) -> Path:
    return (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
    )


def _touch_routed(workspace: Path, filename: str) -> Path:
    path = _assignment_dir(workspace) / "scans" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic evidence")
    return path


def _evidence(
    page_number: int,
    filename: str,
    **kwargs: Any,
) -> RoutedSubmissionEvidence:
    return RoutedSubmissionEvidence(
        page_number=page_number,
        routed_evidence_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/{filename}"
        ),
        **kwargs,
    )


def _write_status_manifest(workspace: Path, student_id: str = "00107") -> Path:
    manifest = build_submission_manifest(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        student_id,
        [
            _evidence(1, "response_00107_pg_001.pdf"),
            _evidence(3, "response_00107_pg_003.pdf"),
            _evidence(
                3,
                "response_00107_pg_003__dup_001.pdf",
                duplicate_number=1,
            ),
            _evidence(
                4,
                "response_00107_pg_004.pdf",
                evidence_state="needs_rescan",
            ),
            _evidence(
                5,
                "response_00107_pg_005.pdf",
                evidence_role="excluded",
            ),
            _evidence(
                6,
                "response_00107_pg_006.pdf",
                evidence_role="candidate",
            ),
        ],
        expected_pages=6,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )
    manifest["submission_state"] = "in_progress"
    path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, student_id
    )
    return write_submission_manifest(path, manifest)


def test_manifest_status_reports_all_page_and_evidence_states(
    tmp_path: Path,
) -> None:
    manifest_path = _write_status_manifest(tmp_path)

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert result.students_with_manifests == ("00107",)
    status = result.student_statuses[0]
    assert status.manifest_path == manifest_path
    assert status.submission_state == "in_progress"
    assert [page.page_number for page in status.pages] == [1, 2, 3, 4, 5, 6]
    assert status.missing_pages == (2,)
    assert status.duplicate_pages == (3,)
    assert status.needs_rescan_pages == (4,)
    assert status.excluded_pages == (5,)
    assert status.unselected_present_pages == (6,)
    assert status.pages[2].evidence_count == 2
    assert status.pages[2].evidence_roles == ("candidate", "candidate")
    assert status.pages[3].evidence_states == ("needs_rescan",)


def test_routed_evidence_without_manifest_needs_assembly_without_writes(
    tmp_path: Path,
) -> None:
    _touch_routed(tmp_path, "response_00108_pg_002.pdf")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, expected_pages=3
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert result.students_with_routed_evidence == ("00108",)
    assert result.students_without_manifests == ("00108",)
    assert [path.name for path in result.unassembled_routed_files] == [
        "response_00108_pg_002.pdf"
    ]
    assert result.student_statuses[0].missing_pages == (1, 3)
    assert before == after
    assert not list(tmp_path.rglob("submission.json"))


def test_student_can_have_both_manifest_and_routed_evidence(
    tmp_path: Path,
) -> None:
    _write_status_manifest(tmp_path)
    _touch_routed(tmp_path, "response_00107_pg_001.pdf")

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert result.students_with_manifests == ("00107",)
    assert result.students_with_routed_evidence == ("00107",)
    assert not result.students_without_manifests
    assert not result.unassembled_routed_files


def test_new_routed_file_for_manifest_student_is_unassembled(
    tmp_path: Path,
) -> None:
    _write_status_manifest(tmp_path)
    path = _touch_routed(tmp_path, "response_00107_pg_007.pdf")

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert result.unassembled_routed_files == (path,)


def test_skipped_routed_files_are_reported_and_sorted(tmp_path: Path) -> None:
    _touch_routed(tmp_path, "response_00107_pg_zero.pdf")
    _touch_routed(tmp_path, "debug_page.png")

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert [item.path.name for item in result.skipped_routed_files] == [
        "debug_page.png",
        "response_00107_pg_zero.pdf",
    ]
    assert "does not match" in result.skipped_routed_files[0].reason
    assert "malformed" in result.skipped_routed_files[1].reason


def test_missing_and_empty_assignment_return_empty_status(
    tmp_path: Path,
) -> None:
    missing = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert not missing.student_statuses

    (_assignment_dir(tmp_path) / "scans").mkdir(parents=True)
    (_assignment_dir(tmp_path) / "submissions").mkdir()
    empty = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert not empty.student_statuses
    assert not empty.skipped_routed_files


def test_invalid_existing_manifest_is_an_error(tmp_path: Path) -> None:
    path = submission_manifest_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, "00107"
    )
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SubmissionManifestError, match="not valid JSON"):
        list_assignment_submission_status(
            tmp_path, CLASS_ID, ASSIGNMENT_ID
        )


def test_expected_pages_does_not_change_existing_manifest_status(
    tmp_path: Path,
) -> None:
    path = _write_status_manifest(tmp_path)
    original = path.read_bytes()

    result = list_assignment_submission_status(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, expected_pages=10
    )

    assert result.student_statuses[0].missing_pages == (2,)
    assert path.read_bytes() == original


def test_cli_prints_status_students_skips_and_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_status_manifest(tmp_path)
    _touch_routed(tmp_path, "response_00107_pg_001.pdf")
    _touch_routed(tmp_path, "response_00108_pg_002.pdf")
    _touch_routed(tmp_path, "notes.txt")
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)
    before = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    exit_code = main(
        [
            "list-submissions",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--expected-pages",
            "3",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Students with manifests: 1" in output
    assert "Students with routed evidence: 2" in output
    assert "Students needing assembly: 1" in output
    assert "Unassembled routed files: 1" in output
    assert "- in_progress: 1" in output
    assert "- present but unselected: 1" in output
    assert "- 00107: in_progress" in output
    assert "- 00108: routed evidence exists; no manifest; missing=1,3" in output
    assert "classes/" in output
    assert "response_00108_pg_002.pdf" in output
    assert str(tmp_path) not in output
    assert before == {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }


def test_cli_invalid_manifest_exits_nonzero_and_bad_expected_pages_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = submission_manifest_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, "00107"
    )
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(["list-submissions", CLASS_ID, ASSIGNMENT_ID]) == 1
    assert "could not list submission status" in capsys.readouterr().out

    with pytest.raises(SystemExit) as error:
        main(
            [
                "list-submissions",
                CLASS_ID,
                ASSIGNMENT_ID,
                "--expected-pages",
                "0",
            ]
        )
    assert error.value.code == 2
