"""Assignment assembly discovers immutable observations, never evidence names."""

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
)
from quillan.cli import main
import quillan.cli_app.handlers.submissions as cli_submissions
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_observations import group_response_page_observations_by_student
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_manifest_paths import write_submission_manifest
from tests.observation_test_support import successful_image_page


def test_assignment_discovery_groups_observations_by_stored_identity(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    discovered = group_response_page_observations_by_student(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert discovered == {observation.student_id: (observation,)}


def test_assignment_assembly_reports_created_then_unchanged(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    first = assemble_assignment_submissions(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        created_at="2026-07-21T00:00:00+00:00",
    )
    assert not first.failures
    assert first.assembled[0].status == "created"
    second = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert second.assembled[0].status == "unchanged"


def test_orphan_teacher_readable_evidence_filename_is_not_identity(
    tmp_path: Path,
) -> None:
    orphan = (
        tmp_path
        / "classes"
        / "class_synthetic"
        / "modules"
        / "quillan"
        / "work"
        / "assignment_synthetic"
        / "scans"
        / "evidence"
        / ("iss_" + "1" * 32)
    )
    # The exact filename is irrelevant because no observation record names it.
    orphan.mkdir(parents=True)
    (
        orphan
        / "response_misleading_pg_999__obs_ffffffffffffffffffffffffffffffff.png"
    ).write_bytes(b"orphan")
    assert group_response_page_observations_by_student(
        tmp_path, "class_synthetic", "assignment_synthetic"
    ) == {}


def test_direct_cli_assembles_observations_and_rejects_retired_authority_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    monkeypatch.setattr(cli_submissions, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "assemble-submissions",
            observation.class_id,
            observation.assignment_id,
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Created manifests: 1" in output
    assert "Failures: 0" in output

    for retired in ("--expected-pages", "--overwrite"):
        with pytest.raises(SystemExit) as error:
            main(
                [
                    "assemble-submissions",
                    observation.class_id,
                    observation.assignment_id,
                    retired,
                    *(("2",) if retired == "--expected-pages" else ()),
                ]
            )
        assert error.value.code == 2


def test_cli_reports_two_assembled_targets_and_one_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure = SimpleNamespace(
        student_id="response_00108",
        category="unexpected_error",
        reason="Unexpected assembly failure for response_00108: programming failure",
    )
    result = SimpleNamespace(
        assembled=(),
        created_count=2,
        updated_count=0,
        unchanged_count=0,
        failures=(failure,),
    )
    monkeypatch.setattr(cli_submissions, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        cli_submissions, "assemble_assignment_submissions", lambda *_args: result
    )
    assert main(["assemble-submissions", "class_a", "assignment_a"]) == 1
    output = capsys.readouterr().out
    assert "Created manifests: 2" in output
    assert "Failures: 1" in output
    assert "response_00108: unexpected_error" in output


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_assignment_wrapper_does_not_traverse_junctioned_student_directory(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    first = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    valid_manifest = first.assembled[0].manifest_path
    submissions = valid_manifest.parent.parent
    outside = tmp_path / "outside-submissions"
    outside.mkdir()
    sentinel = outside / "submission.json"
    sentinel.write_bytes(b"external sentinel")
    junction = submissions / "junction_student"
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    try:
        second = assemble_assignment_submissions(
            tmp_path, observation.class_id, observation.assignment_id
        )
        assert second.assembled[0].manifest_path == valid_manifest
        assert second.assembled[0].status == "unchanged"
        assert sentinel.read_bytes() == b"external sentinel"
    finally:
        os.rmdir(junction)


def test_assignment_wrapper_does_not_traverse_symlinked_student_directory(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    first = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    valid_manifest = first.assembled[0].manifest_path
    outside = tmp_path / "outside-symlinked-submission"
    outside.mkdir()
    sentinel = outside / "submission.json"
    sentinel.write_bytes(b"external sentinel")
    link = valid_manifest.parent.parent / "symlink_student"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation unavailable: WinError 1314")
        raise
    try:
        second = assemble_assignment_submissions(
            tmp_path, observation.class_id, observation.assignment_id
        )
        assert second.assembled[0].manifest_path == valid_manifest
        assert second.assembled[0].status == "unchanged"
        assert sentinel.read_bytes() == b"external sentinel"
    finally:
        link.unlink()


@pytest.mark.parametrize(
    ("manifest_kind", "category"),
    [
        ("malformed", "existing_manifest_invalid"),
        ("different_issuance", "existing_manifest_issuance_conflict"),
        ("plain_paper", "existing_plain_paper_submission"),
    ],
)
def test_assignment_wrapper_reports_conflicts_only_as_failures(
    tmp_path: Path, manifest_kind: str, category: str
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    first = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest_path = first.assembled[0].manifest_path
    if manifest_kind == "malformed":
        manifest_path.write_bytes(b"not json")
    elif manifest_kind == "different_issuance":
        manifest = deepcopy(load_submission_manifest(manifest_path))
        manifest["module_details"]["response_issuance_id"] = "iss_" + "f" * 32
        for page in manifest["pages"]:
            page["page_state"] = "missing"
            page["selected_evidence_id"] = None
            page["evidence"] = []
        write_submission_manifest(manifest_path, manifest, overwrite=True)
    else:
        plain_paper: dict[str, Any] = {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "submission_manifest",
            "class_id": observation.class_id,
            "assignment_id": observation.assignment_id,
            "student_id": observation.student_id,
            "expected_pages": None,
            "submission_state": "unreviewed",
            "pages": [],
            "created_at": "2026-07-21T00:00:00+00:00",
            "updated_at": "2026-07-21T00:00:00+00:00",
            "module_details": {
                "submission_entry_method": "plain_paper_manual",
                "physical_evidence_status": "teacher_has_external_plain_paper",
                "created_by_workflow": "plain_paper_submission",
            },
        }
        write_submission_manifest(manifest_path, plain_paper, overwrite=True)
    result = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not result.assembled
    assert result.failures[0].category == category
