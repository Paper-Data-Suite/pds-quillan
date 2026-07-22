"""Scripted recorder for clear-delimited interactive menu acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Final

import pytest

import quillan.menu as menu


_CLEAR_PREFIX: Final = "<<<QUILLAN-CLEAR:"
_RECORDER_EVENTS: dict[str, set[str]] = {}


def _record_event(event: str) -> None:
    current = os.environ.get("PYTEST_CURRENT_TEST", "")
    node_id, separator, _phase = current.rpartition(" (")
    if separator and node_id:
        _RECORDER_EVENTS.setdefault(node_id, set()).add(event)


def recorder_events(node_id: str) -> frozenset[str]:
    """Return recorder lifecycle events observed for one pytest item."""
    return frozenset(_RECORDER_EVENTS.get(node_id, ()))


@dataclass(frozen=True, slots=True)
class RecordedPrompt:
    prompt: str
    choice: str


@dataclass(frozen=True, slots=True)
class RecordedScreen:
    clear_number: int
    output: str


class MenuScreenRecorder:
    """Capture clear events, output segments, prompts, pauses, and choices."""

    def __init__(self, responses: list[str]) -> None:
        _record_event("instantiated")
        self._responses = iter(responses)
        self.clear_count = 0
        self.prompts: list[RecordedPrompt] = []

    def install(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        clear_aliases: tuple[str, ...] = (),
    ) -> None:
        _record_event("installed")
        monkeypatch.setattr(menu, "clear_screen", self._clear)
        for alias in clear_aliases:
            monkeypatch.setattr(alias, self._clear)
        monkeypatch.setattr("builtins.input", self._input)

    def _clear(self) -> None:
        self.clear_count += 1
        print(f"{_CLEAR_PREFIX}{self.clear_count}>>>")

    def _input(self, prompt: str = "") -> str:
        try:
            choice = next(self._responses)
        except StopIteration as error:
            raise AssertionError(
                f"Menu requested an unexpected input after prompt {prompt!r}."
            ) from error
        self.prompts.append(RecordedPrompt(prompt, choice))
        return choice

    def screens(self, output: str) -> tuple[RecordedScreen, ...]:
        _record_event("screens")
        screens: list[RecordedScreen] = []
        for chunk in output.split(_CLEAR_PREFIX)[1:]:
            number_text, separator, body = chunk.partition(">>>")
            if not separator or not number_text.isdigit():
                raise AssertionError("Malformed clear marker in recorded output.")
            screens.append(RecordedScreen(int(number_text), body.strip()))
        if len(screens) != self.clear_count:
            raise AssertionError("Captured screen count disagrees with clear events.")
        return tuple(screens)

    def print_transcript(
        self, screens: tuple[RecordedScreen, ...], *, label: str
    ) -> None:
        """Print an artifact-friendly transcript after assertions succeed."""
        print(f"=== {label} ===")
        for screen in screens:
            print(f"--- CLEAR EVENT {screen.clear_number} ---")
            print(screen.output)
        print("--- PROMPTS AND CHOICES ---")
        for prompt in self.prompts:
            print(f"{prompt.prompt}{prompt.choice}")


def assert_focused_child_screen(
    screens: tuple[RecordedScreen, ...],
    *,
    heading: str,
    required_text: str | tuple[str, ...],
    forbidden_parent_text: str | tuple[str, ...],
    parent_heading: str,
    result_heading: str,
    unrelated_previous_text: str | tuple[str, ...] = (),
) -> None:
    """Assert one complete parent/child/result/redraw clear-screen lifecycle."""
    _record_event("asserted")
    required = (required_text,) if isinstance(required_text, str) else required_text
    forbidden = (
        (forbidden_parent_text,)
        if isinstance(forbidden_parent_text, str)
        else forbidden_parent_text
    )
    unrelated = (
        (unrelated_previous_text,)
        if isinstance(unrelated_previous_text, str)
        else unrelated_previous_text
    )
    child_indexes = [
        index
        for index, screen in enumerate(screens)
        if heading in screen.output
        and all(text in screen.output for text in required)
        and all(text not in screen.output for text in (*forbidden, *unrelated))
    ]
    assert child_indexes, f"No clear-delimited screen has heading {heading!r}."
    child_index = child_indexes[0]
    assert child_index > 0, "Focused child was not cleared after a parent screen."
    child = screens[child_index]
    prior_indexes = [
        index
        for index, screen in enumerate(screens[:child_index])
        if parent_heading in screen.output
    ]
    assert prior_indexes, "Focused child has no prior parent screen."
    parent_index = prior_indexes[-1]
    assert child.clear_number > screens[parent_index].clear_number
    for text in required:
        assert text in child.output
    for text in (*forbidden, *unrelated):
        assert text not in child.output

    result_indexes = [
        index
        for index, screen in enumerate(screens[child_index:], child_index)
        if result_heading in screen.output
    ]
    assert result_indexes, f"No later cleared result screen has {result_heading!r}."
    result_index = result_indexes[0]
    assert screens[result_index].clear_number >= child.clear_number
    redraw_indexes = [
        index
        for index, screen in enumerate(screens[result_index + 1 :], result_index + 1)
        if parent_heading in screen.output
    ]
    assert redraw_indexes, "Parent screen was not redrawn after returning."
    assert screens[redraw_indexes[0]].clear_number > screens[result_index].clear_number
