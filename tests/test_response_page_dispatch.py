"""Focused tests for the frozen Quillan dispatch result."""

from dataclasses import FrozenInstanceError, replace
import copy
from datetime import date, datetime, timezone
from pathlib import Path

from pds_core.scan_routes import build_retained_source_filename
import pytest

from quillan.module_errors import QuillanDispatchResultError
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)


def valid_result() -> QuillanResponsePageDispatchResult:
    timestamp = datetime(2026, 7, 20, tzinfo=timezone.utc)
    retained_filename = build_retained_source_filename(
        intake_timestamp=timestamp,
        original_filename="original.pdf",
        sha256_hex="a" * 64,
    )
    retained = Path.cwd() / "workspace" / "scans" / "source" / "2026-07-20" / retained_filename
    return QuillanResponsePageDispatchResult(
        route_id="rt_0123456789abcdef0123456789abcdef",
        page_id="pg_0123456789abcdef0123456789abcdef",
        issuance_id="iss_0123456789abcdef0123456789abcdef",
        generation_id="gen_0123456789abcdef0123456789abcdef",
        artifact_id="art_0123456789abcdef0123456789abcdef",
        class_id="english10_p2",
        assignment_id="literary_analysis",
        student_id="00107",
        logical_page=1,
        total_pages=2,
        page_role="response_start",
        source_scan_id=f"scan_{retained.stem}",
        source_filename="original.pdf",
        source_page_number=1,
        retained_source_path=retained,
        retained_source_relative_path=f"scans/source/2026-07-20/{retained_filename}",
        source_sha256="a" * 64,
        intake_timestamp=timestamp,
        intake_date=date(2026, 7, 20),
    )


def test_valid_result_is_frozen_and_continuation_is_derived() -> None:
    result = valid_result()
    assert validate_quillan_response_page_dispatch_result(result) is result
    assert not result.is_continuation
    continuation = replace(result, logical_page=2, page_role="continuation")
    assert validate_quillan_response_page_dispatch_result(continuation).is_continuation
    with pytest.raises(FrozenInstanceError):
        result.page_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "result",
    [
        object(),
        replace(valid_result(), logical_page=True),
        replace(valid_result(), page_role="continuation"),
        replace(valid_result(), source_sha256="A" * 64),
        replace(valid_result(), intake_timestamp=datetime(2026, 7, 20)),
        replace(valid_result(), intake_date=datetime(2026, 7, 20)),
    ],
)
def test_invalid_result_uses_typed_failure(result: object) -> None:
    with pytest.raises(QuillanDispatchResultError):
        validate_quillan_response_page_dispatch_result(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route_id", "bad"),
        ("page_id", "bad"),
        ("issuance_id", "bad"),
        ("generation_id", "bad"),
        ("artifact_id", "bad"),
        ("class_id", "../bad"),
        ("assignment_id", "../bad"),
        ("student_id", "../bad"),
        ("logical_page", False),
        ("logical_page", 0),
        ("logical_page", -1),
        ("logical_page", 3),
        ("total_pages", True),
        ("total_pages", 0),
        ("total_pages", -1),
        ("page_role", "continuation"),
        ("source_scan_id", "arbitrary_safe_id"),
        ("source_filename", "../original.pdf"),
        ("source_filename", "original.exe"),
        ("source_page_number", True),
        ("source_page_number", 0),
        ("source_page_number", -1),
        ("retained_source_relative_path", "/scans/source/2026-07-20/file.pdf"),
        ("retained_source_relative_path", r"scans\source\2026-07-20\file.pdf"),
        ("retained_source_relative_path", "scans/source/../file.pdf"),
        ("retained_source_path", "not-a-path"),
        ("retained_source_path", Path("relative.pdf")),
        ("source_sha256", "A" * 64),
        ("source_sha256", "a" * 63),
        ("intake_timestamp", datetime(2026, 7, 20)),
        ("intake_date", datetime(2026, 7, 20, tzinfo=timezone.utc)),
        ("intake_date", date(2026, 7, 21)),
    ],
)
def test_every_result_field_boundary(field: str, value: object) -> None:
    result = copy.copy(valid_result())
    object.__setattr__(result, field, value)
    with pytest.raises(QuillanDispatchResultError):
        validate_quillan_response_page_dispatch_result(result)


def test_result_rejects_core_filename_and_extension_contradictions() -> None:
    result = valid_result()
    arbitrary = replace(
        result,
        retained_source_path=result.retained_source_path.with_name("arbitrary.pdf"),
        retained_source_relative_path=(
            "scans/source/2026-07-20/arbitrary.pdf"
        ),
        source_scan_id="scan_arbitrary",
    )
    mismatch = replace(
        result,
        source_filename="original.png",
    )
    scan_mismatch = replace(result, source_scan_id="scan_arbitrary")
    bucket_mismatch = replace(
        result,
        retained_source_relative_path=result.retained_source_relative_path.replace(
            "2026-07-20", "2026-07-21"
        ),
    )
    for invalid in (arbitrary, mismatch, scan_mismatch, bucket_mismatch):
        with pytest.raises(QuillanDispatchResultError):
            validate_quillan_response_page_dispatch_result(invalid)


def test_result_model_is_slotted() -> None:
    assert "__dict__" not in dir(valid_result())


@pytest.mark.parametrize("control", ["\n", "\r", "\t", "\x00", "\u2028", "\u2029"])
def test_result_source_filename_rejects_control_and_line_separators(
    control: str,
) -> None:
    with pytest.raises(QuillanDispatchResultError):
        validate_quillan_response_page_dispatch_result(
            replace(valid_result(), source_filename=f"original{control}.pdf")
        )
