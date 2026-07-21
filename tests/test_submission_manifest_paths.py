"""Tests for canonical submission manifest paths and safe writing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_dir,
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": "2026-06-20T00:00:00+00:00",
        "updated_at": "2026-06-20T00:00:00+00:00",
        "module_details": {"teacher_note": "Café"},
    }


def test_submission_paths_use_canonical_quillan_layout(tmp_path: Path) -> None:
    expected_dir = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
    )

    result_dir = submission_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    result_path = submission_manifest_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )

    assert isinstance(result_dir, Path)
    assert isinstance(result_path, Path)
    assert result_dir == expected_dir
    assert result_path == expected_dir / "submission.json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "../unsafe"),
        ("assignment_id", "bad assignment"),
        ("student_id", ""),
    ],
)
def test_submission_paths_reject_invalid_identifiers(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    identifiers = {
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
    }
    identifiers[field] = value

    expected_field = "work_id" if field == "assignment_id" else field
    with pytest.raises(SubmissionManifestPathError, match=expected_field):
        submission_dir(tmp_path, **identifiers)


def test_valid_manifest_is_written_readably_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "submission.json"
    manifest = _manifest()

    result = write_submission_manifest(path, manifest)

    raw = path.read_bytes()
    assert result == path
    assert path.parent.is_dir()
    assert raw.endswith(b"\n")
    assert b'\n  "schema_version"' in raw
    assert "Café" in raw.decode("utf-8")
    assert load_submission_manifest(path) == manifest


def test_invalid_manifest_does_not_create_output(tmp_path: Path) -> None:
    path = tmp_path / "not-created" / "submission.json"
    manifest = _manifest()
    del manifest["schema_version"]

    with pytest.raises(SubmissionManifestError, match="schema_version"):
        write_submission_manifest(path, manifest)

    assert not path.exists()
    assert not path.parent.exists()


def test_existing_manifest_is_not_overwritten_by_default(tmp_path: Path) -> None:
    path = tmp_path / "submission.json"
    path.write_text("original\n", encoding="utf-8")

    with pytest.raises(SubmissionManifestPathError, match="already exists"):
        write_submission_manifest(path, _manifest())

    assert path.read_text(encoding="utf-8") == "original\n"


def test_existing_manifest_is_replaced_when_overwrite_is_enabled(
    tmp_path: Path,
) -> None:
    path = tmp_path / "submission.json"
    path.write_text("original\n", encoding="utf-8")
    manifest = _manifest()

    result = write_submission_manifest(path, manifest, overwrite=True)

    assert result == path
    assert json.loads(path.read_text(encoding="utf-8")) == manifest


def test_parent_path_that_is_a_file_raises(tmp_path: Path) -> None:
    parent = tmp_path / "submission-parent"
    parent.write_text("not a directory", encoding="utf-8")
    path = parent / "submission.json"

    with pytest.raises(
        SubmissionManifestPathError,
        match="not a directory",
    ):
        write_submission_manifest(path, _manifest())

    assert parent.read_text(encoding="utf-8") == "not a directory"


def test_manifest_symlink_is_rejected_without_modifying_target(tmp_path: Path) -> None:
    target = tmp_path / "outside.json"
    target.write_text("original", encoding="utf-8")
    path = tmp_path / "submission.json"
    try:
        os.symlink(target, path)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation is unavailable: WinError 1314")
        raise

    with pytest.raises(SubmissionManifestPathError, match="symlink"):
        write_submission_manifest(path, _manifest(), overwrite=True)

    assert target.read_text(encoding="utf-8") == "original"


def test_overwrite_preflight_rejects_fabricated_link_without_target_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "submission.json"
    path.write_text("external target bytes", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    original_read = Path.read_bytes

    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda candidate: candidate == path or original_is_symlink(candidate),
    )

    def guarded_read(candidate: Path) -> bytes:
        if candidate == path:
            pytest.fail("unsafe manifest target was read before preflight")
        return original_read(candidate)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(SubmissionManifestPathError, match="symlink"):
        write_submission_manifest(path, _manifest(), overwrite=True)


def test_overwrite_rejects_missing_and_directory_targets(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(SubmissionManifestPathError, match="does not exist"):
        write_submission_manifest(missing, _manifest(), overwrite=True)
    directory = tmp_path / "submission.json"
    directory.mkdir()
    with pytest.raises(SubmissionManifestPathError):
        write_submission_manifest(directory, _manifest(), overwrite=True)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_manifest_preflight_rejects_real_windows_junction_without_external_read(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "submission.json"
    target.write_text("external", encoding="utf-8")
    junction = tmp_path / "submission-parent"
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    try:
        with pytest.raises(SubmissionManifestPathError, match="junction"):
            write_submission_manifest(
                junction / "submission.json", _manifest(), overwrite=True
            )
        assert target.read_text(encoding="utf-8") == "external"
    finally:
        junction.rmdir()
