from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest
from pds_core.academic_work_registrations import (
    AcademicWorkIntent,
    AcademicWorkRegistrationLifecycle,
)
from pds_core.registry_services import (
    RegistryServicePartialState,
    RegistryServicePartialSuccessError,
)

import quillan.academic_work_registration as registration_module
from quillan.academic_work_registration import (
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_WORK_KIND,
    QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
    QuillanAcademicWorkRegistrationConflictError,
    QuillanAcademicWorkRegistrationNotFoundError,
    QuillanAcademicWorkRegistrationValidationError,
    build_quillan_academic_work_registration_request,
    load_current_quillan_academic_work_registration,
    load_managed_assignment_registration_context,
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)
from quillan.work_paths import QuillanWorkPaths, quillan_work_paths


def _assignment(
    *, title: str = "Unit Essay", class_ids: list[str] | None = None
) -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": "essay1",
        "title": title,
        "class_ids": class_ids or ["class1"],
        "writing_type": "literary_analysis",
        "student_prompt": "Analyze the text.",
        "standards_profile_id": "ela_profile",
        "focus_standard_ids": ["njsls-ela:W.AW.9-10.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_4_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."},
                {"value": 2, "label": "Approaching", "description": "Approaching."},
                {"value": 3, "label": "Meeting", "description": "Meeting."},
                {"value": 4, "label": "Exceeding", "description": "Exceeding."},
            ],
        },
        "basic_requirements": {"paragraphs_min": 3},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-08-01T00:00:00+00:00",
        "module_details": {},
    }


def _managed_assignment(
    tmp_path: Path, *, title: str = "Unit Essay", class_ids: list[str] | None = None
) -> QuillanWorkPaths:
    paths = quillan_work_paths(tmp_path, "class1", "essay1")
    paths.work_root.mkdir(parents=True)
    paths.assignment_path.write_text(
        json.dumps(_assignment(title=title, class_ids=class_ids)), encoding="utf-8"
    )
    return paths


def test_exact_contract_mapping_is_immutable_and_pure(tmp_path: Path) -> None:
    paths = _managed_assignment(tmp_path)
    context = load_managed_assignment_registration_context(
        tmp_path, "class1", "essay1"
    )
    request = build_quillan_academic_work_registration_request(
        context, academic_intent="summative", lifecycle="active"
    )

    assert request.work.module_id == "quillan"
    assert request.work.class_id == "class1"
    assert request.work.work_id == "essay1"
    assert request.producer_contract_version == QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION
    assert request.producer_contract_version == "quillan_academic_work_v1"
    assert request.title == "Unit Essay"
    assert request.work_kind == QUILLAN_ACADEMIC_WORK_KIND == "assignment"
    assert request.academic_intent == "summative"
    assert request.lifecycle == "active"
    assert len(request.source_records) == 1
    source = request.source_records[0]
    assert source.module_id == "quillan"
    assert source.record_kind == QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND == "assignment"
    assert source.record_id == "essay1"
    assert source.contract_version == QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION == "2"
    assert not (tmp_path / "registry").exists()
    assert paths.assignment_path.exists()
    with pytest.raises(FrozenInstanceError):
        setattr(request, "title", "Changed")


@pytest.mark.parametrize(
    "intent,lifecycle",
    [("exam", "active"), ("summative", "finished")],
)
def test_request_rejects_unsupported_explicit_values(
    tmp_path: Path, intent: str, lifecycle: str
) -> None:
    _managed_assignment(tmp_path)
    context = load_managed_assignment_registration_context(
        tmp_path, "class1", "essay1"
    )
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        build_quillan_academic_work_registration_request(
            context,
            academic_intent=cast(AcademicWorkIntent, intent),
            lifecycle=cast(AcademicWorkRegistrationLifecycle, lifecycle),
        )
    assert not (tmp_path / "registry").exists()


