# Installed v0.10.0 class-set workflow acceptance over canonical state.

from __future__ import annotations

import argparse
import importlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from pds_core.classes import write_class_roster
from pds_core.module_operations import (
    ModuleAttentionReport,
    ModuleOperationsRequest,
    ModuleReadinessReport,
    invoke_module_attention,
    invoke_module_readiness,
)
from pds_core.rosters import create_roster

from quillan.assignment_copying import commit_assignment_copy, plan_assignment_copy
from quillan.batch_feedback_export import (
    build_batch_feedback_export_plan,
    execute_batch_feedback_export,
)
from quillan.class_review_completion import build_class_review_completion_view
from quillan.diagnostic_events import list_diagnostic_events
from quillan.menu_context import MenuSessionContext, revalidate_menu_context
from quillan.review_configuration_presets import (
    PRESET_CONFIGURATION_FIELDS,
    commit_review_configuration_preset,
    inspect_review_configuration_presets,
    plan_review_configuration_preset_from_assignment,
)
from quillan.review_continuation import derive_review_continuation
from quillan.review_student_navigation import build_review_student_navigation
from quillan.review_work_queue import build_assignment_review_work_queue
from quillan.pds_operations import get_module_operations_profile

EXPECTED_QUILLAN_VERSION = "0.10.2"
CLASS_ID = "synthetic_release_class"
ASSIGNMENT_ID = "synthetic_release_digital"
COPY_ASSIGNMENT_ID = "synthetic_release_copy"
PRESET_ID = "synthetic_release_preset"
STANDARD_ID = "synthetic:W.RELEASE.1"
MATRIX_CLASS_ID = "synthetic_matrix_class"
MATRIX_ASSIGNMENT_ID = "synthetic_matrix_assignment"
MATRIX_STUDENT_IDS = (
    "m001_no_submission",
    "m002_minimum",
    "m003_observations",
    "m004_ratings",
    "m005_feedback",
    "m006_export_missing",
    "m007_export_stale",
    "m008_complete",
)


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    origin = module.__file__
    assert origin is not None, module_name
    return Path(origin).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    assert type(value) is dict, path
    return value


