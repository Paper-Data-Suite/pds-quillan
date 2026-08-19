"""Contract tests for the generated Quillan issue #379 audit report."""

from __future__ import annotations

import json

import pytest

from tests.teacher_workflow_audit_reporting import (
    AuditProvenance,
    METRICS_BEGIN,
    METRICS_END,
    parse_metric_rows,
    render_teacher_workflow_audit_report,
)


def _row(label: str, *, prompts: int = 5, screens: int = 4, transitions: int = 3,
         selections: int = 1, reselections: int = 0, repeated: int = 0,
         back: int = 1, pauses: int = 1) -> dict[str, object]:
    return {
        "label": label,
        "prompt_count": prompts,
        "screen_count": screens,
        "menu_transition_count": transitions,
        "class_selection_count": 0,
        "assignment_selection_count": 0,
        "student_selection_count": 0,
        "context_selection_count": selections,
        "context_reselection_count": reselections,
        "repeated_configuration_count": repeated,
        "backtracking_count": back,
        "pause_count": pauses,
    }


def _required_rows() -> list[dict[str, object]]:
    labels = [
        "assignment creation",
        "repeated assignment creation",
        "class-set student handoff",
        "complete individual review",
        "student selection",
        "printable-response generation",
        "complete scan intake",
        "partial scan intake",
        "Core scan review",
        "route selection/correction",
        "post-dispatch review",
        "successful retry",
        "assignment dashboard",
        "full diagnostic dashboard",
        "plain-paper creation",
        "evidence opening",
        "page selection and page management",
        "minimum requirements",
        "review units",
        "observations",
        "ratings",
        "feedback composition",
        "teacher notes",
        "workflow-state changes",
        "feedback export",
        "assignment-report export",
        "help",
    ]
    rows = [_row(label) for label in labels]
    for row in rows:
        if row["label"] == "assignment creation":
            row.update(prompt_count=20, screen_count=15, menu_transition_count=14)
        elif row["label"] == "repeated assignment creation":
            row.update(
                prompt_count=39,
                screen_count=29,
                menu_transition_count=28,
                context_reselection_count=1,
                repeated_configuration_count=10,
            )
        elif row["label"] == "complete individual review":
            row.update(prompt_count=72, screen_count=58, menu_transition_count=44)
        elif row["label"] == "student selection":
            row.update(prompt_count=11, screen_count=10, menu_transition_count=8)
        elif row["label"] == "class-set student handoff":
            row.update(
                prompt_count=14,
                screen_count=13,
                menu_transition_count=11,
                context_reselection_count=1,
                student_selection_count=2,
                backtracking_count=4,
            )
    return rows


def test_parse_metric_rows_reads_only_marker_body() -> None:
    rows = [_row("assignment creation"), _row("student selection")]
    output = "before\n" + METRICS_BEGIN + "\n"
    output += "\n".join(json.dumps(row) for row in rows)
    output += "\n" + METRICS_END + "\nafter\n"
    assert parse_metric_rows(output) == tuple(rows)


def test_parse_metric_rows_rejects_missing_markers() -> None:
    with pytest.raises(ValueError, match="markers"):
        parse_metric_rows("{}")


def test_render_report_contains_required_evidence_and_phase_mapping() -> None:
    report = render_teacher_workflow_audit_report(
        _required_rows(),
        AuditProvenance(
            git_sha="abc123",
            quillan_version="0.9.0",
            python_version="3.11.9",
            pds_core_version="0.6.1",
            operating_system="Windows 11",
            generated_at_utc="2026-08-19T19:00:00+00:00",
        ),
    )
    for text in (
        "Audited Git SHA: `abc123`",
        "39 prompts / 29 screens",
        "10 repeated configuration decisions",
        "adds **3 prompts / 3 screens / 3 transitions**",
        "One continuous complete individual-review journey",
        "single end-to-end teacher-facing",
        "## Scenario matrix",
        "## Friction findings",
        "## Confirmed safety properties to preserve",
        "#380 — Safe assignment copying",
        "#381 — Reusable review configuration",
        "#382 — Recent class/assignment context",
        "#383 — Deterministic review work queue",
        "#384 — Next/previous/next-needing-review navigation",
        "#385 — `Continue Review` guidance",
        "#386 — Compact routine review screen",
        "#387 — Batch feedback export",
        "#388 — Class summary/review-completion views",
        "#389 — Guided Meridian sharing/publication",
        "#390 — Privacy-conscious diagnostics",
        "no real student or school data",
    ):
        assert text in report
    assert "TODO" not in report
    assert "<placeholder>" not in report
