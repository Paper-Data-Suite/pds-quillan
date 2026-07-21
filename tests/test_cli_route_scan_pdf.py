"""Retained PDF orchestration coverage for the route-scan service."""

from pathlib import Path

from pds_core.module_profiles import ModuleProfile, ModuleRegistry
from pypdf import PdfWriter

from quillan.pds2_scan_intake import process_quillan_scan_source


def _handler(*_args: object) -> object:
    return object()


def test_real_three_page_pdf_routes_as_three_independent_terminal_pages(tmp_path: Path) -> None:
    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=30, height=30)
    with source.open("wb") as output:
        writer.write(output)
    registry = ModuleRegistry((ModuleProfile(
        "quillan", "Quillan", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), _handler,
    ),))
    result = process_quillan_scan_source(source, workspace_root=tmp_path, registry=registry)
    assert result.retained_source is not None
    assert [page.source_page_number for page in result.pages] == [1, 2, 3]
    assert all(page.failure_stage == "qr_detection" for page in result.pages)