def test_missing_assignment_is_rejected_without_registry(tmp_path: Path) -> None:
    with pytest.raises(QuillanAcademicWorkRegistrationNotFoundError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


def test_assignment_identity_and_class_membership_are_required(tmp_path: Path) -> None:
    paths = _managed_assignment(tmp_path)
    data = json.loads(paths.assignment_path.read_text(encoding="utf-8"))
    data["assignment_id"] = "other"
    paths.assignment_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")

    paths.assignment_path.write_text(
        json.dumps(_assignment(class_ids=["class2"])), encoding="utf-8"
    )
    with pytest.raises(
        QuillanAcademicWorkRegistrationValidationError, match="not included"
    ):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


def test_linked_assignment_fails_closed(tmp_path: Path) -> None:
    paths = quillan_work_paths(tmp_path, "class1", "essay1")
    paths.work_root.mkdir(parents=True)
    target = tmp_path / "external_assignment.json"
    target.write_text(json.dumps(_assignment()), encoding="utf-8")
    try:
        paths.assignment_path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


def test_create_exact_replay_and_update_preserve_producer_bytes(tmp_path: Path) -> None:
    paths = _managed_assignment(tmp_path)
    assignment_bytes = paths.assignment_path.read_bytes()
    submission_path = paths.submissions_dir / "student1" / "submission.json"
    submission_path.parent.mkdir(parents=True)
    submission_path.write_text('{"sentinel":"submission"}', encoding="utf-8")
    review_path = submission_path.with_name("review.json")
    review_path.write_text('{"sentinel":"review"}', encoding="utf-8")
    submission_bytes = submission_path.read_bytes()
    review_bytes = review_path.read_bytes()

    created = register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="planned",
    )
    assert created.disposition == "created"
    assert created.registration.registration_revision == 1
    revision_one = tmp_path / "registry/work/class1/quillan/essay1/revisions/1.json"
    current = tmp_path / "registry/work/class1/quillan/essay1/current.json"
    revision_bytes = revision_one.read_bytes()
    current_bytes = current.read_bytes()

    replay = register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="planned",
    )
    assert replay.disposition == "existing"
    assert replay.registration == created.registration
    assert revision_one.read_bytes() == revision_bytes
    assert current.read_bytes() == current_bytes
    assert not revision_one.with_name("2.json").exists()

    updated = update_quillan_academic_work_registration(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="summative",
        lifecycle="active",
        expected_current_revision=1,
    )
    assert updated.disposition == "updated"
    assert updated.registration.registration_revision == 2
    assert updated.registration.created_at == created.registration.created_at
    assert revision_one.read_bytes() == revision_bytes
    assert paths.assignment_path.read_bytes() == assignment_bytes
    assert submission_path.read_bytes() == submission_bytes
    assert review_path.read_bytes() == review_bytes
    assert not (tmp_path / "registry/publications").exists()
    assert not (tmp_path / "registry/withdrawals").exists()
    assert not (tmp_path / "registry/catalog.sqlite").exists()
    assert not (tmp_path / "settings/academic_periods").exists()
    assert not (tmp_path / "registry/.locks").exists()


def test_title_change_requires_explicit_update(tmp_path: Path) -> None:
    paths = _managed_assignment(tmp_path, title="Original")
    created = register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="active",
    )
    data = json.loads(paths.assignment_path.read_text(encoding="utf-8"))
    data["title"] = "Corrected"
    data["updated_at"] = "2026-08-02T00:00:00+00:00"
    paths.assignment_path.write_text(json.dumps(data), encoding="utf-8")

    current = load_current_quillan_academic_work_registration(
        tmp_path, "class1", "essay1"
    )
    assert current == created.registration
    assert current is not None and current.title == "Original"

    updated = update_quillan_academic_work_registration(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="active",
        expected_current_revision=1,
    )
    assert updated.registration.registration_revision == 2
    assert updated.registration.title == "Corrected"


def test_show_loader_preserves_audit_visibility_after_class_removed(
    tmp_path: Path,
) -> None:
    paths = _managed_assignment(tmp_path)
    created = register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="active",
    )
    data = json.loads(paths.assignment_path.read_text(encoding="utf-8"))
    data["class_ids"] = ["class2"]
    paths.assignment_path.write_text(json.dumps(data), encoding="utf-8")

    assert (
        load_current_quillan_academic_work_registration(tmp_path, "class1", "essay1")
        == created.registration
    )
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        update_quillan_academic_work_registration(
            tmp_path,
            "class1",
            "essay1",
            academic_intent="formative",
            lifecycle="active",
            expected_current_revision=1,
        )


def test_conflicting_initial_and_stale_update_fail_closed(tmp_path: Path) -> None:
    _managed_assignment(tmp_path)
    register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="planned",
    )
    with pytest.raises(QuillanAcademicWorkRegistrationConflictError):
        register_quillan_academic_work(
            tmp_path,
            "class1",
            "essay1",
            academic_intent="summative",
            lifecycle="planned",
        )
    update_quillan_academic_work_registration(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="summative",
        lifecycle="active",
        expected_current_revision=1,
    )
    with pytest.raises(QuillanAcademicWorkRegistrationConflictError):
        update_quillan_academic_work_registration(
            tmp_path,
            "class1",
            "essay1",
            academic_intent="diagnostic",
            lifecycle="active",
            expected_current_revision=1,
        )


def test_stale_equivalent_update_is_idempotent(tmp_path: Path) -> None:
    _managed_assignment(tmp_path)
    register_quillan_academic_work(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="formative",
        lifecycle="planned",
    )
    updated = update_quillan_academic_work_registration(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="summative",
        lifecycle="active",
        expected_current_revision=1,
    )
    replay = update_quillan_academic_work_registration(
        tmp_path,
        "class1",
        "essay1",
        academic_intent="summative",
        lifecycle="active",
        expected_current_revision=1,
    )
    assert replay.disposition == "existing"
    assert replay.registration == updated.registration


