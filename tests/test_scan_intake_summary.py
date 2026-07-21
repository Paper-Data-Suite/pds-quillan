from quillan.pds2_scan_intake import QuillanScanIntakeSummary
from quillan.scan_intake_summary import format_scan_intake_summary


def test_empty_summary_is_deterministic_and_states_write_boundary() -> None:
    summary = QuillanScanIntakeSummary((), ("quillan",), skipped_unsupported_count=2, skipped_nonfile_count=1)
    text = format_scan_intake_summary(summary)
    assert "Batch status: zero_success" in text
    assert "Skipped unsupported files: 2" in text
    assert "Skipped nonfile entries: 1" in text
    assert "Observation persistence" not in text
