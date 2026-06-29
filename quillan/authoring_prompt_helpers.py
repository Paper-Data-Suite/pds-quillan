"""Shared teacher-facing prompts for review-material authoring."""

from __future__ import annotations

from collections.abc import Callable


def print_identifier_guidance(field_name: str, suggestion: str) -> None:
    """Explain teacher-facing labels versus stored system IDs."""
    print(f"Suggested {field_name}:")
    print(suggestion)
    print()
    print("This is the short system name Quillan stores in JSON.")
    print("Labels can use spaces and capitalization.")
    print("Use lowercase letters, numbers, underscores, or hyphens. No spaces.")
    print("For multi-word values, use underscores instead of spaces.")
    print()


def prompt_identifier_with_guidance(
    field_name: str,
    suggestion: str,
    *,
    input_func: Callable[[str], str] | None = None,
) -> str:
    """Prompt for an identifier, accepting the suggested value on Enter."""
    reader = input if input_func is None else input_func
    print_identifier_guidance(field_name, suggestion)
    value = reader(
        f"Press Enter to accept, or type a different {field_name}: "
    ).strip()
    return value or suggestion


def prompt_writing_assignment_types(
    *,
    input_func: Callable[[str], str] | None = None,
) -> str:
    """Prompt text for comma-separated writing assignment types."""
    reader = input if input_func is None else input_func
    return reader(
        "Writing assignment types this material applies to, comma-separated.\n"
        "\n"
        "Use lowercase words. For multi-word types, use underscores instead "
        "of spaces.\n"
        "\n"
        "Examples:\n"
        "general, persuasive_writing, persuasive_speech, argumentative\n"
    )


def prompt_display_order(
    *,
    within: str = "menus",
    input_func: Callable[[str], str] | None = None,
) -> str:
    """Prompt for optional display order in teacher-facing language."""
    reader = input if input_func is None else input_func
    return reader(
        "Display order (optional)\n"
        "\n"
        f"This controls where this item appears in {within}.\n"
        "Leave blank to place it next.\n"
        "\n"
        "Example:\n"
        "1\n"
    )


def print_standard_ids_help() -> None:
    """Explain optional standards references."""
    print("Linked standards, comma-separated (optional)")
    print()
    print("Use this only if you want this item connected to specific standards.")
    print("Leave blank if this item is not tied to a specific standard.")
    print()
    print("Example:")
    print("njsls-ela:W.AW.11-12.1")
    print()


def print_criterion_ids_help() -> None:
    """Explain optional rubric criterion references."""
    print("Linked rubric criteria, comma-separated (optional)")
    print()
    print(
        "Use this only if this item connects to criteria from a rubric/scoring "
        "profile."
    )
    print("Leave blank if you are not sure.")
    print()
    print("Example:")
    print("rhetorical_technique")
    print()


def print_priority_severity_help() -> None:
    """Explain severity without implying grading."""
    print("Default priority/severity (optional)")
    print()
    print("Use this only for concerns or issues you may want to spot quickly later.")
    print("This is not a grade and does not affect scoring.")
    print()
    print("Suggested scale:")
    print("1 = minor note")
    print("2 = moderate concern")
    print("3 = important issue")
    print()
    print("Leave blank for positive or neutral items.")
    print()
