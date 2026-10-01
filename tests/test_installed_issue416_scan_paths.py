"""Qualification-harness coverage for Quillan Issue #416."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from scripts.verify_installed_issue416_scan_paths import (
    EXPECTED_CORE_VERSION,
    MIN_HISTORICAL_PATH_LENGTH,
    _historical_image,
    _historical_pdf,
    _legacy_retained_filename,
    _pdf_bytes,
    _png_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_installed_issue416_scan_paths.py"


def test_historical_acceptance_helpers_process_legacy_pdf_and_image(
    tmp_path: Path,
) -> None:
    workspace = tmp_path.resolve()
    pdf = _pdf_bytes()
    png = _png_bytes()

    historical_pdf = _historical_pdf(workspace, pdf)
    historical_image = _historical_image(workspace, png)

    assert historical_pdf.retained_source_path.is_file()
    assert historical_image.retained_source_path.is_file()
    assert historical_pdf.retained_source_path.read_bytes() == pdf
    assert historical_image.retained_source_path.read_bytes() == png


def test_historical_fixture_uses_released_core_063_serialization_shape() -> None:
    source_filename = "historical_" + ("x" * 90) + ".pdf"
    content = b"synthetic bytes"
    timestamp = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)

    retained = _legacy_retained_filename(source_filename, content, timestamp)

    assert retained.startswith("20260824T120000000000Z__historical_")
    assert retained.endswith(".pdf")
    assert "__" + hashlib.sha256(content).hexdigest()[:12] in retained


def test_installed_issue416_acceptance_is_source_isolated_and_complete() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert EXPECTED_CORE_VERSION == "0.6.4"
    assert MIN_HISTORICAL_PATH_LENGTH >= 280
    assert 'metadata.version("quillan")' in source
    assert 'metadata.version("pds-core")' in source
    assert "_module_origin(module_name).is_relative_to(repository)" in source
    assert "retain_source_scan(" in source
    assert "validate_quillan_retained_source(" in source
    assert "retained_source_page_count(" in source
    assert "load_retained_page_for_qr(" in source
    assert "materialize_routed_page_evidence(" in source
    assert "list_quillan_page_observations(" in source
    assert "LongPathsEnabled" in source
    assert "long_paths_policy_before" in source
    assert "long_paths_policy_after" in source
    assert "pdfinfo_from_path" not in source
    assert "convert_from_path" not in source
    assert "cv2.imread" not in source
    assert "SetValue" not in source
    assert "CreateKey" not in source
    assert '"migration_or_rename": False' in source


def test_installed_issue416_acceptance_reports_required_release_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    for field in (
        "fresh_core_064_provenance",
        "fresh_pdf_processing",
        "historical_core_063_provenance",
        "historical_pdf_processing",
        "historical_image_processing",
        "bounded_new_routed_evidence",
        "legacy_routed_evidence_read",
        "historical_pdf_path_length",
        "new_evidence_filename_length",
    ):
        assert field in source
