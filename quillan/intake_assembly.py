"""Derive submission assembly guidance from scan-intake results."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from quillan.scan_intake_summary import ScanIntakeSummary


@dataclass(frozen=True, slots=True)
class IntakeAssemblyTarget:
    """One class assignment with newly routed evidence."""

    class_id: str
    assignment_id: str
    routed_page_count: int


def assembly_targets_from_intake_summary(
    summary: ScanIntakeSummary,
) -> tuple[IntakeAssemblyTarget, ...]:
    """Return deterministic assembly targets from routed intake pages."""
    counts: Counter[tuple[str, str]] = Counter()
    for source in summary.source_results:
        for page in source.page_results:
            if (
                page.status == "routed"
                and page.class_id is not None
                and page.assignment_id is not None
            ):
                counts[(page.class_id, page.assignment_id)] += 1

    return tuple(
        IntakeAssemblyTarget(
            class_id=class_id,
            assignment_id=assignment_id,
            routed_page_count=counts[(class_id, assignment_id)],
        )
        for class_id, assignment_id in sorted(counts)
    )
