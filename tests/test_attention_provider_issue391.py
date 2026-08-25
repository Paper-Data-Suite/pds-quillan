from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pds_core.module_operations import (
    MODULE_OPERATIONS_CONTRACT_VERSION,
    ModuleAttentionReport,
    ModuleOperationsRequest,
    invoke_module_attention,
    invoke_module_readiness,
    validate_module_operations_profile,
)

import quillan.attention_provider as attention
from quillan.assignment_discovery import DiscoveredAssignment
from quillan.class_review_completion import ClassReviewCompletionView
from quillan.pds_operations import (
    evaluate_quillan_attention,
    evaluate_quillan_readiness,
    get_module_operations_profile,
)
from quillan.share_results import ShareResultsStatus
from quillan.work_paths import QuillanWorkPathError


def _completion_view(
    *,
    class_id: str = "class_a",
    assignment_id: str = "assignment_a",
) -> ClassReviewCompletionView:
    return ClassReviewCompletionView(
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title="Synthetic Assignment",
        items=(),
        category_counts=(
            ("no_submission", 9),
            ("needs_assembly", 2),
            ("minimum_requirements_pending", 0),
            ("observations_pending", 0),
            ("ratings_pending", 1),
            ("feedback_pending", 0),
            ("export_pending", 3),
            ("complete", 4),
            ("attention_required", 0),
        ),
        feedback_pdf_counts=(),
        feedback_markdown_counts=(),
        unrostered_student_ids=(),
        warnings=(),
    )


def _share_status(
    *,
    next_step: str = "publish_initial",
    complete: bool = True,
) -> ShareResultsStatus:
    review = SimpleNamespace(
        roster_count=10,
        complete_count=10 if complete else 5,
        needs_work_count=0 if complete else 5,
        attention_count=0,
        unrostered_diagnostic_count=0,
        warning_count=0,
    )
    return ShareResultsStatus(
        class_id="class_a",
        assignment_id="assignment_a",
        assignment_title="Synthetic Assignment",
        registration_revision=1,
        registration_title="Synthetic Assignment",
        registration_title_stale=False,
        academic_intent="summative",
        lifecycle="active",
        native_result_state_valid=True,
        represented_native_result_count=10,
        native_state_matches_producer_head=True,
        producer_head_revision=1,
        producer_head_sha256="0" * 64,
        core_head_publication_id=None,
        core_head_revision=None,
        core_head_withdrawn=False,
        current_selectable_publication_id=None,
        catalog_available=True,
        publication_plan="initial_publication",
        next_step=next_step,  # type: ignore[arg-type]
        review_context=review,  # type: ignore[arg-type]
        warnings=(),
    )


def test_profile_is_valid_core_v1_profile_after_issue392() -> None:
    profile = get_module_operations_profile()
    assert validate_module_operations_profile(profile) == profile
    assert profile.module_id == "quillan"
    assert profile.supported_core_operations_contract_versions == frozenset(
        {MODULE_OPERATIONS_CONTRACT_VERSION}
    )
    assert profile.readiness_provider is evaluate_quillan_readiness
    assert profile.attention_provider is evaluate_quillan_attention

    missing_readiness = invoke_module_readiness(
        profile,
        ModuleOperationsRequest(),
    )
    assert missing_readiness.code == "module_operations.evaluation_unavailable"


