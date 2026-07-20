"""Tests for Quillan's module-qualified work path contract."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from pds_core.routes import module_work_dir
from pds_core.routing_models import ModuleWorkRef
import pytest

from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    initialize_managed_work_layout,
    initialize_student_submission_dir,
    preflight_managed_work_layout,
    preflight_quillan_work_collection,
    preflight_work_file_destination,
    quillan_work_collection_dir,
    quillan_work_paths,
    quillan_work_ref,
    relative_assignment_path,
    relative_submission_manifest_path,
    response_page_issuance_path,
    response_page_record_path,
    review_record_path,
    student_submission_dir,
    submission_manifest_path,
)

CLASS_ID = "English12_P03"
ASSIGNMENT_ID = "Essay_007"
STUDENT_ID = "00107"


def test_work_reference_and_exact_layout_are_module_qualified(tmp_path: Path) -> None:
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    root = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / QUILLAN_MODULE_ID
        / "work"
        / ASSIGNMENT_ID
    )

    assert work_ref == ModuleWorkRef(QUILLAN_MODULE_ID, CLASS_ID, ASSIGNMENT_ID)
    assert paths.work_ref is not None
    assert paths.roster_path == tmp_path / "classes" / CLASS_ID / "roster.csv"
    assert paths.work_collection_dir == root.parent
    assert quillan_work_collection_dir(tmp_path, CLASS_ID) == root.parent
    assert paths.work_root == root
    assert paths.assignment_path == root / "assignment.json"
    assert paths.response_pages_dir == root / "response_pages"
    assert paths.response_page_issuances_dir == root / "response_pages" / "issuances"
    assert paths.response_page_records_dir == root / "response_pages" / "pages"
    assert paths.templates_dir == root / "templates"
    assert paths.scans_dir == root / "scans"
    assert paths.submissions_dir == root / "submissions"
    assert paths.exports_dir == root / "exports"
    assert student_submission_dir(tmp_path, work_ref, STUDENT_ID) == (
        root / "submissions" / STUDENT_ID
    )
    assert submission_manifest_path(tmp_path, work_ref, STUDENT_ID) == (
        root / "submissions" / STUDENT_ID / "submission.json"
    )
    assert review_record_path(tmp_path, work_ref, STUDENT_ID) == (
        root / "submissions" / STUDENT_ID / "review.json"
    )
    assert response_page_issuance_path(
        tmp_path, work_ref, "iss_0123456789abcdef0123456789abcdef"
    ) == root / "response_pages" / "issuances" / (
        "iss_0123456789abcdef0123456789abcdef.json"
    )
    assert response_page_record_path(
        tmp_path, work_ref, "pg_0123456789abcdef0123456789abcdef"
    ) == root / "response_pages" / "pages" / (
        "pg_0123456789abcdef0123456789abcdef.json"
    )
    assert all(
        path.is_relative_to(root)
        for path in (
            paths.assignment_path,
            paths.response_pages_dir,
            paths.response_page_issuances_dir,
            paths.response_page_records_dir,
            paths.templates_dir,
            paths.scans_dir,
            paths.submissions_dir,
            paths.exports_dir,
        )
    )
    assert all(
        "assignments" not in path.parts
        for path in (
            paths.roster_path,
            paths.work_collection_dir,
            paths.work_root,
            paths.assignment_path,
            paths.response_pages_dir,
            paths.response_page_issuances_dir,
            paths.response_page_records_dir,
            paths.templates_dir,
            paths.scans_dir,
            paths.submissions_dir,
            paths.exports_dir,
        )
    )


@pytest.mark.parametrize(
    ("class_id", "assignment_id"),
    [("../class", ASSIGNMENT_ID), (CLASS_ID, "bad/work"), ("", ASSIGNMENT_ID)],
)
def test_invalid_work_identifiers_are_rejected(
    tmp_path: Path, class_id: str, assignment_id: str
) -> None:
    workspace = tmp_path / "absent"
    with pytest.raises(ValueError):
        quillan_work_paths(workspace, class_id, assignment_id)
    assert not workspace.exists()


def test_all_path_construction_is_side_effect_free(tmp_path: Path) -> None:
    workspace = tmp_path / "absent"
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    quillan_work_collection_dir(workspace, CLASS_ID)
    quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID)
    student_submission_dir(workspace, work_ref, STUDENT_ID)
    submission_manifest_path(workspace, work_ref, STUDENT_ID)
    review_record_path(workspace, work_ref, STUDENT_ID)
    response_page_issuance_path(
        workspace, work_ref, "iss_0123456789abcdef0123456789abcdef"
    )
    response_page_record_path(
        workspace, work_ref, "pg_0123456789abcdef0123456789abcdef"
    )

    assert not workspace.exists()


def test_relative_paths_are_central_exact_pure_and_preserve_leading_zeroes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "absent"
    assert relative_assignment_path(CLASS_ID, ASSIGNMENT_ID) == (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/assignment.json"
    )
    assert relative_submission_manifest_path(
        CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/submission.json"
    )
    with pytest.raises(ValueError):
        relative_assignment_path(CLASS_ID, "../unsafe")
    with pytest.raises(ValueError):
        relative_submission_manifest_path(CLASS_ID, ASSIGNMENT_ID, "bad/student")
    assert not workspace.exists()


def test_work_file_preflight_is_contained_and_nonmutating(tmp_path: Path) -> None:
    workspace = tmp_path / "absent"
    paths = quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID)

    assert preflight_managed_work_layout(paths) == paths
    assert preflight_work_file_destination(
        workspace, paths.work_ref, "assignment.json"
    ) == paths.assignment_path
    with pytest.raises(ValueError):
        preflight_work_file_destination(
            workspace, paths.work_ref, "../outside.json"
        )
    with pytest.raises(QuillanWorkPathError, match="module_id"):
        preflight_work_file_destination(
            workspace,
            ModuleWorkRef("scoreform", CLASS_ID, ASSIGNMENT_ID),
            "assignment.json",
        )
    assert not workspace.exists()


def test_work_collection_preflight_is_bounded_pure_and_allows_absence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "absent"
    expected = quillan_work_collection_dir(workspace, CLASS_ID)

    assert preflight_quillan_work_collection(workspace, CLASS_ID) == expected
    assert not workspace.exists()


def test_work_collection_preflight_rejects_wrong_type_ancestor_without_mutation(
    tmp_path: Path,
) -> None:
    modules = tmp_path / "classes" / CLASS_ID / "modules"
    modules.parent.mkdir(parents=True)
    modules.write_bytes(b"unchanged")

    with pytest.raises(QuillanWorkPathError, match="not a directory"):
        preflight_quillan_work_collection(tmp_path, CLASS_ID)

    assert modules.read_bytes() == b"unchanged"
    assert list(modules.parent.iterdir()) == [modules]


def test_student_helpers_reject_other_modules_and_invalid_students(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "absent"
    other = ModuleWorkRef("scoreform", CLASS_ID, ASSIGNMENT_ID)
    with pytest.raises(QuillanWorkPathError, match="module_id"):
        student_submission_dir(workspace, other, STUDENT_ID)
    with pytest.raises(ValueError, match="student_id"):
        student_submission_dir(
            workspace, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), "../student"
        )
    with pytest.raises(QuillanWorkPathError, match="module_id"):
        response_page_issuance_path(
            workspace,
            other,
            "iss_0123456789abcdef0123456789abcdef",
        )
    with pytest.raises(ValueError, match="page_id"):
        response_page_record_path(
            workspace, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), "../unsafe"
        )

    assert module_work_dir(workspace, other) != quillan_work_paths(
        workspace, CLASS_ID, ASSIGNMENT_ID
    ).work_root
    assert not workspace.exists()


def test_initializer_creates_only_static_layout_and_is_idempotent(
    tmp_path: Path,
) -> None:
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    initialize_managed_work_layout(paths)
    marker = paths.work_root / "teacher-marker.txt"
    marker.write_text("preserve", encoding="utf-8")

    assert initialize_managed_work_layout(paths) == paths
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert {child.name for child in paths.work_root.iterdir()} == {
        "response_pages",
        "templates",
        "scans",
        "submissions",
        "exports",
        "teacher-marker.txt",
    }
    assert paths.response_page_issuances_dir.is_dir()
    assert paths.response_page_records_dir.is_dir()
    assert not paths.assignment_path.exists()
    assert not (paths.work_root / "routes").exists()
    assert not list(paths.work_root.rglob("*.json"))
    assert not list(paths.work_root.rglob("*.pdf"))


@pytest.mark.parametrize(
    "collision_name",
    [
        "work_root",
        "response_pages_dir",
        "response_page_issuances_dir",
        "response_page_records_dir",
        "templates_dir",
        "scans_dir",
        "submissions_dir",
        "exports_dir",
    ],
)
def test_initializer_preflights_all_wrong_type_collisions(
    tmp_path: Path, collision_name: str
) -> None:
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    collision = getattr(paths, collision_name)
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_bytes(b"unchanged")

    with pytest.raises(QuillanWorkPathError, match="not a directory"):
        initialize_managed_work_layout(paths)

    assert collision.read_bytes() == b"unchanged"
    for required in (
        paths.response_pages_dir,
        paths.templates_dir,
        paths.scans_dir,
        paths.submissions_dir,
        paths.exports_dir,
    ):
        if (
            required != collision
            and not required.is_relative_to(collision)
            and not collision.is_relative_to(required)
        ):
            assert not required.exists()


def test_initializer_preserves_sibling_module_work(tmp_path: Path) -> None:
    sibling = module_work_dir(
        tmp_path, ModuleWorkRef("scoreform", CLASS_ID, ASSIGNMENT_ID)
    )
    sibling.mkdir(parents=True)
    marker = sibling / "marker.txt"
    marker.write_text("sibling", encoding="utf-8")

    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )

    assert marker.read_text(encoding="utf-8") == "sibling"


def test_student_directory_initialization_is_narrow_and_idempotent(
    tmp_path: Path,
) -> None:
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    student_dir = initialize_student_submission_dir(
        tmp_path, paths.work_ref, STUDENT_ID
    )
    assert student_dir.is_dir()
    assert list(student_dir.iterdir()) == []
    assert initialize_student_submission_dir(
        tmp_path, paths.work_ref, STUDENT_ID
    ) == student_dir
    assert not paths.response_pages_dir.exists()
    assert not paths.templates_dir.exists()
    assert not paths.scans_dir.exists()
    assert not paths.exports_dir.exists()


def test_student_directory_initialization_rejects_link_like_target(
    tmp_path: Path,
) -> None:
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    initialize_managed_work_layout(paths)
    outside = tmp_path / "outside-student"
    outside.mkdir()
    marker = outside / "marker.bin"
    marker.write_bytes(b"unchanged")
    student = student_submission_dir(tmp_path, paths.work_ref, STUDENT_ID)
    try:
        os.symlink(outside, student, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    with pytest.raises(QuillanWorkPathError, match="symlink or junction"):
        initialize_student_submission_dir(tmp_path, paths.work_ref, STUDENT_ID)

    assert marker.read_bytes() == b"unchanged"
    assert student.is_symlink()


def test_initializer_rejects_symlink_ancestor_before_mutation(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    modules = workspace / "classes" / CLASS_ID / "modules"
    modules.parent.mkdir(parents=True)
    try:
        os.symlink(outside, modules, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    with pytest.raises(QuillanWorkPathError, match="symlink"):
        initialize_managed_work_layout(
            quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID)
        )

    assert list(outside.iterdir()) == []


def test_link_like_predicate_has_deterministic_symlink_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "is_symlink", lambda _path: True)
    assert _is_link_like(tmp_path / "synthetic")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_initializer_rejects_real_windows_junction_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    modules = workspace / "classes" / CLASS_ID / "modules"
    modules.parent.mkdir(parents=True)
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(modules), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(
            "Windows junction creation unavailable: "
            f"exit {result.returncode}: {result.stderr.strip()}"
        )
    try:
        with pytest.raises(QuillanWorkPathError, match="junction"):
            initialize_managed_work_layout(
                quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID)
            )
        assert marker.read_text(encoding="utf-8") == "unchanged"
        assert list(outside.iterdir()) == [marker]
    finally:
        os.rmdir(modules)


def test_production_modules_do_not_reconstruct_canonical_work_literal() -> None:
    production_root = Path(__file__).parents[1] / "quillan"
    offenders = [
        path
        for path in production_root.rglob("*.py")
        if path.name != "work_paths.py"
        and "modules/quillan/work" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
