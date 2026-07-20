"""Typed runtime result for one dispatched Quillan response page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pds_core.identifiers import validate_identifier

from quillan.module_errors import QuillanDispatchResultError
from quillan.printable_response_records import (
    page_role_for_logical_page,
    validate_artifact_id,
    validate_generation_id,
    validate_issuance_id,
    validate_page_id,
)
from quillan.printable_response_routes import validate_route_id
from quillan.retained_source_provenance import (
    validate_core_retention_event_consistency,
)


@dataclass(frozen=True, slots=True)
class QuillanResponsePageDispatchResult:
    route_id: str
    page_id: str
    issuance_id: str
    generation_id: str
    artifact_id: str
    class_id: str
    assignment_id: str
    student_id: str
    logical_page: int
    total_pages: int
    page_role: str
    source_scan_id: str
    source_filename: str
    source_page_number: int
    retained_source_path: Path
    retained_source_relative_path: str
    source_sha256: str
    intake_timestamp: datetime
    intake_date: date

    @property
    def is_continuation(self) -> bool:
        return self.page_role == "continuation"


def validate_quillan_response_page_dispatch_result(
    result: object,
) -> QuillanResponsePageDispatchResult:
    """Revalidate and return one exact Quillan dispatch result."""
    try:
        if not isinstance(result, QuillanResponsePageDispatchResult):
            raise ValueError(
                "result must be a QuillanResponsePageDispatchResult."
            )
        validate_route_id(result.route_id)
        validate_page_id(result.page_id)
        validate_issuance_id(result.issuance_id)
        validate_generation_id(result.generation_id)
        validate_artifact_id(result.artifact_id)
        validate_identifier(result.class_id, "class_id")
        validate_identifier(result.assignment_id, "assignment_id")
        validate_identifier(result.student_id, "student_id")
        logical_page = _positive_integer(result.logical_page, "logical_page")
        total_pages = _positive_integer(result.total_pages, "total_pages")
        if logical_page > total_pages:
            raise ValueError("logical_page must not exceed total_pages.")
        if result.page_role != page_role_for_logical_page(logical_page):
            raise ValueError("page_role contradicts logical_page.")
        _positive_integer(result.source_page_number, "source_page_number")
        validate_core_retention_event_consistency(
            source_scan_id=result.source_scan_id,
            source_filename=result.source_filename,
            source_sha256=result.source_sha256,
            retained_source_path=result.retained_source_path,
            retained_source_relative_path=result.retained_source_relative_path,
            intake_timestamp=result.intake_timestamp,
            intake_date=result.intake_date,
        )
        return result
    except QuillanDispatchResultError:
        raise
    except (ValueError, TypeError, AttributeError, IndexError) as error:
        raise QuillanDispatchResultError(
            f"Invalid Quillan response-page dispatch result: {error}"
        ) from error


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


__all__ = [
    "QuillanResponsePageDispatchResult",
    "validate_quillan_response_page_dispatch_result",
]
