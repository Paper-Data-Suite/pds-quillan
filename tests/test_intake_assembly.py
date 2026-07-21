"""Explicit #339 migration gate for scan-to-submission assembly."""

from quillan.intake_assembly import assembly_targets_from_intake_summary
from quillan.pds2_scan_intake import QuillanScanIntakeSummary


def test_intake_summary_has_no_assembly_targets_before_observations() -> None:
    summary = QuillanScanIntakeSummary((), ("quillan",))
    assert assembly_targets_from_intake_summary(summary) == ()
