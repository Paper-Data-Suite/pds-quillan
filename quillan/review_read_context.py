"""Fresh redraw-scoped canonical read context for assignment review composition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.rosters import RosterError, StudentRecord

from quillan.record_context import (
    QuillanAssignmentRecordContext,
    QuillanRecordContextError,
    load_quillan_assignment_context,
)
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    group_response_page_observations_by_student,
)
from quillan.work_paths import quillan_work_ref


class ReviewReadContextError(ValueError):
    """Raised when the mandatory assignment review read boundary cannot be built."""


ObservationGroups = Mapping[
    str,
    tuple[QuillanResponsePageObservation, ...],
]


@dataclass(frozen=True, slots=True)
class AssignmentReviewReadContext:
    """One fresh, immutable assignment-level read shared within a single redraw."""

    assignment_context: QuillanAssignmentRecordContext
    roster_students: tuple[StudentRecord, ...] | None
    roster_error: str | None
    observations_by_student: ObservationGroups | None
    observations_error: str | None

    @property
    def workspace_root(self) -> Path:
        return self.assignment_context.paths.workspace_root

    @property
    def class_id(self) -> str:
        return self.assignment_context.paths.work_ref.class_id

    @property
    def assignment_id(self) -> str:
        return self.assignment_context.paths.work_ref.work_id

    @property
    def roster_available(self) -> bool:
        return self.roster_students is not None

    @property
    def observations_available(self) -> bool:
        return self.observations_by_student is not None

    def __post_init__(self) -> None:
        if type(self.assignment_context) is not QuillanAssignmentRecordContext:
            raise ReviewReadContextError(
                "assignment_context must be an exact QuillanAssignmentRecordContext."
            )
        _validate_optional_read(
            self.roster_students,
            self.roster_error,
            value_name="roster_students",
            error_name="roster_error",
        )
        if self.roster_students is not None and type(self.roster_students) is not tuple:
            raise ReviewReadContextError("roster_students must be an immutable tuple.")

        _validate_optional_read(
            self.observations_by_student,
            self.observations_error,
            value_name="observations_by_student",
            error_name="observations_error",
        )
        if self.observations_by_student is None:
            return
        if type(self.observations_by_student) is not type(MappingProxyType({})):
            raise ReviewReadContextError(
                "observations_by_student must be an immutable mapping proxy."
            )

        observation_groups: ObservationGroups = self.observations_by_student
        keys: tuple[str, ...] = tuple(observation_groups)
        if keys != tuple(sorted(keys)):
            raise ReviewReadContextError(
                "observations_by_student must use deterministic student ordering."
            )
        for student_id, observations in observation_groups.items():
            validate_identifier(student_id, "student_id")
            if type(observations) is not tuple:
                raise ReviewReadContextError(
                    "Each routed-observation group must be an immutable tuple."
                )
            for observation in observations:
                if type(observation) is not QuillanResponsePageObservation:
                    raise ReviewReadContextError(
                        "Observation groups must contain exact "
                        "QuillanResponsePageObservation records."
                    )
                if observation.student_id != student_id:
                    raise ReviewReadContextError(
                        "Observation group key contradicts persisted student identity."
                    )
                if (
                    observation.class_id != self.class_id
                    or observation.assignment_id != self.assignment_id
                ):
                    raise ReviewReadContextError(
                        "Observation identity does not match the assignment read context."
                    )


def build_assignment_review_read_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentReviewReadContext:
    """Build one fresh strict assignment read for reuse within a single redraw."""
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
    except (TypeError, ValueError) as error:
        raise ReviewReadContextError(str(error)) from error

    work_ref = quillan_work_ref(class_id, assignment_id)
    try:
        assignment_context = load_quillan_assignment_context(workspace_root, work_ref)
    except (OSError, QuillanRecordContextError) as error:
        raise ReviewReadContextError(f"Could not load assignment: {error}") from error

    root = assignment_context.paths.workspace_root

    roster_students: tuple[StudentRecord, ...] | None
    roster_error: str | None
    try:
        roster_students = tuple(load_class_roster(root, class_id).students)
    except (OSError, RosterError) as error:
        roster_students = None
        roster_error = _error_message(error)
    else:
        roster_error = None

    observations_by_student: ObservationGroups | None
    observations_error: str | None
    try:
        observations = group_response_page_observations_by_student(
            root,
            class_id,
            assignment_id,
        )
    except (OSError, ValueError) as error:
        observations_by_student = None
        observations_error = _error_message(error)
    else:
        observations_by_student = _freeze_observation_groups(observations)
        observations_error = None

    return AssignmentReviewReadContext(
        assignment_context=assignment_context,
        roster_students=roster_students,
        roster_error=roster_error,
        observations_by_student=observations_by_student,
        observations_error=observations_error,
    )


def _freeze_observation_groups(
    observations: Mapping[str, tuple[QuillanResponsePageObservation, ...]],
) -> ObservationGroups:
    return MappingProxyType(
        {
            student_id: tuple(observations[student_id])
            for student_id in sorted(observations)
        }
    )


def _validate_optional_read(
    value: object | None,
    error: str | None,
    *,
    value_name: str,
    error_name: str,
) -> None:
    if value is None:
        if not isinstance(error, str) or not error:
            raise ReviewReadContextError(
                f"{error_name} must explain why {value_name} is unavailable."
            )
        return
    if error is not None:
        raise ReviewReadContextError(
            f"{error_name} must be None when {value_name} is available."
        )


def _error_message(error: BaseException) -> str:
    message = str(error).strip()
    return message or type(error).__name__
