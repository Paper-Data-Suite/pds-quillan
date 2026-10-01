"""Installed Issue #416 scan-path compatibility acceptance.

Run this program outside the source checkout with the candidate Quillan wheel
and an exact PDS Core 0.6.4 wheel installed in the active environment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import cv2
import numpy as np
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan
from reportlab.pdfgen import canvas

from quillan.printable_response_records import page_role_for_logical_page
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    canonical_response_page_observation_json,
    derive_observation_id,
    list_quillan_page_observations,
)
from quillan.retained_scan_pages import (
    load_retained_page_for_qr,
    retained_source_page_count,
)
from quillan.retained_source import validate_quillan_retained_source
from quillan.routed_evidence import materialize_routed_page_evidence
from quillan.work_paths import (
    ROUTED_EVIDENCE_FILENAME_MAX_LENGTH,
    quillan_work_ref,
    response_page_observation_path,
    routed_evidence_path,
)

EXPECTED_CORE_VERSION = "0.6.4"
MIN_HISTORICAL_PATH_LENGTH = 300
CLASS_ID = "issue416_installed_class"
ASSIGNMENT_ID = "issue416_installed_assignment"


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"{module_name} has no import origin")
    return Path(raw).resolve()


def _pdf_bytes() -> bytes:
    with tempfile.TemporaryDirectory(prefix="quillan-416-pdf-") as directory:
        path = Path(directory) / "fixture.pdf"
        document = canvas.Canvas(str(path), pagesize=(200, 200))
        document.drawString(20, 120, "Issue 416 page one")
        document.showPage()
        document.drawString(20, 120, "Issue 416 page two")
        document.showPage()
        document.save()
        return path.read_bytes()


def _png_bytes() -> bytes:
    image = np.zeros((17, 23, 3), dtype=np.uint8)
    image[:, :, 1] = 180
    encoded, payload = cv2.imencode(".png", image)
    if not encoded or payload.size == 0:
        raise AssertionError("Could not encode synthetic PNG fixture.")
    return payload.tobytes()


def _legacy_retained_filename(
    source_filename: str,
    content: bytes,
    timestamp: datetime,
) -> str:
    source = Path(source_filename)
    if source.name != source_filename:
        raise AssertionError("Historical source filename must be filename-only.")
    digest = hashlib.sha256(content).hexdigest()
    utc = timestamp.astimezone(timezone.utc)
    timestamp_component = utc.strftime("%Y%m%dT%H%M%S%fZ")
    return (
        f"{timestamp_component}__{source.stem}__"
        f"{digest[:12]}{source.suffix.lower()}"
    )


def _historical_retained(
    workspace: Path,
    *,
    source_filename: str,
    content: bytes,
    timestamp: datetime,
) -> RetainedSourceScan:
    digest = hashlib.sha256(content).hexdigest()
    retained_filename = _legacy_retained_filename(
        source_filename,
        content,
        timestamp,
    )
    retained = (
        workspace
        / "scans"
        / "source"
        / timestamp.date().isoformat()
        / retained_filename
    )
    retained.parent.mkdir(parents=True, exist_ok=True)
    retained.write_bytes(content)
    return RetainedSourceScan(
        source_scan_id=f"scan_{retained.stem}",
        source_filename=source_filename,
        source_sha256=digest,
        retained_source_path=retained,
        retained_source_relative_path=retained.relative_to(workspace).as_posix(),
        intake_timestamp=timestamp,
        intake_date=timestamp.date(),
    )


def _deep_workspace(base: Path, historical_leaf: str) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    workspace = base / "workspace"
    probe = (
        workspace
        / "scans"
        / "source"
        / "2026-08-24"
        / historical_leaf
    )
    index = 0
    while len(str(probe)) < MIN_HISTORICAL_PATH_LENGTH:
        workspace = workspace / (f"depth_{index:02d}_" + ("x" * 18))
        probe = (
            workspace
            / "scans"
            / "source"
            / "2026-08-24"
            / historical_leaf
        )
        index += 1
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _windows_long_paths_policy() -> int | str:
    if os.name != "nt":
        return "not_windows"
    try:
        winreg = importlib.import_module("winreg")
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
            0,
            winreg.KEY_READ,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        finally:
            winreg.CloseKey(key)
        return int(value)
    except (OSError, AttributeError, TypeError, ValueError):
        return "unavailable"


def _fresh_core_064(
    workspace: Path,
    staging: Path,
    pdf: bytes,
) -> RetainedSourceScan:
    routes = importlib.import_module("pds_core.scan_routes")
    filename_max = getattr(routes, "RETAINED_SOURCE_FILENAME_MAX_LENGTH", None)
    scan_id_max = getattr(routes, "SOURCE_SCAN_ID_MAX_LENGTH", None)
    if not isinstance(filename_max, int) or not isinstance(scan_id_max, int):
        raise AssertionError("Installed Core does not expose the 0.6.4 writer bounds.")

    staging.mkdir(parents=True, exist_ok=True)
    source_filename = "fresh_core_064_" + ("x" * 110) + ".pdf"
    source = staging / source_filename
    source.write_bytes(pdf)
    timestamp = datetime(2026, 9, 30, 15, 30, 45, 123456, tzinfo=timezone.utc)
    retained = retain_source_scan(
        workspace,
        source,
        intake_timestamp=timestamp,
    )
    parts = retained.retained_source_path.name.split("__")
    if (
        retained.source_filename != source_filename
        or len(parts) != 3
        or not parts[1].startswith("scan_")
        or len(retained.retained_source_path.name) > filename_max
        or len(retained.source_scan_id) > scan_id_max
    ):
        raise AssertionError("Fresh Core 0.6.4 retention did not use bounded identity.")
    validate_quillan_retained_source(
        retained,
        workspace_root=workspace,
        source_page_number=1,
    )
    if retained_source_page_count(retained, workspace_root=workspace) != 2:
        raise AssertionError("Fresh retained PDF page count was not two.")
    rendered = load_retained_page_for_qr(
        retained,
        2,
        workspace_root=workspace,
    )
    if rendered.ndim != 3 or rendered.shape[2] != 3:
        raise AssertionError("Fresh retained PDF did not render to BGR.")
    return retained


def _historical_pdf(
    workspace: Path,
    pdf: bytes,
) -> RetainedSourceScan:
    source_filename = (
        "historical_core_063_pdf_with_deliberately_long_external_source_"
        + ("h" * 72)
        + ".pdf"
    )
    timestamp = datetime(2026, 8, 24, 12, 34, 56, 654321, tzinfo=timezone.utc)
    retained = _historical_retained(
        workspace,
        source_filename=source_filename,
        content=pdf,
        timestamp=timestamp,
    )
    validate_quillan_retained_source(
        retained,
        workspace_root=workspace,
        source_page_number=2,
    )
    before = retained.retained_source_path.read_bytes()
    if retained_source_page_count(retained, workspace_root=workspace) != 2:
        raise AssertionError("Historical retained PDF page count was not two.")
    rendered = load_retained_page_for_qr(
        retained,
        2,
        workspace_root=workspace,
    )
    if rendered.ndim != 3 or rendered.shape[2] != 3:
        raise AssertionError("Historical retained PDF did not render to BGR.")
    if retained.retained_source_path.read_bytes() != before:
        raise AssertionError("Historical retained PDF bytes changed during processing.")
    return retained


def _historical_image(
    workspace: Path,
    png: bytes,
) -> RetainedSourceScan:
    source_filename = (
        "historical_core_063_image_with_deliberately_long_external_source_"
        + ("i" * 68)
        + ".png"
    )
    timestamp = datetime(2026, 8, 24, 12, 35, 56, 654321, tzinfo=timezone.utc)
    retained = _historical_retained(
        workspace,
        source_filename=source_filename,
        content=png,
        timestamp=timestamp,
    )
    validate_quillan_retained_source(
        retained,
        workspace_root=workspace,
        source_page_number=1,
    )
    before = retained.retained_source_path.read_bytes()
    decoded = load_retained_page_for_qr(
        retained,
        1,
        workspace_root=workspace,
    )
    if decoded.shape != (17, 23, 3):
        raise AssertionError("Historical retained image did not decode as expected.")
    if retained.retained_source_path.read_bytes() != before:
        raise AssertionError("Historical retained image bytes changed during decoding.")
    return retained


def _dispatch_result(
    retained: RetainedSourceScan,
    *,
    route_digit: str,
    page_digit: str,
    issuance_digit: str,
    student_id: str,
) -> QuillanResponsePageDispatchResult:
    return QuillanResponsePageDispatchResult(
        route_id="rt_" + (route_digit * 32),
        page_id="pg_" + (page_digit * 32),
        issuance_id="iss_" + (issuance_digit * 32),
        generation_id="gen_" + ("4" * 32),
        artifact_id="art_" + ("5" * 32),
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=student_id,
        logical_page=1,
        total_pages=1,
        page_role=page_role_for_logical_page(1),
        source_scan_id=retained.source_scan_id,
        source_filename=retained.source_filename,
        source_page_number=1,
        retained_source_path=retained.retained_source_path,
        retained_source_relative_path=retained.retained_source_relative_path,
        source_sha256=retained.source_sha256,
        intake_timestamp=retained.intake_timestamp,
        intake_date=retained.intake_date,
    )


def _bounded_new_evidence(
    workspace: Path,
    retained: RetainedSourceScan,
) -> tuple[str, int]:
    student_id = "student_" + ("s" * 180)
    result = _dispatch_result(
        retained,
        route_digit="1",
        page_digit="2",
        issuance_digit="3",
        student_id=student_id,
    )
    observation_id = derive_observation_id(
        result.source_scan_id,
        result.source_page_number,
        result.route_id,
        result.page_id,
    )
    evidence = materialize_routed_page_evidence(
        workspace,
        result,
        observation_id=observation_id,
    )
    if evidence.path.name != f"{observation_id}.png":
        raise AssertionError("New routed evidence did not use observation-ID leaf.")
    if len(evidence.path.name) > ROUTED_EVIDENCE_FILENAME_MAX_LENGTH:
        raise AssertionError("New routed-evidence leaf exceeded its explicit bound.")
    if student_id in evidence.path.name:
        raise AssertionError("New routed-evidence leaf repeated student identity.")
    return observation_id, len(evidence.path.name)


def _legacy_evidence_observation(
    workspace: Path,
    retained: RetainedSourceScan,
) -> QuillanResponsePageObservation:
    student_id = "legacy_student_1"
    result = _dispatch_result(
        retained,
        route_digit="6",
        page_digit="7",
        issuance_digit="8",
        student_id=student_id,
    )
    observation_id = derive_observation_id(
        result.source_scan_id,
        result.source_page_number,
        result.route_id,
        result.page_id,
    )
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    bounded = routed_evidence_path(
        workspace,
        work_ref,
        result.issuance_id,
        student_id,
        result.logical_page,
        observation_id,
        ".png",
    )
    legacy = bounded.with_name(
        f"response_{student_id}_pg_{result.logical_page:03d}__"
        f"{observation_id}.png"
    )
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(retained.retained_source_path.read_bytes())
    observation = QuillanResponsePageObservation(
        schema_version="1",
        observation_id=observation_id,
        record_type="response_page_observation",
        module_id="quillan",
        created_at=retained.intake_timestamp.isoformat(),
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=student_id,
        generation_id=result.generation_id,
        artifact_id=result.artifact_id,
        issuance_id=result.issuance_id,
        page_id=result.page_id,
        route_id=result.route_id,
        logical_page=result.logical_page,
        total_pages=result.total_pages,
        page_role=result.page_role,
        source_scan_id=retained.source_scan_id,
        source_filename=retained.source_filename,
        source_page_number=1,
        retained_source_path=retained.retained_source_relative_path,
        source_sha256=retained.source_sha256,
        intake_timestamp=retained.intake_timestamp.isoformat(),
        intake_date=retained.intake_date.isoformat(),
        routed_evidence_path=legacy.relative_to(workspace).as_posix(),
        routed_evidence_sha256=hashlib.sha256(legacy.read_bytes()).hexdigest(),
        routed_evidence_size_bytes=legacy.stat().st_size,
        routed_evidence_kind="retained_image_copy",
        module_details={},
    )
    observation_path = response_page_observation_path(
        workspace,
        work_ref,
        observation_id,
    )
    observation_path.parent.mkdir(parents=True, exist_ok=True)
    observation_path.write_bytes(
        canonical_response_page_observation_json(observation)
    )
    loaded = list_quillan_page_observations(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    if loaded != (observation,):
        raise AssertionError("Legacy routed-evidence observation did not reload exactly.")
    if not legacy.is_file() or bounded.exists():
        raise AssertionError("Legacy evidence was renamed or bounded evidence was created.")
    return observation


def _prepare_workspace(root: Path, pdf: bytes) -> Path:
    if root.exists() and any(root.iterdir()):
        raise AssertionError("Issue #416 acceptance workspace must be empty.")
    root.mkdir(parents=True, exist_ok=True)
    sample_source = (
        "historical_core_063_pdf_with_deliberately_long_external_source_"
        + ("h" * 72)
        + ".pdf"
    )
    sample_leaf = _legacy_retained_filename(
        sample_source,
        pdf,
        datetime(2026, 8, 24, 12, 34, 56, 654321, tzinfo=timezone.utc),
    )
    workspace = _deep_workspace(root, sample_leaf)
    probe = workspace / "scans" / "source" / "2026-08-24" / sample_leaf
    if len(str(probe)) < MIN_HISTORICAL_PATH_LENGTH:
        raise AssertionError("Historical path-pressure fixture is not deep enough.")
    return workspace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-quillan-version", required=True)
    parser.add_argument(
        "--expected-core-version",
        default=EXPECTED_CORE_VERSION,
        choices=(EXPECTED_CORE_VERSION,),
    )
    args = parser.parse_args()

    repository = args.repository.resolve()
    if metadata.version("quillan") != args.expected_quillan_version:
        raise AssertionError("Installed Quillan version mismatch.")
    if metadata.version("pds-core") != args.expected_core_version:
        raise AssertionError("Installed Core version mismatch.")
    for module_name in ("quillan", "pds_core"):
        if _module_origin(module_name).is_relative_to(repository):
            raise AssertionError(f"{module_name} import is source-shadowed.")

    policy_before = _windows_long_paths_policy()
    pdf = _pdf_bytes()
    png = _png_bytes()
    workspace = _prepare_workspace(args.workspace.resolve(), pdf)
    staging = args.workspace.resolve() / "bounded-source-input"

    fresh = _fresh_core_064(workspace, staging, pdf)
    historical_pdf = _historical_pdf(workspace, pdf)
    historical_image = _historical_image(workspace, png)
    _, evidence_leaf_length = _bounded_new_evidence(workspace, fresh)
    _legacy_evidence_observation(workspace, historical_image)

    historical_pdf_length = len(str(historical_pdf.retained_source_path))
    if historical_pdf_length < MIN_HISTORICAL_PATH_LENGTH:
        raise AssertionError("Historical PDF path did not retain deep-path pressure.")
    historical_pdf_bytes = historical_pdf.retained_source_path.read_bytes()
    historical_image_bytes = historical_image.retained_source_path.read_bytes()
    if hashlib.sha256(historical_pdf_bytes).hexdigest() != historical_pdf.source_sha256:
        raise AssertionError("Historical PDF provenance changed.")
    if hashlib.sha256(historical_image_bytes).hexdigest() != historical_image.source_sha256:
        raise AssertionError("Historical image provenance changed.")

    policy_after = _windows_long_paths_policy()
    if policy_after != policy_before:
        raise AssertionError("Windows LongPathsEnabled changed during acceptance.")

    result: dict[str, Any] = {
        "status": "PASS",
        "quillan_version": args.expected_quillan_version,
        "core_version": args.expected_core_version,
        "fresh_core_064_provenance": "PASS",
        "fresh_pdf_processing": "PASS",
        "historical_core_063_provenance": "PASS",
        "historical_pdf_processing": "PASS",
        "historical_image_processing": "PASS",
        "bounded_new_routed_evidence": "PASS",
        "legacy_routed_evidence_read": "PASS",
        "migration_or_rename": False,
        "historical_pdf_path_length": historical_pdf_length,
        "new_evidence_filename_length": evidence_leaf_length,
        "new_evidence_filename_max": ROUTED_EVIDENCE_FILENAME_MAX_LENGTH,
        "long_paths_policy_before": policy_before,
        "long_paths_policy_after": policy_after,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
