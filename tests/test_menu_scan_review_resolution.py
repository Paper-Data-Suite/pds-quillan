"""Menu tests for teacher-facing Quillan scan review resolution."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import RouteLocator

from quillan.cli import main
from quillan.submission_observation_assembly import QuillanSubmissionAssemblyBatch
import quillan.review_menu as review_menu
import quillan.scan_review_menu as scan_review_menu
from quillan.post_dispatch_review import (
    PersistedPostDispatchReviewOccurrence,
    create_post_dispatch_review_occurrence,
)
from quillan.post_dispatch_review_resolution import (
    discover_post_dispatch_review_items,
)
from quillan.work_paths import quillan_work_ref
from quillan.work_paths import quillan_work_paths
from quillan.submission_manifest_paths import submission_manifest_path
from tests.test_scan_review_resolution import _write_failure, _write_routed_failure
from tests.test_post_dispatch_review_resolution import _retry_case
from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen


def _inputs(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> list[str]:
    responses: Iterator[str] = iter(values)
    prompts: list[str] = []

    def fake_input(_prompt: str = "") -> str:
        prompts.append(_prompt)
        try:
            return next(responses)
        except StopIteration as error:
            raise AssertionError("Menu requested unexpected input.") from error

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


@pytest.mark.menu_density_workflow("Core scan review")
def test_menu_resolves_one_scan_review_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure_path = _write_failure(tmp_path)
    before = failure_path.read_bytes()
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    recorder = MenuScreenRecorder(
        ["2", "r", "1", "1", "1", "", "3", "", "y", "", "", "b", "b", "q"],
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Scan Review Details",
        required_text="No QR payload was found.",
        forbidden_parent_text="Select a review item:",
        parent_heading="Resolve Scan Review Items",
        result_heading="Core Routing Review Result",
        unrelated_previous_text="teacher_scan.pdf, page 2",
    )
    assert "Resolve Scan Review Items" in output
    assert "Select Scan Review Assignment" in output
    assert "No QR payload was found." in output
    assert "Core routing-review item resolved." in output
    assert "scans/review/resolutions/" in output
    assert failure_path.read_bytes() == before
    assert "archive" not in output.casefold()


def test_menu_scan_review_empty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["2", "r", "", "b", "q"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "There are no unresolved or deferred scan review items." in output
    assert not (tmp_path / "scans").exists()
    assert "archive" not in output.casefold()


def _post_dispatch_occurrence(
    root: Path,
) -> PersistedPostDispatchReviewOccurrence:
    return create_post_dispatch_review_occurrence(
        root,
        quillan_work_ref("english12_p3", "essay_01"),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Synthetic assembly failure.",
        student_id="student_01",
    )


def test_global_scan_review_reaches_post_dispatch_only_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _post_dispatch_occurrence(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["2", "r", "1", "1", "b", "b", "b", "q"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Select Scan Review Assignment" in output
    assert "Class: english12_p3; Assignment: essay_01" in output
    assert "Quillan Post-Dispatch Problems" in output
    assert "submission_assembly" in output
    assert "\nResolve Scan Review Items\n" not in output


def test_global_scan_review_combined_source_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_failure(tmp_path)
    _post_dispatch_occurrence(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["2", "r", "1", "1", "b", "b", "b", "q"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Select Scan Review Assignment" in output
    assert "1. Core routing problems" in output
    assert "2. Quillan post-dispatch problems" in output
    assert "3. All active problems" in output


def _unscoped_core_failure(root: Path, *, suffix: str = "c1d2e3f4a5b6") -> Path:
    return _write_failure(
        root,
        failure_id=f"failure_20260711T130000000000Z_{suffix}",
        scoped=False,
    )


def test_global_scan_review_unscoped_core_only_remains_reachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _unscoped_core_failure(tmp_path)
    recorder = MenuScreenRecorder(["b"])
    recorder.install(monkeypatch)

    scan_review_menu.launch_scan_review_resolution_menu(tmp_path)

    screen = recorder.screens(capsys.readouterr().out)[0].output
    assert "Scan Review" in screen
    assert "2. Unscoped Core routing problems" in screen
    assert "3. All Core routing problems" in screen
    assert "Select assignment-scoped problems" not in screen


def test_global_scan_review_scoped_and_unscoped_core_show_all_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_failure(tmp_path)
    _unscoped_core_failure(tmp_path)
    recorder = MenuScreenRecorder(["b"])
    recorder.install(monkeypatch)

    scan_review_menu.launch_scan_review_resolution_menu(tmp_path)

    screen = recorder.screens(capsys.readouterr().out)[0].output
    assert "1. Select assignment-scoped problems" in screen
    assert "2. Unscoped Core routing problems" in screen
    assert "3. All Core routing problems" in screen


def test_global_scan_review_post_dispatch_and_unscoped_core_show_all_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _post_dispatch_occurrence(tmp_path)
    _unscoped_core_failure(tmp_path)
    recorder = MenuScreenRecorder(["b"])
    recorder.install(monkeypatch)

    scan_review_menu.launch_scan_review_resolution_menu(tmp_path)

    screen = recorder.screens(capsys.readouterr().out)[0].output
    assert "1. Select assignment-scoped problems" in screen
    assert "2. Unscoped Core routing problems" in screen
    assert "3. All Core routing problems" in screen


def test_global_scan_review_all_problem_sources_remain_reachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_failure(tmp_path)
    _post_dispatch_occurrence(tmp_path)
    _unscoped_core_failure(tmp_path)
    recorder = MenuScreenRecorder(["1", "b", "2", "b", "3", "b", "b"])
    recorder.install(monkeypatch)

    scan_review_menu.launch_scan_review_resolution_menu(tmp_path)

    screens = recorder.screens(capsys.readouterr().out)
    outputs = tuple(screen.output for screen in screens)
    assert any("Select Scan Review Assignment" in output for output in outputs)
    core_screens = [
        output for output in outputs if "Resolve Scan Review Items" in output
    ]
    assert len(core_screens) == 2
    assert core_screens[0].count("payload_missing") == 1
    assert core_screens[1].count("payload_missing") == 2


def test_selecting_unscoped_core_does_not_fabricate_work_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_failure(tmp_path)
    _unscoped_core_failure(tmp_path)
    recorder = MenuScreenRecorder(["2", "1", "", "b", "b", "b"])
    recorder.install(monkeypatch)

    scan_review_menu.launch_scan_review_resolution_menu(tmp_path)

    screens = recorder.screens(capsys.readouterr().out)
    detail = next(
        screen.output for screen in screens if "Scan Review Details" in screen.output
    )
    assert "Class:" in detail
    assert "Assignment:" in detail
    assert "english12_p3" not in detail
    assert "essay_01" not in detail
    assert screens[-1].output.startswith("\x1b[32mQuillan\x1b[0m\nScan Review")


def test_post_dispatch_list_is_compact_and_detail_discloses_multi_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = create_post_dispatch_review_occurrence(
        tmp_path,
        quillan_work_ref("english12_p3", "essay_01"),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Synthetic assembly failure.",
        student_id="student_01",
        issuance_ids=("iss_" + "a" * 32, "iss_" + "b" * 32),
        page_ids=("pg_" + "a" * 32, "pg_" + "b" * 32),
        observation_ids=("obs_" + "a" * 32, "obs_" + "b" * 32),
    )
    _inputs(monkeypatch, ["1", "", "b", "b"])

    scan_review_menu._launch_post_dispatch_review_menu(
        tmp_path, "english12_p3", "essay_01"
    )

    output = capsys.readouterr().out
    compact, detail = output.split("Post-Dispatch Problem Details", maxsplit=1)
    assert occurrence.occurrence.issuance_ids[0] not in compact
    assert "Issuance IDs: " in detail
    assert occurrence.occurrence.issuance_ids[0] in detail
    assert occurrence.occurrence.issuance_ids[1] in detail


@pytest.mark.menu_density_workflow("post-dispatch review")
def test_post_dispatch_density_recorder_captures_focused_segments_and_redraw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _post_dispatch_occurrence(tmp_path)
    recorder = MenuScreenRecorder(["1", "", "b", "b"])
    recorder.install(monkeypatch)

    scan_review_menu._launch_post_dispatch_review_menu(
        tmp_path, "english12_p3", "essay_01"
    )

    screens = recorder.screens(capsys.readouterr().out)
    assert [screen.clear_number for screen in screens] == [1, 2, 3, 4]
    listing, detail, actions, redrawn_listing = screens
    assert "Quillan Post-Dispatch Problems" in listing.output
    assert occurrence.occurrence.failure_message not in listing.output
    assert "Post-Dispatch Problem Details" in detail.output
    assert occurrence.occurrence.failure_message in detail.output
    assert "Quillan Post-Dispatch Problems" not in detail.output
    assert "Choose Post-Dispatch Action" in actions.output
    assert occurrence.occurrence.failure_id in actions.output
    assert occurrence.occurrence.failure_message not in actions.output
    assert "Quillan Post-Dispatch Problems" in redrawn_listing.output
    assert [prompt.prompt for prompt in recorder.prompts] == [
        "Select a post-dispatch problem: ",
        "Press Enter to choose an action...",
        "Select an action: ",
        "Select a post-dispatch problem: ",
    ]
    assert_focused_child_screen(
        screens,
        heading="Post-Dispatch Problem Details",
        required_text=occurrence.occurrence.failure_id,
        forbidden_parent_text="Select a post-dispatch problem:",
        parent_heading="Quillan Post-Dispatch Problems",
        result_heading="Choose Post-Dispatch Action",
        unrelated_previous_text="1. submission_assembly",
    )
    for screen in screens:
        print(f"--- CLEAR EVENT {screen.clear_number} ---")
        print(screen.output)
    print("--- PROMPTS AND CHOICES ---")
    for prompt in recorder.prompts:
        print(f"{prompt.prompt}{prompt.choice}")


@pytest.mark.menu_density_workflow("route selection/correction")
def test_route_correction_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    locator, target, registration = _write_routed_failure(tmp_path)
    corrected = replace(
        registration,
        locator=RouteLocator(
            "PDS2", locator.work, "rt_ffffffffffffffffffffffffffffffff"
        ),
        target=target,
    )
    write_route_registration(tmp_path, corrected)
    recorder = MenuScreenRecorder(
        ["1", "", "2", "2", "y", "", "y", "", "b"]
    )
    recorder.install(monkeypatch)

    assert (
        scan_review_menu._launch_core_review_menu(tmp_path)
        == 0
    )

    screens = recorder.screens(capsys.readouterr().out)
    assert any(
        "Select Registered Route" in screen.output
        and "Class: english10_p2" in screen.output
        and "Assignment: literary_analysis" in screen.output
        and "2. " in screen.output
        for screen in screens
    ), "\n---\n".join(screen.output for screen in screens)
    assert_focused_child_screen(
        screens,
        heading="Scan Review Details",
        required_text="Teacher routing decision required.",
        forbidden_parent_text="Select a review item:",
        parent_heading="Resolve Scan Review Items",
        result_heading="Core Routing Review Result",
        unrelated_previous_text="route_mismatch (unresolved)",
    )


def _successful_assembly_result() -> QuillanSubmissionAssemblyBatch:
    return QuillanSubmissionAssemblyBatch(assembled=(), failures=())


def test_empty_retry_does_not_offer_resolution_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _post_dispatch_occurrence(tmp_path)
    item = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items[0]
    monkeypatch.setattr(
        scan_review_menu,
        "assemble_assignment_submissions",
        lambda *_args, **_kwargs: _successful_assembly_result(),
    )
    prompts = _inputs(monkeypatch, [""])

    scan_review_menu._retry_post_dispatch_assembly(tmp_path, item)

    output = capsys.readouterr().out
    assert (
        "The retry completed without an operational failure, but it did not prove "
        "that this occurrence was resolved." in output
    )
    assert "Record this occurrence as resolved after retry? [y/N]: " not in prompts
    assert discover_post_dispatch_review_items(tmp_path, occurrence.work_ref).items


def test_successful_retry_requires_confirmation_and_does_not_auto_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    item = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items[0]
    monkeypatch.setattr(
        scan_review_menu,
        "assemble_assignment_submissions",
        lambda *_args, **_kwargs: assembly,
    )
    prompts = _inputs(monkeypatch, ["n", ""])

    scan_review_menu._retry_post_dispatch_assembly(tmp_path, item)

    output = capsys.readouterr().out
    assert "The retry completed successfully." in output
    assert "Record this occurrence as resolved after retry? [y/N]: " in prompts
    assert discover_post_dispatch_review_items(tmp_path, occurrence.work_ref).items


def test_successful_retry_records_typed_provenance_only_after_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    item = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items[0]
    monkeypatch.setattr(
        scan_review_menu,
        "assemble_assignment_submissions",
        lambda *_args, **_kwargs: assembly,
    )
    _inputs(monkeypatch, ["y", ""])

    scan_review_menu._retry_post_dispatch_assembly(tmp_path, item)

    output = capsys.readouterr().out
    assert "The retry completed successfully." in output
    assert "Resolution record:" in output
    included = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref, include_resolved=True
    )
    assert included.items[0].latest_resolution is not None
    provenance = included.items[0].latest_resolution.resolution.retry_provenance
    assert provenance is not None
    assert provenance["operation"] == "submission_assembly"
    assert provenance["assembled_status"] == "created"
    assert provenance["manifest_path"] == assembly.assembled[0].manifest_relative_path


@pytest.mark.menu_density_workflow("successful retry")
def test_successful_retry_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    monkeypatch.setattr(
        scan_review_menu,
        "assemble_assignment_submissions",
        lambda *_args, **_kwargs: assembly,
    )
    recorder = MenuScreenRecorder(["1", "", "1", "y", "", "b"])
    recorder.install(monkeypatch)

    scan_review_menu._launch_post_dispatch_review_menu(
        tmp_path, occurrence.work_ref.class_id, occurrence.work_ref.work_id
    )

    screens = recorder.screens(capsys.readouterr().out)
    assert_focused_child_screen(
        screens,
        heading="Post-Dispatch Problem Details",
        required_text=occurrence.occurrence.failure_id,
        forbidden_parent_text="1. submission_assembly",
        parent_heading="Quillan Post-Dispatch Problems",
        result_heading="Retry Resolution Result",
        unrelated_previous_text="Select a post-dispatch problem:",
    )


def test_failed_retry_keeps_occurrence_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _post_dispatch_occurrence(tmp_path)
    item = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items[0]
    monkeypatch.setattr(
        scan_review_menu,
        "assemble_assignment_submissions",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("retry failed")),
    )
    _inputs(monkeypatch, [""])

    scan_review_menu._retry_post_dispatch_assembly(tmp_path, item)

    output = capsys.readouterr().out
    assert "retry failed" in output
    assert "no resolution was recorded" in output.lower()
    assert discover_post_dispatch_review_items(tmp_path, occurrence.work_ref).items


def test_contextual_status_view_uses_shared_typed_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _post_dispatch_occurrence(tmp_path)
    item = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items[0]
    typed_status = object()
    calls: list[object] = []
    monkeypatch.setattr(
        scan_review_menu,
        "list_assignment_submission_status",
        lambda *_args, **_kwargs: typed_status,
    )
    monkeypatch.setattr(
        scan_review_menu,
        "print_assignment_submission_status",
        lambda value, root: calls.extend((value, root)),
    )
    _inputs(monkeypatch, [""])

    scan_review_menu._view_post_dispatch_status(tmp_path, item)

    assert calls == [typed_status, tmp_path]
    assert "Current Submission Status" in capsys.readouterr().out
    assert discover_post_dispatch_review_items(tmp_path, occurrence.work_ref).items


@pytest.mark.parametrize("kind", ["evidence", "manifest"])
def test_contextual_open_menu_uses_only_selected_occurrence_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    work_ref = quillan_work_ref("english12_p3", "essay_01")
    evidence = (
        quillan_work_paths(tmp_path, "english12_p3", "essay_01").work_root
        / "scans"
        / "evidence"
        / "response_student_01_page_1.png"
    )
    manifest = submission_manifest_path(
        tmp_path, "english12_p3", "essay_01", "student_01"
    )
    selected = evidence if kind == "evidence" else manifest
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(b"fixture")
    occurrence = create_post_dispatch_review_occurrence(
        tmp_path,
        work_ref,
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Synthetic assembly failure.",
        student_id="student_01",
        possible_evidence_path=evidence if kind == "evidence" else None,
        possible_manifest_path=manifest if kind == "manifest" else None,
    )
    item = discover_post_dispatch_review_items(tmp_path, work_ref).items[0]
    opened: list[tuple[str, str]] = []

    def open_selected(
        _root: Path,
        _work_ref: object,
        _failure_id: str,
        *,
        kind: str,
        relative_path: str,
    ) -> object:
        opened.append((kind, relative_path))
        return type("Opened", (), {"relative_path": relative_path})()

    monkeypatch.setattr(
        scan_review_menu, "open_post_dispatch_possible_path", open_selected
    )
    _inputs(monkeypatch, ["1", ""])

    scan_review_menu._open_post_dispatch_context_path(
        tmp_path, item, kind  # type: ignore[arg-type]
    )

    relative = selected.relative_to(tmp_path).as_posix()
    assert opened == [(kind, relative)]
    assert f"Opened validated {kind}: {relative}" in capsys.readouterr().out
    assert discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items