@pytest.mark.parametrize("revision", [True, 0, -1])
def test_update_requires_positive_non_boolean_revision(
    tmp_path: Path, revision: int
) -> None:
    _managed_assignment(tmp_path)
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        update_quillan_academic_work_registration(
            tmp_path,
            "class1",
            "essay1",
            academic_intent="formative",
            lifecycle="active",
            expected_current_revision=revision,
        )
    assert not (tmp_path / "registry").exists()


def test_core_partial_success_state_and_cause_are_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _managed_assignment(tmp_path)
    state = RegistryServicePartialState(
        operation="register_academic_work",
        registration=None,
        publication=None,
        withdrawal=None,
        canonical_path=tmp_path / "registry/work/candidate.json",
        current_selected=False,
        message="revision durable; pointer uncertain",
    )
    core_error = RegistryServicePartialSuccessError("partial", state)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise core_error

    monkeypatch.setattr(registration_module, "register_academic_work", fail)
    with pytest.raises(
        registration_module.QuillanAcademicWorkRegistrationPartialSuccessError
    ) as captured:
        register_quillan_academic_work(
            tmp_path,
            "class1",
            "essay1",
            academic_intent="formative",
            lifecycle="planned",
        )
    assert captured.value.state is state
    assert captured.value.__cause__ is core_error
    assert not (tmp_path / "registry").exists()


def test_registration_writes_are_isolated_to_explicit_quillan_boundary() -> None:
    quillan_root = Path(registration_module.__file__).parent
    wrapper_callers: set[str] = set()
    for source_path in quillan_root.rglob("*.py"):
        relative = source_path.relative_to(quillan_root).as_posix()
        source = source_path.read_text(encoding="utf-8")
        if source_path.name != "academic_work_registration.py":
            assert "register_academic_work(" not in source, relative
            assert "update_academic_work_registration(" not in source, relative
        if (
            "register_quillan_academic_work(" in source
            or "update_quillan_academic_work_registration(" in source
        ):
            wrapper_callers.add(relative)

    assert wrapper_callers == {
        "academic_work_menu.py",
        "academic_work_registration.py",
        "cli_app/handlers/academic_work.py",
    }
    boundary_source = Path(registration_module.__file__).read_text(encoding="utf-8")
    assert "write_academic_work_registration" not in boundary_source


def test_supported_vocabularies_are_exact() -> None:
    assert registration_module.SUPPORTED_ACADEMIC_INTENTS == (
        "formative",
        "summative",
        "diagnostic",
        "practice",
        "feedback_only",
        "reporting_only",
    )
    assert registration_module.SUPPORTED_ACADEMIC_WORK_LIFECYCLES == (
        "planned",
        "active",
        "closed",
        "cancelled",
    )


def test_linked_work_root_fails_closed(tmp_path: Path) -> None:
    external = tmp_path / "external_work"
    external.mkdir()
    canonical = quillan_work_paths(tmp_path, "class1", "essay1").work_root
    canonical.parent.mkdir(parents=True)
    try:
        canonical.symlink_to(external, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(module="scoreform"),
        lambda data: data.update(record_type="quiz"),
        lambda data: data.update(schema_version="1"),
    ],
)
def test_wrong_assignment_contract_fails_closed(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> None:
    paths = _managed_assignment(tmp_path)
    data = json.loads(paths.assignment_path.read_text(encoding="utf-8"))
    mutate(data)
    paths.assignment_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


def test_malformed_assignment_json_fails_closed(tmp_path: Path) -> None:
    paths = _managed_assignment(tmp_path)
    paths.assignment_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(QuillanAcademicWorkRegistrationValidationError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not (tmp_path / "registry").exists()


def test_public_registration_api_accepts_identity_not_arbitrary_assignment_path(
) -> None:
    import inspect

    for function in (
        registration_module.load_managed_assignment_registration_context,
        registration_module.load_current_quillan_academic_work_registration,
        registration_module.register_quillan_academic_work,
        registration_module.update_quillan_academic_work_registration,
    ):
        parameters = inspect.signature(function).parameters
        assert "assignment_path" not in parameters
        assert "source_path" not in parameters


def test_context_loading_missing_work_creates_nothing(tmp_path: Path) -> None:
    expected = quillan_work_paths(tmp_path, "class1", "essay1").work_root
    with pytest.raises(QuillanAcademicWorkRegistrationNotFoundError):
        load_managed_assignment_registration_context(tmp_path, "class1", "essay1")
    assert not expected.exists()
    assert not (tmp_path / "registry").exists()
