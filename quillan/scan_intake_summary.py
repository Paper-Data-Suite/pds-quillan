"""Deterministic presentation for retained PDS2 scan intake."""

from __future__ import annotations

from quillan.pds2_scan_intake import (
    QuillanScanIntakeSummary,
    QuillanScanPageOutcome,
    QuillanScanSourceResult,
)

ScanIntakePageResult = QuillanScanPageOutcome
ScanIntakeSourceResult = QuillanScanSourceResult
ScanIntakeSummary = QuillanScanIntakeSummary


def format_scan_intake_summary(summary: QuillanScanIntakeSummary) -> str:
    """Return stable dispatch-stage totals and actionable page diagnostics."""
    modules = summary.successful_pages_by_module
    module_text = ", ".join(f"{module_id}={count}" for module_id, count in modules.items()) or "none"
    lines = [
        "PDS2 retained-source scan intake summary",
        f"Sources selected: {summary.source_count}",
        f"Sources retained: {summary.retained_source_count}",
        f"Source failures: {summary.source_failure_count}",
        f"Source pages discovered: {summary.total_source_pages}",
        f"Pages with decoded QR text: {summary.decoded_payload_count}",
        f"Valid PDS2 locators: {summary.valid_locator_count}",
        f"Dispatch successes: {summary.dispatch_success_count}",
        f"Core dispatch failures: {summary.core_dispatch_failure_count}",
        f"Pre-dispatch failures: {summary.pre_dispatch_failure_count}",
        f"Quillan integration failures: {summary.quillan_integration_failure_count}",
        f"Successful Quillan pages: {summary.quillan_success_count}",
        f"Pages handled by other modules: {summary.other_module_success_count}",
        f"Successful pages by module: {module_text}",
        f"Review records preserved: {summary.review_record_count}",
        f"Review-record write failures: {summary.review_persistence_failure_count}",
        f"Skipped unsupported files: {summary.skipped_unsupported_count}",
        f"Skipped nonfile entries: {summary.skipped_nonfile_count}",
        f"Batch status: {summary.batch_status}",
    ]
    for source in summary.source_results:
        if source.source_error is not None:
            lines.append(f"Source failure: {source.source_filename}: {source.source_error}")
            if source.scan_review_record is not None:
                lines.append(
                    "  Source review record: "
                    f"{source.scan_review_record.metadata_relative_path}"
                )
            if source.scan_review_error is not None:
                lines.append(
                    "  Source review persistence failed: "
                    f"{source.scan_review_error.error}"
                )
                if source.scan_review_error.durable_path is not None:
                    lines.append(
                        "  Possibly durable path: "
                        f"{source.scan_review_error.durable_path}"
                    )
        for page in source.pages:
            if page.terminal_category == "dispatch_success":
                continue
            lines.append(
                f"Page failure: {source.source_filename} page {page.source_page_number}; "
                f"terminal={page.terminal_category}; stage={page.failure_stage or 'core_dispatch'}; "
                f"error={page.error or getattr(page.dispatch_outcome, 'error', 'unknown')}"
            )
            if page.locator is not None:
                lines.append(f"  Module: {page.locator.module_id}; Route: {page.locator.route_id}")
            if page.review_record is not None:
                lines.append(
                    f"  Review record: {page.review_record.metadata_relative_path}"
                )
            if page.review_error is not None:
                lines.append(
                    f"  Review persistence failed: {page.review_error.error}"
                )
                if page.review_error.durable_path is not None:
                    lines.append(
                        f"  Possibly durable path: {page.review_error.durable_path}"
                    )
    return "\n".join(lines)


__all__ = [
    "QuillanScanIntakeSummary", "QuillanScanPageOutcome", "QuillanScanSourceResult",
    "ScanIntakePageResult", "ScanIntakeSourceResult", "ScanIntakeSummary",
    "format_scan_intake_summary",
]
