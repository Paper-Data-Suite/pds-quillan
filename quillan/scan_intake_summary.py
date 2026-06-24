"""Structured summaries for QR-aware scan intake."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping


@dataclass(frozen=True, slots=True)
class ScanIntakePageResult:
    """Structured outcome for one attempted scan page."""

    source_filename: str
    source_page_number: int | None
    payload_page_number: int | None
    status: Literal["routed", "preserved", "failed"]
    failure_category: str | None = None
    failure_message: str | None = None
    class_id: str | None = None
    assignment_id: str | None = None
    student_id: str | None = None
    routed_evidence_relative_path: str | None = None
    retained_source_relative_path: str | None = None
    review_metadata_relative_path: str | None = None


@dataclass(frozen=True, slots=True)
class ScanIntakeSourceResult:
    """Structured outcome for one scan source file."""

    source_filename: str
    source_path: Path
    source_type: Literal["image", "pdf"]
    status: Literal["completed", "partial", "failed", "preserved"]
    pages_attempted: int
    routed_count: int
    preserved_count: int
    failed_count: int
    page_results: tuple[ScanIntakePageResult, ...]
    source_failure_category: str | None = None
    source_failure_message: str | None = None
    review_metadata_relative_path: str | None = None


@dataclass(frozen=True, slots=True)
class ScanIntakeSummary:
    """Aggregate QR-aware scan intake outcomes."""

    source_results: tuple[ScanIntakeSourceResult, ...]
    skipped_unsupported_count: int = 0

    @property
    def source_count(self) -> int:
        return len(self.source_results)

    @property
    def pages_attempted(self) -> int:
        return sum(source.pages_attempted for source in self.source_results)

    @property
    def routed_count(self) -> int:
        return sum(source.routed_count for source in self.source_results)

    @property
    def preserved_count(self) -> int:
        return sum(source.preserved_count for source in self.source_results)

    @property
    def failed_count(self) -> int:
        return sum(source.failed_count for source in self.source_results)

    @property
    def requires_review(self) -> bool:
        return (
            self.preserved_count > 0
            or self.failed_count > 0
            or any(
                source.source_failure_category is not None
                for source in self.source_results
            )
        )

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0 or any(
            source.status == "failed" for source in self.source_results
        )

    @property
    def failure_categories(self) -> Mapping[str, int]:
        categories: Counter[str] = Counter()
        for source in self.source_results:
            if source.source_failure_category is not None:
                categories[source.source_failure_category] += 1
            for page in source.page_results:
                if page.failure_category is not None:
                    categories[page.failure_category] += 1
        return dict(sorted(categories.items()))


def format_scan_intake_summary(summary: ScanIntakeSummary) -> str:
    """Return concise, stable human-readable scan intake totals."""
    lines = [
        "Scan intake summary",
        f"Sources processed: {summary.source_count}",
        f"Pages attempted: {summary.pages_attempted}",
        f"Routed: {summary.routed_count}",
        f"Preserved for review: {summary.preserved_count}",
        f"Failed: {summary.failed_count}",
        f"Skipped unsupported files: {summary.skipped_unsupported_count}",
        f"Review required: {'yes' if summary.requires_review else 'no'}",
    ]
    if summary.has_failures:
        lines.extend(
            [
                "",
                "One or more pages could not be routed or preserved. Resolve "
                "failed pages before treating intake as complete.",
            ]
        )
    elif summary.requires_review:
        lines.extend(["", "Review required before intake is complete."])

    if summary.failure_categories:
        lines.extend(["Failure categories:"])
        lines.extend(
            f"- {category}: {count}"
            for category, count in summary.failure_categories.items()
        )
    return "\n".join(lines)