def test_profile_construction_does_not_import_attention_implementation() -> None:
    script = r"""
import json
import sys
from quillan.pds_operations import get_module_operations_profile

profile = get_module_operations_profile()
print(json.dumps({
    "module": profile.module_id,
    "attention_callable": callable(profile.attention_provider),
    "readiness_callable": callable(profile.readiness_provider),
    "attention_impl_imported": "quillan.attention_provider" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "module": "quillan",
        "attention_callable": True,
        "readiness_callable": True,
        "attention_impl_imported": False,
    }


def test_missing_workspace_is_unavailable_not_empty_evaluated() -> None:
    profile = get_module_operations_profile()
    result = invoke_module_attention(profile, ModuleOperationsRequest())
    assert result.code == "module_operations.evaluation_unavailable"
    assert isinstance(result.report, ModuleAttentionReport)
    assert result.report.evaluation == "unavailable"
    assert result.report.summaries == ()
    assert tuple(notice.code for notice in result.report.notices) == (
        "quillan_attention_unavailable",
    )


def test_empty_existing_workspace_is_evaluated_empty_and_read_only(
    tmp_path: Path,
) -> None:
    before = tuple(tmp_path.rglob("*"))
    request = ModuleOperationsRequest(workspace_root=tmp_path)
    result = invoke_module_attention(get_module_operations_profile(), request)
    after = tuple(tmp_path.rglob("*"))

    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleAttentionReport)
    assert result.report.evaluation == "evaluated"
    assert result.report.summaries == ()
    assert result.report.notices == ()
    assert before == after == ()


def test_provider_aggregates_existing_quillan_projections_without_student_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = DiscoveredAssignment(
        assignment_id="assignment_a",
        path=tmp_path / "assignment.json",
        assignment={},
        error=None,
    )

    monkeypatch.setattr(attention, "_class_ids", lambda root, requested: ("class_a",))
    monkeypatch.setattr(attention, "_assignment_entries", lambda root, class_id: (entry,))
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(
            items=(
                SimpleNamespace(
                    class_id="class_a",
                    assignment_id="assignment_a",
                ),
            ),
            warnings=(),
        ),
    )
    monkeypatch.setattr(
        attention,
        "discover_post_dispatch_review_items",
        lambda *args, **kwargs: SimpleNamespace(
            items=(object(), object()),
            warnings=(),
        ),
    )
    monkeypatch.setattr(
        attention,
        "build_class_review_completion_view",
        lambda *args, **kwargs: _completion_view(),
    )
    monkeypatch.setattr(
        attention,
        "build_share_results_status",
        lambda *args, **kwargs: _share_status(),
    )

    report = attention.evaluate_quillan_attention(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    by_code = {summary.code: summary for summary in report.summaries}

    assert report.evaluation == "evaluated"
    assert report.notices == ()
    assert tuple(by_code) == (
        "quillan_scan_review",
        "quillan_post_dispatch_review",
        "quillan_needs_assembly",
        "quillan_ratings_pending",
        "quillan_feedback_export_pending",
        "quillan_results_publication_pending",
    )
    assert by_code["quillan_scan_review"].count == 1
    assert by_code["quillan_post_dispatch_review"].count == 2
    assert by_code["quillan_needs_assembly"].count == 2
    assert by_code["quillan_ratings_pending"].count == 1
    assert by_code["quillan_feedback_export_pending"].count == 3
    assert by_code["quillan_results_publication_pending"].count == 1
    assert "quillan.no_submission" not in by_code

    for summary in report.summaries:
        assert summary.class_id == "class_a"
        assert summary.work_ref is not None
        assert summary.work_ref.module_id == "quillan"
        assert summary.work_ref.class_id == "class_a"
        assert summary.work_ref.work_id == "assignment_a"
        assert summary.action is not None
        assert summary.action.module_id == "quillan"


@pytest.mark.parametrize(
    "next_step",
    [
        "register_academic_work",
        "update_cancelled_registration",
        "resolve_native_result_state",
        "generate_manifest",
        "publish_initial",
        "supersede_current",
    ],
)
def test_routine_share_attention_requires_completed_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    next_step: str,
) -> None:
    entry = DiscoveredAssignment(
        assignment_id="assignment_a",
        path=tmp_path / "assignment.json",
        assignment={},
        error=None,
    )
    monkeypatch.setattr(attention, "_class_ids", lambda root, requested: ("class_a",))
    monkeypatch.setattr(attention, "_assignment_entries", lambda root, class_id: (entry,))
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "discover_post_dispatch_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "build_class_review_completion_view",
        lambda *args, **kwargs: ClassReviewCompletionView(
            class_id="class_a",
            assignment_id="assignment_a",
            assignment_title="Synthetic Assignment",
            items=(),
            category_counts=(
                ("no_submission", 0),
                ("needs_assembly", 0),
                ("minimum_requirements_pending", 0),
                ("observations_pending", 0),
                ("ratings_pending", 0),
                ("feedback_pending", 0),
                ("export_pending", 0),
                ("complete", 0),
                ("attention_required", 0),
            ),
            feedback_pdf_counts=(),
            feedback_markdown_counts=(),
            unrostered_student_ids=(),
            warnings=(),
        ),
    )
    monkeypatch.setattr(
        attention,
        "build_share_results_status",
        lambda *args, **kwargs: _share_status(
            next_step=next_step,
            complete=False,
        ),
    )

    report = attention.evaluate_quillan_attention(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    assert not any(summary.code.startswith("quillan_results_") for summary in report.summaries)


@pytest.mark.parametrize(
    ("next_step", "expected_code"),
    [
        (
            "advanced_republication_required",
            "quillan_results_republication_attention",
        ),
        (
            "resolve_publication_state",
            "quillan_results_publication_state_attention",
        ),
    ],
)
def test_existing_publication_integrity_attention_does_not_require_review_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    next_step: str,
    expected_code: str,
) -> None:
    entry = DiscoveredAssignment(
        assignment_id="assignment_a",
        path=tmp_path / "assignment.json",
        assignment={},
        error=None,
    )
    monkeypatch.setattr(attention, "_class_ids", lambda root, requested: ("class_a",))
    monkeypatch.setattr(attention, "_assignment_entries", lambda root, class_id: (entry,))
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "discover_post_dispatch_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "build_class_review_completion_view",
        lambda *args, **kwargs: _completion_view(),
    )
    monkeypatch.setattr(
        attention,
        "build_share_results_status",
        lambda *args, **kwargs: _share_status(
            next_step=next_step,
            complete=False,
        ),
    )

    report = attention.evaluate_quillan_attention(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    assert expected_code in {summary.code for summary in report.summaries}


def test_class_filter_is_preserved_in_every_shared_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = DiscoveredAssignment(
        assignment_id="assignment_a",
        path=tmp_path / "assignment.json",
        assignment={},
        error=None,
    )
    monkeypatch.setattr(
        attention,
        "_assignment_entries",
        lambda root, class_id: (entry,),
    )
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(
            items=(
                SimpleNamespace(
                    class_id="class_a",
                    assignment_id="assignment_a",
                ),
            ),
            warnings=(),
        ),
    )
    monkeypatch.setattr(
        attention,
        "discover_post_dispatch_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "build_class_review_completion_view",
        lambda *args, **kwargs: _completion_view(),
    )
    monkeypatch.setattr(
        attention,
        "build_share_results_status",
        lambda *args, **kwargs: _share_status(next_step="already_shared_current"),
    )

    request = ModuleOperationsRequest(
        workspace_root=tmp_path,
        class_id="class_a",
    )
    result = invoke_module_attention(get_module_operations_profile(), request)
    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleAttentionReport)
    assert result.report.summaries
    for summary in result.report.summaries:
        assert summary.class_id == "class_a"
        if summary.work_ref is not None:
            assert summary.work_ref.class_id == "class_a"


def test_partial_global_evaluation_is_not_silently_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        attention,
        "_class_ids",
        lambda root, requested: ("class_a", "class_b"),
    )

    def assignment_entries(
        root: Path, class_id: str
    ) -> tuple[DiscoveredAssignment, ...]:
        if class_id == "class_b":
            raise QuillanWorkPathError("synthetic unsafe scope")
        return ()

    monkeypatch.setattr(attention, "_assignment_entries", assignment_entries)
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )

    report = attention.evaluate_quillan_attention(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    assert report.evaluation == "evaluated"
    assert report.summaries == ()
    assert tuple(notice.code for notice in report.notices) == (
        "quillan_attention_partial",
    )


def test_unsafe_requested_class_scope_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        attention,
        "_assignment_entries",
        lambda root, class_id: (_ for _ in ()).throw(
            QuillanWorkPathError("synthetic unsafe scope")
        ),
    )
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )

    result = invoke_module_attention(
        get_module_operations_profile(),
        ModuleOperationsRequest(
            workspace_root=tmp_path,
            class_id="class_a",
        ),
    )
    assert result.code == "module_operations.evaluation_unavailable"
    assert isinstance(result.report, ModuleAttentionReport)
    assert result.report.summaries == ()


def test_shared_report_contains_no_student_or_private_payload_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_values = {
        "STUDENT-SENTINEL",
        "WRITING-SENTINEL",
        "FEEDBACK-SENTINEL",
        "C:\\private\\teacher\\file.png",
        "PDS2|PRIVATE-QR-SENTINEL",
    }
    entry = DiscoveredAssignment(
        assignment_id="assignment_a",
        path=tmp_path / "assignment.json",
        assignment={},
        error=None,
    )
    monkeypatch.setattr(attention, "_class_ids", lambda root, requested: ("class_a",))
    monkeypatch.setattr(attention, "_assignment_entries", lambda root, class_id: (entry,))
    monkeypatch.setattr(
        attention,
        "discover_scan_review_items",
        lambda *args, **kwargs: SimpleNamespace(
            items=(
                SimpleNamespace(
                    class_id="class_a",
                    assignment_id="assignment_a",
                    student_id="STUDENT-SENTINEL",
                    source_filename="C:\\private\\teacher\\file.png",
                    detected_payload="PDS2|PRIVATE-QR-SENTINEL",
                ),
            ),
            warnings=(),
        ),
    )
    monkeypatch.setattr(
        attention,
        "discover_post_dispatch_review_items",
        lambda *args, **kwargs: SimpleNamespace(items=(), warnings=()),
    )
    monkeypatch.setattr(
        attention,
        "build_class_review_completion_view",
        lambda *args, **kwargs: _completion_view(),
    )
    monkeypatch.setattr(
        attention,
        "build_share_results_status",
        lambda *args, **kwargs: _share_status(next_step="already_shared_current"),
    )

    report = attention.evaluate_quillan_attention(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    rendered = repr(report)
    for sentinel in sentinel_values:
        assert sentinel not in rendered

    for summary in report.summaries:
        assert not hasattr(summary, "student_id")
        assert not hasattr(summary, "student_name")
        assert not hasattr(summary, "metadata")
        assert not hasattr(summary, "path")


def test_attention_query_does_not_create_local_diagnostic_events(
    tmp_path: Path,
) -> None:
    request = ModuleOperationsRequest(workspace_root=tmp_path)
    report = attention.evaluate_quillan_attention(request)
    assert report.evaluation == "evaluated"
    assert not (tmp_path / "shared" / "quillan" / "diagnostics").exists()
