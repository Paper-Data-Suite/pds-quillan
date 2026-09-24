"""Issue #414 tests for routine queue exclusion of scan-review diagnostics."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import quillan.review_dashboard as dashboard_module
from quillan.review_dashboard import (
    ReviewDashboardError,
    build_assignment_review_dashboard_from_read_context,
)
from quillan.review_read_context import build_assignment_review_read_context
from quillan.review_work_queue import build_assignment_review_work_queue_from_read_context
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import _write_assignment, _write_roster


def test_routine_queue_does_not_discover_scan_review_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def unexpected_scan_discovery(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("routine review queue invoked scan-review discovery")

    monkeypatch.setattr(
        dashboard_module,
        "discover_scan_review_items",
        unexpected_scan_discovery,
    )

    queue = build_assignment_review_work_queue_from_read_context(read_context)

    assert queue.roster_count == 3
    assert queue.needs_work_count == 3


def test_full_dashboard_still_discovers_scan_review_items_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    calls = 0

    def counted_scan_discovery(*_args: object, **_kwargs: object):
        nonlocal calls
        calls += 1
        return SimpleNamespace(items=(), warnings=())

    monkeypatch.setattr(
        dashboard_module,
        "discover_scan_review_items",
        counted_scan_discovery,
    )

    dashboard = build_assignment_review_dashboard_from_read_context(read_context)

    assert calls == 1
    assert dashboard.scan_review_available is True
    assert dashboard.scan_review_items == ()


def test_explicit_scan_exclusion_never_calls_scan_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def unexpected_scan_discovery(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("scan-review discovery should be excluded")

    monkeypatch.setattr(
        dashboard_module,
        "discover_scan_review_items",
        unexpected_scan_discovery,
    )

    dashboard = build_assignment_review_dashboard_from_read_context(
        read_context,
        include_scan_review=False,
    )

    assert dashboard.scan_review_available is False
    assert dashboard.scan_review_items == ()
    assert dashboard.scan_review_counts == (
        ("attention_items", 0),
        ("unresolved", 0),
        ("deferred", 0),
        ("metadata_warning_count", 0),
    )
    assert "scan_review_unavailable" not in {
        warning.code for warning in dashboard.warnings
    }


@pytest.mark.parametrize("value", (None, 0, 1, "false", object()))
def test_dashboard_rejects_non_boolean_scan_review_mode(
    tmp_path: Path,
    value: object,
) -> None:
    _write_assignment(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    with pytest.raises(ReviewDashboardError, match="include_scan_review must be a Boolean"):
        build_assignment_review_dashboard_from_read_context(
            read_context,
            include_scan_review=value,  # type: ignore[arg-type]
        )
