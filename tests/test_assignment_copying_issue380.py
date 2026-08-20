"""Focused acceptance for issue #380 safe assignment copying."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)
import pytest

import quillan.assignment_copying as copy_module
import quillan.assignment_copy_workflows as copy_workflows
import quillan.assignment_workflows as workflows
import quillan.atomic_record_io as atomic_record_io
from quillan.assignment_copying import (
    AssignmentCopyError,
    commit_assignment_copy,
    plan_assignment_copy,
)
from quillan.academic_work_registration import register_quillan_academic_work
from quillan.assignments import load_assignment_config
from quillan.assignment_workflows import AssignmentBatchWriteError
from quillan.work_paths import initialize_managed_work_layout, quillan_work_paths
from tests.menu_screen_recorder import MenuScreenRecorder

STANDARD_ID = "njsls-ela:W.AW.9-10.1"
SECOND_STANDARD_ID = "njsls-ela:RL.CR.9-10.1"


def _write_roster(root: Path, class_id: str) -> None:
    write_class_roster(
        root,
        create_roster(
            class_id,
            [
                {
                    "student_id": "synthetic1",
                    "last_name": "Synthetic",
                    "first_name": "Avery",
                    "period": "2",
                }
            ],
        ),
    )


def _write_standards(root: Path, *, include_profile: bool = True) -> None:
    profiles = (
        StandardsProfile(
            profile_id="english10_profile",
            standards=(STANDARD_ID, SECOND_STANDARD_ID),
            title="English 10",
        ),
    ) if include_profile else ()
    write_workspace_standards_library(
        root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.AW.9-10.1",
                    source="NJSLS",
                    short_name="Argument",
                    description="Write arguments.",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id=SECOND_STANDARD_ID,
                    code="RL.CR.9-10.1",
                    source="NJSLS",
                    short_name="Reading",
                    description="Read closely.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=profiles,
        ),
        overwrite=True,
    )


def _source_assignment(
    *,
    assignment_id: str = "literary_analysis",
    class_ids: list[str] | None = None,
    created_at: str = "2026-08-01T12:00:00+00:00",
) -> dict[str, object]:
    return workflows.build_assignment_config(
        assignment_id=assignment_id,
        title="Literary Analysis",
        class_ids=class_ids or ["english10_p2"],
        writing_type="literary_analysis",
        student_prompt="Analyze how the author develops the central idea.",
        standards_profile_id="english10_profile",
        focus_standard_ids=[STANDARD_ID, SECOND_STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "standards_4_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                },
                {
                    "value": 2,
                    "label": "Meeting",
                    "description": "Clear evidence.",
                },
            ],
        },
        basic_requirements={
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        minimum_requirement_policy={"allow_return_without_full_review": True},
        created_at=created_at,
    )


def _workspace(root: Path, *class_ids: str) -> Path:
    for class_id in class_ids or ("english10_p2", "english10_p4"):
        _write_roster(root, class_id)
    _write_standards(root)
    return root


def _write_source(
    root: Path,
    *,
    class_id: str = "english10_p2",
    assignment_id: str = "literary_analysis",
    class_ids: list[str] | None = None,
) -> Path:
    assignment = _source_assignment(
        assignment_id=assignment_id,
        class_ids=class_ids or [class_id],
    )
    return workflows.write_assignment_config(root, class_id, assignment)


def test_copy_builds_fresh_allowlisted_assignment_for_different_class(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    source_bytes = source_path.read_bytes()
    created_at = datetime(2026, 8, 19, 23, 0, tzinfo=timezone.utc)

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
        title="Literary Analysis - Period 4",
        created_at=created_at,
    )

    target = plan.assignment
    assert target["schema_version"] == "2"
    assert target["module"] == "quillan"
    assert target["record_type"] == "assignment"
    assert target["assignment_id"] == "literary_analysis"
    assert target["class_ids"] == ["english10_p4"]
    assert target["title"] == "Literary Analysis - Period 4"
    assert target["student_prompt"] == (
        "Analyze how the author develops the central idea."
    )
    assert target["writing_type"] == "literary_analysis"
    assert target["standards_profile_id"] == "english10_profile"
    assert target["focus_standard_ids"] == [STANDARD_ID, SECOND_STANDARD_ID]
    assert target["review_unit"] == {
        "type": "paragraph",
        "singular_label": "paragraph",
        "plural_label": "paragraphs",
    }
    assert target["basic_requirements"]["paragraphs_min"] == 4
    assert target["minimum_requirement_policy"] == {
        "allow_return_without_full_review": True
    }
    assert target["created_at"] == "2026-08-19T23:00:00+00:00"
    assert target["updated_at"] == target["created_at"]
    assert target["module_details"] == {}
    assert target["created_at"] != _source_assignment()["created_at"]

    saved = commit_assignment_copy(plan)

    assert len(saved) == 1
    assert load_assignment_config(saved[0]) == target
    assert source_path.read_bytes() == source_bytes


def test_copy_within_same_class_requires_new_assignment_id(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2")
    _write_source(tmp_path)

    with pytest.raises(AssignmentCopyError, match="cannot be its own"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p2"],
            target_assignment_id="literary_analysis",
        )

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p2"],
        target_assignment_id="literary_analysis_revision",
    )
    saved = commit_assignment_copy(plan)
    assert saved[0].parent.name == "literary_analysis_revision"


def test_copy_to_multiple_classes_uses_exact_target_class_set(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p3", "english10_p4")
    _write_source(
        tmp_path,
        class_ids=["english10_p2", "english10_p3"],
    )

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p3", "english10_p4"],
        target_assignment_id="literary_analysis_copy",
    )
    saved = commit_assignment_copy(plan)

    assert plan.assignment["class_ids"] == ["english10_p3", "english10_p4"]
    assert len(saved) == 2
    assert load_assignment_config(saved[0]) == load_assignment_config(saved[1])
    source_sibling = quillan_work_paths(
        tmp_path, "english10_p3", "literary_analysis"
    ).assignment_path
    assert not source_sibling.exists()


def test_copy_rejects_any_existing_target_state_without_cleaning_it(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    paths = quillan_work_paths(tmp_path, "english10_p4", "literary_analysis")
    marker = paths.submissions_dir / "synthetic1" / "review.json"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"existing-state")

    with pytest.raises(AssignmentCopyError, match="already contains assignment state"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert marker.read_bytes() == b"existing-state"
    assert not paths.assignment_path.exists()


def test_copy_accepts_only_empty_canonical_managed_skeleton(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    target_paths = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    )
    initialize_managed_work_layout(target_paths)

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    commit_assignment_copy(plan)

    assert target_paths.assignment_path.is_file()


def test_copy_never_copies_source_descendants(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    source_root = source_path.parent
    rich_state = {
        "response_pages/issuances/issue.json": b"issuance",
        "response_pages/pages/page.json": b"page",
        "routes/source-route.json": b"route",
        "templates/printable_response_pages.pdf": b"pdf",
        "scans/evidence/issue/evidence.png": b"evidence",
        "scans/review/post_dispatch/failure.json": b"review",
        "submissions/synthetic1/submission.json": b"submission",
        "submissions/synthetic1/review.json": b"review-record",
        "submissions/synthetic1/exports/feedback.md": b"feedback",
        "exports/class_summary.csv": b"report",
        "exports/manifests/academic_results/1.json": b"manifest",
        "future_state/new_kind.json": b"future",
    }
    for relative, content in rich_state.items():
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    source_snapshot = {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*")
        if path.is_file()
    }

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    saved = commit_assignment_copy(plan)
    target_root = saved[0].parent

    target_files = {
        path.relative_to(target_root).as_posix()
        for path in target_root.rglob("*")
        if path.is_file()
    }
    assert target_files == {"assignment.json"}
    assert {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*")
        if path.is_file()
    } == source_snapshot


def test_copy_detects_source_change_after_preview(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["title"] = "Concurrent source edit"
    source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(AssignmentCopyError, match="changed after preview"):
        commit_assignment_copy(plan)

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()


def test_copy_detects_target_state_added_after_preview(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    target_paths = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    )
    marker = target_paths.exports_dir / "concurrent.csv"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"concurrent")

    with pytest.raises(AssignmentCopyError, match="already contains assignment state"):
        commit_assignment_copy(plan)

    assert marker.read_bytes() == b"concurrent"
    assert not target_paths.assignment_path.exists()


def test_copy_revalidates_source_standards_against_current_library(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    _write_standards(tmp_path, include_profile=False)

    with pytest.raises(AssignmentCopyError, match="standards are not valid"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )


def test_copy_requires_valid_target_roster(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2")
    _write_source(tmp_path)

    with pytest.raises(AssignmentCopyError, match="roster-ready"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )




def test_copy_allowlist_resets_module_details_and_excludes_unknown_fields(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["module_details"] = {"source_only": {"sentinel": True}}
    source["future_assignment_state"] = {"must_not_copy": True}
    source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )

    target = plan.assignment
    assert target["module_details"] == {}
    assert "future_assignment_state" not in target


def test_copy_multi_target_preflight_failure_writes_nothing(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    # Core routes are work-local but not part of Quillan's empty managed skeleton.
    blocked_path = (
        quillan_work_paths(tmp_path, "english10_p5", "literary_analysis").work_root
        / "routes"
        / "orphan.json"
    )
    blocked_path.parent.mkdir(parents=True)
    blocked_path.write_bytes(b"route-state")

    with pytest.raises(AssignmentCopyError):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4", "english10_p5"],
            target_assignment_id="literary_analysis",
        )

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root.exists()
    assert blocked_path.read_bytes() == b"route-state"


def test_copy_rejects_link_like_target_state(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    target_root = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root
    target_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = target_root / "future_state"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(AssignmentCopyError, match="symlink|junction|reparse"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )


@pytest.mark.parametrize(
    "responses",
    [
        ["b"],
        ["1", "1", "b"],
        ["1", "1", "2", "b"],
        ["1", "1", "2", "", "b"],
        ["1", "1", "2", "", "", "b"],
        ["1", "1", "2", "", "", "", "n"],
    ],
)
def test_teacher_copy_cancellation_is_side_effect_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    source_bytes = source_path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    answers = iter(responses)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    assert copy_workflows.prompt_copy_assignment() == 0

    assert source_path.read_bytes() == source_bytes
    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root.exists()

def test_copy_rejects_preexisting_core_academic_work_state(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    target_assignment = _source_assignment(
        class_ids=["english10_p4"],
    )
    target_path = workflows.write_assignment_config(
        tmp_path, "english10_p4", target_assignment
    )
    register_quillan_academic_work(
        tmp_path,
        "english10_p4",
        "literary_analysis",
        academic_intent="formative",
        lifecycle="planned",
    )
    shutil.rmtree(target_path.parent)

    with pytest.raises(AssignmentCopyError, match="Academic Work Registration"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert not target_path.parent.exists()

def test_teacher_copy_workflow_reuses_configuration_without_reentry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    recorder = MenuScreenRecorder(
        [
            "2",  # Assignment Management -> copy
            "1",  # source class
            "1",  # source assignment
            "2",  # target class
            "",   # reuse assignment ID
            "",   # reuse title
            "",   # reuse prompt
            "",   # save
            "",   # parent-menu pause
            "b",
        ]
    )
    recorder.install(monkeypatch)

    assert workflows.launch_assignment_menu() == 0

    screens = recorder.screens(capsys.readouterr().out)
    prompt_text = "\n".join(item.prompt for item in recorder.prompts)
    assert "Copy Writing Assignment" in "\n".join(screen.output for screen in screens)
    assert "Review Copied Assignment Before Saving" in "\n".join(
        screen.output for screen in screens
    )
    assert "Writing type:" not in prompt_text
    assert "Select standards profile:" not in prompt_text
    assert "Select Focus Standards by number" not in prompt_text
    assert "Use default paragraph review units?" not in prompt_text
    assert "Use default four-level standards scale?" not in prompt_text
    assert "paragraphs_min:" not in prompt_text
    assert "Allow teacher to return work" not in prompt_text
    target = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path
    assert target.is_file()



def test_copy_preserves_structured_batch_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    possibly_durable = tmp_path / "possibly-durable.json"

    def fail_write(*_args: object, **_kwargs: object) -> tuple[Path, ...]:
        raise AssignmentBatchWriteError(
            "synthetic batch failure",
            possibly_durable_paths=(possibly_durable,),
            rollback_diagnostics=("synthetic rollback diagnostic",),
        )

    monkeypatch.setattr(copy_module, "write_assignment_configs", fail_write)

    with pytest.raises(AssignmentBatchWriteError) as error:
        commit_assignment_copy(plan)

    assert error.value.possibly_durable_paths == (possibly_durable,)
    assert error.value.rollback_diagnostics == ("synthetic rollback diagnostic",)

def test_copy_detects_standards_change_after_preview(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    _write_standards(tmp_path, include_profile=False)

    with pytest.raises(AssignmentCopyError, match="standards changed after preview"):
        commit_assignment_copy(plan)

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()


def test_copy_detects_target_roster_change_after_preview(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    roster_path = tmp_path / "classes" / "english10_p4" / "roster.csv"
    roster_path.unlink()

    with pytest.raises(AssignmentCopyError, match="changed after preview"):
        commit_assignment_copy(plan)

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()


def test_copy_rejects_removed_focus_standard_before_target_mutation(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    write_workspace_standards_library(
        tmp_path,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.AW.9-10.1",
                    source="NJSLS",
                    short_name="Argument",
                    description="Write arguments.",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id=SECOND_STANDARD_ID,
                    code="RL.CR.9-10.1",
                    source="NJSLS",
                    short_name="Reading",
                    description="Read closely.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="english10_profile",
                    standards=(STANDARD_ID,),
                    title="English 10",
                ),
            ),
        ),
        overwrite=True,
    )

    with pytest.raises(AssignmentCopyError, match="standards are not valid"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root.exists()


def test_copy_rejects_malformed_standards_library_before_target_mutation(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    standards_path = tmp_path / "standards" / "library.json"
    standards_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(AssignmentCopyError, match="standards are not valid"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root.exists()


def test_copy_rejects_invalid_target_roster_without_mutation(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    roster_path = tmp_path / "classes" / "english10_p4" / "roster.csv"
    roster_path.write_text(
        "class_id,student_id\nenglish10_p4,synthetic1\n",
        encoding="utf-8",
    )

    with pytest.raises(AssignmentCopyError, match="roster-ready"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root.exists()


def test_copy_rejects_duplicate_target_class_selection(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)

    with pytest.raises(AssignmentCopyError, match="must be unique"):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4", "english10_p4"],
            target_assignment_id="literary_analysis",
        )


@pytest.mark.parametrize(
    "relative_path",
    (
        "assignment.json",
        "scans/evidence/issue/evidence.png",
        "exports/manifests/academic_results/1.json",
        "routes/route_001.json",
    ),
)
def test_copy_rejects_representative_existing_target_state(
    tmp_path: Path,
    relative_path: str,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    target_root = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).work_root
    marker = target_root / relative_path
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"preexisting-target-state")

    with pytest.raises(AssignmentCopyError):
        plan_assignment_copy(
            tmp_path,
            source_class_id="english10_p2",
            source_assignment_id="literary_analysis",
            target_class_ids=["english10_p4"],
            target_assignment_id="literary_analysis",
        )

    assert marker.read_bytes() == b"preexisting-target-state"


@pytest.mark.parametrize("mutation", ("remove", "invalid"))
def test_copy_detects_source_unavailable_or_invalid_after_preview(
    tmp_path: Path,
    mutation: str,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    source_path = _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )

    if mutation == "remove":
        source_path.unlink()
    else:
        source_path.write_bytes(b"{not valid json")

    with pytest.raises(
        AssignmentCopyError,
        match="changed or became unavailable after planning",
    ):
        commit_assignment_copy(plan)

    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()


def test_copy_detects_target_assignment_appearing_after_preview(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    target_path = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(b"concurrent-target-assignment")

    with pytest.raises(AssignmentCopyError, match="already contains assignment state"):
        commit_assignment_copy(plan)

    assert target_path.read_bytes() == b"concurrent-target-assignment"


def test_copy_real_batch_writer_compensates_first_target_when_second_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4", "english10_p5"],
        target_assignment_id="literary_analysis",
    )
    original_create = atomic_record_io.create_exclusive_record
    calls = 0

    def fail_second_write(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic second-target write failure")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(workflows, "create_exclusive_record", fail_second_write)

    with pytest.raises(AssignmentBatchWriteError) as error:
        commit_assignment_copy(plan)

    assert "synthetic second-target write failure" in str(error.value)
    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()
    assert not quillan_work_paths(
        tmp_path, "english10_p5", "literary_analysis"
    ).assignment_path.exists()


def test_copy_real_batch_writer_compensates_after_second_target_verification_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4", "english10_p5"],
        target_assignment_id="literary_analysis",
    )
    original_create = atomic_record_io.create_exclusive_record
    calls = 0

    def fail_second_verification(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            def reject_verification(_loaded: Any) -> None:
                raise ValueError("synthetic second-target verification failure")

            kwargs["verify_bytes"] = reject_verification
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        workflows,
        "create_exclusive_record",
        fail_second_verification,
    )

    with pytest.raises(AssignmentBatchWriteError) as error:
        commit_assignment_copy(plan)

    assert "synthetic second-target verification failure" in str(error.value)
    assert not error.value.possibly_durable_paths
    assert not quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path.exists()
    assert not quillan_work_paths(
        tmp_path, "english10_p5", "literary_analysis"
    ).assignment_path.exists()


def test_copy_reports_compensation_failure_as_possibly_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4", "english10_p5"],
        target_assignment_id="literary_analysis",
    )
    first_path = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path
    original_create = atomic_record_io.create_exclusive_record
    calls = 0

    def fail_second_write(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic second-target failure")
        return original_create(*args, **kwargs)

    def fail_compensation(
        _root: Path,
        _work_ref: Any,
        entry: Any,
    ) -> tuple[str | None, tuple[Path, ...]]:
        path = Path(entry.path)
        return "synthetic compensation failure", (path,)

    monkeypatch.setattr(workflows, "create_exclusive_record", fail_second_write)
    monkeypatch.setattr(
        workflows,
        "_compensate_assignment_entry",
        fail_compensation,
    )

    with pytest.raises(AssignmentBatchWriteError) as error:
        commit_assignment_copy(plan)

    assert first_path.exists()
    assert first_path in error.value.possibly_durable_paths
    assert "synthetic compensation failure" in error.value.rollback_diagnostics


def test_copy_preserves_concurrent_target_mutation_during_compensation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4", "english10_p5"],
        target_assignment_id="literary_analysis",
    )
    first_path = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis"
    ).assignment_path
    second_path = quillan_work_paths(
        tmp_path, "english10_p5", "literary_analysis"
    ).assignment_path
    concurrent_bytes = b'{"concurrent":"preserve-me"}\n'
    original_create = atomic_record_io.create_exclusive_record
    calls = 0

    def mutate_first_then_fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            first_path.write_bytes(concurrent_bytes)
            raise OSError("synthetic second-target failure after concurrent mutation")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        workflows,
        "create_exclusive_record",
        mutate_first_then_fail_second,
    )

    with pytest.raises(AssignmentBatchWriteError) as error:
        commit_assignment_copy(plan)

    assert first_path.read_bytes() == concurrent_bytes
    assert not second_path.exists()
    assert first_path in error.value.possibly_durable_paths
    assert any(
        "changed before compensation" in diagnostic
        for diagnostic in error.value.rollback_diagnostics
    )


def test_copy_preserves_source_core_and_shared_state(tmp_path: Path) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    register_quillan_academic_work(
        tmp_path,
        "english10_p2",
        "literary_analysis",
        academic_intent="formative",
        lifecycle="planned",
    )
    source_route = (
        quillan_work_paths(tmp_path, "english10_p2", "literary_analysis").work_root
        / "routes"
        / "source-route.json"
    )
    source_route.parent.mkdir(parents=True)
    source_route.write_bytes(b"source-route-state")

    registry_root = tmp_path / "registry"
    registry_before = {
        path.relative_to(registry_root).as_posix(): path.read_bytes()
        for path in registry_root.rglob("*")
        if path.is_file()
    }
    standards_path = tmp_path / "standards" / "library.json"
    standards_before = standards_path.read_bytes()
    roster_paths = (
        tmp_path / "classes" / "english10_p2" / "roster.csv",
        tmp_path / "classes" / "english10_p4" / "roster.csv",
    )
    roster_before = tuple(path.read_bytes() for path in roster_paths)

    plan = plan_assignment_copy(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        target_class_ids=["english10_p4"],
        target_assignment_id="literary_analysis",
    )
    saved = commit_assignment_copy(plan)

    assert {
        path.relative_to(registry_root).as_posix(): path.read_bytes()
        for path in registry_root.rglob("*")
        if path.is_file()
    } == registry_before
    assert standards_path.read_bytes() == standards_before
    assert tuple(path.read_bytes() for path in roster_paths) == roster_before
    assert source_route.read_bytes() == b"source-route-state"
    target_root = saved[0].parent
    assert {
        path.relative_to(target_root).as_posix()
        for path in target_root.rglob("*")
        if path.is_file()
    } == {"assignment.json"}
    assert not (tmp_path / "registry" / "publications").exists()
    assert not (tmp_path / "registry" / "catalog.sqlite").exists()


def test_teacher_copy_workflow_supports_multiclass_title_and_prompt_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4", "english10_p5")
    _write_source(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    responses = iter(
        (
            "1",
            "1",
            "2,3",
            "literary_analysis_copy",
            "Literary Analysis - Revised",
            "Compare how the two authors develop the central idea.",
            "",
        )
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert copy_workflows.prompt_copy_assignment() == 0

    output = capsys.readouterr().out
    assert "Source Assignment" in output
    assert "Review Copied Assignment Before Saving" in output
    assert "Assignment Copy Saved" in output
    assert "not copied" in output
    p4 = quillan_work_paths(
        tmp_path, "english10_p4", "literary_analysis_copy"
    ).assignment_path
    p5 = quillan_work_paths(
        tmp_path, "english10_p5", "literary_analysis_copy"
    ).assignment_path
    first = load_assignment_config(p4)
    second = load_assignment_config(p5)
    assert first == second
    assert first["class_ids"] == ["english10_p4", "english10_p5"]
    assert first["title"] == "Literary Analysis - Revised"
    assert first["student_prompt"] == (
        "Compare how the two authors develop the central idea."
    )


def test_teacher_copy_workflow_reports_collision_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _workspace(tmp_path, "english10_p2", "english10_p4")
    _write_source(tmp_path)
    target = _source_assignment(class_ids=["english10_p4"])
    target_path = workflows.write_assignment_config(tmp_path, "english10_p4", target)
    original = target_path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    responses = iter(("1", "1", "2", "", "", ""))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert copy_workflows.prompt_copy_assignment() == 1

    assert target_path.read_bytes() == original
    output = capsys.readouterr().out
    assert "already contains assignment state" in output
    assert "Traceback" not in output
