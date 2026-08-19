"""Scripted recorder for clear-delimited interactive menu acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Final

import pytest

import quillan.menu as menu


_CLEAR_PREFIX: Final = "<<<QUILLAN-CLEAR:"
_ANSI_ESCAPE: Final = re.compile(r"\x1b\[[0-9;]*m")
_RECORDER_EVENTS: dict[str, set[str]] = {}
_RECORDED_WORKFLOWS: dict[str, "RecordedWorkflow"] = {}

_CONTEXT_PROMPT_KINDS: Final[tuple[tuple[str, str], ...]] = (
    ("class", "Select class:"),
    ("class", "Select class for assignment:"),
    ("class", "Select class(es) for assignment:"),
    ("assignment", "Select assignment:"),
    ("student", "Select student/submission:"),
)

_REUSABLE_ASSIGNMENT_CONFIGURATION_PROMPTS: Final[tuple[str, ...]] = (
    "Writing type:",
    "Select standards profile:",
    "Select Focus Standards by number, comma-separated:",
    "Use default paragraph review units?",
    "Use default four-level standards scale?",
    "paragraphs_min:",
    "sentences_per_paragraph_min:",
    "word_count_min:",
    "word_count_max:",
    "required_elements, comma-separated:",
    "Allow teacher to return work without full standards review if minimum requirements are unmet?",
)


def _current_node_id() -> str:
    current = os.environ.get("PYTEST_CURRENT_TEST", "")
    node_id, separator, _phase = current.rpartition(" (")
    return node_id if separator else ""


def _record_event(event: str) -> None:
    node_id = _current_node_id()
    if node_id:
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


@dataclass(frozen=True, slots=True)
class RecordedWorkflow:
    """Immutable screen/prompt trace retained for one recorder-backed pytest item."""

    screens: tuple[RecordedScreen, ...]
    prompts: tuple[RecordedPrompt, ...]


@dataclass(frozen=True, slots=True)
class WorkflowAuditMetrics:
    """Generic, reproducible interaction counts derived from one real workflow."""

    prompt_count: int
    screen_count: int
    menu_transition_count: int
    class_selection_count: int
    assignment_selection_count: int
    student_selection_count: int
    context_selection_count: int
    context_reselection_count: int
    repeated_configuration_count: int
    backtracking_count: int
    pause_count: int


def recorded_workflow(node_id: str) -> RecordedWorkflow | None:
    """Return the retained recorder trace for one pytest item, if executed."""
    return _RECORDED_WORKFLOWS.get(node_id)


def workflow_audit_metrics(node_id: str) -> WorkflowAuditMetrics | None:
    """Summarize interaction cost without asserting today's exact counts forever."""
    workflow = recorded_workflow(node_id)
    if workflow is None:
        return None

    context_counts = {"class": 0, "assignment": 0, "student": 0}
    seen_configuration_prompts: set[str] = set()
    repeated_configuration_count = 0
    backtracking_count = 0
    pause_count = 0

    for recorded in workflow.prompts:
        prompt = recorded.prompt.strip()
        context_kind = _context_prompt_kind(prompt)
        if context_kind is not None:
            context_counts[context_kind] += 1

        configuration_prompt = _configuration_prompt_kind(prompt)
        if configuration_prompt is not None:
            if configuration_prompt in seen_configuration_prompts:
                repeated_configuration_count += 1
            else:
                seen_configuration_prompts.add(configuration_prompt)

        if recorded.choice.strip().casefold() == "b":
            backtracking_count += 1
        if prompt.startswith("Press Enter"):
            pause_count += 1

    context_selection_count = sum(context_counts.values())
    context_reselection_count = sum(
        max(count - 1, 0) for count in context_counts.values()
    )
    headings = tuple(_screen_heading(screen.output) for screen in workflow.screens)
    menu_transition_count = sum(
        previous != current
        for previous, current in zip(headings, headings[1:], strict=False)
    )

    return WorkflowAuditMetrics(
        prompt_count=len(workflow.prompts),
        screen_count=len(workflow.screens),
        menu_transition_count=menu_transition_count,
        class_selection_count=context_counts["class"],
        assignment_selection_count=context_counts["assignment"],
        student_selection_count=context_counts["student"],
        context_selection_count=context_selection_count,
        context_reselection_count=context_reselection_count,
        repeated_configuration_count=repeated_configuration_count,
        backtracking_count=backtracking_count,
        pause_count=pause_count,
    )


def _context_prompt_kind(prompt: str) -> str | None:
    for kind, expected in _CONTEXT_PROMPT_KINDS:
        if prompt == expected:
            return kind
    return None


def _configuration_prompt_kind(prompt: str) -> str | None:
    normalized = prompt.lstrip()
    for expected in _REUSABLE_ASSIGNMENT_CONFIGURATION_PROMPTS:
        if normalized.startswith(expected):
            return expected
    return None


def _screen_heading(output: str) -> str:
    lines = [
        _ANSI_ESCAPE.sub("", line).strip()
        for line in output.splitlines()
        if line.strip()
    ]
    if not lines:
        return "<empty>"
    if lines[0] == "Quillan" and len(lines) > 1:
        return lines[1]
    return lines[0]


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
        captured = tuple(screens)
        node_id = _current_node_id()
        if node_id:
            _RECORDED_WORKFLOWS[node_id] = RecordedWorkflow(
                screens=captured,
                prompts=tuple(self.prompts),
            )
        return captured

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
