from __future__ import annotations

import json
from pathlib import Path

import pytest

import quillan.menu as root_menu
import quillan.review_menu as review_menu
import quillan.share_results_menu as share_menu
from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    generate_academic_result_manifest,
    list_academic_result_manifest_revisions,
)
from quillan.academic_result_publication import (
    load_quillan_publication_series_status,
    publish_quillan_academic_results,
    supersede_quillan_academic_results as real_supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.academic_work_registration import (
    load_current_quillan_academic_work_registration,
    register_quillan_academic_work,
)
from quillan.share_results_menu import (
    launch_share_results_with_meridian_menu,
)
from quillan.work_paths import quillan_work_ref
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _write_assignment
from tests.test_academic_result_manifest_generation import _prepare_plain_pair
from tests.test_academic_result_publication import _registered_manifest


def _patch_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)


def _responses(
    monkeypatch: pytest.MonkeyPatch,
    values: tuple[str, ...],
) -> None:
    responses = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))


def _change_title(tmp_path: Path, title: str) -> None:
    assignment = _write_assignment(tmp_path)
    data = json.loads(assignment.read_text(encoding="utf-8"))
    data["title"] = title
    assignment.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def _new_manifest_revision(
    tmp_path: Path,
) -> AcademicResultManifestGenerationResult:
    assignment = _write_assignment(tmp_path)
    assignment.write_bytes(assignment.read_bytes() + b"\n")
    return generate_academic_result_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )


def test_assignment_review_actions_routes_s_with_exact_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shell(monkeypatch)
    fake_dashboard = object()
    monkeypatch.setattr(
        review_menu,
        "_load_review_dashboard",
        lambda *_args: fake_dashboard,
    )
    monkeypatch.setattr(
        review_menu,
        "_load_class_review_completion_from_dashboard",
        lambda *_args: (None, None),
    )
    monkeypatch.setattr(
        review_menu,
        "_print_compact_assignment_dashboard",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "print_active_context",
        lambda *_args, **_kwargs: None,
    )
    seen: list[tuple[Path, str, str]] = []

    def launch(root: Path, class_id: str, assignment_id: str) -> int:
        seen.append((root, class_id, assignment_id))
        return 0

    monkeypatch.setattr(
        share_menu,
        "launch_share_results_with_meridian_menu",
        launch,
    )
    _responses(monkeypatch, ("s", "b"))

    assert (
        review_menu._launch_assignment_review_actions(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
        )
        == 0
    )
    assert seen == [(tmp_path, CLASS_ID, ASSIGNMENT_ID)]


def test_guided_registration_then_generation_reuses_active_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare_plain_pair(tmp_path)
    _patch_shell(monkeypatch)
    _responses(
        monkeypatch,
        (
            "1",
            "2",
            "2",
            "REGISTER",
            "1",
            "GENERATE",
            "b",
        ),
    )

    assert (
        launch_share_results_with_meridian_menu(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
        )
        == 0
    )

    registration = load_current_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert registration is not None
    assert registration.academic_intent == "summative"
    assert registration.lifecycle == "active"
    history = list_academic_result_manifest_revisions(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
    )
    assert len(history) == 1

    output = capsys.readouterr().out
    assert "Select class:" not in output
    assert "Select assignment:" not in output
    assert "Next step: Register Academic Work" in output
    assert "Next step: Generate / exact replay manifest" in output
    assert "Next step: Publish first result set" in output


def test_cancel_before_register_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    _patch_shell(monkeypatch)
    _responses(
        monkeypatch,
        ("1", "2", "2", "NO", "b"),
    )

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert (
        load_current_quillan_academic_work_registration(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
        )
        is None
    )
    assert (
        list_academic_result_manifest_revisions(
            tmp_path,
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        )
        == ()
    )


def test_cancel_generation_preserves_existing_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    registration = register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
    )
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("1", "NO", "b"))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    current = load_current_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert current == registration.registration
    assert (
        list_academic_result_manifest_revisions(
            tmp_path,
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        )
        == ()
    )


