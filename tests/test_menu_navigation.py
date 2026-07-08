from __future__ import annotations

import pytest

from quillan.menu_navigation import (
    NavigationChoice,
    QuitQuillan,
    ReturnToMainMenu,
    parse_navigation_choice,
)


@pytest.mark.parametrize("value", ["b", "B"])
def test_parse_navigation_choice_back_is_case_insensitive(value: str) -> None:
    assert parse_navigation_choice(value) is NavigationChoice.BACK


@pytest.mark.parametrize("value", ["m", "M"])
def test_parse_navigation_choice_unwinds_to_main_menu(value: str) -> None:
    with pytest.raises(ReturnToMainMenu):
        parse_navigation_choice(value)


@pytest.mark.parametrize("value", ["q", "Q"])
def test_parse_navigation_choice_quits(value: str) -> None:
    with pytest.raises(QuitQuillan):
        parse_navigation_choice(value)


@pytest.mark.parametrize("value", ["a", "A"])
def test_all_is_available_only_when_explicitly_enabled(value: str) -> None:
    assert parse_navigation_choice(value) is None
    assert (
        parse_navigation_choice(value, allow_all=True)
        is NavigationChoice.ALL
    )
