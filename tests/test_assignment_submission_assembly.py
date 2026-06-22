"""Tests for assignment-level routed-evidence assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.cli
from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
    discover_assignment_routed_evidence,
)
from quillan.cli import main
from quillan.submission_manifest import load_submission_manifest

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
TIMESTAMP = "2026-06-22T12:00:00+00:00"


def _scans_dir(workspace: Path) -> Path:
    path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _touch_evidence(workspace: Path, filename: str) -> Path:
    path = _scans_dir(workspace) / filename
    path.write_bytes(b"synthetic evidence")
    return path


@pytest.mark.parametrize("extension", ["pdf", "png", "jpg", "jpeg", "tif", "tiff"])
def test_discovery_supports_extensions_case_insensitively(
    tmp_path: Path, extension: str
) -> None:
    _touch_evidence(tmp_path, f"response_00107_pg_001.{extension.upper()}")

    discovered = discover_assignment_routed_evidence(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert list(discovered) == ["00107"]
    assert discovered["00107"][0].page_number == 1


def test_discovery_groups_students_and_parses_duplicates_deterministically(
    tmp_path: Path,
) -> None:
    _touch_evidence(tmp_path, "response_00108_pg_003__dup_002.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_002__dup_001.png")
    _touch_evidence(tmp_path, "response_00107_pg_002.pdf")

    discovered = discover_assignment_routed_evidence(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert list(discovered) == ["00107", "00108"]
    first_student = discovered["00107"]
    assert [
        (item.page_number, item.duplicate_number) for item in first_student
    ] == [(2, None), (2, 1)]
    assert first_student[0].retained_source_path is None
    assert first_student[0].source_scan_id is None
    assert first_student[0].source_filename is None
    assert first_student[0].source_sha256 is None
    assert first_student[0].source_page_number is None


def test_discovery_skips_unrelated_and_malformed_files_with_reasons(
    tmp_path: Path,
) -> None:
    _touch_evidence(tmp_path, "debug_page.png")
    _touch_evidence(tmp_path, "response_00107_pg_zero.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_000.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_001__dup_000.pdf")

    result = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert not result.students_with_evidence
    assert len(result.skipped_files) == 4
    reasons = {item.path.name: item.reason for item in result.skipped_files}
    assert "does not match" in reasons["debug_page.png"]
    assert "malformed" in reasons["response_00107_pg_zero.pdf"]
    assert "page number" in reasons["response_00107_pg_000.pdf"]
    assert "duplicate number" in reasons[
        "response_00107_pg_001__dup_000.pdf"
    ]


def test_assembly_writes_reloadable_manifests_with_missing_duplicate_and_extra_pages(
    tmp_path: Path,
) -> None:
    _touch_evidence(tmp_path, "response_00107_pg_001.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_001__dup_001.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_004.jpg")
    _touch_evidence(tmp_path, "response_00108_pg_002.tif")

    result = assemble_assignment_submissions(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_pages=3,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )

    assert result.students_with_evidence == ("00107", "00108")
    assert len(result.written_manifests) == 2
    first = load_submission_manifest(result.written_manifests[0])
    assert [page["page_number"] for page in first["pages"]] == [1, 2, 3, 4]
    assert [page["page_state"] for page in first["pages"]] == [
        "duplicate",
        "missing",
        "missing",
        "present",
    ]
    assert first["pages"][0]["selected_evidence_id"] is None
    assert {
        item["evidence_role"] for item in first["pages"][0]["evidence"]
    } == {"candidate"}
    assert all(
        item["retained_source"] is None
        for page in first["pages"]
        for item in page["evidence"]
    )
    summary = result.student_summaries[0]
    assert summary.duplicate_pages == (1,)
    assert summary.missing_pages == (2, 3)


def test_existing_manifest_is_skipped_while_other_students_assemble(
    tmp_path: Path,
) -> None:
    _touch_evidence(tmp_path, "response_00107_pg_001.pdf")
    first_result = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    existing_manifest = first_result.written_manifests[0]
    original_text = existing_manifest.read_text(encoding="utf-8")

    for path in _scans_dir(tmp_path).iterdir():
        path.unlink()
    _touch_evidence(tmp_path, "response_00108_pg_002.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_003.pdf")

    result = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )

    assert result.skipped_existing_manifests == (existing_manifest,)
    assert existing_manifest.read_text(encoding="utf-8") == original_text
    assert len(result.written_manifests) == 1
    assert result.written_manifests[0].parent.name == "00108"


def test_overwrite_fully_regenerates_existing_manifest(tmp_path: Path) -> None:
    evidence = _touch_evidence(tmp_path, "response_00107_pg_001.pdf")
    first = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    manifest_path = first.written_manifests[0]
    evidence.unlink()
    _touch_evidence(tmp_path, "response_00107_pg_002.pdf")

    result = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, overwrite=True
    )

    assert result.written_manifests == (manifest_path,)
    assert not result.skipped_existing_manifests
    manifest = load_submission_manifest(manifest_path)
    assert [page["page_number"] for page in manifest["pages"]] == [2]


def test_missing_or_empty_scans_directory_returns_empty_result(
    tmp_path: Path,
) -> None:
    missing = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert not missing.students_with_evidence
    assert not missing.written_manifests

    _scans_dir(tmp_path)
    empty = assemble_assignment_submissions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert not empty.students_with_evidence
    assert not empty.skipped_files


def test_empty_assignment_still_validates_expected_pages(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected_pages"):
        assemble_assignment_submissions(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, expected_pages=0
        )


def test_cli_assembles_and_prints_workspace_relative_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _touch_evidence(tmp_path, "response_00107_pg_001.pdf")
    _touch_evidence(tmp_path, "response_00107_pg_001__dup_001.pdf")
    _touch_evidence(tmp_path, "notes.txt")
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    result = main(
        [
            "assemble-submissions",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--expected-pages",
            "2",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "Students with routed evidence: 1" in output
    assert "Created manifests: 1" in output
    assert "Missing pages: 1" in output
    assert "Duplicate pages: 1" in output
    assert "Skipped files: 1" in output
    assert "Failures: 0" in output
    assert "classes/" in output
    assert str(tmp_path) not in output

    overwrite_result = main(
        [
            "assemble-submissions",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--overwrite",
        ]
    )
    assert overwrite_result == 0


def test_cli_handles_empty_assignment_and_rejects_invalid_expected_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(["assemble-submissions", CLASS_ID, ASSIGNMENT_ID]) == 0
    output = capsys.readouterr().out
    assert "Students with routed evidence: 0" in output
    assert "Created manifests: 0" in output

    with pytest.raises(SystemExit) as error:
        main(
            [
                "assemble-submissions",
                CLASS_ID,
                ASSIGNMENT_ID,
                "--expected-pages",
                "0",
            ]
        )
    assert error.value.code == 2
