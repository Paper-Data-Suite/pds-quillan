"""Tests for retained source intake and successful routed evidence filing."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pds_core.scan_retention import RetainedSourceScan
from pds_core.scan_routes import build_retained_source_filename

import quillan.evidence_filing as evidence_filing
from quillan.evidence_filing import (
    EvidenceFilingError,
    file_routed_response_evidence,
)
from quillan.route_planning import RoutePlan

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
INTAKE_TIMESTAMP = datetime(2026, 6, 19, 23, 45, 1, 123456, tzinfo=timezone.utc)
SOURCE_BYTES = b"%PDF-1.4\nsynthetic scan evidence\n%%EOF\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    assignment_dir = (
        tmp_path / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID
    )
    assignment_dir.mkdir(parents=True)
    (assignment_dir / "assignment.json").write_text(
        '{"synthetic": true}\n',
        encoding="utf-8",
    )
    roster_path = tmp_path / "classes" / CLASS_ID / "roster.csv"
    roster_path.write_text("student_id\n00107\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def route_plan(workspace: Path) -> RoutePlan:
    assignment_dir = (
        workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID
    )
    return RoutePlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        page_number=2,
        assignment_config_path=assignment_dir / "assignment.json",
        roster_path=workspace / "classes" / CLASS_ID / "roster.csv",
        routed_evidence_dir=assignment_dir / "scans",
        student_submission_dir=assignment_dir / "submissions" / STUDENT_ID,
    )


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "Teacher Scan.PDF"
    path.write_bytes(SOURCE_BYTES)
    return path


def test_files_retained_source_and_routed_evidence_with_provenance(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    original_bytes = source_file.read_bytes()
    result = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
    )

    expected_sha256 = hashlib.sha256(SOURCE_BYTES).hexdigest()
    expected_retained_name = build_retained_source_filename(
        intake_timestamp=INTAKE_TIMESTAMP,
        original_filename=source_file.name,
        sha256_hex=expected_sha256,
    )
    expected_retained_path = (
        workspace / "scans" / "source" / "2026-06-19" / expected_retained_name
    ).resolve()
    expected_routed_path = (
        route_plan.routed_evidence_dir / "response_00107_pg_002.pdf"
    ).resolve()

    assert result.retained_source.source_filename == "Teacher Scan.PDF"
    assert result.retained_source.source_sha256 == expected_sha256
    assert result.retained_source.source_scan_id == (
        f"scan_{expected_retained_path.stem}"
    )
    assert result.retained_source.retained_source_path == expected_retained_path
    assert result.retained_source.retained_source_relative_path == (
        f"scans/source/2026-06-19/{expected_retained_name}"
    )
    assert result.routed_evidence_path == expected_routed_path
    assert result.routed_evidence_relative_path == (
        "classes/english12_p3_synthetic/modules/quillan/work/"
        "essay_01_synthetic/scans/response_00107_pg_002.pdf"
    )
    assert result.class_id == CLASS_ID
    assert result.assignment_id == ASSIGNMENT_ID
    assert result.student_id == "00107"
    assert result.page_number == 2
    assert result.duplicate_number is None
    assert expected_retained_path.read_bytes() == SOURCE_BYTES
    assert expected_routed_path.read_bytes() == SOURCE_BYTES
    assert source_file.read_bytes() == original_bytes


def test_delegates_source_retention_to_core_helper(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retained_path = workspace / "scans" / "source" / "retained.pdf"
    retained_path.parent.mkdir(parents=True)
    retained_path.write_bytes(b"retained by core")
    retained = RetainedSourceScan(
        source_scan_id="scan_delegated",
        source_filename=source_file.name,
        source_sha256="a" * 64,
        retained_source_path=retained_path,
        retained_source_relative_path="scans/source/retained.pdf",
        intake_timestamp=INTAKE_TIMESTAMP,
        intake_date=date(2026, 6, 19),
    )
    calls: list[tuple[object, object, object, object]] = []

    def fake_retain_source_scan(
        root: object,
        source: object,
        *,
        intake_timestamp: object,
        intake_date: object,
    ) -> RetainedSourceScan:
        calls.append((root, source, intake_timestamp, intake_date))
        return retained

    monkeypatch.setattr(
        evidence_filing,
        "retain_source_scan",
        fake_retain_source_scan,
    )

    result = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
        intake_date="2026-06-18",
    )

    assert calls == [
        (workspace.resolve(), source_file, INTAKE_TIMESTAMP, "2026-06-18")
    ]
    assert result.retained_source is retained
    assert result.routed_evidence_path.read_bytes() == b"retained by core"


def test_intake_date_defaults_to_utc_date(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    eastern = timezone(timedelta(hours=-4))
    timestamp = datetime(2026, 6, 19, 23, 30, tzinfo=eastern)

    result = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=timestamp,
    )

    assert "/2026-06-20/" in (
        f"/{result.retained_source.retained_source_relative_path}/"
    )


def test_explicit_intake_date_is_used(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    result = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
        intake_date="2026-06-18",
    )

    assert "/2026-06-18/" in (
        f"/{result.retained_source.retained_source_relative_path}/"
    )


def test_retained_source_collision_is_refused(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
    )

    with pytest.raises(EvidenceFilingError, match="already exists"):
        file_routed_response_evidence(
            workspace,
            route_plan=route_plan,
            source_file_path=source_file,
            intake_timestamp=INTAKE_TIMESTAMP,
        )


@pytest.mark.parametrize("filename", ["scan.txt", "scan.exe", "scan"])
def test_unsupported_source_extension_fails_without_creating_scan_dirs(
    workspace: Path,
    route_plan: RoutePlan,
    tmp_path: Path,
    filename: str,
) -> None:
    source = tmp_path / filename
    source.write_bytes(b"synthetic")

    with pytest.raises(EvidenceFilingError, match="supported scan extension"):
        file_routed_response_evidence(
            workspace,
            route_plan=route_plan,
            source_file_path=source,
            intake_timestamp=INTAKE_TIMESTAMP,
        )

    assert not (workspace / "scans").exists()
    assert not route_plan.routed_evidence_dir.exists()


def test_missing_source_fails_without_creating_scan_dirs(
    workspace: Path,
    route_plan: RoutePlan,
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceFilingError, match="does not exist"):
        file_routed_response_evidence(
            workspace,
            route_plan=route_plan,
            source_file_path=tmp_path / "missing.pdf",
            intake_timestamp=INTAKE_TIMESTAMP,
        )

    assert not (workspace / "scans").exists()
    assert not route_plan.routed_evidence_dir.exists()


def test_directory_source_fails(
    workspace: Path,
    route_plan: RoutePlan,
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceFilingError, match="not a regular file"):
        file_routed_response_evidence(
            workspace,
            route_plan=route_plan,
            source_file_path=tmp_path,
            intake_timestamp=INTAKE_TIMESTAMP,
        )


def test_duplicates_use_incrementing_exclusive_filenames(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    first = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
    )
    second = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP + timedelta(microseconds=1),
    )
    third = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP + timedelta(microseconds=2),
    )

    assert first.routed_evidence_path.name == "response_00107_pg_002.pdf"
    assert second.routed_evidence_path.name == (
        "response_00107_pg_002__dup_001.pdf"
    )
    assert third.routed_evidence_path.name == (
        "response_00107_pg_002__dup_002.pdf"
    )
    assert second.duplicate_number == 1
    assert third.duplicate_number == 2
    assert first.routed_evidence_path.read_bytes() == SOURCE_BYTES
    assert second.routed_evidence_path.read_bytes() == SOURCE_BYTES
    assert third.routed_evidence_path.read_bytes() == SOURCE_BYTES


@pytest.mark.parametrize(
    ("page_number", "expected_name"),
    [
        (1, "response_00107_pg_001.pdf"),
        (999, "response_00107_pg_999.pdf"),
        (1000, "response_00107_pg_1000.pdf"),
    ],
)
def test_page_number_formatting(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
    page_number: int,
    expected_name: str,
) -> None:
    result = file_routed_response_evidence(
        workspace,
        route_plan=replace(route_plan, page_number=page_number),
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
    )

    assert result.routed_evidence_path.name == expected_name


def test_page_number_none_is_rejected_before_writes(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    with pytest.raises(EvidenceFilingError, match="positive integer"):
        file_routed_response_evidence(
            workspace,
            route_plan=replace(route_plan, page_number=None),
            source_file_path=source_file,
            intake_timestamp=INTAKE_TIMESTAMP,
        )

    assert not (workspace / "scans").exists()
    assert not route_plan.routed_evidence_dir.exists()


def test_already_extracted_page_artifact_can_be_routed(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
    tmp_path: Path,
) -> None:
    page_bytes = b"\x89PNG\r\nsynthetic extracted page"
    page_artifact = tmp_path / "page-2.PNG"
    page_artifact.write_bytes(page_bytes)

    result = file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        routed_source_file_path=page_artifact,
        intake_timestamp=INTAKE_TIMESTAMP,
    )

    assert result.routed_evidence_path.name == "response_00107_pg_002.png"
    assert result.routed_evidence_path.read_bytes() == page_bytes
    assert result.retained_source.retained_source_path.read_bytes() == SOURCE_BYTES


@pytest.mark.parametrize(
    "extension",
    ["../pdf", "/pdf", r"\pdf", ".html", ""],
)
def test_unsafe_or_unsupported_routed_extension_fails_before_writes(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
    extension: str,
) -> None:
    with pytest.raises(EvidenceFilingError, match="Unsupported routed"):
        file_routed_response_evidence(
            workspace,
            route_plan=route_plan,
            source_file_path=source_file,
            intake_timestamp=INTAKE_TIMESTAMP,
            routed_extension=extension,
        )

    assert not (workspace / "scans").exists()
    assert not route_plan.routed_evidence_dir.exists()


def test_routed_directory_outside_workspace_is_rejected_before_writes(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
    tmp_path: Path,
) -> None:
    unsafe_plan = replace(
        route_plan,
        routed_evidence_dir=tmp_path.parent / "outside-workspace",
    )

    with pytest.raises(EvidenceFilingError, match="escapes"):
        file_routed_response_evidence(
            workspace,
            route_plan=unsafe_plan,
            source_file_path=source_file,
            intake_timestamp=INTAKE_TIMESTAMP,
        )

    assert not (workspace / "scans").exists()


def test_mismatched_routed_evidence_dir_is_rejected_before_writes(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    bad_plan = replace(
        route_plan,
        routed_evidence_dir=(
            workspace
            / "classes"
            / CLASS_ID
            / "modules"
            / "quillan"
            / "work"
            / "different_assignment"
            / "scans"
        ),
    )

    with pytest.raises(EvidenceFilingError, match="does not match"):
        file_routed_response_evidence(
            workspace,
            route_plan=bad_plan,
            source_file_path=source_file,
            intake_timestamp=INTAKE_TIMESTAMP,
        )

    assert not (workspace / "scans").exists()
    assert not route_plan.routed_evidence_dir.exists()
    assert not bad_plan.routed_evidence_dir.exists()


def test_success_does_not_create_review_submission_or_output_records(
    workspace: Path,
    route_plan: RoutePlan,
    source_file: Path,
) -> None:
    assignment_config_before = route_plan.assignment_config_path.read_bytes()
    roster_before = route_plan.roster_path.read_bytes()

    file_routed_response_evidence(
        workspace,
        route_plan=route_plan,
        source_file_path=source_file,
        intake_timestamp=INTAKE_TIMESTAMP,
    )

    assert not (workspace / "scans" / "review").exists()
    assert not route_plan.student_submission_dir.exists()
    assert not list(workspace.rglob("submission.json"))
    assert not list(workspace.rglob("requirements.json"))
    assert not list(workspace.rglob("tags.json"))
    assert not list(workspace.rglob("scores.json"))
    assert not list(workspace.rglob("feedback.md"))
    assert route_plan.assignment_config_path.read_bytes() == assignment_config_before
    assert route_plan.roster_path.read_bytes() == roster_before
