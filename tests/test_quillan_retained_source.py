"""Focused nonwriting retained-source validation tests."""

from dataclasses import replace
from datetime import date, datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys

from pds_core.scan_retention import RetainedSourceScan
from pds_core.scan_routes import build_retained_source_filename
import pytest

from quillan.module_errors import QuillanRetainedSourceError
import quillan.retained_source as retained_service
from quillan.retained_source import validate_quillan_retained_source


def retained_source(root: Path, extension: str = ".pdf") -> RetainedSourceScan:
    timestamp = datetime(2026, 7, 20, tzinfo=timezone.utc)
    source_filename = f"original{extension}"
    retained_filename = build_retained_source_filename(
        intake_timestamp=timestamp,
        original_filename=source_filename,
        sha256_hex="a" * 64,
    )
    retained = root / "scans" / "source" / "2026-07-20" / retained_filename
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"synthetic")
    return RetainedSourceScan(
        source_scan_id=f"scan_{retained.stem}",
        source_filename=source_filename,
        source_sha256="a" * 64,
        retained_source_path=retained,
        retained_source_relative_path=retained.relative_to(root).as_posix(),
        intake_timestamp=timestamp,
        intake_date=date(2026, 7, 20),
    )


def test_exact_pdf_provenance_is_validated_without_mutation(tmp_path: Path) -> None:
    source = retained_source(tmp_path)
    before = source.retained_source_path.read_bytes()
    result = validate_quillan_retained_source(
        source, workspace_root=tmp_path, source_page_number=3
    )
    assert result.retained_source is source
    assert result.source_page_number == 3
    assert source.retained_source_path.read_bytes() == before


def test_image_has_only_one_source_page(tmp_path: Path) -> None:
    source = retained_source(tmp_path, ".png")
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=2
        )


def test_path_and_provenance_contradictions_fail(tmp_path: Path) -> None:
    source = retained_source(tmp_path)
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            replace(source, source_sha256="A" * 64),
            workspace_root=tmp_path,
            source_page_number=1,
        )


@pytest.mark.parametrize("extension", [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"])
def test_all_supported_extensions_describe_exact_core_events(
    tmp_path: Path, extension: str
) -> None:
    source = retained_source(tmp_path, extension)
    result = validate_quillan_retained_source(
        source, workspace_root=tmp_path, source_page_number=1
    )
    assert result.retained_source is source


@pytest.mark.parametrize("page", [True, 0, -1])
def test_invalid_source_page_is_rejected_without_mutation(
    tmp_path: Path, page: object
) -> None:
    source = retained_source(tmp_path)
    before = source.retained_source_path.read_bytes()
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=page
        )
    assert source.retained_source_path.read_bytes() == before


def test_every_core_retention_identity_contradiction_is_rejected(
    tmp_path: Path,
) -> None:
    source = retained_source(tmp_path)
    arbitrary = source.retained_source_path.with_name("arbitrary.pdf")
    arbitrary.write_bytes(b"sentinel")
    contradictions = (
        replace(source, source_scan_id="arbitrary_safe_id"),
        replace(source, source_filename="different.pdf"),
        replace(source, source_filename="original.png"),
        replace(source, source_sha256="b" * 64),
        replace(
            source,
            intake_timestamp=source.intake_timestamp.replace(second=1),
        ),
        replace(source, intake_date=date(2026, 7, 21)),
        replace(source, retained_source_path=arbitrary),
        replace(
            source,
            retained_source_relative_path="scans/source/2026-07-20/arbitrary.pdf",
        ),
        replace(
            source,
            retained_source_relative_path="scans/source/2026-07-21/"
            + source.retained_source_path.name,
        ),
        replace(source, retained_source_relative_path="/scans/source/file.pdf"),
        replace(source, retained_source_relative_path=r"scans\source\file.pdf"),
        replace(source, retained_source_relative_path="scans/source/../file.pdf"),
    )
    before = source.retained_source_path.read_bytes()
    sentinel = arbitrary.read_bytes()
    for invalid in contradictions:
        with pytest.raises(QuillanRetainedSourceError):
            validate_quillan_retained_source(
                invalid, workspace_root=tmp_path, source_page_number=1
            )
        assert source.retained_source_path.read_bytes() == before
        assert arbitrary.read_bytes() == sentinel


def test_missing_directory_external_relative_and_wrong_workspace_fail(
    tmp_path: Path,
) -> None:
    source = retained_source(tmp_path)
    missing = source.retained_source_path.with_name("missing.pdf")
    directory = source.retained_source_path.with_name("directory.pdf")
    directory.mkdir()
    outside = tmp_path.parent / source.retained_source_path.name
    outside.write_bytes(b"external sentinel")
    cases = (
        (replace(source, retained_source_path=missing), tmp_path),
        (replace(source, retained_source_path=directory), tmp_path),
        (replace(source, retained_source_path=outside), tmp_path),
        (replace(source, retained_source_path=Path(source.retained_source_path.name)), tmp_path),
        (source, Path("relative-root")),
    )
    for invalid, root in cases:
        with pytest.raises(QuillanRetainedSourceError):
            validate_quillan_retained_source(
                invalid, workspace_root=root, source_page_number=1
            )
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root="wrong", source_page_number=1  # type: ignore[arg-type]
        )
    assert outside.read_bytes() == b"external sentinel"


