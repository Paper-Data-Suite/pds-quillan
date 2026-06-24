"""Tests for deriving submission assembly targets from scan intake."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from quillan.intake_assembly import (
    IntakeAssemblyTarget,
    assembly_targets_from_intake_summary,
)
from quillan.scan_intake_summary import (
    ScanIntakePageResult,
    ScanIntakeSourceResult,
    ScanIntakeSummary,
)


def _page(
    status: Literal["routed", "preserved", "failed"],
    *,
    class_id: str | None = "english12",
    assignment_id: str | None = "final_exam",
) -> ScanIntakePageResult:
    return ScanIntakePageResult(
        source_filename="scan.pdf",
        source_page_number=1,
        payload_page_number=1,
        status=status,
        class_id=class_id,
        assignment_id=assignment_id,
    )


def _source(*pages: ScanIntakePageResult) -> ScanIntakeSourceResult:
    return ScanIntakeSourceResult(
        source_filename="scan.pdf",
        source_path=Path("scan.pdf"),
        source_type="pdf",
        status="completed",
        pages_attempted=len(pages),
        routed_count=sum(1 for page in pages if page.status == "routed"),
        preserved_count=sum(1 for page in pages if page.status == "preserved"),
        failed_count=sum(1 for page in pages if page.status == "failed"),
        page_results=pages,
    )


def test_empty_intake_summary_returns_no_assembly_targets() -> None:
    assert assembly_targets_from_intake_summary(ScanIntakeSummary(())) == ()


def test_one_routed_page_returns_one_target() -> None:
    summary = ScanIntakeSummary((_source(_page("routed")),))

    assert assembly_targets_from_intake_summary(summary) == (
        IntakeAssemblyTarget("english12", "final_exam", 1),
    )


def test_multiple_routed_pages_for_same_assignment_are_counted() -> None:
    summary = ScanIntakeSummary(
        (_source(_page("routed"), _page("routed")),)
    )

    assert assembly_targets_from_intake_summary(summary) == (
        IntakeAssemblyTarget("english12", "final_exam", 2),
    )


def test_multiple_targets_are_sorted_deterministically() -> None:
    summary = ScanIntakeSummary(
        (
            _source(
                _page(
                    "routed",
                    class_id="english12",
                    assignment_id="memoir_unit",
                ),
                _page(
                    "routed",
                    class_id="english12",
                    assignment_id="final_exam",
                ),
                _page(
                    "routed",
                    class_id="biology",
                    assignment_id="lab_01",
                ),
            ),
        )
    )

    assert assembly_targets_from_intake_summary(summary) == (
        IntakeAssemblyTarget("biology", "lab_01", 1),
        IntakeAssemblyTarget("english12", "final_exam", 1),
        IntakeAssemblyTarget("english12", "memoir_unit", 1),
    )


def test_preserved_and_failed_pages_do_not_create_targets() -> None:
    summary = ScanIntakeSummary(
        (
            _source(
                _page("preserved"),
                _page("failed"),
            ),
        )
    )

    assert assembly_targets_from_intake_summary(summary) == ()


def test_routed_page_missing_class_or_assignment_is_ignored() -> None:
    summary = ScanIntakeSummary(
        (
            _source(
                _page("routed", class_id=None),
                _page("routed", assignment_id=None),
            ),
        )
    )

    assert assembly_targets_from_intake_summary(summary) == ()