def _run_cli(workspace: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PDS_WORKSPACE_ROOT"] = str(workspace)
    command = [
        sys.executable,
        "-c",
        "from quillan.cli import main; raise SystemExit(main())",
        *arguments,
    ]
    result = subprocess.run(
        command,
        cwd=workspace.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"installed CLI failed: {arguments!r}\n{result.stdout}\n{result.stderr}"
        )
    return result


def _matrix_identity(student_id: str) -> list[str]:
    return [MATRIX_CLASS_ID, MATRIX_ASSIGNMENT_ID, student_id]


def _set_minimum_met(workspace: Path, student_id: str) -> None:
    identity = _matrix_identity(student_id)
    _run_cli(
        workspace,
        [
            "requirements",
            "set-check",
            *identity,
            "--requirement-key",
            "paragraphs_min",
            "--met",
            "true",
        ],
    )
    _run_cli(
        workspace,
        ["requirements", "set-outcome", *identity, "--outcome", "met"],
    )


def _set_observations_complete(workspace: Path, student_id: str) -> None:
    _set_minimum_met(workspace, student_id)
    identity = _matrix_identity(student_id)
    _run_cli(workspace, ["review-units", "set", *identity, "--count", "1"])
    _run_cli(
        workspace,
        [
            "observations",
            "set",
            *identity,
            "--unit-id",
            "paragraph_1",
            "--standard-id",
            STANDARD_ID,
            "--applicable",
            "true",
            "--evidence-present",
            "true",
            "--rating",
            "2",
            "--rationale",
            "Synthetic matrix evidence.",
            "--include-in-feedback",
            "true",
        ],
    )
    _run_cli(workspace, ["observations", "mark-complete", *identity, "--yes"])


def _set_ratings_complete(workspace: Path, student_id: str) -> None:
    _set_observations_complete(workspace, student_id)
    identity = _matrix_identity(student_id)
    _run_cli(
        workspace,
        [
            "ratings",
            "set",
            *identity,
            "--standard-id",
            STANDARD_ID,
            "--rating",
            "2",
            "--rationale",
            "Synthetic matrix overall rating.",
            "--include-in-feedback",
            "true",
        ],
    )
    _run_cli(workspace, ["ratings", "mark-complete", *identity, "--yes"])


def _set_feedback_composed(workspace: Path, student_id: str) -> None:
    _set_ratings_complete(workspace, student_id)
    identity = _matrix_identity(student_id)
    _run_cli(
        workspace,
        [
            "feedback",
            "set-options",
            *identity,
            "--standard-id",
            STANDARD_ID,
            "--include-overall-rating",
            "true",
            "--include-overall-rationale",
            "true",
            "--observation-ids",
            "observation_0001",
        ],
    )
    _run_cli(
        workspace,
        [
            "feedback",
            "add-comment",
            *identity,
            "--standard-id",
            STANDARD_ID,
            "--text",
            "Synthetic matrix feedback.",
            "--include-in-feedback",
            "true",
        ],
    )
    _run_cli(workspace, ["feedback", "mark-composed", *identity, "--yes"])
    _run_cli(
        workspace,
        [
            "review-workflow",
            "set-state",
            *identity,
            "--state",
            "ready_for_export",
            "--yes",
        ],
    )


def _export_feedback(workspace: Path, student_id: str) -> None:
    _run_cli(
        workspace,
        ["export-feedback", *_matrix_identity(student_id), "--format", "both"],
    )


def _assert_source_isolation(repository: Path) -> dict[str, bool]:
    repository = repository.resolve()
    quillan_origin = _module_origin("quillan")
    core_origin = _module_origin("pds_core")
    assert quillan_origin != repository and not quillan_origin.is_relative_to(repository)
    assert core_origin != repository and not core_origin.is_relative_to(repository)
    return {
        "quillan_source_isolated": True,
        "core_source_isolated": True,
    }


def _exercise_assignment_copy(workspace: Path) -> dict[str, object]:
    plan = plan_assignment_copy(
        workspace,
        source_class_id=CLASS_ID,
        source_assignment_id=ASSIGNMENT_ID,
        target_class_ids=[CLASS_ID],
        target_assignment_id=COPY_ASSIGNMENT_ID,
        title="Synthetic Release Copy",
    )
    paths = commit_assignment_copy(plan)
    assert len(paths) == 1
    copied = paths[0]
    files = tuple(
        sorted(
            path.relative_to(copied.parent).as_posix()
            for path in copied.parent.rglob("*")
            if path.is_file()
        )
    )
    assert files == ("assignment.json",)

    source = _load_json(
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    target = _load_json(copied)
    assert target["assignment_id"] == COPY_ASSIGNMENT_ID
    assert target["class_ids"] == [CLASS_ID]
    for field in (
        "writing_type",
        "standards_profile_id",
        "focus_standard_ids",
        "review_unit",
        "rating_scale",
        "basic_requirements",
        "minimum_requirement_policy",
    ):
        assert target[field] == source[field], field
    assert target["module_details"] == {}
    return {
        "assignment_copy": "passed",
        "copy_target_files": list(files),
    }


def _exercise_review_preset(workspace: Path) -> dict[str, object]:
    plan = plan_review_configuration_preset_from_assignment(
        workspace,
        source_class_id=CLASS_ID,
        source_assignment_id=ASSIGNMENT_ID,
        preset_id=PRESET_ID,
        title="Synthetic Release Preset",
        description="Installed #393 reusable review configuration.",
    )
    path = commit_review_configuration_preset(plan)
    assert path.is_file()
    inspections = inspect_review_configuration_presets(workspace)
    item = next(
        candidate
        for candidate in inspections
        if candidate.preset is not None
        and candidate.preset["preset_id"] == PRESET_ID
    )
    assert item.status == "valid"
    assert item.preset is not None

    source = _load_json(
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    for field in PRESET_CONFIGURATION_FIELDS:
        assert item.preset[field] == source[field], field
    for forbidden in ("assignment_id", "class_ids", "student_prompt"):
        assert forbidden not in item.preset
    return {
        "review_preset": "passed",
        "preset_status": item.status,
    }


def _exercise_context(workspace: Path) -> dict[str, object]:
    context = MenuSessionContext()
    assert context.bind_workspace(workspace) is False
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    validated = revalidate_menu_context(context, workspace)
    assert validated.assignment is not None
    assert validated.assignment.class_id == CLASS_ID
    assert validated.assignment.assignment_id == ASSIGNMENT_ID

    context.clear_assignment()
    assert context.class_id == CLASS_ID
    assert context.assignment_id is None
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    context.clear_selection()
    assert context.class_id is None
    assert context.assignment_id is None
    context.activate_assignment(CLASS_ID, ASSIGNMENT_ID)
    return {
        "recent_context": "passed",
        "active_class_id": context.class_id,
        "active_assignment_id": context.assignment_id,
    }


def _exercise_class_review_state(workspace: Path) -> dict[str, object]:
    queue = build_assignment_review_work_queue(workspace, CLASS_ID, ASSIGNMENT_ID)
    assert tuple(item.student_id for item in queue.items) == ("00107", "00208")
    assert tuple(item.category for item in queue.items) == (
        "complete",
        "minimum_requirements_pending",
    )
    assert queue.items[0].reason_code == "current_feedback_export_present"
    assert queue.items[1].reason_code == "minimum_requirement_outcome_not_checked"
    assert queue.complete_count == 1
    assert queue.roster_count == 2

    first = build_review_student_navigation(
        workspace, CLASS_ID, ASSIGNMENT_ID, "00107"
    )
    assert first.position == 1
    assert first.previous is None
    assert first.next is not None and first.next.student_id == "00208"
    assert first.next_needing_review is not None
    assert first.next_needing_review.student_id == "00208"

    second = build_review_student_navigation(
        workspace, CLASS_ID, ASSIGNMENT_ID, "00208"
    )
    assert second.position == 2
    assert second.previous is not None and second.previous.student_id == "00107"
    assert second.next is None
    assert second.next_needing_review is None

    first_continuation = derive_review_continuation(first.current)
    assert first_continuation.status == "complete"
    assert first_continuation.target is None
    second_continuation = derive_review_continuation(second.current)
    assert second_continuation.status == "available"
    assert second_continuation.target == "minimum_requirements"

    completion = build_class_review_completion_view(
        workspace, CLASS_ID, ASSIGNMENT_ID
    )
    assert completion.roster_count == 2
    assert completion.complete_count == 1
    assert completion.needs_work_count == 1
    assert completion.export_pending_count == 0

    plan = build_batch_feedback_export_plan(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="completed",
        feedback_format="both",
        overwrite_policy="none",
    )
    assert tuple(item.student_id for item in plan.items) == ("00107",)
    assert all(item.action == "skip_current" for item in plan.items)
    result = execute_batch_feedback_export(workspace, plan)
    assert result.failure_count == 0
    assert all(item.outcome == "skipped_current" for item in result.items)

    return {
        "review_queue": "passed",
        "queue_categories": [item.category for item in queue.items],
        "queue_reason_codes": [item.reason_code for item in queue.items],
        "navigation": {
            "first_previous": None,
            "first_next": first.next.student_id if first.next else None,
            "first_next_needing_review": (
                first.next_needing_review.student_id
                if first.next_needing_review
                else None
            ),
            "second_previous": second.previous.student_id if second.previous else None,
            "second_next": None,
        },
        "continue_review": {
            "00107": {
                "status": first_continuation.status,
                "target": first_continuation.target,
            },
            "00208": {
                "status": second_continuation.status,
                "target": second_continuation.target,
            },
        },
        "batch_feedback": {
            "actions": [item.action for item in plan.items],
            "outcomes": [item.outcome for item in result.items],
        },
        "class_completion": {
            "roster_count": completion.roster_count,
            "complete_count": completion.complete_count,
            "needs_work_count": completion.needs_work_count,
        },
    }


def _exercise_mixed_matrix(workspace: Path) -> dict[str, object]:
    students = tuple(
        {
            "student_id": student_id,
            "last_name": "Matrix",
            "first_name": f"Student {index}",
            "period": "5",
        }
        for index, student_id in enumerate(MATRIX_STUDENT_IDS, start=1)
    )
    write_class_roster(workspace, create_roster(MATRIX_CLASS_ID, students))

    copy_plan = plan_assignment_copy(
        workspace,
        source_class_id=CLASS_ID,
        source_assignment_id=ASSIGNMENT_ID,
        target_class_ids=[MATRIX_CLASS_ID],
        target_assignment_id=MATRIX_ASSIGNMENT_ID,
        title="Synthetic Installed Mixed-State Matrix",
    )
    copied = commit_assignment_copy(copy_plan)
    assert len(copied) == 1

    for student_id in MATRIX_STUDENT_IDS[1:]:
        _run_cli(
            workspace,
            [
                "create-plain-paper-submission",
                MATRIX_CLASS_ID,
                MATRIX_ASSIGNMENT_ID,
                student_id,
                "--yes",
            ],
        )

    _set_minimum_met(workspace, MATRIX_STUDENT_IDS[2])
    _set_observations_complete(workspace, MATRIX_STUDENT_IDS[3])
    _set_ratings_complete(workspace, MATRIX_STUDENT_IDS[4])
    _set_feedback_composed(workspace, MATRIX_STUDENT_IDS[5])

    _set_feedback_composed(workspace, MATRIX_STUDENT_IDS[6])
    _export_feedback(workspace, MATRIX_STUDENT_IDS[6])
    _run_cli(
        workspace,
        [
            "add-note",
            *_matrix_identity(MATRIX_STUDENT_IDS[6]),
            "--text",
            "Synthetic note after export to make feedback stale.",
        ],
    )

    _set_feedback_composed(workspace, MATRIX_STUDENT_IDS[7])
    _export_feedback(workspace, MATRIX_STUDENT_IDS[7])

    queue = build_assignment_review_work_queue(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
    )
    expected_categories = (
        "no_submission",
        "minimum_requirements_pending",
        "observations_pending",
        "ratings_pending",
        "feedback_pending",
        "export_pending",
        "export_pending",
        "complete",
    )
    actual_categories = tuple(item.category for item in queue.items)
    assert tuple(item.student_id for item in queue.items) == MATRIX_STUDENT_IDS
    assert actual_categories == expected_categories

    by_id = {item.student_id: item for item in queue.items}
    assert by_id[MATRIX_STUDENT_IDS[5]].reason_code == "feedback_export_missing"
    assert by_id[MATRIX_STUDENT_IDS[6]].reason_code == "feedback_export_stale"
    assert by_id[MATRIX_STUDENT_IDS[7]].reason_code == (
        "current_feedback_export_present"
    )

    continuation_targets = {
        student_id: (
            derive_review_continuation(by_id[student_id]).status,
            derive_review_continuation(by_id[student_id]).target,
        )
        for student_id in MATRIX_STUDENT_IDS
    }
    assert continuation_targets[MATRIX_STUDENT_IDS[0]] == ("unavailable", None)
    assert continuation_targets[MATRIX_STUDENT_IDS[1]] == (
        "available",
        "minimum_requirements",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[2]] == (
        "available",
        "review_unit_observations",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[3]] == (
        "available",
        "overall_focus_standard_ratings",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[4]] == (
        "available",
        "focus_standard_feedback",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[5]] == (
        "available",
        "feedback_export",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[6]] == (
        "available",
        "feedback_export",
    )
    assert continuation_targets[MATRIX_STUDENT_IDS[7]] == ("complete", None)

    navigation = build_review_student_navigation(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
        MATRIX_STUDENT_IDS[2],
    )
    assert navigation.previous is not None
    assert navigation.previous.student_id == MATRIX_STUDENT_IDS[1]
    assert navigation.next is not None
    assert navigation.next.student_id == MATRIX_STUDENT_IDS[3]
    assert navigation.next_needing_review is not None
    assert navigation.next_needing_review.student_id == MATRIX_STUDENT_IDS[3]

    before_completion = build_class_review_completion_view(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
    )
    assert before_completion.roster_count == len(MATRIX_STUDENT_IDS)
    assert before_completion.complete_count == 1
    assert before_completion.needs_work_count == 7
    assert before_completion.export_pending_count == 2

    missing_plan = build_batch_feedback_export_plan(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
        scope="selected",
        feedback_format="both",
        overwrite_policy="none",
        student_ids=(MATRIX_STUDENT_IDS[5],),
    )
    assert missing_plan.items[0].action == "create"
    missing_result = execute_batch_feedback_export(workspace, missing_plan)
    assert missing_result.failure_count == 0
    assert missing_result.items[0].outcome == "created"

    stale_plan = build_batch_feedback_export_plan(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
        scope="selected",
        feedback_format="both",
        overwrite_policy="stale",
        student_ids=(MATRIX_STUDENT_IDS[6],),
    )
    assert stale_plan.items[0].action == "replace"
    stale_result = execute_batch_feedback_export(workspace, stale_plan)
    assert stale_result.failure_count == 0
    assert stale_result.items[0].outcome == "replaced"

    after_completion = build_class_review_completion_view(
        workspace,
        MATRIX_CLASS_ID,
        MATRIX_ASSIGNMENT_ID,
    )
    assert after_completion.complete_count == 3
    assert after_completion.needs_work_count == 5
    assert after_completion.export_pending_count == 0

    profile = get_module_operations_profile()
    request = ModuleOperationsRequest(
        workspace_root=workspace,
        class_id=MATRIX_CLASS_ID,
    )
    readiness = invoke_module_readiness(profile, request)
    assert readiness.code == "module_operations.evaluated"
    assert isinstance(readiness.report, ModuleReadinessReport)
    assert readiness.report.ready is True

    attention = invoke_module_attention(profile, request)
    assert attention.code == "module_operations.evaluated"
    assert isinstance(attention.report, ModuleAttentionReport)
    assert attention.report.summaries

    diagnostics = list_diagnostic_events(workspace, limit=200)
    diagnostic_codes = tuple(event.code for event in diagnostics.events)
    assert "batch_export_verified" in diagnostic_codes

    return {
        "mixed_matrix": "passed",
        "pre_batch_categories": list(actual_categories),
        "pre_batch_reason_codes": {
            student_id: by_id[student_id].reason_code
            for student_id in MATRIX_STUDENT_IDS
        },
        "continuation": {
            student_id: {
                "status": continuation_targets[student_id][0],
                "target": continuation_targets[student_id][1],
            }
            for student_id in MATRIX_STUDENT_IDS
        },
        "navigation": {
            "current": MATRIX_STUDENT_IDS[2],
            "previous": navigation.previous.student_id,
            "next": navigation.next.student_id,
            "next_needing_review": navigation.next_needing_review.student_id,
        },
        "batch_feedback": {
            "missing_action": missing_plan.items[0].action,
            "missing_outcome": missing_result.items[0].outcome,
            "stale_action": stale_plan.items[0].action,
            "stale_outcome": stale_result.items[0].outcome,
        },
        "completion_before_batch": {
            "complete": before_completion.complete_count,
            "needs_work": before_completion.needs_work_count,
            "export_pending": before_completion.export_pending_count,
        },
        "completion_after_batch": {
            "complete": after_completion.complete_count,
            "needs_work": after_completion.needs_work_count,
            "export_pending": after_completion.export_pending_count,
        },
        "operations_independence": {
            "readiness_ready": readiness.report.ready,
            "attention_summary_codes": sorted(
                {summary.code for summary in attention.report.summaries}
            ),
        },
        "diagnostic_codes": sorted(set(diagnostic_codes)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument(
        "--expected-core-version",
        choices=("0.6.2", "0.6.3"),
        required=True,
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve(strict=True)
    repository = args.repository.resolve(strict=True)
    assert workspace.is_dir()

    assert metadata.version("quillan") == EXPECTED_QUILLAN_VERSION
    assert metadata.version("pds-core") == args.expected_core_version

    result: dict[str, object] = {
        "quillan_version": EXPECTED_QUILLAN_VERSION,
        "core_version": args.expected_core_version,
        **_assert_source_isolation(repository),
        **_exercise_assignment_copy(workspace),
        **_exercise_review_preset(workspace),
        **_exercise_context(workspace),
        **_exercise_class_review_state(workspace),
        **_exercise_mixed_matrix(workspace),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
