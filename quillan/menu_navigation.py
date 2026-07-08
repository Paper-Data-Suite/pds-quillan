"""Shared navigation primitives for teacher-facing interactive menus."""

from __future__ import annotations

from enum import Enum


class NavigationChoice(Enum):
    """A recognized controlled-prompt navigation command."""

    BACK = "b"
    MAIN_MENU = "m"
    QUIT = "q"
    ALL = "a"


class ReturnToMainMenu(Exception):
    """Unwind the current workflow and redraw Quillan's main menu."""


class QuitQuillan(Exception):
    """Unwind the current workflow and exit Quillan cleanly."""


def parse_navigation_choice(
    value: str,
    *,
    allow_back: bool = True,
    allow_main_menu: bool = True,
    allow_quit: bool = True,
    allow_all: bool = False,
) -> NavigationChoice | None:
    """Parse a letter command from a controlled prompt and raise global signals."""
    normalized = value.strip().casefold()
    choice = {
        "b": NavigationChoice.BACK,
        "m": NavigationChoice.MAIN_MENU,
        "q": NavigationChoice.QUIT,
        "a": NavigationChoice.ALL,
    }.get(normalized)
    if choice is NavigationChoice.BACK and allow_back:
        return choice
    if choice is NavigationChoice.MAIN_MENU and allow_main_menu:
        raise ReturnToMainMenu
    if choice is NavigationChoice.QUIT and allow_quit:
        raise QuitQuillan
    if choice is NavigationChoice.ALL and allow_all:
        return choice
    return None


def print_navigation_options(
    *,
    back: bool = True,
    main_menu: bool = True,
    quit: bool = True,
    all_items: bool = False,
) -> None:
    """Print the standard commands supported by a controlled prompt."""
    if all_items:
        print("A. All")
    if back:
        print("B. Back")
    if main_menu:
        print("M. Main Menu")
    if quit:
        print("Q. Quit")


def navigation_hint(*, all_items: bool = False) -> str:
    """Return a concise invalid-selection hint for the standard commands."""
    commands = "A, B, M, or Q" if all_items else "B, M, or Q"
    return f"Please choose a listed option, {commands}."
