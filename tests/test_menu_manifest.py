"""Teacher-menu tests for explicit immutable Academic Result Manifests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import pytest

import quillan.assignment_workflows as assignment_workflows
import quillan.manifest_menu as menu
from quillan.academic_result_manifest import (
    AcademicResultManifest,
    manifest_from_mapping,
    manifest_to_canonical_json_bytes,
)
from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    StoredAcademicResultManifest,
)
from tests.test_academic_result_manifest import valid_mapping


def _manifest() -> AcademicResultManifest:
    mapping = valid_mapping()
    mapping["record_set"]["record_set_id"] = "academic_results"
    mapping["record_set"]["revision"] = 1
    mapping["work"]["class_id"] = "english12_p3"
    mapping["work"]["work_id"] = "villainy_essay"
    mapping["assignment"]["assignment_id"] = "villainy_essay"
    mapping["students"] = []
    return manifest_from_mapping(mapping)


def _result(tmp_path: Path) -> AcademicResultManifestGenerationResult:
    manifest = _manifest()
    content = manifest_to_canonical_json_bytes(manifest)
    relative = (
        "classes/english12_p3/modules/quillan/work/villainy_essay/"
        "exports/manifests/academic_results/1.json"
    )
    return AcademicResultManifestGenerationResult(
        disposition="create_initial",
        reason="initial_publication",
        manifest=manifest,
        revision=1,
        path=tmp_path.joinpath(*Path(relative).parts),
        relative_path=relative,
        content=content,
        sha256=sha256(content).hexdigest(),
    )


def _stored(tmp_path: Path) -> StoredAcademicResultManifest:
    result = _result(tmp_path)
    return StoredAcademicResultManifest(
        manifest=result.manifest,
        revision=result.revision,
        path=result.path,
        relative_path=result.relative_path,
        content=result.content,
        sha256=result.sha256,
    )


def _patch_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(menu, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        menu,
        "prompt_assignment_choice",
        lambda _root: SimpleNamespace(
            class_id="english12_p3",
            assignment_id="villainy_essay",
            title="Villainy Essay",
        ),
    )
    context = SimpleNamespace(
        assignment=SimpleNamespace(title="Villainy Essay"),
        native_students=(),
    )
    monkeypatch.setattr(
        menu,
        "load_academic_result_manifest_generation_context",
        lambda *_args: context,
    )
    monkeypatch.setattr(
        menu, "list_academic_result_manifest_revisions", lambda *_args: ()
    )
    monkeypatch.setattr(
        menu,
        "load_current_quillan_academic_work_registration",
        lambda *_args: None,
    )
    import quillan.menu as root_menu

    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)


def test_manifest_menu_cancellation_does_not_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    called = False

    def generate(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("generation should not be called")

    monkeypatch.setattr(menu, "generate_academic_result_manifest", generate)
    responses = iter(["1", "NOPE", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_result_manifest_menu() == 0
    assert called is False


def test_manifest_menu_requires_generate_and_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_shell(monkeypatch, tmp_path)
    result = _result(tmp_path)
    calls = 0

    def generate(
        *_args: object, **_kwargs: object
    ) -> AcademicResultManifestGenerationResult:
        nonlocal calls
        calls += 1
        return result

    monkeypatch.setattr(menu, "generate_academic_result_manifest", generate)
    responses = iter(["1", "GENERATE", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    assert menu.launch_academic_result_manifest_menu() == 0
    assert calls == 1
    output = capsys.readouterr().out
    assert "Proposed operation:" in output
    assert "does not publish through Core" in output
    assert "Disposition: create_initial" in output
    assert "Manifest SHA-256:" in output


def test_assignment_management_routes_option_five_to_manifest_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = 0

    def launch() -> int:
        nonlocal called
        called += 1
        return 0

    monkeypatch.setattr(menu, "launch_academic_result_manifest_menu", launch)
    import quillan.menu as root_menu

    monkeypatch.setattr(root_menu, "clear_screen", lambda: None)
    monkeypatch.setattr(root_menu, "pause_for_user", lambda: None)
    monkeypatch.setattr(root_menu, "print_menu_header", lambda _title=None: None)
    responses = iter(["5", "B"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert assignment_workflows.launch_assignment_menu() == 0
    assert called == 1


def test_menu_history_display_contains_no_student_ids(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    menu._print_history((_stored(tmp_path),))
    output = capsys.readouterr().out
    assert "students 0" in output
    assert "student_" not in output
