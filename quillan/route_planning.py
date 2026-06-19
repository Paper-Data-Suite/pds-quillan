"""Pure route planning for already-decoded Quillan response pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pds_core.classes import load_class_roster
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.rosters import RosterError, student_lookup
from pds_core.routes import class_dir, class_roster_path
from pds_core.scan_failure_metadata import is_routing_failure_category

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.storage import (
    assignment_config_path,
    assignment_scans_dir,
    student_submission_dir,
)


@dataclass(frozen=True, slots=True)
class DecodedResponsePage:
    """Identity fields obtained from an already-decoded response-page payload."""

    module: str | None
    document_type: str | None
    class_id: str | None
    assignment_id: str | None
    student_id: str | None
    page_number: int | None
    raw_payload: str | None = None


@dataclass(frozen=True, slots=True)
class RoutePlan:
    """Validated paths and identity for a future response-page route."""

    class_id: str
    assignment_id: str
    student_id: str
    page_number: int | None
    assignment_config_path: Path
    roster_path: Path
    routed_evidence_dir: Path
    student_submission_dir: Path


@dataclass(frozen=True, slots=True)
class RouteFailure:
    """Structured explanation of why a decoded page cannot be routed."""

    failure_category: str
    failure_message: str
    module: str | None
    class_id: str | None
    assignment_id: str | None
    student_id: str | None
    page_number: int | None
    raw_payload: str | None
    module_details: dict[str, object]


def plan_decoded_response_page_route(
    workspace_root: str | Path,
    decoded_page: DecodedResponsePage,
) -> RoutePlan | RouteFailure:
    """Plan a route for decoded Quillan response data without writing files."""
    if decoded_page.module != "quillan":
        return _failure(
            decoded_page,
            "module_unsupported",
            "Decoded page is not for the Quillan module.",
            reason="module_unsupported",
            expected_module="quillan",
        )

    if decoded_page.document_type != "response":
        return _failure(
            decoded_page,
            "payload_invalid",
            "Decoded page is not a Quillan response page.",
            reason="document_type_invalid",
            field="document_type",
            expected_document_type="response",
        )

    for field_name in ("class_id", "assignment_id", "student_id"):
        value = getattr(decoded_page, field_name)
        if value is None:
            return _failure(
                decoded_page,
                "payload_invalid",
                f"Decoded response page is missing {field_name}.",
                reason="field_missing",
                field=field_name,
            )
        try:
            validate_identifier(value, field_name)
        except IdentifierValidationError as error:
            return _failure(
                decoded_page,
                "identifier_invalid",
                str(error),
                reason="identifier_invalid",
                field=field_name,
            )

    if decoded_page.page_number is not None and (
        isinstance(decoded_page.page_number, bool)
        or not isinstance(decoded_page.page_number, int)
        or decoded_page.page_number < 1
    ):
        return _failure(
            decoded_page,
            "payload_invalid",
            "page_number must be a positive integer when present.",
            reason="page_number_invalid",
            field="page_number",
        )

    class_id = cast(str, decoded_page.class_id)
    assignment_id = cast(str, decoded_page.assignment_id)
    student_id = cast(str, decoded_page.student_id)
    root = Path(workspace_root)
    resolved_class_dir = class_dir(root, class_id)

    try:
        class_exists = resolved_class_dir.is_dir()
    except OSError as error:
        return _failure(
            decoded_page,
            "processing_error",
            f"Could not inspect class directory: {error}",
            reason="class_check_failed",
        )
    if not class_exists:
        return _failure(
            decoded_page,
            "class_unknown",
            f"Class is not present in the workspace: {class_id}",
            reason="class_unknown",
        )

    roster_path = class_roster_path(root, class_id)
    try:
        roster_exists = roster_path.is_file()
    except OSError as error:
        return _failure(
            decoded_page,
            "processing_error",
            f"Could not inspect class roster: {error}",
            reason="roster_check_failed",
        )
    if not roster_exists:
        return _failure(
            decoded_page,
            "processing_error",
            f"Class roster is missing: {roster_path}",
            reason="roster_missing",
        )

    try:
        roster = load_class_roster(root, class_id)
    except RosterError as error:
        return _failure(
            decoded_page,
            "processing_error",
            f"Class roster is invalid or unreadable: {error}",
            reason="roster_invalid",
        )

    resolved_assignment_config_path = assignment_config_path(
        root,
        class_id,
        assignment_id,
    )
    try:
        assignment_exists = resolved_assignment_config_path.is_file()
    except OSError as error:
        return _failure(
            decoded_page,
            "processing_error",
            f"Could not inspect assignment config: {error}",
            reason="assignment_check_failed",
        )
    if not assignment_exists:
        return _failure(
            decoded_page,
            "assignment_unknown",
            f"Assignment is not present for class {class_id}: {assignment_id}",
            reason="assignment_unknown",
        )

    try:
        assignment = load_assignment_config(resolved_assignment_config_path)
    except (AssignmentConfigError, OSError, UnicodeError) as error:
        return _failure(
            decoded_page,
            "processing_error",
            f"Assignment config is invalid or unreadable: {error}",
            reason="assignment_config_invalid",
        )

    configured_assignment_id = cast(str, assignment["assignment_id"])
    if configured_assignment_id != assignment_id:
        return _failure(
            decoded_page,
            "route_mismatch",
            "Assignment config ID does not match the decoded assignment ID.",
            reason="assignment_id_mismatch",
            configured_assignment_id=configured_assignment_id,
        )

    configured_class_ids = cast(list[str], assignment["class_ids"])
    if class_id not in configured_class_ids:
        return _failure(
            decoded_page,
            "route_mismatch",
            "Assignment config does not include the decoded class ID.",
            reason="assignment_class_mismatch",
            configured_class_ids=list(configured_class_ids),
        )

    if student_id not in student_lookup(roster):
        return _failure(
            decoded_page,
            "student_unknown",
            f"Student is not present in the class roster: {student_id}",
            reason="student_unknown",
        )

    return RoutePlan(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        page_number=decoded_page.page_number,
        assignment_config_path=resolved_assignment_config_path,
        roster_path=roster_path,
        routed_evidence_dir=assignment_scans_dir(root, class_id, assignment_id),
        student_submission_dir=student_submission_dir(
            root,
            class_id,
            assignment_id,
            student_id,
        ),
    )


def _failure(
    decoded_page: DecodedResponsePage,
    category: str,
    message: str,
    **module_details: object,
) -> RouteFailure:
    if not is_routing_failure_category(category):
        raise ValueError(f"Unsupported routing failure category: {category}")
    return RouteFailure(
        failure_category=category,
        failure_message=message,
        module=decoded_page.module,
        class_id=decoded_page.class_id,
        assignment_id=decoded_page.assignment_id,
        student_id=decoded_page.student_id,
        page_number=decoded_page.page_number,
        raw_payload=decoded_page.raw_payload,
        module_details=dict(module_details),
    )
