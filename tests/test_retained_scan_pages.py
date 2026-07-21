from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan

from quillan.module_errors import (
    QuillanPageImageError,
    QuillanPdfDependencyError,
    QuillanPdfPageConversionError,
    QuillanPdfPageCountError,
    QuillanSourcePageError,
)
import quillan.retained_scan_pages as pages
from quillan.retained_scan_pages import load_retained_page_for_qr, retained_source_page_count


def _retained(root: Path, filename: str) -> RetainedSourceScan:
    source = root.parent / filename
    image = np.full((20, 30, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(source), image)
    return retain_source_scan(root, source)


def test_image_is_exactly_one_bgr_page(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _retained(workspace, "scan.png")
    assert retained_source_page_count(retained, workspace_root=workspace) == 1
    loaded = load_retained_page_for_qr(retained, 1, workspace_root=workspace)
    assert loaded.dtype == np.uint8 and loaded.shape == (20, 30, 3)
    with pytest.raises(QuillanSourcePageError):
        load_retained_page_for_qr(retained, 2, workspace_root=workspace)


class _InfoMissing(Exception):
    pass


class _PageCount(Exception):
    pass


class _Syntax(Exception):
    pass


class _Timeout(Exception):
    pass


def _pdf_event(tmp_path: Path) -> RetainedSourceScan:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return retain_source_scan(workspace, source)


def _pdf_support(info: object, convert: object) -> tuple[object, object, tuple[type[BaseException], ...]]:
    return info, convert, (_InfoMissing, _PageCount, _Syntax, _Timeout)


@pytest.mark.parametrize("count", [0, -1, True, "2", None])
def test_pdf_page_count_must_be_positive_integer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: object) -> None:
    retained = _pdf_event(tmp_path)
    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(lambda _path: {"Pages": count}, object()))
    with pytest.raises(QuillanPdfPageCountError):
        retained_source_page_count(retained, workspace_root=tmp_path / "workspace")


def test_pdf_positive_page_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    retained = _pdf_event(tmp_path)
    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(lambda _path: {"Pages": 6}, object()))
    assert retained_source_page_count(retained, workspace_root=tmp_path / "workspace") == 6


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (_InfoMissing("poppler"), QuillanPdfDependencyError),
        (_PageCount("malformed"), QuillanPdfPageCountError),
        (_Syntax("syntax"), QuillanPdfPageCountError),
        (_Timeout("slow"), QuillanPdfPageCountError),
        (RuntimeError("unexpected"), QuillanPdfPageCountError),
    ],
)
def test_pdf_page_count_wraps_dependency_and_parser_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    expected: type[Exception],
) -> None:
    retained = _pdf_event(tmp_path)

    def fail(_path: str) -> object:
        raise raised

    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(fail, object()))
    with pytest.raises(expected):
        retained_source_page_count(retained, workspace_root=tmp_path / "workspace")


def test_pdf_dependency_import_failure_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    retained = _pdf_event(tmp_path)

    def missing() -> object:
        raise QuillanPdfDependencyError("missing pdf2image")

    monkeypatch.setattr(pages, "_load_pdf2image", missing)
    with pytest.raises(QuillanPdfDependencyError):
        retained_source_page_count(retained, workspace_root=tmp_path / "workspace")


def test_pdf_conversion_requests_exactly_one_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    retained = _pdf_event(tmp_path)
    calls: list[dict[str, object]] = []

    def convert(_path: str, **kwargs: object) -> list[Image.Image]:
        calls.append(kwargs)
        return [Image.new("RGB", (12, 8), "white")]

    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(object(), convert))
    image = load_retained_page_for_qr(retained, 2, workspace_root=tmp_path / "workspace")
    assert calls == [{"first_page": 2, "last_page": 2}]
    assert image.shape == (8, 12, 3)


def test_pdf_conversion_failure_and_invalid_result_are_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    retained = _pdf_event(tmp_path)

    def fail(_path: str, **_kwargs: object) -> object:
        raise _Timeout("slow")

    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(object(), fail))
    with pytest.raises(QuillanPdfPageConversionError):
        load_retained_page_for_qr(retained, 2, workspace_root=tmp_path / "workspace")
    monkeypatch.setattr(pages, "_load_pdf2image", lambda: _pdf_support(object(), lambda *_args, **_kwargs: [object()]))
    with pytest.raises(QuillanPageImageError):
        load_retained_page_for_qr(retained, 2, workspace_root=tmp_path / "workspace")
