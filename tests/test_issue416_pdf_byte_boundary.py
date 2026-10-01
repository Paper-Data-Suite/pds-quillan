"""Issue #416 Slice 2: PDF decoding is independent of retained path length."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, cast

from PIL import Image
from pds_core.scan_retention import RetainedSourceScan
import pytest

import quillan.retained_scan_pages as pages
from quillan.retained_scan_pages import (
    load_retained_page_for_qr,
    retained_source_page_count,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "issue416" / "retained_source_provenance.json"


class _InfoMissing(Exception):
    pass


class _PageCount(Exception):
    pass


class _Syntax(Exception):
    pass


class _Timeout(Exception):
    pass


def _fixture() -> dict[str, Any]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _historical_retained_source(workspace: Path) -> RetainedSourceScan:
    fixture = _fixture()
    legacy = cast(dict[str, str], fixture["legacy_v063"])
    retained = workspace.joinpath(*Path(legacy["retained_source_relative_path"]).parts)
    retained.parent.mkdir(parents=True, exist_ok=True)
    retained.write_bytes(cast(str, fixture["content_text"]).encode("utf-8"))
    return RetainedSourceScan(
        source_scan_id=legacy["source_scan_id"],
        source_filename=cast(str, fixture["source_filename"]),
        source_sha256=cast(str, fixture["source_sha256"]),
        retained_source_path=retained,
        retained_source_relative_path=legacy["retained_source_relative_path"],
        intake_timestamp=datetime.fromisoformat(
            cast(str, fixture["intake_timestamp"])
        ),
        intake_date=date.fromisoformat(cast(str, fixture["intake_date"])),
    )


def _pdf_support(
    info: object,
    convert: object,
) -> tuple[object, object, tuple[type[BaseException], ...]]:
    return info, convert, (_InfoMissing, _PageCount, _Syntax, _Timeout)


def test_historical_pdf_page_count_sends_bytes_not_retained_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _historical_retained_source(workspace)
    expected = retained.retained_source_path.read_bytes()
    observed: list[bytes] = []

    def info(pdf_bytes: bytes) -> dict[str, int]:
        observed.append(pdf_bytes)
        return {"Pages": 3}

    monkeypatch.setattr(
        pages,
        "_load_pdf2image",
        lambda: _pdf_support(info, object()),
    )

    assert retained_source_page_count(retained, workspace_root=workspace) == 3
    assert observed == [expected]


def test_historical_pdf_conversion_sends_bytes_and_exact_page_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _historical_retained_source(workspace)
    expected = retained.retained_source_path.read_bytes()
    observed: list[tuple[bytes, dict[str, object]]] = []

    def convert(pdf_bytes: bytes, **kwargs: object) -> list[Image.Image]:
        observed.append((pdf_bytes, kwargs))
        return [Image.new("RGB", (11, 7), "white")]

    monkeypatch.setattr(
        pages,
        "_load_pdf2image",
        lambda: _pdf_support(object(), convert),
    )

    image = load_retained_page_for_qr(retained, 2, workspace_root=workspace)

    assert observed == [
        (expected, {"first_page": 2, "last_page": 2})
    ]
    assert image.shape == (7, 11, 3)


def test_retained_pdf_loader_contains_no_path_based_pdf2image_api_calls() -> None:
    source = (ROOT / "quillan" / "retained_scan_pages.py").read_text(
        encoding="utf-8"
    )

    assert "pdfinfo_from_path" not in source
    assert "convert_from_path" not in source
    assert "pdfinfo_from_bytes" in source
    assert "convert_from_bytes" in source
