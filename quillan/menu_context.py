"""Session-local active class/assignment context for teacher menus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pds_core.classes import list_class_folders

from quillan.assignment_picker import AssignmentChoice, available_assignments


@dataclass(frozen=True, slots=True)
class ContextValidation:
    """Result of revalidating a session context against the current workspace."""

    assignment: AssignmentChoice | None
    message: str | None = None


@dataclass(slots=True)
class MenuSessionContext:
    """Ephemeral navigation context owned by one interactive Quillan session."""

    workspace_root: Path | None = None
    class_id: str | None = None
    assignment_id: str | None = None

    def __post_init__(self) -> None:
        if self.assignment_id is not None and self.class_id is None:
            raise ValueError("assignment context requires class context")
        if self.workspace_root is not None:
            self.workspace_root = _canonical_workspace_root(self.workspace_root)

    def bind_workspace(self, workspace_root: Path) -> bool:
        """Bind to a canonical workspace and clear targets if the root changed."""
        canonical = _canonical_workspace_root(workspace_root)
        changed = self.workspace_root is not None and self.workspace_root != canonical
        self.workspace_root = canonical
        if changed:
            self.class_id = None
            self.assignment_id = None
        return changed

    def activate_class(self, class_id: str) -> None:
        """Activate one exact class and clear any prior assignment."""
        _require_identity(class_id, "class_id")
        self.class_id = class_id
        self.assignment_id = None

    def activate_assignment(self, class_id: str, assignment_id: str) -> None:
        """Atomically activate one exact class/assignment pair."""
        _require_identity(class_id, "class_id")
        _require_identity(assignment_id, "assignment_id")
        self.class_id = class_id
        self.assignment_id = assignment_id

    def clear_assignment(self) -> None:
        """Clear assignment context while retaining the active class."""
        self.assignment_id = None

    def clear_selection(self) -> None:
        """Clear class and assignment context while retaining workspace binding."""
        self.class_id = None
        self.assignment_id = None


def _canonical_workspace_root(workspace_root: Path) -> Path:
    return workspace_root.expanduser().resolve(strict=False)


def _require_identity(value: str, field: str) -> None:
    if not value or value.strip() != value:
        raise ValueError(f"{field} must be a non-empty exact identifier")


def exact_assignment_choice(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentChoice | None:
    """Return only the exact canonical assignment identity, never a title match."""
    return next(
        (
            choice
            for choice in available_assignments(workspace_root, class_id)
            if choice.assignment_id == assignment_id
        ),
        None,
    )


def revalidate_menu_context(
    context: MenuSessionContext,
    workspace_root: Path,
) -> ContextValidation:
    """Fail closed when remembered context is stale or belongs elsewhere."""
    previous_class = context.class_id
    previous_assignment = context.assignment_id
    if context.bind_workspace(workspace_root):
        return ContextValidation(
            assignment=None,
            message=(
                "Active class/assignment context was cleared because the "
                "resolved workspace changed."
            ),
        )

    if context.class_id is None:
        return ContextValidation(assignment=None)

    class_ids = {
        folder.class_id
        for folder in list_class_folders(workspace_root, require_roster=True)
    }
    if context.class_id not in class_ids:
        context.clear_selection()
        return ContextValidation(
            assignment=None,
            message=(
                "Active class context is no longer available in this workspace: "
                f"{previous_class}. Select a class and assignment again."
            ),
        )

    if context.assignment_id is None:
        return ContextValidation(assignment=None)

    choice = exact_assignment_choice(
        workspace_root,
        context.class_id,
        context.assignment_id,
    )
    if choice is None:
        context.clear_assignment()
        return ContextValidation(
            assignment=None,
            message=(
                "Active assignment context is no longer a valid canonical "
                f"assignment for class {previous_class}: {previous_assignment}. "
                "Select an assignment again."
            ),
        )
    return ContextValidation(assignment=choice)


def print_active_context(
    workspace_root: Path | None,
    class_id: str,
    assignment_id: str | None = None,
) -> None:
    """Render an exact, bounded active-context block for teacher-facing screens."""
    print("Active context")
    print(f"Class: {class_id}")
    if assignment_id is not None:
        choice = (
            None
            if workspace_root is None
            else exact_assignment_choice(workspace_root, class_id, assignment_id)
        )
        if choice is not None and choice.title is not None:
            print(f"Assignment: {assignment_id} - {choice.title}")
        elif choice is not None:
            print(f"Assignment: {assignment_id}")
        else:
            print(f"Assignment: {assignment_id} - title unavailable")
    print()


def print_session_context(context: MenuSessionContext) -> None:
    """Render session context when a class has been explicitly selected."""
    if context.class_id is None:
        return
    print_active_context(
        context.workspace_root,
        context.class_id,
        context.assignment_id,
    )
