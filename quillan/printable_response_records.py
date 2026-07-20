"""Immutable Quillan v1 printable-response identity and record models."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import secrets
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.rosters import (
    ROSTER_REQUIRED_COLUMNS,
    RosterValidationError,
    StudentRecord,
    student_display_name,
    validate_roster_rows,
)
from pds_core.routing_models import ModuleRecordRef

from quillan.assignments import ASSIGNMENT_SCHEMA_VERSION, validate_assignment_config
from quillan.pds_contract import (
    QUILLAN_MODULE_ID,
    RESPONSE_PAGE_CONTRACT_VERSION,
    RESPONSE_PAGE_RECORD_KIND,
)

PRINTABLE_RESPONSE_ISSUANCE_SCHEMA_VERSION: Final[str] = "1"
PRINTABLE_RESPONSE_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(
    {"class_packet_pdf", "individual_pdf"}
)
PRINTABLE_RESPONSE_GENERATION_REASONS: Final[frozenset[str]] = frozenset(
    {"initial", "additional_copy", "regeneration"}
)
PRINTABLE_RESPONSE_PAGE_ROLES: Final[frozenset[str]] = frozenset(
    {"response_start", "continuation"}
)
PRINTABLE_RESPONSE_LIFECYCLE_STATUSES: Final[frozenset[str]] = frozenset(
    {"prepared", "issued", "cancelled", "superseded", "invalidated"}
)
_TERMINAL_STATUSES = frozenset({"cancelled", "superseded", "invalidated"})
_ALLOWED_TRANSITIONS = frozenset(
    {
        ("prepared", "issued"),
        ("prepared", "cancelled"),
        ("prepared", "invalidated"),
        ("issued", "superseded"),
        ("issued", "invalidated"),
    }
)
_ID_PATTERN = re.compile(r"^(?P<prefix>gen|art|iss|pg)_[0-9a-f]{32}$")


class PrintableResponseRecordValidationError(ValueError):
    """Raised when an immutable printable-response record is invalid."""


def _validate_typed_id(value: object, prefix: str, field: str) -> str:
    if not isinstance(value, str):
        raise PrintableResponseRecordValidationError(f"{field} must be a string.")
    if _ID_PATTERN.fullmatch(value) is None or not value.startswith(f"{prefix}_"):
        raise PrintableResponseRecordValidationError(
            f"{field} must be {prefix}_ followed by 32 lowercase hexadecimal characters."
        )
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise PrintableResponseRecordValidationError(str(error)) from error
    return value


def validate_generation_id(value: object) -> str:
    return _validate_typed_id(value, "gen", "generation_id")


def validate_artifact_id(value: object) -> str:
    return _validate_typed_id(value, "art", "artifact_id")


def validate_issuance_id(value: object) -> str:
    return _validate_typed_id(value, "iss", "issuance_id")


def validate_page_id(value: object) -> str:
    return _validate_typed_id(value, "pg", "page_id")


def _generate_id(prefix: str, token_hex: Callable[[int], str]) -> str:
    value = f"{prefix}_{token_hex(16)}"
    return _validate_typed_id(value, prefix, f"{prefix}_id")


def generate_generation_id(
    token_hex: Callable[[int], str] = secrets.token_hex,
) -> str:
    return _generate_id("gen", token_hex)


def generate_artifact_id(token_hex: Callable[[int], str] = secrets.token_hex) -> str:
    return _generate_id("art", token_hex)


def generate_issuance_id(token_hex: Callable[[int], str] = secrets.token_hex) -> str:
    return _generate_id("iss", token_hex)


def generate_page_id(token_hex: Callable[[int], str] = secrets.token_hex) -> str:
    return _generate_id("pg", token_hex)


def _exact_mapping(value: object, keys: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PrintableResponseRecordValidationError(f"{name} must be an object.")
    actual_keys = tuple(value)
    non_string_keys = tuple(key for key in actual_keys if not isinstance(key, str))
    if non_string_keys:
        raise PrintableResponseRecordValidationError(
            f"Invalid {name}: object keys must be strings."
        )
    actual = set(cast(tuple[str, ...], actual_keys))
    missing = sorted(keys - actual)
    unknown = sorted(actual - keys)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise PrintableResponseRecordValidationError(f"Invalid {name}: {'; '.join(details)}.")
    return cast(Mapping[str, Any], value)


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrintableResponseRecordValidationError(
            f"{field} must be a nonempty string."
        )
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise PrintableResponseRecordValidationError(f"{field} must be a string.")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise PrintableResponseRecordValidationError(f"{field} must be a string.")
    try:
        return validate_identifier(value, field)
    except (IdentifierValidationError, TypeError) as error:
        raise PrintableResponseRecordValidationError(str(error)) from error


def _positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PrintableResponseRecordValidationError(
            f"{field} must be a positive integer."
        )
    return value


def _timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise PrintableResponseRecordValidationError(
            f"{field} must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PrintableResponseRecordValidationError(
            f"{field} must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PrintableResponseRecordValidationError(
            f"{field} must be a timezone-aware ISO 8601 string."
        )
    return value


def _timestamp_value(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True, slots=True)
class PrintableResponseGenerationContext:
    output_kind: str
    reason: str
    predecessor_issuance_id: str | None

    def __post_init__(self) -> None:
        _string(self.output_kind, "generation_context.output_kind")
        _string(self.reason, "generation_context.reason")
        if self.output_kind not in PRINTABLE_RESPONSE_OUTPUT_KINDS:
            raise PrintableResponseRecordValidationError("Unsupported output_kind.")
        if self.reason not in PRINTABLE_RESPONSE_GENERATION_REASONS:
            raise PrintableResponseRecordValidationError("Unsupported generation reason.")
        if self.reason == "regeneration":
            validate_issuance_id(self.predecessor_issuance_id)
        elif self.predecessor_issuance_id is not None:
            raise PrintableResponseRecordValidationError(
                f"{self.reason} requires predecessor_issuance_id to be null."
            )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "output_kind": self.output_kind,
            "reason": self.reason,
            "predecessor_issuance_id": self.predecessor_issuance_id,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponseGenerationContext:
        data = _exact_mapping(
            value,
            frozenset({"output_kind", "reason", "predecessor_issuance_id"}),
            "generation_context",
        )
        return cls(data["output_kind"], data["reason"], data["predecessor_issuance_id"])


@dataclass(frozen=True, slots=True)
class PrintableResponseAssignmentSnapshot:
    schema_version: str
    title: str
    updated_at: str

    def __post_init__(self) -> None:
        _string(self.schema_version, "assignment_snapshot.schema_version")
        if self.schema_version != ASSIGNMENT_SCHEMA_VERSION:
            raise PrintableResponseRecordValidationError(
                f"assignment_snapshot.schema_version must be {ASSIGNMENT_SCHEMA_VERSION!r}."
            )
        _nonempty_string(self.title, "assignment_snapshot.title")
        _timestamp(self.updated_at, "assignment_snapshot.updated_at")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponseAssignmentSnapshot:
        data = _exact_mapping(
            value,
            frozenset({"schema_version", "title", "updated_at"}),
            "assignment_snapshot",
        )
        return cls(data["schema_version"], data["title"], data["updated_at"])


@dataclass(frozen=True, slots=True)
class PrintableResponseStudentSnapshot:
    display_name: str
    last_name: str
    first_name: str
    period: str

    def __post_init__(self) -> None:
        _normalized_roster_string(
            self.display_name, "student_snapshot.display_name"
        )
        _normalized_roster_string(self.last_name, "student_snapshot.last_name")
        _normalized_roster_string(self.first_name, "student_snapshot.first_name")
        _normalized_roster_string(self.period, "student_snapshot.period")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "last_name": self.last_name,
            "first_name": self.first_name,
            "period": self.period,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponseStudentSnapshot:
        data = _exact_mapping(
            value,
            frozenset({"display_name", "last_name", "first_name", "period"}),
            "student_snapshot",
        )
        return cls(
            data["display_name"], data["last_name"], data["first_name"], data["period"]
        )


@dataclass(frozen=True, slots=True)
class PrintableResponseLifecycle:
    status: str
    revision: int
    created_at: str
    updated_at: str
    issued_at: str | None
    ended_at: str | None
    reason: str | None
    replacement_issuance_id: str | None

    def __post_init__(self) -> None:
        _string(self.status, "lifecycle.status")
        if self.status not in PRINTABLE_RESPONSE_LIFECYCLE_STATUSES:
            raise PrintableResponseRecordValidationError("Unsupported lifecycle status.")
        _positive_integer(self.revision, "lifecycle.revision")
        _timestamp(self.created_at, "lifecycle.created_at")
        _timestamp(self.updated_at, "lifecycle.updated_at")
        if _timestamp_value(self.updated_at) < _timestamp_value(self.created_at):
            raise PrintableResponseRecordValidationError(
                "lifecycle.updated_at must not precede created_at."
            )
        if self.issued_at is not None:
            _timestamp(self.issued_at, "lifecycle.issued_at")
            if _timestamp_value(self.issued_at) < _timestamp_value(self.created_at):
                raise PrintableResponseRecordValidationError(
                    "lifecycle.issued_at must not precede created_at."
                )
            if _timestamp_value(self.issued_at) > _timestamp_value(self.updated_at):
                raise PrintableResponseRecordValidationError(
                    "lifecycle.issued_at must not follow updated_at."
                )
        if self.status == "prepared" and self.revision != 1:
            raise PrintableResponseRecordValidationError(
                "A prepared lifecycle must have revision 1."
            )
        if self.status == "prepared":
            if self.created_at != self.updated_at or self.issued_at is not None:
                raise PrintableResponseRecordValidationError(
                    "A prepared lifecycle requires equal creation/update times and no issued_at."
                )
        if self.status == "issued" and self.revision != 2:
            raise PrintableResponseRecordValidationError(
                "An issued lifecycle must have revision 2."
            )
        if self.status == "issued" and self.issued_at is None:
            raise PrintableResponseRecordValidationError("issued_at is required for issued.")
        if self.status in {"prepared", "issued"}:
            if self.ended_at is not None or self.reason is not None:
                raise PrintableResponseRecordValidationError(
                    "Active lifecycle statuses cannot have ended_at or reason."
                )
        else:
            if self.ended_at is None:
                raise PrintableResponseRecordValidationError(
                    "ended_at is required for terminal lifecycle statuses."
                )
            _timestamp(self.ended_at, "lifecycle.ended_at")
            if _timestamp_value(self.ended_at) < _timestamp_value(self.updated_at):
                raise PrintableResponseRecordValidationError(
                    "lifecycle.ended_at must not precede updated_at."
                )
            _nonempty_string(self.reason, "lifecycle.reason")
            if self.ended_at != self.updated_at:
                raise PrintableResponseRecordValidationError(
                    "Terminal lifecycle ended_at must equal updated_at."
                )
        if self.status == "cancelled" and self.issued_at is not None:
            raise PrintableResponseRecordValidationError(
                "A cancelled issuance cannot have issued_at."
            )
        if self.status == "cancelled" and self.revision != 2:
            raise PrintableResponseRecordValidationError(
                "A cancelled lifecycle must have revision 2."
            )
        if self.status == "superseded":
            if self.revision != 3:
                raise PrintableResponseRecordValidationError(
                    "A superseded lifecycle must have revision 3."
                )
            validate_issuance_id(self.replacement_issuance_id)
            if self.issued_at is None:
                raise PrintableResponseRecordValidationError(
                    "A superseded issuance must retain issued_at."
                )
        elif self.replacement_issuance_id is not None:
            raise PrintableResponseRecordValidationError(
                "replacement_issuance_id is allowed only for superseded."
            )
        if self.status == "invalidated":
            expected_revision = 3 if self.issued_at is not None else 2
            if self.revision != expected_revision:
                raise PrintableResponseRecordValidationError(
                    "An invalidated lifecycle revision must reflect whether it was issued."
                )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "issued_at": self.issued_at,
            "ended_at": self.ended_at,
            "reason": self.reason,
            "replacement_issuance_id": self.replacement_issuance_id,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponseLifecycle:
        data = _exact_mapping(
            value,
            frozenset(
                {
                    "status", "revision", "created_at", "updated_at", "issued_at",
                    "ended_at", "reason", "replacement_issuance_id",
                }
            ),
            "lifecycle",
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PrintableResponseIssuance:
    schema_version: str
    issuance_id: str
    generation_id: str
    artifact_id: str
    class_id: str
    assignment_id: str
    student_id: str
    generation_context: PrintableResponseGenerationContext
    class_label: str
    assignment_snapshot: PrintableResponseAssignmentSnapshot
    student_snapshot: PrintableResponseStudentSnapshot
    page_count: int
    page_ids: tuple[str, ...]
    lifecycle: PrintableResponseLifecycle

    def __post_init__(self) -> None:
        _string(self.schema_version, "schema_version")
        if self.schema_version != PRINTABLE_RESPONSE_ISSUANCE_SCHEMA_VERSION:
            raise PrintableResponseRecordValidationError("Unsupported issuance schema_version.")
        validate_issuance_id(self.issuance_id)
        validate_generation_id(self.generation_id)
        validate_artifact_id(self.artifact_id)
        _identifier(self.class_id, "class_id")
        _identifier(self.assignment_id, "assignment_id")
        _identifier(self.student_id, "student_id")
        if not isinstance(self.generation_context, PrintableResponseGenerationContext):
            raise PrintableResponseRecordValidationError("Invalid generation_context.")
        _nonempty_string(self.class_label, "class_label")
        if not isinstance(self.assignment_snapshot, PrintableResponseAssignmentSnapshot):
            raise PrintableResponseRecordValidationError("Invalid assignment_snapshot.")
        if not isinstance(self.student_snapshot, PrintableResponseStudentSnapshot):
            raise PrintableResponseRecordValidationError("Invalid student_snapshot.")
        if not isinstance(self.lifecycle, PrintableResponseLifecycle):
            raise PrintableResponseRecordValidationError("Invalid lifecycle.")
        _positive_integer(self.page_count, "page_count")
        if not isinstance(self.page_ids, tuple):
            raise PrintableResponseRecordValidationError("page_ids must be a tuple.")
        for page_id in self.page_ids:
            validate_page_id(page_id)
        if len(self.page_ids) != self.page_count or len(set(self.page_ids)) != len(self.page_ids):
            raise PrintableResponseRecordValidationError(
                "page_ids must be unique and have exactly page_count members."
            )
        if self.generation_context.predecessor_issuance_id == self.issuance_id:
            raise PrintableResponseRecordValidationError("An issuance cannot name itself as predecessor.")
        if self.lifecycle.replacement_issuance_id == self.issuance_id:
            raise PrintableResponseRecordValidationError("An issuance cannot replace itself.")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "issuance_id": self.issuance_id,
            "generation_id": self.generation_id,
            "artifact_id": self.artifact_id,
            "class_id": self.class_id,
            "assignment_id": self.assignment_id,
            "student_id": self.student_id,
            "generation_context": self.generation_context.to_mapping(),
            "class_label": self.class_label,
            "assignment_snapshot": self.assignment_snapshot.to_mapping(),
            "student_snapshot": self.student_snapshot.to_mapping(),
            "page_count": self.page_count,
            "page_ids": list(self.page_ids),
            "lifecycle": self.lifecycle.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponseIssuance:
        keys = frozenset(
            {
                "schema_version", "issuance_id", "generation_id", "artifact_id",
                "class_id", "assignment_id", "student_id", "generation_context",
                "class_label", "assignment_snapshot", "student_snapshot", "page_count",
                "page_ids", "lifecycle",
            }
        )
        data = _exact_mapping(value, keys, "printable response issuance")
        page_ids = data["page_ids"]
        if not isinstance(page_ids, list):
            raise PrintableResponseRecordValidationError("page_ids must be an array.")
        return cls(
            schema_version=data["schema_version"],
            issuance_id=data["issuance_id"],
            generation_id=data["generation_id"],
            artifact_id=data["artifact_id"],
            class_id=data["class_id"],
            assignment_id=data["assignment_id"],
            student_id=data["student_id"],
            generation_context=PrintableResponseGenerationContext.from_mapping(data["generation_context"]),
            class_label=data["class_label"],
            assignment_snapshot=PrintableResponseAssignmentSnapshot.from_mapping(data["assignment_snapshot"]),
            student_snapshot=PrintableResponseStudentSnapshot.from_mapping(data["student_snapshot"]),
            page_count=data["page_count"],
            page_ids=tuple(page_ids),
            lifecycle=PrintableResponseLifecycle.from_mapping(data["lifecycle"]),
        )


@dataclass(frozen=True, slots=True)
class PrintableResponsePage:
    schema_version: str
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
    created_at: str

    def __post_init__(self) -> None:
        _string(self.schema_version, "schema_version")
        if self.schema_version != RESPONSE_PAGE_CONTRACT_VERSION:
            raise PrintableResponseRecordValidationError("Unsupported page schema_version.")
        validate_page_id(self.page_id)
        validate_issuance_id(self.issuance_id)
        validate_generation_id(self.generation_id)
        validate_artifact_id(self.artifact_id)
        _identifier(self.class_id, "class_id")
        _identifier(self.assignment_id, "assignment_id")
        _identifier(self.student_id, "student_id")
        _positive_integer(self.logical_page, "logical_page")
        _positive_integer(self.total_pages, "total_pages")
        if self.logical_page > self.total_pages:
            raise PrintableResponseRecordValidationError("logical_page exceeds total_pages.")
        _string(self.page_role, "page_role")
        expected_role = page_role_for_logical_page(self.logical_page)
        if self.page_role != expected_role:
            raise PrintableResponseRecordValidationError(
                f"logical_page {self.logical_page} requires page_role {expected_role!r}."
            )
        _timestamp(self.created_at, "created_at")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "page_id": self.page_id,
            "issuance_id": self.issuance_id,
            "generation_id": self.generation_id,
            "artifact_id": self.artifact_id,
            "class_id": self.class_id,
            "assignment_id": self.assignment_id,
            "student_id": self.student_id,
            "logical_page": self.logical_page,
            "total_pages": self.total_pages,
            "page_role": self.page_role,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintableResponsePage:
        keys = frozenset(
            {
                "schema_version", "page_id", "issuance_id", "generation_id",
                "artifact_id", "class_id", "assignment_id", "student_id",
                "logical_page", "total_pages", "page_role", "created_at",
            }
        )
        return cls(**_exact_mapping(value, keys, "printable response page"))


@dataclass(frozen=True, slots=True)
class PrintableResponseRecordSet:
    issuance: PrintableResponseIssuance
    pages: tuple[PrintableResponsePage, ...]

    def __post_init__(self) -> None:
        validate_printable_response_record_set(self)


@dataclass(frozen=True, slots=True)
class PrintableResponsePageContext:
    page: PrintableResponsePage
    issuance: PrintableResponseIssuance
    member_pages: tuple[PrintableResponsePage, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.page, PrintableResponsePage):
            raise PrintableResponseRecordValidationError("Context page is invalid.")
        if not isinstance(self.issuance, PrintableResponseIssuance):
            raise PrintableResponseRecordValidationError("Context issuance is invalid.")
        if not isinstance(self.member_pages, tuple):
            raise PrintableResponseRecordValidationError(
                "Context member_pages must be a tuple."
            )
        record_set = PrintableResponseRecordSet(self.issuance, self.member_pages)
        matches = tuple(
            member for member in record_set.pages if member.page_id == self.page.page_id
        )
        if len(matches) != 1 or matches[0] != self.page:
            raise PrintableResponseRecordValidationError(
                "Context page must occur exactly once in its complete record set."
            )

    @property
    def student_id(self) -> str:
        return self.page.student_id

    @property
    def logical_page(self) -> int:
        return self.page.logical_page

    @property
    def total_pages(self) -> int:
        return self.page.total_pages

    @property
    def page_role(self) -> str:
        return self.page.page_role

    @property
    def is_continuation(self) -> bool:
        return self.page.page_role == "continuation"


def page_role_for_logical_page(logical_page: int) -> str:
    _positive_integer(logical_page, "logical_page")
    return "response_start" if logical_page == 1 else "continuation"


def validate_printable_response_record_set(
    record_set: object,
) -> None:
    if not isinstance(record_set, PrintableResponseRecordSet):
        raise PrintableResponseRecordValidationError(
            "record_set must be a PrintableResponseRecordSet."
        )
    if not isinstance(record_set.issuance, PrintableResponseIssuance):
        raise PrintableResponseRecordValidationError("record_set.issuance is invalid.")
    if not isinstance(record_set.pages, tuple):
        raise PrintableResponseRecordValidationError("record_set.pages must be a tuple.")
    issuance = record_set.issuance
    if len(record_set.pages) != issuance.page_count:
        raise PrintableResponseRecordValidationError("Record-set page count is incomplete.")
    for expected_number, (expected_id, page) in enumerate(
        zip(issuance.page_ids, record_set.pages, strict=True), start=1
    ):
        if not isinstance(page, PrintableResponsePage):
            raise PrintableResponseRecordValidationError("record_set contains an invalid page.")
        if page.page_id != expected_id or page.logical_page != expected_number:
            raise PrintableResponseRecordValidationError("Page membership is reordered or incomplete.")
        if page.total_pages != issuance.page_count:
            raise PrintableResponseRecordValidationError("Page total does not match issuance page_count.")
        page_context = (
            page.issuance_id, page.generation_id, page.artifact_id, page.class_id,
            page.assignment_id, page.student_id,
        )
        issuance_context = (
            issuance.issuance_id, issuance.generation_id, issuance.artifact_id,
            issuance.class_id, issuance.assignment_id, issuance.student_id,
        )
        if page_context != issuance_context:
            raise PrintableResponseRecordValidationError("Page provenance contradicts its issuance.")
        if page.created_at != issuance.lifecycle.created_at:
            raise PrintableResponseRecordValidationError("All member pages must share issuance created_at.")


def _clock_iso(clock: Callable[[], datetime | str] | None) -> str:
    value: datetime | str = (
        datetime.now(timezone.utc) if clock is None else clock()
    )
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PrintableResponseRecordValidationError("clock must return an aware datetime.")
        value = value.isoformat()
    return _timestamp(value, "clock")


def _normalized_roster_string(value: object, field: str) -> str:
    text = _nonempty_string(value, field)
    if text != text.strip():
        raise PrintableResponseRecordValidationError(
            f"{field} must not have surrounding whitespace."
        )
    return text


def _validate_student(student: object, class_id: str) -> StudentRecord:
    if not isinstance(student, StudentRecord):
        raise PrintableResponseRecordValidationError("student must be a StudentRecord.")
    row = {
        "class_id": student.class_id,
        "student_id": student.student_id,
        "last_name": student.last_name,
        "first_name": student.first_name,
        "period": student.period,
    }
    try:
        validated = validate_roster_rows(ROSTER_REQUIRED_COLUMNS, (row,)).students[0]
    except RosterValidationError as error:
        raise PrintableResponseRecordValidationError(
            f"student does not satisfy the roster contract: {error}"
        ) from error
    validated_required = (
        validated.class_id,
        validated.student_id,
        validated.last_name,
        validated.first_name,
        validated.period,
    )
    supplied_required = (
        student.class_id,
        student.student_id,
        student.last_name,
        student.first_name,
        student.period,
    )
    if validated_required != supplied_required:
        raise PrintableResponseRecordValidationError(
            "student fields must already be normalized by the roster contract."
        )
    if validated.class_id != class_id:
        raise PrintableResponseRecordValidationError(
            "Student class_id does not match class_id."
        )
    return student


def build_printable_response_record_set(
    class_id: str,
    assignment: Mapping[str, Any],
    student: StudentRecord,
    *,
    generation_id: str,
    artifact_id: str,
    output_kind: str,
    reason: str,
    pages_per_student: int,
    class_label: str | None = None,
    predecessor_issuance_id: str | None = None,
    issuance_id: str | None = None,
    page_ids: Sequence[str] | None = None,
    issuance_id_generator: Callable[[], str] = generate_issuance_id,
    page_id_generator: Callable[[], str] = generate_page_id,
    clock: Callable[[], datetime | str] | None = None,
) -> PrintableResponseRecordSet:
    """Purely plan one student-specific issuance and all physical pages."""
    class_id = _identifier(class_id, "class_id")
    if not isinstance(assignment, dict):
        assignment = dict(assignment)
    try:
        validate_assignment_config(assignment)
    except ValueError as error:
        raise PrintableResponseRecordValidationError(str(error)) from error
    if class_id not in assignment["class_ids"]:
        raise PrintableResponseRecordValidationError("Assignment does not belong to class_id.")
    student = _validate_student(student, class_id)
    pages_per_student = _positive_integer(pages_per_student, "pages_per_student")
    issuance_id = validate_issuance_id(
        issuance_id_generator() if issuance_id is None else issuance_id
    )
    generated_page_ids = (
        tuple(page_id_generator() for _ in range(pages_per_student))
        if page_ids is None
        else tuple(page_ids)
    )
    if len(generated_page_ids) != pages_per_student:
        raise PrintableResponseRecordValidationError("page_ids length must equal pages_per_student.")
    for page_id in generated_page_ids:
        validate_page_id(page_id)
    if len(set(generated_page_ids)) != len(generated_page_ids):
        raise PrintableResponseRecordValidationError("page_ids must be unique.")
    generation_id = validate_generation_id(generation_id)
    artifact_id = validate_artifact_id(artifact_id)
    timestamp = _clock_iso(clock)
    context = PrintableResponseGenerationContext(output_kind, reason, predecessor_issuance_id)
    lifecycle = PrintableResponseLifecycle(
        "prepared", 1, timestamp, timestamp, None, None, None, None
    )
    assignment_snapshot = PrintableResponseAssignmentSnapshot(
        cast(str, assignment["schema_version"]),
        cast(str, assignment["title"]),
        cast(str, assignment["updated_at"]),
    )
    snapshot = PrintableResponseStudentSnapshot(
        student_display_name(student), student.last_name, student.first_name, student.period
    )
    issuance = PrintableResponseIssuance(
        PRINTABLE_RESPONSE_ISSUANCE_SCHEMA_VERSION,
        issuance_id,
        generation_id,
        artifact_id,
        class_id,
        cast(str, assignment["assignment_id"]),
        student.student_id,
        context,
        class_id if class_label is None else class_label,
        assignment_snapshot,
        snapshot,
        pages_per_student,
        generated_page_ids,
        lifecycle,
    )
    pages = tuple(
        PrintableResponsePage(
            RESPONSE_PAGE_CONTRACT_VERSION,
            page_id,
            issuance_id,
            generation_id,
            artifact_id,
            class_id,
            issuance.assignment_id,
            student.student_id,
            logical_page,
            pages_per_student,
            page_role_for_logical_page(logical_page),
            timestamp,
        )
        for logical_page, page_id in enumerate(generated_page_ids, start=1)
    )
    return PrintableResponseRecordSet(issuance, pages)


def transition_printable_response_lifecycle(
    lifecycle: PrintableResponseLifecycle,
    *,
    new_status: str,
    timestamp: datetime | str,
    reason: str | None = None,
    replacement_issuance_id: str | None = None,
) -> PrintableResponseLifecycle:
    """Construct one allowed immutable lifecycle transition."""
    if not isinstance(lifecycle, PrintableResponseLifecycle):
        raise PrintableResponseRecordValidationError("lifecycle is invalid.")
    _string(new_status, "new_status")
    if (lifecycle.status, new_status) not in _ALLOWED_TRANSITIONS:
        raise PrintableResponseRecordValidationError(
            f"Lifecycle transition {lifecycle.status!r} -> {new_status!r} is not allowed."
        )
    if new_status not in _TERMINAL_STATUSES and reason is not None:
        raise PrintableResponseRecordValidationError(
            "A reason is allowed only for a terminal lifecycle status."
        )
    if new_status != "superseded" and replacement_issuance_id is not None:
        raise PrintableResponseRecordValidationError(
            "replacement_issuance_id is allowed only for superseded."
        )
    timestamp_text = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
    _timestamp(timestamp_text, "timestamp")
    if _timestamp_value(timestamp_text) < _timestamp_value(lifecycle.updated_at):
        raise PrintableResponseRecordValidationError("Transition timestamp precedes updated_at.")
    terminal = new_status in _TERMINAL_STATUSES
    return PrintableResponseLifecycle(
        status=new_status,
        revision=lifecycle.revision + 1,
        created_at=lifecycle.created_at,
        updated_at=timestamp_text,
        issued_at=timestamp_text if new_status == "issued" else lifecycle.issued_at,
        ended_at=timestamp_text if terminal else None,
        reason=reason if terminal else None,
        replacement_issuance_id=(
            replacement_issuance_id if new_status == "superseded" else None
        ),
    )


def response_page_target(page_or_page_id: PrintableResponsePage | str) -> ModuleRecordRef:
    """Return the pure future Core route target for one immutable page."""
    page_id = (
        page_or_page_id.page_id
        if isinstance(page_or_page_id, PrintableResponsePage)
        else page_or_page_id
    )
    return ModuleRecordRef(
        module_id=QUILLAN_MODULE_ID,
        record_kind=RESPONSE_PAGE_RECORD_KIND,
        record_id=validate_page_id(page_id),
        contract_version=RESPONSE_PAGE_CONTRACT_VERSION,
    )


def printable_response_issuance_to_mapping(
    issuance: object,
) -> dict[str, Any]:
    if not isinstance(issuance, PrintableResponseIssuance):
        raise PrintableResponseRecordValidationError(
            "issuance must be a PrintableResponseIssuance."
        )
    return issuance.to_mapping()


def printable_response_issuance_from_mapping(value: object) -> PrintableResponseIssuance:
    return PrintableResponseIssuance.from_mapping(value)


def printable_response_page_to_mapping(page: object) -> dict[str, Any]:
    if not isinstance(page, PrintableResponsePage):
        raise PrintableResponseRecordValidationError(
            "page must be a PrintableResponsePage."
        )
    return page.to_mapping()


def printable_response_page_from_mapping(value: object) -> PrintableResponsePage:
    return PrintableResponsePage.from_mapping(value)


__all__ = [
    "PRINTABLE_RESPONSE_GENERATION_REASONS",
    "PRINTABLE_RESPONSE_ISSUANCE_SCHEMA_VERSION",
    "PRINTABLE_RESPONSE_LIFECYCLE_STATUSES",
    "PRINTABLE_RESPONSE_OUTPUT_KINDS",
    "PRINTABLE_RESPONSE_PAGE_ROLES",
    "PrintableResponseAssignmentSnapshot",
    "PrintableResponseGenerationContext",
    "PrintableResponseIssuance",
    "PrintableResponseLifecycle",
    "PrintableResponsePage",
    "PrintableResponsePageContext",
    "PrintableResponseRecordSet",
    "PrintableResponseRecordValidationError",
    "PrintableResponseStudentSnapshot",
    "build_printable_response_record_set",
    "generate_artifact_id",
    "generate_generation_id",
    "generate_issuance_id",
    "generate_page_id",
    "page_role_for_logical_page",
    "printable_response_issuance_from_mapping",
    "printable_response_issuance_to_mapping",
    "printable_response_page_from_mapping",
    "printable_response_page_to_mapping",
    "response_page_target",
    "transition_printable_response_lifecycle",
    "validate_artifact_id",
    "validate_generation_id",
    "validate_issuance_id",
    "validate_page_id",
    "validate_printable_response_record_set",
]
