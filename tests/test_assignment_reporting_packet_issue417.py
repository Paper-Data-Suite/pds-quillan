"""Issue #417 Slice 5 tests for coherent assignment reporting packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

import quillan.assignment_reporting_packet as packet_module
from quillan.assignment_reporting_packet import (
    AssignmentReportingPacketError,
    export_assignment_reporting_packet,
)
from quillan.assignment_review_report_export import (
    AssignmentReviewReportExportError,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_assignment_reporting_snapshot_issue417 import _prepare_workspace
from tests.test_class_summary_export import TIMESTAMP


def test_packet_generates_all_five_outputs_from_one_snapshot_and_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_workspace(tmp_path)

    original_builder = getattr(packet_module, "build_assignment_reporting_snapshot")
    build_count = 0

    def counted_builder(*args: Any, **kwargs: Any) -> Any:
        nonlocal build_count
        build_count += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        packet_module,
        "build_assignment_reporting_snapshot",
        counted_builder,
    )

    source_files = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    result = export_assignment_reporting_packet(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        generated_at=TIMESTAMP,
    )

    assert build_count == 1
    assert result.generated_at == TIMESTAMP
    assert result.student_performance_summary.created_at == TIMESTAMP
    assert result.class_summary.created_at == TIMESTAMP
    assert result.standards_summary.created_at == TIMESTAMP
    assert result.assignment_review_report.created_at == TIMESTAMP
    assert result.assignment_results_manifest.generated_at == TIMESTAMP
    assert len(result.relative_paths) == 5
    assert len(set(result.relative_paths)) == 5

    for relative_path in result.relative_paths:
        assert (tmp_path / relative_path).is_file()

    assert len(
        PdfReader(str(result.assignment_review_report.report_path)).pages
    ) >= 2

    manifest = json.loads(
        result.assignment_results_manifest.manifest_path.read_text(
            encoding="utf-8"
        )
    )
    inventory = {
        item["artifact"]: item["status"]
        for item in manifest["generated_artifacts"]
    }
    assert inventory == {
        "student_performance_summary_csv": "present",
        "class_summary_csv": "present",
        "standards_summary_csv": "present",
        "assignment_review_report_pdf": "present",
        "assignment_results_manifest_json": "generated",
    }

    for path, original in source_files.items():
        assert path.read_bytes() == original


def test_packet_existing_output_conflict_fails_before_any_new_output(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)
    exports = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
    )
    exports.mkdir(parents=True, exist_ok=True)
    existing = exports / "class_summary.csv"
    existing.write_bytes(b"keep-me")

    with pytest.raises(
        AssignmentReportingPacketError,
        match="existing report artifacts",
    ):
        export_assignment_reporting_packet(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            generated_at=TIMESTAMP,
        )

    assert existing.read_bytes() == b"keep-me"
    assert not (exports / "student_performance_summary.csv").exists()
    assert not (exports / "standards_summary.csv").exists()
    assert not (exports / "assignment_review_report.pdf").exists()
    assert not (exports / "assignment_results_manifest.json").exists()


def test_packet_runtime_failure_reports_completed_derived_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_workspace(tmp_path)

    def fail_pdf(*args: Any, **kwargs: Any) -> Any:
        raise AssignmentReviewReportExportError("synthetic failure")

    monkeypatch.setattr(
        packet_module,
        "export_assignment_review_report_from_snapshot",
        fail_pdf,
    )

    with pytest.raises(AssignmentReportingPacketError) as captured:
        export_assignment_reporting_packet(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            generated_at=TIMESTAMP,
        )

    assert captured.value.completed_relative_paths == (
        (
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            "exports/student_performance_summary.csv"
        ),
        (
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            "exports/class_summary.csv"
        ),
        (
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            "exports/standards_summary.csv"
        ),
    )
