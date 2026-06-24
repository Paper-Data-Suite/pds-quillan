"""Tests for structured QR scan-intake summaries."""

from __future__ import annotations

from pathlib import Path

from quillan.scan_intake_summary import (
    ScanIntakePageResult,
    ScanIntakeSourceResult,
    ScanIntakeSummary,
    format_scan_intake_summary,
)


def _source(
    *pages: ScanIntakePageResult,
    source_failure_category: str | None = None,
) -> ScanIntakeSourceResult:
    routed = sum(1 for page in pages if page.status == "routed")
    preserved = sum(1 for page in pages if page.status == "preserved")
    failed = sum(1 for page in pages if page.status == "failed")
    return ScanIntakeSourceResult(
        source_filename="scan.pdf",
        source_path=Path("scan.pdf"),
        source_type="pdf",
        status="partial" if preserved or failed else "completed",
        pages_attempted=len(pages),
        routed_count=routed,
        preserved_count=preserved,
        failed_count=failed,
        page_results=pages,
        source_failure_category=source_failure_category,
    )


def test_empty_summary_counts_are_zero() -> None:
    summary = ScanIntakeSummary(())

    assert summary.source_count == 0
    assert summary.pages_attempted == 0
    assert summary.routed_count == 0
    assert summary.preserved_count == 0
    assert summary.failed_count == 0
    assert summary.skipped_unsupported_count == 0
    assert not summary.requires_review
    assert not summary.has_failures
    assert summary.failure_categories == {}


def test_fully_routed_source_counts_routed_pages_and_paths() -> None:
    page = ScanIntakePageResult(
        source_filename="scan.pdf",
        source_page_number=1,
        payload_page_number=2,
        status="routed",
        routed_evidence_relative_path="classes/c/a/scans/response.png",
        retained_source_relative_path="scans/source/2026-06-23/source.pdf",
    )
    summary = ScanIntakeSummary((_source(page),))

    assert summary.source_count == 1
    assert summary.pages_attempted == 1
    assert summary.routed_count == 1
    assert summary.preserved_count == 0
    assert not summary.requires_review
    assert page.routed_evidence_relative_path == "classes/c/a/scans/response.png"
    assert page.retained_source_relative_path == "scans/source/2026-06-23/source.pdf"


def test_mixed_source_counts_totals_and_categories() -> None:
    routed = ScanIntakePageResult("scan.pdf", 1, 1, "routed")
    preserved = ScanIntakePageResult(
        "scan.pdf",
        2,
        None,
        "preserved",
        failure_category="payload_missing",
        review_metadata_relative_path="scans/review/failure.json",
    )
    failed = ScanIntakePageResult(
        "scan.pdf",
        3,
        None,
        "failed",
        failure_category="processing_error",
    )
    summary = ScanIntakeSummary((_source(routed, preserved, failed),))

    assert summary.pages_attempted == 3
    assert summary.routed_count == 1
    assert summary.preserved_count == 1
    assert summary.failed_count == 1
    assert summary.requires_review
    assert summary.has_failures
    assert summary.failure_categories == {
        "payload_missing": 1,
        "processing_error": 1,
    }
    assert preserved.review_metadata_relative_path == "scans/review/failure.json"


def test_source_failure_category_is_counted() -> None:
    summary = ScanIntakeSummary(
        (
            _source(
                source_failure_category="source_unreadable",
            ),
        )
    )

    assert summary.requires_review
    assert summary.failure_categories == {"source_unreadable": 1}


def test_summary_formatter_includes_review_message_and_categories() -> None:
    preserved = ScanIntakePageResult(
        "scan.pdf",
        1,
        None,
        "preserved",
        failure_category="payload_missing",
    )

    output = format_scan_intake_summary(ScanIntakeSummary((_source(preserved),)))

    assert "Scan intake summary" in output
    assert "Sources processed: 1" in output
    assert "Pages attempted: 1" in output
    assert "Skipped unsupported files: 0" in output
    assert "Review required: yes" in output
    assert "Review required before intake is complete." in output
    assert "- payload_missing: 1" in output


def test_summary_formatter_includes_skipped_unsupported_count() -> None:
    output = format_scan_intake_summary(
        ScanIntakeSummary((), skipped_unsupported_count=3)
    )

    assert "Skipped unsupported files: 3" in output
