from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_module_operations_document_covers_normative_boundaries() -> None:
    text = (ROOT / "docs" / "module_operations.md").read_text(encoding="utf-8")
    required = (
        "pds-core>=0.6.2,<0.7",
        "paper_data_suite.module_operations",
        "quillan.pds_operations:get_module_operations_profile",
        "attention_provider = present",
        "readiness_provider = absent",
        "quillan_scan_review",
        "quillan_feedback_export_pending",
        "quillan_results_publication_pending",
        "quillan_attention_partial",
        "quillan_attention_unavailable",
        "open_review_queue",
        "student IDs",
        "diagnostic-event history",
        "Attention evaluation is observational",
        "attention != publication authorization",
    )
    for value in required:
        assert value in text


def test_readme_links_operations_provider_and_no_longer_installs_core060() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[Module Operations Provider](docs/module_operations.md)" in text
    assert "pds-core>=0.6.2,<0.7" in text
    assert "pds_core-0.6.0-py3-none-any.whl" not in text
