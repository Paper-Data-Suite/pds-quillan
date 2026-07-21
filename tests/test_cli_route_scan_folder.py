from pathlib import Path

from pds_core.module_profiles import ModuleProfile, ModuleRegistry

from quillan.pds2_scan_intake import process_quillan_scan_folder


def _handler(*_args: object) -> object:
    return object()


def test_empty_folder_has_zero_success(tmp_path: Path) -> None:
    registry = ModuleRegistry((ModuleProfile(
        "quillan", "Quillan", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), _handler,
    ),))
    folder = tmp_path / "empty"
    folder.mkdir()
    summary = process_quillan_scan_folder(folder, workspace_root=tmp_path, registry=registry)
    assert summary.zero_success
    assert not summary.complete_success