def test_stale_title_requires_explicit_continue_before_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    registered = register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
    )
    _change_title(tmp_path, "Revised Synthetic Title")
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("1", "1", "GENERATE", "b"))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    current = load_current_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert current == registered.registration
    assert current.title != "Revised Synthetic Title"
    assert len(
        list_academic_result_manifest_revisions(
            tmp_path,
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        )
    ) == 1


def test_stale_title_can_be_explicitly_updated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
    )
    _change_title(tmp_path, "Revised Synthetic Title")
    _patch_shell(monkeypatch)
    _responses(
        monkeypatch,
        (
            "2",
            "2",
            "2",
            "UPDATE",
            "b",
        ),
    )

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    current = load_current_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert current is not None
    assert current.registration_revision == 2
    assert current.title == "Revised Synthetic Title"
    assert current.academic_intent == "summative"
    assert current.lifecycle == "active"


def test_cancelled_registration_requires_explicit_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="cancelled",
    )
    _patch_shell(monkeypatch)
    _responses(
        monkeypatch,
        (
            "1",
            "2",
            "2",
            "UPDATE",
            "b",
        ),
    )

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    current = load_current_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert current is not None
    assert current.registration_revision == 2
    assert current.lifecycle == "active"


def test_initial_publication_requires_publish_and_reconciles_final_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("1", "PUBLISH", "b"))

    assert (
        launch_share_results_with_meridian_menu(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
        )
        == 0
    )

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert len(state.publications) == 1
    assert state.core_head is not None
    assert state.core_head.record_set_revision == manifest.revision
    assert state.current_selectable_publication == state.core_head
    output = capsys.readouterr().out
    assert "Status: published through Core" in output
    assert "Catalog reconciliation: verified" in output
    assert "Ready for authorized compatible Meridian discovery." in output


def test_cancel_publish_preserves_manifest_without_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("1", "NO", "b"))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert state.publications == ()
    assert state.producer_head is not None
    assert state.producer_head.revision == manifest.revision


def test_supersession_uses_exact_fresh_core_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=first_manifest.revision,
    )
    second_manifest = _new_manifest_revision(tmp_path)
    expected_ids: list[str] = []
    real = real_supersede_quillan_academic_results

    def capture(
        workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        *,
        manifest_revision: int,
        expected_current_publication_id: str,
    ) -> object:
        expected_ids.append(expected_current_publication_id)
        return real(
            workspace_root,
            class_id,
            assignment_id,
            manifest_revision=manifest_revision,
            expected_current_publication_id=expected_current_publication_id,
        )

    monkeypatch.setattr(
        share_menu,
        "supersede_quillan_academic_results",
        capture,
    )
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("1", "SUPERSEDE", "b"))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert expected_ids == [first.publication.publication_id]
    assert state.core_head is not None
    assert state.core_head.record_set_revision == second_manifest.revision
    assert (
        state.core_head.supersedes_publication_id
        == first.publication.publication_id
    )


def test_already_current_is_no_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    before = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("b",))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    after = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert after.publications == before.publications
    assert after.core_head == first.publication


def test_withdrawn_head_never_auto_republishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="synthetic hold",
    )
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("b",))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert len(state.publications) == 1
    assert state.core_head == first.publication
    assert state.current_selectable_publication is None
    output = capsys.readouterr().out
    assert "advanced Academic Result Publications" in output
    assert "REPUBLISH" not in output


def test_status_screen_does_not_claim_meridian_ingestion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare_plain_pair(tmp_path)
    _patch_shell(monkeypatch)
    _responses(monkeypatch, ("b",))

    launch_share_results_with_meridian_menu(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    assert "authorized compatible Meridian installation can discover it" in output
    assert "Meridian received" not in output
    assert "Meridian imported" not in output
    assert "Sent to Meridian" not in output
