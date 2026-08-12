"""Teacher-menu tests for explicit Academic Work Registration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pds_core.academic_work_registrations import AcademicWorkRegistration
from pds_core.registry_services import AcademicWorkRegistrationServiceResult
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef

import quillan.academic_work_menu as menu
from quillan.academic_work_registration import ManagedAssignmentRegistrationContext


def _context(
    tmp_path: Path, *, title: str = "Current Title"
) -> ManagedAssignmentRegistrationContext:
    return ManagedAssignmentRegistrationContext(
        work=ModuleWorkRef(module_id="quillan", class_id="class1", work_id="essay1"),
        work_root=tmp_path / "work",
        assignment_path=tmp_path / "work/assignment.json",
        title=title,
    )


def _registration(
    *, revision: int = 1, title: str = "Current Title"
) -> AcademicWorkRegistration:
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    return AcademicWorkRegistration(
        schema_version="1",
        record_type="academic_work_registration",
        work=ModuleWorkRef(module_id="quillan", class_id="class1", work_id="essay1"),
        registration_revision=revision,
        producer_contract_version="quillan_academic_work_v1",
        title=title,
        work_kind="assignment",
        academic_intent="formative",
        lifecycle="active",
        created_at=now,
        updated_at=now,
        source_records=(
            ModuleRecordRef(
                module_id="quillan",
                record_kind="assignment",
                record_id="essay1",
                contract_version="2",
            ),
        ),
    )


def _patch_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(menu, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        menu,
        "prompt_assignment_choice",
        lambda _root: SimpleNamespace(
            class_id="class1", assignment_id="essay1", title="Current Title"
        ),
    )
    monkeypatch.setattr(
        menu,
        "load_managed_assignment_registration_context",
        lambda *_args: _context(tmp_path),
    )
    import quillan.menu as root_menu

    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)


def test_menu_cancellation_does_not_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    monkeypatch.setattr(
        menu, "load_current_quillan_academic_work_registration", lambda *_args: None
    )
    called = False

    def register(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("register should not be called")

    monkeypatch.setattr(menu, "register_quillan_academic_work", register)
    responses = iter(["1", "1", "2", "NOPE", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_work_registration_menu() == 0
    assert called is False


def test_menu_register_requires_typed_confirmation_and_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    monkeypatch.setattr(
        menu, "load_current_quillan_academic_work_registration", lambda *_args: None
    )
    created = _registration()
    captured: dict[str, object] = {}

    def register(
        *_args: object, **kwargs: object
    ) -> AcademicWorkRegistrationServiceResult:
        captured.update(kwargs)
        return AcademicWorkRegistrationServiceResult(created, "created")

    monkeypatch.setattr(menu, "register_quillan_academic_work", register)
    responses = iter(["1", "2", "2", "REGISTER", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_work_registration_menu() == 0
    assert captured == {"academic_intent": "summative", "lifecycle": "active"}
    output = capsys.readouterr().out
    assert "Proposed Academic Work Registration:" in output
    assert "contract=2" in output
    assert "Disposition: created" in output


def test_menu_update_uses_exact_observed_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    current = _registration(revision=7, title="Old Title")
    monkeypatch.setattr(
        menu, "load_current_quillan_academic_work_registration", lambda *_args: current
    )
    updated = _registration(revision=8, title="Current Title")
    captured: dict[str, object] = {}

    def update(
        *_args: object, **kwargs: object
    ) -> AcademicWorkRegistrationServiceResult:
        captured.update(kwargs)
        return AcademicWorkRegistrationServiceResult(updated, "updated")

    monkeypatch.setattr(menu, "update_quillan_academic_work_registration", update)
    responses = iter(["1", "2", "2", "UPDATE", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_work_registration_menu() == 0
    assert captured["expected_current_revision"] == 7
    assert captured["academic_intent"] == "summative"
    assert captured["lifecycle"] == "active"


def test_menu_displays_stale_title_notice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    current = _registration(title="Old Title")
    monkeypatch.setattr(
        menu, "load_current_quillan_academic_work_registration", lambda *_args: current
    )
    responses = iter(["B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_work_registration_menu() == 0
    assert "registration title is stale" in capsys.readouterr().out


def test_assignment_edit_staleness_notice_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    current = _registration(revision=3, title="Old Title")
    monkeypatch.setattr(
        menu,
        "load_current_quillan_academic_work_registration",
        lambda *_args: current,
    )
    menu.print_registration_title_staleness_notices(
        tmp_path, ["class1"], "essay1", "Current Title"
    )
    output = capsys.readouterr().out
    assert "revision 3" in output
    assert "Old Title" in output
    assert "Update" in output


def test_assignment_edit_notice_failure_does_not_fail_completed_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_args: object) -> None:
        raise RuntimeError("synthetic registry read failure")

    monkeypatch.setattr(
        menu, "load_current_quillan_academic_work_registration", fail
    )
    menu.print_registration_title_staleness_notices(
        tmp_path, ["class1"], "essay1", "Current Title"
    )
    output = capsys.readouterr().out
    assert "assignment saved" in output
    assert "Registration state was not changed" in output
