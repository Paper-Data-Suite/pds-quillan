"""Focused contract/service acceptance for issue #381 Slice 1."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)
import pytest

import quillan.review_configuration_presets as presets_module
from quillan.assignment_workflows import (
    build_assignment_config,
    write_assignment_config,
)
from quillan.atomic_record_io import AtomicRecordDurabilityError
from quillan.review_configuration_presets import (
    PRESET_CONFIGURATION_FIELDS,
    ReviewConfigurationPresetError,
    build_review_configuration_preset,
    commit_review_configuration_preset,
    inspect_review_configuration_presets,
    load_review_configuration_preset,
    plan_review_configuration_preset_creation,
    plan_review_configuration_preset_from_assignment,
    review_configuration_preset_path,
    validate_review_configuration_preset,
)
from quillan.work_paths import quillan_work_paths

STANDARD_ID = "njsls-ela:W.AW.9-10.1"
SECOND_STANDARD_ID = "njsls-ela:RL.CR.9-10.1"


def _write_standards(root: Path, *, include_second: bool = True) -> None:
    standards = [
        StandardDefinition(
            standard_id=STANDARD_ID,
            code="W.AW.9-10.1",
            source="NJSLS",
            short_name="Argument",
            description="Write arguments.",
            available_modules=("quillan",),
        )
    ]
    profile_standards = [STANDARD_ID]
    if include_second:
        standards.append(
            StandardDefinition(
                standard_id=SECOND_STANDARD_ID,
                code="RL.CR.9-10.1",
                source="NJSLS",
                short_name="Reading",
                description="Read closely.",
                available_modules=("quillan",),
            )
        )
        profile_standards.append(SECOND_STANDARD_ID)
    write_workspace_standards_library(
        root,
        StandardsLibrary(
            standards=tuple(standards),
            profiles=(
                StandardsProfile(
                    profile_id="english10_profile",
                    standards=tuple(profile_standards),
                    title="English 10",
                ),
            ),
        ),
        overwrite=True,
    )


def _rating_scale() -> dict[str, Any]:
    return {
        "scale_id": "standards_4_level",
        "levels": [
            {
                "value": 1,
                "label": "Developing",
                "description": "Limited evidence.",
            },
            {
                "value": 2,
                "label": "Meeting",
                "description": "Clear evidence.",
            },
        ],
    }


def _preset_kwargs() -> dict[str, Any]:
    return {
        "preset_id": "english10_literary_analysis",
        "title": "English 10 Literary Analysis",
        "description": "Reusable literary-analysis review configuration.",
        "writing_type": "literary_analysis",
        "standards_profile_id": "english10_profile",
        "focus_standard_ids": [STANDARD_ID, SECOND_STANDARD_ID],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": _rating_scale(),
        "basic_requirements": {
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True
        },
        "created_at": datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
    }


def _source_assignment() -> dict[str, Any]:
    return build_assignment_config(
        assignment_id="literary_analysis",
        title="Literary Analysis",
        class_ids=["english10_p2", "english10_p3"],
        writing_type="literary_analysis",
        student_prompt="Analyze how the author develops the central idea.",
        standards_profile_id="english10_profile",
        focus_standard_ids=[STANDARD_ID, SECOND_STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale=_rating_scale(),
        basic_requirements={
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
        created_at="2026-08-01T12:00:00+00:00",
    )


def test_builder_emits_exact_schema_and_defensive_configuration_copy() -> None:
    kwargs = _preset_kwargs()
    source_rating_scale = kwargs["rating_scale"]
    preset = build_review_configuration_preset(**kwargs)

    assert preset["schema_version"] == "1"
    assert preset["module"] == "quillan"
    assert preset["record_type"] == "review_configuration_preset"
    assert preset["preset_id"] == "english10_literary_analysis"
    assert preset["created_at"] == "2026-08-20T12:00:00+00:00"
    assert preset["updated_at"] == preset["created_at"]
    assert preset["module_details"] == {}
    assert set(PRESET_CONFIGURATION_FIELDS).issubset(preset)

    source_rating_scale["levels"][0]["label"] = "MUTATED"
    assert preset["rating_scale"]["levels"][0]["label"] == "Developing"


def test_validator_rejects_unknown_and_missing_top_level_fields() -> None:
    preset = build_review_configuration_preset(**_preset_kwargs())
    with_unknown = copy.deepcopy(preset)
    with_unknown["feedback_settings"] = {}
    with pytest.raises(ReviewConfigurationPresetError, match="Unknown"):
        validate_review_configuration_preset(with_unknown)

    missing = copy.deepcopy(preset)
    del missing["review_unit"]
    with pytest.raises(ReviewConfigurationPresetError, match="Missing"):
        validate_review_configuration_preset(missing)


def test_validator_rejects_duplicate_focus_standards() -> None:
    kwargs = _preset_kwargs()
    kwargs["focus_standard_ids"] = [STANDARD_ID, STANDARD_ID]
    with pytest.raises(ReviewConfigurationPresetError, match="duplicate"):
        build_review_configuration_preset(**kwargs)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("review_unit", {"type": "paragraph"}, "review_unit"),
        ("rating_scale", {"scale_id": "empty", "levels": []}, "rating_scale"),
        (
            "basic_requirements",
            {"paragraphs_min": 5, "paragraphs_max": 2},
            "paragraphs_min",
        ),
        (
            "minimum_requirement_policy",
            {"allow_return_without_full_review": "yes"},
            "minimum_requirement_policy",
        ),
    ),
)
def test_validator_reuses_assignment_v2_configuration_semantics(
    field: str,
    value: object,
    message: str,
) -> None:
    kwargs = _preset_kwargs()
    kwargs[field] = value
    with pytest.raises(ReviewConfigurationPresetError, match=message):
        build_review_configuration_preset(**kwargs)


def test_validator_rejects_bad_identity_and_timestamp_order() -> None:
    kwargs = _preset_kwargs()
    kwargs["preset_id"] = "../escape"
    with pytest.raises(ReviewConfigurationPresetError):
        build_review_configuration_preset(**kwargs)

    preset = build_review_configuration_preset(**_preset_kwargs())
    preset["updated_at"] = "2026-08-19T12:00:00+00:00"
    with pytest.raises(ReviewConfigurationPresetError, match="must not precede"):
        validate_review_configuration_preset(preset)


def test_direct_plan_is_non_mutating_and_commit_is_create_only(tmp_path: Path) -> None:
    _write_standards(tmp_path)
    expected_dir = tmp_path / "shared" / "review_configuration_presets"

    plan = plan_review_configuration_preset_creation(
        tmp_path,
        **_preset_kwargs(),
    )

    assert plan.path == expected_dir / "english10_literary_analysis.json"
    assert not expected_dir.exists()

    path = commit_review_configuration_preset(plan)
    assert path.is_file()
    assert load_review_configuration_preset(path) == plan.preset

    with pytest.raises(ReviewConfigurationPresetError, match="already exists"):
        plan_review_configuration_preset_creation(
            tmp_path,
            **_preset_kwargs(),
        )


def test_load_rejects_filename_identity_mismatch_and_malformed_json(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "shared" / "review_configuration_presets"
    directory.mkdir(parents=True)
    preset = build_review_configuration_preset(**_preset_kwargs())
    wrong = directory / "wrong_name.json"
    wrong.write_text(json.dumps(preset), encoding="utf-8")
    with pytest.raises(ReviewConfigurationPresetError, match="filename"):
        load_review_configuration_preset(wrong)

    malformed = directory / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    with pytest.raises(ReviewConfigurationPresetError, match="strict UTF-8 JSON"):
        load_review_configuration_preset(malformed)


def test_inspection_keeps_valid_invalid_and_stale_presets_independent(
    tmp_path: Path,
) -> None:
    _write_standards(tmp_path)
    valid_plan = plan_review_configuration_preset_creation(
        tmp_path,
        **_preset_kwargs(),
    )
    commit_review_configuration_preset(valid_plan)

    directory = tmp_path / "shared" / "review_configuration_presets"
    (directory / "broken.json").write_text("{bad", encoding="utf-8")

    stale_kwargs = _preset_kwargs()
    stale_kwargs["preset_id"] = "stale_preset"
    stale_kwargs["title"] = "Stale"
    stale_kwargs["focus_standard_ids"] = [STANDARD_ID]
    stale = build_review_configuration_preset(**stale_kwargs)
    stale["standards_profile_id"] = "missing_profile"
    (directory / "stale_preset.json").write_text(
        json.dumps(stale, indent=2) + "\n",
        encoding="utf-8",
    )

    items = inspect_review_configuration_presets(tmp_path)
    by_name = {item.path.name: item for item in items}
    assert by_name["english10_literary_analysis.json"].status == "valid"
    assert by_name["broken.json"].status == "invalid"
    assert by_name["stale_preset.json"].status == "stale"


def test_removed_focus_standard_makes_preset_stale_without_mutation(
    tmp_path: Path,
) -> None:
    _write_standards(tmp_path)
    plan = plan_review_configuration_preset_creation(
        tmp_path,
        **_preset_kwargs(),
    )
    _write_standards(tmp_path, include_second=False)

    with pytest.raises(ReviewConfigurationPresetError, match="standards"):
        commit_review_configuration_preset(plan)

    assert not plan.path.exists()


def test_save_from_assignment_uses_exact_positive_allowlist(tmp_path: Path) -> None:
    _write_standards(tmp_path)
    source = _source_assignment()
    source["module_details"] = {"source_only": True}
    source["future_field"] = {"must_not_copy": True}
    source_path = write_assignment_config(
        tmp_path,
        "english10_p2",
        source,
    )
    source_root = source_path.parent
    rich_state = {
        "routes/route.json": b"route",
        "scans/evidence.png": b"evidence",
        "submissions/synthetic1/review.json": b"review",
        "exports/summary.csv": b"export",
    }
    for relative, data in rich_state.items():
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source_snapshot = {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*")
        if path.is_file()
    }

    plan = plan_review_configuration_preset_from_assignment(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        preset_id="from_assignment",
        title="From Assignment",
        description="Extracted reusable configuration.",
        created_at="2026-08-20T13:00:00+00:00",
    )
    preset = plan.preset

    assert set(PRESET_CONFIGURATION_FIELDS).issubset(preset)
    for excluded in (
        "assignment_id",
        "class_ids",
        "student_prompt",
        "future_field",
    ):
        assert excluded not in preset
    assert preset["module_details"] == {}
    assert preset["created_at"] == "2026-08-20T13:00:00+00:00"

    commit_review_configuration_preset(plan)
    assert {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*")
        if path.is_file()
    } == source_snapshot


def test_multi_class_source_does_not_require_or_create_sibling_assignment(
    tmp_path: Path,
) -> None:
    _write_standards(tmp_path)
    write_assignment_config(tmp_path, "english10_p2", _source_assignment())

    plan = plan_review_configuration_preset_from_assignment(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        preset_id="multi_source",
        title="Multi source",
        description="Exact selected assignment only.",
    )
    commit_review_configuration_preset(plan)

    sibling = quillan_work_paths(
        tmp_path, "english10_p3", "literary_analysis"
    ).assignment_path
    assert not sibling.exists()


def test_source_change_after_preview_fails_closed(tmp_path: Path) -> None:
    _write_standards(tmp_path)
    source_path = write_assignment_config(
        tmp_path,
        "english10_p2",
        _source_assignment(),
    )
    plan = plan_review_configuration_preset_from_assignment(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        preset_id="stale_source",
        title="Stale source",
        description="Must re-plan after source mutation.",
    )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["title"] = "Changed title"
    source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReviewConfigurationPresetError, match="changed after preview"):
        commit_review_configuration_preset(plan)

    assert not plan.path.exists()


@pytest.mark.parametrize("mutation", ("removed", "invalid"))
def test_source_removed_or_invalid_after_preview_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    _write_standards(tmp_path)
    source_path = write_assignment_config(
        tmp_path,
        "english10_p2",
        _source_assignment(),
    )
    plan = plan_review_configuration_preset_from_assignment(
        tmp_path,
        source_class_id="english10_p2",
        source_assignment_id="literary_analysis",
        preset_id=f"source_{mutation}",
        title="Source mutation",
        description="Must fail closed.",
    )
    if mutation == "removed":
        source_path.unlink()
    else:
        source_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(
        ReviewConfigurationPresetError,
        match="changed or became unavailable",
    ):
        commit_review_configuration_preset(plan)

    assert not plan.path.exists()


def test_commit_surfaces_atomic_durability_error_without_erasing_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_standards(tmp_path)
    plan = plan_review_configuration_preset_creation(
        tmp_path,
        **_preset_kwargs(),
    )
    possibly_durable = plan.path

    def uncertain(*_args: Any, **_kwargs: Any) -> Any:
        raise AtomicRecordDurabilityError(
            "synthetic durability uncertainty",
            possibly_durable_path=possibly_durable,
        )

    monkeypatch.setattr(presets_module, "create_exclusive_record", uncertain)

    with pytest.raises(AtomicRecordDurabilityError) as error:
        commit_review_configuration_preset(plan)

    assert error.value.possibly_durable_path == possibly_durable


def test_commit_failure_cleans_new_empty_preset_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_standards(tmp_path)
    plan = plan_review_configuration_preset_creation(
        tmp_path,
        **_preset_kwargs(),
    )

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("synthetic write failure")

    monkeypatch.setattr(presets_module, "create_exclusive_record", fail)

    with pytest.raises(ReviewConfigurationPresetError, match="synthetic write failure"):
        commit_review_configuration_preset(plan)

    assert not (tmp_path / "shared" / "review_configuration_presets").exists()


def test_symlink_like_preset_directory_is_rejected_when_supported(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    link = shared / "review_configuration_presets"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(
        ReviewConfigurationPresetError,
        match="symlink|junction|reparse",
    ):
        review_configuration_preset_path(
            tmp_path,
            "english10_literary_analysis",
        )
