"""Issue #389 real menu-density acceptance for Share Results with Meridian."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.academic_result_publication import (
    load_quillan_publication_series_status,
)
from quillan.cli import main
import quillan.review_menu as review_menu
from tests.menu_screen_recorder import (
    MenuScreenRecorder,
    assert_focused_child_screen,
)
from tests.test_academic_result_manifest_generation import _prepare_plain_pair
from tests.test_menu_export_actions import (
    ASSIGNMENT_ID,
    CLASS_ID,
    _enter_assignment_review_actions,
    _exit_assignment_review_actions_to_main,
    _write_workspace,
)


@pytest.mark.menu_density_workflow("share results with Meridian")
def test_share_results_with_meridian_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Drive the full routine path through the actual main-menu hierarchy."""
    _write_workspace(tmp_path)
    _prepare_plain_pair(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)

    recorder = MenuScreenRecorder(
        _enter_assignment_review_actions()
        + [
            "s",  # Assignment Review Actions -> Share Results with Meridian.
            "1",  # Register Academic Work.
            "2",  # summative.
            "2",  # active.
            "REGISTER",
            "1",  # Generate / exact replay manifest.
            "GENERATE",
            "1",  # Publish first result set.
            "PUBLISH",
            "b",  # Return from final already-current share status.
        ]
        + _exit_assignment_review_actions_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert len(state.publications) == 1
    assert state.core_head is not None
    assert state.current_selectable_publication == state.core_head
    assert state.catalog_available is True

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Share Results with Meridian",
        required_text=(
            f"Class: {CLASS_ID}",
            "Next step: Register Academic Work",
        ),
        forbidden_parent_text="F. Batch Feedback Export",
        parent_heading="Assignment Review Actions",
        result_heading="Share Results with Meridian",
        unrelated_previous_text="7. Review class progress",
    )

    assert "S. Share Results with Meridian" in output
    assert "Next step: Register Academic Work" in output
    assert "Next step: Generate / exact replay manifest" in output
    assert "Next step: Publish first result set" in output
    assert "Status: published through Core" in output
    assert "Catalog reconciliation: verified" in output
    assert "Ready for authorized compatible Meridian discovery." in output
    assert "Meridian received" not in output
    assert "Meridian imported" not in output

    prompts = tuple(recorder.prompts)
    assert any(
        "REGISTER" in item.prompt and item.choice == "REGISTER"
        for item in prompts
    )
    assert any(
        "GENERATE" in item.prompt and item.choice == "GENERATE"
        for item in prompts
    )
    assert any(
        "PUBLISH" in item.prompt and item.choice == "PUBLISH"
        for item in prompts
    )
    assert sum("Select class" in item.prompt for item in prompts) <= 1
    assert sum("Select assignment" in item.prompt for item in prompts) <= 1