def test_link_like_source_branch_is_rejected_without_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = retained_source(tmp_path)
    monkeypatch.setattr(
        retained_service,
        "_is_link_like",
        lambda path: path == source.retained_source_path,
    )
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=1
        )


def test_real_symlinked_retained_source_is_rejected(tmp_path: Path) -> None:
    source = retained_source(tmp_path)
    target = source.retained_source_path.with_name("target.pdf")
    target.write_bytes(b"target sentinel")
    source.retained_source_path.unlink()
    try:
        os.symlink(target, source.retained_source_path)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=1
        )
    assert target.read_bytes() == b"target sentinel"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_real_windows_junctioned_source_ancestor_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "junction-target"
    target.mkdir()
    junction = tmp_path / "junction"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    source = retained_source(target)
    redirected_path = junction / source.retained_source_path.relative_to(target)
    redirected = replace(
        source,
        retained_source_path=redirected_path,
    )
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            redirected, workspace_root=junction, source_page_number=1
        )


@pytest.mark.parametrize("control", ["\n", "\r", "\t", "\x00", "\u2028", "\u2029"])
def test_source_filename_rejects_control_and_line_separators(
    tmp_path: Path, control: str
) -> None:
    source = retained_source(tmp_path)
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            replace(source, source_filename=f"original{control}.pdf"),
            workspace_root=tmp_path,
            source_page_number=1,
        )


def test_unexpected_retained_boundary_runtime_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = retained_source(tmp_path)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("programming failure")

    monkeypatch.setattr(retained_service, "_validate_file_chain", fail)
    with pytest.raises(RuntimeError, match="programming failure"):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=1
        )


@pytest.mark.parametrize("component", ["scans", "source", "date"])
def test_each_intermediate_retained_link_branch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    component: str,
) -> None:
    source = retained_source(tmp_path)
    components = {
        "scans": tmp_path / "scans",
        "source": tmp_path / "scans" / "source",
        "date": tmp_path / "scans" / "source" / "2026-07-20",
    }
    rejected = components[component]
    original = retained_service._is_link_like
    monkeypatch.setattr(
        retained_service,
        "_is_link_like",
        lambda path: path == rejected or original(path),
    )
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=1
        )


@pytest.mark.parametrize("component", ["scans", "source", "date"])
@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_real_junctioned_intermediate_retained_paths_are_rejected(
    tmp_path: Path, component: str
) -> None:
    source = retained_source(tmp_path)
    components = {
        "scans": tmp_path / "scans",
        "source": tmp_path / "scans" / "source",
        "date": tmp_path / "scans" / "source" / "2026-07-20",
    }
    junction = components[component]
    target = tmp_path / f"external-{component}"
    shutil.move(str(junction), str(target))
    sentinel = target / "sentinel.txt"
    sentinel.write_text("external sentinel", encoding="utf-8")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    with pytest.raises(QuillanRetainedSourceError):
        validate_quillan_retained_source(
            source, workspace_root=tmp_path, source_page_number=1
        )
    assert sentinel.read_text(encoding="utf-8") == "external sentinel"
