"""Issue #388 tests for the focused class review completion projection."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.class_review_completion as completion
from quillan.class_review_completion import (
    ClassReviewCompletionError,
    ClassReviewCompletionFilter,
    derive_class_review_completion_view,
    filter_class_review_completion_items,
)
from quillan.review_dashboard import (
    AssignmentReviewDashboard,
    DashboardStudentStatus,
)
from quillan.review_work_queue import WORK_QUEUE_CATEGORIES

CLASS_ID = "english12_p3"
ASSIGNMENT_ID = "literary_analysis"


def _student(
    student_id: str,
    *,
    category_source: str,
    display_name: str | None = None,
    pdf_status: str = "missing",
    markdown_status: str = "missing",
    roster_status: str = "rostered",
) -> DashboardStudentStatus:
    values: dict[str, object] = {
        "needs_assembly": False,
        "submission_status": "valid",
        "review_status": "valid",
        "review_state": "not_started",
        "minimum_status": "met",
    }
    if category_source == "no_submission":
        values.update(
            submission_status="missing",
            review_status="unavailable",
            review_state=None,
            minimum_status=None,
        )
    elif category_source == "needs_assembly":
        values.update(
            needs_assembly=True,
            submission_status="missing",
            review_status="unavailable",
            review_state=None,
            minimum_status=None,
        )
    elif category_source == "minimum_requirements_pending":
        values.update(review_state="not_started", minimum_status="not_checked")
    elif category_source == "observations_pending":
        values.update(review_state="not_started")
    elif category_source == "ratings_pending":
        values.update(review_state="observations_complete")
    elif category_source == "feedback_pending":
        values.update(review_state="ratings_complete")
    elif category_source == "export_pending":
        values.update(review_state="feedback_composed")
    elif category_source == "complete":
        values.update(review_state="exported")
    elif category_source == "attention_required":
        values.update(review_status="invalid")
    else:
        raise AssertionError(f"Unsupported test category source: {category_source}")

    return DashboardStudentStatus(
        student_id=student_id,
        display_name=display_name or f"Student {student_id}",
        roster_status=roster_status,
        routed_evidence_present=bool(values["needs_assembly"]),
        needs_assembly=bool(values["needs_assembly"]),
        submission_status=str(values["submission_status"]),
        submission_path=(
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            f"submissions/{student_id}/submission.json"
        ),
        submission_state=(
            "unreviewed" if values["submission_status"] == "valid" else None
        ),
        plain_paper=False,
        evidence_file_count=0,
        page_counts=(),
        review_status=str(values["review_status"]),
        review_path=(
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            f"submissions/{student_id}/review.json"
        ),
        review_state=(
            None if values["review_state"] is None else str(values["review_state"])
        ),
        minimum_requirement_status=(
            None
            if values["minimum_status"] is None
            else str(values["minimum_status"])
        ),
        returned_without_full_review=False,
        feedback_pdf_status=pdf_status,
        feedback_markdown_status=markdown_status,
        warnings=(),
    )


def _dashboard(*, roster_available: bool = True) -> AssignmentReviewDashboard:
    students = (
        _student("001", category_source="no_submission", display_name="Avery Rivera"),
        _student("002", category_source="needs_assembly", display_name="Mina Patel"),
        _student("003", category_source="minimum_requirements_pending"),
        _student("004", category_source="observations_pending"),
        _student("005", category_source="ratings_pending"),
        _student("006", category_source="feedback_pending"),
        _student(
            "007",
            category_source="export_pending",
            pdf_status="missing",
            markdown_status="missing",
        ),
        _student(
            "008",
            category_source="export_pending",
            pdf_status="stale",
            markdown_status="stale",
        ),
        _student(
            "009",
            category_source="export_pending",
            pdf_status="unknown",
            markdown_status="unknown",
        ),
        _student(
            "010",
            category_source="complete",
            display_name="Alex Lee",
            pdf_status="present",
            markdown_status="missing",
        ),
        _student(
            "011",
            category_source="complete",
            display_name="Alex Lee",
            pdf_status="missing",
            markdown_status="present",
        ),
        _student("012", category_source="attention_required"),
        _student(
            "900",
            category_source="complete",
            roster_status="unrostered",
            pdf_status="present",
        ),
    )
    return AssignmentReviewDashboard(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Literary Analysis",
        writing_type="literary_analysis",
        standards_profile_id="njsls_ela_2023",
        focus_standard_count=2,
        assignment_path=(
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/assignment.json"
        ),
        roster_available=roster_available,
        rostered_count=12 if roster_available else None,
        students=students,
        submission_counts=(),
        submission_state_counts=(),
        page_counts=(),
        page_student_counts=(),
        routed_counts=(),
        review_counts=(),
        review_state_counts=(),
        minimum_requirement_counts=(),
        workflow_counts=(),
        feedback_pdf_counts=(),
        feedback_markdown_counts=(),
        scan_review_available=True,
        scan_review_counts=(),
        scan_review_categories=(),
        unassembled_routed_files=(),
        unused_duplicate_routed_files=(),
        scan_review_items=(),
        warnings=(),
    )


def _view() -> completion.ClassReviewCompletionView:
    return derive_class_review_completion_view(
        _dashboard(),
        configured_requirement_count=1,
    )


def test_projection_reuses_queue_categories_and_scopes_export_counts() -> None:
    view = _view()

    assert [item.student_id for item in view.items] == [
        f"{number:03d}" for number in range(1, 13)
    ]
    counts = dict(view.category_counts)
    assert list(counts) == list(WORK_QUEUE_CATEGORIES)
    assert counts == {
        "no_submission": 1,
        "needs_assembly": 1,
        "minimum_requirements_pending": 1,
        "observations_pending": 1,
        "ratings_pending": 1,
        "feedback_pending": 1,
        "export_pending": 3,
        "complete": 2,
        "attention_required": 1,
    }
    assert view.roster_count == 12
    assert view.complete_count == 2
    assert view.needs_work_count == 10
    assert view.export_capable_count == 5
    assert view.export_pending_count == 3
    assert view.attention_count == 1

    assert dict(view.feedback_pdf_counts) == {
        "present": 1,
        "stale": 1,
        "missing": 2,
        "unknown": 1,
    }
    assert dict(view.feedback_markdown_counts) == {
        "present": 1,
        "stale": 1,
        "missing": 2,
        "unknown": 1,
    }

    # Earlier-stage students also have missing export files, but they are excluded
    # from focused export-status counts until their review path is export-capable.
    assert sum(dict(view.feedback_pdf_counts).values()) == 5
    assert sum(dict(view.feedback_markdown_counts).values()) == 5


def test_unrostered_records_are_bounded_diagnostics_not_completion_rows() -> None:
    view = _view()

    assert view.unrostered_student_ids == ("900",)
    assert "unrostered_records_excluded" in view.warnings
    assert all(item.student_id != "900" for item in view.items)
    assert view.roster_count == 12


def test_duplicate_display_names_keep_exact_student_identity() -> None:
    view = _view()
    duplicate_name_items = [
        item for item in view.items if item.display_name == "Alex Lee"
    ]

    assert [item.student_id for item in duplicate_name_items] == ["010", "011"]


@pytest.mark.parametrize(
    ("filter_spec", "expected_ids"),
    (
        (ClassReviewCompletionFilter("all"), tuple(f"{n:03d}" for n in range(1, 13))),
        (
            ClassReviewCompletionFilter("needs_work"),
            ("001", "002", "003", "004", "005", "006", "007", "008", "009", "012"),
        ),
        (ClassReviewCompletionFilter("category", "feedback_pending"), ("006",)),
        (ClassReviewCompletionFilter("category", "complete"), ("010", "011")),
        (ClassReviewCompletionFilter("pdf", "present"), ("010",)),
        (ClassReviewCompletionFilter("pdf", "stale"), ("008",)),
        (ClassReviewCompletionFilter("pdf", "missing"), ("007", "011")),
        (ClassReviewCompletionFilter("pdf", "unknown"), ("009",)),
        (ClassReviewCompletionFilter("markdown", "present"), ("011",)),
        (ClassReviewCompletionFilter("markdown", "stale"), ("008",)),
        (ClassReviewCompletionFilter("markdown", "missing"), ("007", "010")),
        (ClassReviewCompletionFilter("markdown", "unknown"), ("009",)),
    ),
)
def test_filters_are_deterministic_and_preserve_roster_order(
    filter_spec: ClassReviewCompletionFilter,
    expected_ids: tuple[str, ...],
) -> None:
    filtered = filter_class_review_completion_items(_view(), filter_spec)

    assert tuple(item.student_id for item in filtered) == expected_ids


def test_export_filters_do_not_treat_early_review_stages_as_missing_exports() -> None:
    view = _view()

    pdf_missing = filter_class_review_completion_items(
        view, ClassReviewCompletionFilter("pdf", "missing")
    )

    assert tuple(item.student_id for item in pdf_missing) == ("007", "011")
    assert "001" not in {item.student_id for item in pdf_missing}
    assert "006" not in {item.student_id for item in pdf_missing}


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        ("not_a_filter", None),
        ("all", "complete"),
        ("needs_work", "complete"),
        ("category", None),
        ("category", "not_a_category"),
        ("pdf", None),
        ("pdf", "current"),
        ("markdown", "not_a_status"),
    ),
)
def test_invalid_filter_contract_fails_closed(kind: str, value: str | None) -> None:
    with pytest.raises(ClassReviewCompletionError):
        ClassReviewCompletionFilter(kind, value)


def test_roster_unavailable_fails_instead_of_substituting_discovered_records() -> None:
    with pytest.raises(ClassReviewCompletionError, match="roster is unavailable"):
        derive_class_review_completion_view(
            _dashboard(roster_available=False),
            configured_requirement_count=1,
        )


def test_unknown_dashboard_export_status_fails_closed() -> None:
    dashboard = _dashboard()
    first = dashboard.students[0]
    bad_student = DashboardStudentStatus(
        student_id=first.student_id,
        display_name=first.display_name,
        roster_status=first.roster_status,
        routed_evidence_present=first.routed_evidence_present,
        needs_assembly=first.needs_assembly,
        submission_status=first.submission_status,
        submission_path=first.submission_path,
        submission_state=first.submission_state,
        plain_paper=first.plain_paper,
        evidence_file_count=first.evidence_file_count,
        page_counts=first.page_counts,
        review_status=first.review_status,
        review_path=first.review_path,
        review_state=first.review_state,
        minimum_requirement_status=first.minimum_requirement_status,
        returned_without_full_review=first.returned_without_full_review,
        feedback_pdf_status="surprise",
        feedback_markdown_status=first.feedback_markdown_status,
        warnings=first.warnings,
    )
    bad_dashboard = AssignmentReviewDashboard(
        class_id=dashboard.class_id,
        assignment_id=dashboard.assignment_id,
        assignment_title=dashboard.assignment_title,
        writing_type=dashboard.writing_type,
        standards_profile_id=dashboard.standards_profile_id,
        focus_standard_count=dashboard.focus_standard_count,
        assignment_path=dashboard.assignment_path,
        roster_available=dashboard.roster_available,
        rostered_count=dashboard.rostered_count,
        students=(bad_student, *dashboard.students[1:]),
        submission_counts=dashboard.submission_counts,
        submission_state_counts=dashboard.submission_state_counts,
        page_counts=dashboard.page_counts,
        page_student_counts=dashboard.page_student_counts,
        routed_counts=dashboard.routed_counts,
        review_counts=dashboard.review_counts,
        review_state_counts=dashboard.review_state_counts,
        minimum_requirement_counts=dashboard.minimum_requirement_counts,
        workflow_counts=dashboard.workflow_counts,
        feedback_pdf_counts=dashboard.feedback_pdf_counts,
        feedback_markdown_counts=dashboard.feedback_markdown_counts,
        scan_review_available=dashboard.scan_review_available,
        scan_review_counts=dashboard.scan_review_counts,
        scan_review_categories=dashboard.scan_review_categories,
        unassembled_routed_files=dashboard.unassembled_routed_files,
        unused_duplicate_routed_files=dashboard.unused_duplicate_routed_files,
        scan_review_items=dashboard.scan_review_items,
        warnings=dashboard.warnings,
    )

    with pytest.raises(
        ClassReviewCompletionError, match="Unknown feedback export status"
    ):
        derive_class_review_completion_view(
            bad_dashboard,
            configured_requirement_count=1,
        )


def test_builder_uses_one_dashboard_snapshot_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = _dashboard()
    calls: list[tuple[Path, str, str]] = []

    def fake_dashboard(
        root: Path, class_id: str, assignment_id: str
    ) -> AssignmentReviewDashboard:
        calls.append((root, class_id, assignment_id))
        return dashboard

    monkeypatch.setattr(completion, "build_assignment_review_dashboard", fake_dashboard)
    monkeypatch.setattr(completion, "load_assignment", lambda *_args: {"x": "y"})
    monkeypatch.setattr(completion, "configured_requirements", lambda _assignment: (1,))

    before = tuple(tmp_path.rglob("*"))
    view = completion.build_class_review_completion_view(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    after = tuple(tmp_path.rglob("*"))

    assert view.roster_count == 12
    assert calls == [(tmp_path, CLASS_ID, ASSIGNMENT_ID)]
    assert after == before == ()
