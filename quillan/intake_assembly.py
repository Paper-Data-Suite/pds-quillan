"""Derive submission assembly guidance from scan-intake results."""

from __future__ import annotations

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
    """Return no targets before #339 creates durable successful observations."""
    _ = summary
    return ()
