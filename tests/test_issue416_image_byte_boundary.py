"""Issue #416 Slice 3: retained image decoding uses validated bytes."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
from pds_core.scan_retention import RetainedSourceScan
import pytest

from quillan.module_errors import QuillanPageImageError
from quillan.retained_scan_pages import load_retained_page_for_qr

ROOT = Path(__file__).resolve().parents[1]


def _historical_long_image(workspace: Path) -> RetainedSourceScan:
    source_image = np.zeros((9, 13, 3), dtype=np.uint8)
    source_image[:, :, 1] = 200
    encoded_ok, encoded = cv2.imencode(".png", source_image)
    assert encoded_ok
    content = encoded.tobytes()
    digest = hashlib.sha256(content).hexdigest()
    timestamp = datetime(2026, 9, 30, 3, 18, 38, 64717, tzinfo=timezone.utc)
    source_filename = (
        "issue416_historical_retained_image_with_deliberately_long_source_"
        "filename_for_native_path_regression_testing.png"
    )
    retained_filename = (
        "20260930T031838064717Z__"
        "issue416_historical_retained_image_with_deliberately_long_source_"
        "filename_for_native_path_regression_testing__"
        f"{digest[:12]}.png"
    )
    relative = f"scans/source/2026-09-30/{retained_filename}"
    retained_path = workspace.joinpath(*Path(relative).parts)
    retained_path.parent.mkdir(parents=True, exist_ok=True)
    retained_path.write_bytes(content)
    return RetainedSourceScan(
        source_scan_id=f"scan_{retained_path.stem}",
        source_filename=source_filename,
        source_sha256=digest,
        retained_source_path=retained_path,
        retained_source_relative_path=relative,
        intake_timestamp=timestamp,
        intake_date=date(2026, 9, 30),
    )


def test_historical_long_retained_image_decodes_from_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _historical_long_image(workspace)
    original_imdecode = cv2.imdecode
    observed: list[bytes] = []

    def imdecode(
        buffer: NDArray[np.uint8],
        flags: int,
    ) -> NDArray[np.uint8] | None:
        observed.append(buffer.tobytes())
        return cast(NDArray[np.uint8] | None, original_imdecode(buffer, flags))

    def forbidden_imread(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("retained image path must not be passed to cv2.imread")

    monkeypatch.setattr(cv2, "imdecode", imdecode)
    monkeypatch.setattr(cv2, "imread", forbidden_imread)

    image = load_retained_page_for_qr(retained, 1, workspace_root=workspace)

    assert observed == [retained.retained_source_path.read_bytes()]
    assert image.dtype == np.uint8
    assert image.shape == (9, 13, 3)


def test_retained_image_read_failure_is_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _historical_long_image(workspace)
    retained_path = retained.retained_source_path
    original_read_bytes = Path.read_bytes

    def fail(path: Path) -> bytes:
        if path == retained_path:
            raise OSError("synthetic read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail)

    with pytest.raises(QuillanPageImageError, match="read retained image bytes"):
        load_retained_page_for_qr(retained, 1, workspace_root=workspace)


def test_invalid_retained_image_bytes_are_typed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    retained = _historical_long_image(workspace)
    retained.retained_source_path.write_bytes(b"not an image")

    with pytest.raises(QuillanPageImageError):
        load_retained_page_for_qr(retained, 1, workspace_root=workspace)


def test_retained_image_loader_contains_no_cv2_imread_call() -> None:
    source = (ROOT / "quillan" / "retained_scan_pages.py").read_text(
        encoding="utf-8"
    )

    assert "cv2.imread(" not in source
    assert "cv2.imdecode(" in source
    assert "np.frombuffer(" in source
