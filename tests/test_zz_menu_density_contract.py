"""Collection and execution contract for all real density acceptance tests."""

from __future__ import annotations

from collections import Counter
import inspect

import pytest

from tests.menu_screen_recorder import recorder_events
from tests.test_menu_density_matrix import (
    MENU_DENSITY_ACCEPTANCE_MATRIX,
    REQUIRED_MENU_DENSITY_WORKFLOWS,
)


@pytest.mark.menu_density_contract
def test_menu_density_matrix_collected_and_executed_exactly_once(
    request: pytest.FixtureRequest,
) -> None:
    registered = set(MENU_DENSITY_ACCEPTANCE_MATRIX.values())
    collected = {item.nodeid: item for item in request.session.items}
    marked_items: dict[str, list[pytest.Item]] = {}
    for item in request.session.items:
        marker = item.get_closest_marker("menu_density_workflow")
        if marker is None:
            continue
        assert len(marker.args) == 1 and not marker.kwargs
        label = marker.args[0]
        assert isinstance(label, str)
        marked_items.setdefault(label, []).append(item)

    assert set(marked_items) == REQUIRED_MENU_DENSITY_WORKFLOWS
    assert Counter(
        label for label, items in marked_items.items() for _item in items
    ) == Counter({label: 1 for label in REQUIRED_MENU_DENSITY_WORKFLOWS})
    assert registered == {
        items[0].nodeid for items in marked_items.values()
    }
    assert registered <= collected.keys()

    expected_events = frozenset(
        {"instantiated", "installed", "screens", "asserted"}
    )
    for label, node_id in MENU_DENSITY_ACCEPTANCE_MATRIX.items():
        item = collected[node_id]
        marker = item.get_closest_marker("menu_density_workflow")
        assert marker is not None and marker.args == (label,)
        assert recorder_events(node_id) == expected_events
        source = inspect.getsource(getattr(item, "obj"))
        assert "MenuScreenRecorder" in source
        assert ".install(" in source
        assert ".screens(" in source
        assert "assert_focused_child_screen(" in source
        assert "RecordedScreen(" not in source
