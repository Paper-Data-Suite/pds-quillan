"""Persistence tests for immutable printable-response record sets."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from pds_core.classes import load_class_roster, write_class_roster
from pds_core.rosters import StudentRecord, create_roster
from pds_core.routing_models import ModuleWorkRef
import pytest

import quillan.printable_response_persistence as persistence

from quillan.printable_response_persistence import (
    PrintableResponseIntegrityError,
    PrintableResponseLifecycleCleanupError,
    PrintableResponseLifecycleError,
    PrintableResponseNotFoundError,
    PrintableResponsePersistenceError,
    PrintableResponsePersistenceValidationError,
    PrintableResponseReadError,
    PrintableResponseRecordCollisionError,
    PrintableResponseRecordSetWriteError,
    PrintableResponseRevisionConflictError,
    canonical_printable_response_json,
    load_printable_response_issuance,
    load_printable_response_page,
    load_printable_response_page_context,
    transition_printable_response_issuance,
    write_printable_response_record_set,
)
from quillan.printable_response_records import (
    PrintableResponseRecordSet,
    build_printable_response_record_set,
)
from quillan.work_paths import (
    QuillanWorkPaths,
    _is_link_like,
    quillan_work_paths,
    quillan_work_ref,
)

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "literary_analysis"
STUDENT_ID = "00107"
GENERATION_ID = "gen_0123456789abcdef0123456789abcdef"
ARTIFACT_ID = "art_0123456789abcdef0123456789abcdef"
ISSUANCE_ID = "iss_0123456789abcdef0123456789abcdef"
FRESH_GENERATION_ID = "gen_f123456789abcdef0123456789abcdef"
FRESH_ARTIFACT_ID = "art_f123456789abcdef0123456789abcdef"
FRESH_ISSUANCE_ID = "iss_f123456789abcdef0123456789abcdef"
PAGE_IDS = (
    "pg_0123456789abcdef0123456789abcdef",
    "pg_1123456789abcdef0123456789abcdef",
)
FRESH_PAGE_IDS = (
    "pg_f123456789abcdef0123456789abcdef",
    "pg_e123456789abcdef0123456789abcdef",
)
NOW = datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc)


def assignment() -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Coming-of-Age Literary Analysis",
        "class_ids": [CLASS_ID],
        "writing_type": "literary_analysis",
        "student_prompt": "Synthetic prompt.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "synthetic_scale",
            "levels": [{"value": 1, "label": "Meets", "description": "Meets."}],
        },
        "basic_requirements": {},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": "2026-07-19T18:00:00+00:00",
        "updated_at": "2026-07-19T18:00:00+00:00",
        "module_details": {},
    }


def student() -> StudentRecord:
    return StudentRecord(CLASS_ID, STUDENT_ID, "Student", "Sample", "2", {})


def prepare_workspace(
    tmp_path: Path,
) -> tuple[QuillanWorkPaths, PrintableResponseRecordSet]:
    write_class_roster(
        tmp_path,
        create_roster(
            CLASS_ID,
            [
                {
                    "student_id": STUDENT_ID,
                    "last_name": "Student",
                    "first_name": "Sample",
                    "period": "2",
                }
            ],
        ),
    )
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    paths.work_root.mkdir(parents=True, exist_ok=True)
    paths.assignment_path.write_text(
        json.dumps(assignment(), indent=2) + "\n", encoding="utf-8"
    )
    records = build_printable_response_record_set(
        CLASS_ID,
        assignment(),
        student(),
        generation_id=GENERATION_ID,
        artifact_id=ARTIFACT_ID,
        output_kind="class_packet_pdf",
        reason="initial",
        pages_per_student=2,
        issuance_id=ISSUANCE_ID,
        page_ids=PAGE_IDS,
        class_label="English 10 Period 2",
        clock=lambda: NOW,
    )
    return paths, records


def regeneration_record_set(
    *,
    generation_id: str = FRESH_GENERATION_ID,
    artifact_id: str = FRESH_ARTIFACT_ID,
    issuance_id: str = FRESH_ISSUANCE_ID,
    page_ids: tuple[str, ...] = FRESH_PAGE_IDS,
) -> PrintableResponseRecordSet:
    return build_printable_response_record_set(
        CLASS_ID,
        assignment(),
        student(),
        generation_id=generation_id,
        artifact_id=artifact_id,
        output_kind="class_packet_pdf",
        reason="regeneration",
        predecessor_issuance_id=ISSUANCE_ID,
        pages_per_student=2,
        issuance_id=issuance_id,
        page_ids=page_ids,
        class_label="English 10 Period 2",
        clock=lambda: datetime(2026, 7, 19, 19, 30, tzinfo=timezone.utc),
    )


def additional_copy_record_set() -> PrintableResponseRecordSet:
    return build_printable_response_record_set(
        CLASS_ID,
        assignment(),
        student(),
        generation_id=FRESH_GENERATION_ID,
        artifact_id=FRESH_ARTIFACT_ID,
        output_kind="class_packet_pdf",
        reason="additional_copy",
        pages_per_student=2,
        issuance_id=FRESH_ISSUANCE_ID,
        page_ids=FRESH_PAGE_IDS,
        class_label="English 10 Period 2",
        clock=lambda: datetime(2026, 7, 19, 19, 30, tzinfo=timezone.utc),
    )


def test_exclusive_write_commits_pages_then_issuance_and_loads_context(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)

    assert persisted.issuance_path.is_file()
    assert all(path.is_file() for path in persisted.page_paths)
    assert persisted.issuance_path.read_bytes().endswith(b"\n")
    assert load_printable_response_issuance(
        tmp_path, paths.work_ref, ISSUANCE_ID
    ) == records.issuance
    context = load_printable_response_page_context(
        tmp_path, paths.work_ref, PAGE_IDS[1]
    )
    assert context.student_id == STUDENT_ID
    assert context.logical_page == 2
    assert context.total_pages == 2
    assert context.is_continuation
    assert context.member_pages == records.pages
    assert not (paths.work_root / "routes").exists()
    assert not list(paths.work_root.rglob("*.pdf"))


def test_persistence_accepts_optional_roster_columns_without_serializing_them(
    tmp_path: Path,
) -> None:
    roster = create_roster(
        CLASS_ID,
        [
            {
                "student_id": STUDENT_ID,
                "last_name": "Student",
                "first_name": "Sample",
                "period": "2",
                "email": "sample@example.test",
                "grade_level": "10",
            }
        ],
    )
    write_class_roster(tmp_path, roster)
    loaded_student = load_class_roster(tmp_path, CLASS_ID).students[0]
    paths = quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    paths.work_root.mkdir(parents=True, exist_ok=True)
    paths.assignment_path.write_text(
        json.dumps(assignment(), indent=2) + "\n", encoding="utf-8"
    )
    records = build_printable_response_record_set(
        CLASS_ID,
        assignment(),
        loaded_student,
        generation_id=GENERATION_ID,
        artifact_id=ARTIFACT_ID,
        output_kind="class_packet_pdf",
        reason="initial",
        pages_per_student=2,
        issuance_id=ISSUANCE_ID,
        page_ids=PAGE_IDS,
        clock=lambda: NOW,
    )

    persisted = write_printable_response_record_set(
        tmp_path, paths.work_ref, records
    )

    assert dict(loaded_student.extra_fields) == {
        "email": "sample@example.test",
        "grade_level": "10",
    }
    for path in (persisted.issuance_path, *persisted.page_paths):
        text = path.read_text(encoding="utf-8")
        assert "email" not in text
        assert "grade_level" not in text
        assert "extra_fields" not in text
        assert "sample@example.test" not in text


def test_collision_preserves_all_existing_bytes_and_writes_nothing_new(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    paths.response_page_records_dir.mkdir(parents=True)
    collision = paths.response_page_records_dir / f"{PAGE_IDS[1]}.json"
    collision.write_bytes(b"existing")

    with pytest.raises(PrintableResponseRecordCollisionError):
        write_printable_response_record_set(tmp_path, paths.work_ref, records)

    assert collision.read_bytes() == b"existing"
    assert not (paths.response_page_records_dir / f"{PAGE_IDS[0]}.json").exists()
    assert not (paths.response_page_issuances_dir / f"{ISSUANCE_ID}.json").exists()


def _malformed_quillan_work_ref() -> ModuleWorkRef:
    malformed = object.__new__(ModuleWorkRef)
    object.__setattr__(malformed, "module_id", "quillan")
    object.__setattr__(malformed, "class_id", [])
    object.__setattr__(malformed, "work_id", ASSIGNMENT_ID)
    return malformed


@pytest.mark.parametrize(
    "invalid_work_ref",
    [
        None,
        object(),
        ModuleWorkRef("scoreform", CLASS_ID, ASSIGNMENT_ID),
        _malformed_quillan_work_ref(),
    ],
)
@pytest.mark.parametrize(
    "operation",
    [
        "load_issuance",
        "load_page",
        "load_record_set",
        "load_page_context",
        "write_record_set",
        "transition_issuance",
    ],
)
def test_every_persistence_entry_rejects_invalid_work_refs_without_side_effects(
    tmp_path: Path,
    invalid_work_ref: object,
    operation: str,
) -> None:
    workspace = tmp_path / "workspace"
    with pytest.raises(PrintableResponsePersistenceError):
        if operation == "load_issuance":
            load_printable_response_issuance(
                workspace, invalid_work_ref, ISSUANCE_ID
            )
        elif operation == "load_page":
            load_printable_response_page(workspace, invalid_work_ref, PAGE_IDS[0])
        elif operation == "load_record_set":
            persistence.load_printable_response_record_set(
                workspace, invalid_work_ref, ISSUANCE_ID
            )
        elif operation == "load_page_context":
            load_printable_response_page_context(
                workspace, invalid_work_ref, PAGE_IDS[0]
            )
        elif operation == "write_record_set":
            write_printable_response_record_set(
                workspace, invalid_work_ref, object()
            )
        else:
            transition_printable_response_issuance(
                workspace,
                invalid_work_ref,
                ISSUANCE_ID,
                expected_revision=1,
                new_status="issued",
                timestamp="2026-07-20T00:00:00+00:00",
            )
    assert not workspace.exists()


@pytest.mark.parametrize("invalid_record_set", [None, {}, object()])
def test_write_rejects_invalid_record_sets_without_side_effects(
    tmp_path: Path, invalid_record_set: object
) -> None:
    workspace = tmp_path / "workspace"
    with pytest.raises(
        PrintableResponsePersistenceValidationError,
        match="PrintableResponseRecordSet",
    ):
        write_printable_response_record_set(
            workspace,
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
            invalid_record_set,
        )
    assert not workspace.exists()


def test_injected_later_write_failure_rolls_back_only_current_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, records = prepare_workspace(tmp_path)
    original = persistence._write_json_exclusive
    calls = 0

    def fail_second(path: Path, value: dict[str, object]) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic write failure")
        return original(path, value)

    monkeypatch.setattr(persistence, "_write_json_exclusive", fail_second)
    with pytest.raises(PrintableResponseRecordSetWriteError, match="rolled back"):
        write_printable_response_record_set(tmp_path, paths.work_ref, records)

    assert not list(paths.response_page_records_dir.glob("*.json"))
    assert not list(paths.response_page_issuances_dir.glob("*.json"))


def test_rollback_preserves_page_replaced_by_competing_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, records = prepare_workspace(tmp_path)
    unrelated = paths.work_root / "unrelated.json"
    unrelated.write_bytes(b"existing unrelated bytes")
    original = persistence._write_json_exclusive
    competing_bytes = b"competing writer bytes\n"
    calls = 0

    def compete_then_fail(path: Path, value: dict[str, object]) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            paths.response_page_records_dir.joinpath(
                f"{PAGE_IDS[0]}.json"
            ).write_bytes(competing_bytes)
            raise OSError("synthetic second-page failure")
        return original(path, value)

    monkeypatch.setattr(persistence, "_write_json_exclusive", compete_then_fail)
    with pytest.raises(persistence.PrintableResponseRollbackError, match=PAGE_IDS[0]):
        write_printable_response_record_set(tmp_path, paths.work_ref, records)

    assert (paths.response_page_records_dir / f"{PAGE_IDS[0]}.json").read_bytes() == competing_bytes
    assert unrelated.read_bytes() == b"existing unrelated bytes"


def test_rollback_preserves_entry_that_becomes_link_like(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, records = prepare_workspace(tmp_path)
    original_write = persistence._write_json_exclusive
    original_is_link_like = _is_link_like
    first_path = paths.response_page_records_dir / f"{PAGE_IDS[0]}.json"
    competed = False
    calls = 0

    def mark_then_fail(path: Path, value: dict[str, object]) -> object:
        nonlocal calls, competed
        calls += 1
        if calls == 2:
            competed = True
            raise OSError("synthetic second-page failure")
        return original_write(path, value)

    def simulate_link_like(path: Path) -> bool:
        return (competed and path == first_path) or original_is_link_like(path)

    monkeypatch.setattr(persistence, "_write_json_exclusive", mark_then_fail)
    monkeypatch.setattr(
        "quillan.printable_response_persistence._is_link_like", simulate_link_like
    )
    with pytest.raises(persistence.PrintableResponseRollbackError, match=PAGE_IDS[0]):
        write_printable_response_record_set(tmp_path, paths.work_ref, records)
    assert first_path.is_file()


def test_snapshot_mismatch_fails_before_record_directories_are_created(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    changed = assignment()
    changed["title"] = "Changed title"
    paths.assignment_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(PrintableResponsePersistenceValidationError, match="snapshot"):
        write_printable_response_record_set(tmp_path, paths.work_ref, records)

    assert not paths.response_pages_dir.exists()


def test_strict_loader_rejects_duplicate_keys_nan_and_identity_mismatch(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    persisted.page_paths[0].write_text(
        '{"page_id":"x","page_id":"y"}\n', encoding="utf-8"
    )
    with pytest.raises(PrintableResponseReadError, match="Duplicate"):
        load_printable_response_page(tmp_path, paths.work_ref, PAGE_IDS[0])

    persisted.page_paths[0].write_text('{"value": NaN}\n', encoding="utf-8")
    with pytest.raises(PrintableResponseReadError, match="constant"):
        load_printable_response_page(tmp_path, paths.work_ref, PAGE_IDS[0])

    persisted.page_paths[0].write_bytes(
        canonical_printable_response_json(records.pages[1].to_mapping())
    )
    with pytest.raises(PrintableResponseIntegrityError, match="filename"):
        load_printable_response_page(tmp_path, paths.work_ref, PAGE_IDS[0])


@pytest.mark.parametrize(
    ("record_kind", "field", "malformed"),
    [
        ("issuance", "output_kind", []),
        ("issuance", "reason", {}),
        ("issuance", "status", []),
        ("issuance", "class_label", 12),
        ("issuance", "schema_version", None),
        ("page", "page_role", {}),
        ("page", "page_role", True),
        ("page", "schema_version", None),
    ],
)
def test_malformed_nested_record_types_raise_typed_read_errors(
    tmp_path: Path, record_kind: str, field: str, malformed: object
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    if record_kind == "issuance":
        mapping = records.issuance.to_mapping()
        if field in {"output_kind", "reason"}:
            mapping["generation_context"][field] = malformed
        elif field == "status":
            mapping["lifecycle"][field] = malformed
        else:
            mapping[field] = malformed
        persisted.issuance_path.write_bytes(canonical_printable_response_json(mapping))
    else:
        mapping = records.pages[0].to_mapping()
        mapping[field] = malformed
        persisted.page_paths[0].write_bytes(canonical_printable_response_json(mapping))
    with pytest.raises(PrintableResponseReadError):
        if record_kind == "issuance":
            load_printable_response_issuance(tmp_path, paths.work_ref, ISSUANCE_ID)
        else:
            load_printable_response_page(tmp_path, paths.work_ref, PAGE_IDS[0])


@pytest.mark.parametrize(
    ("generation_id", "artifact_id", "page_ids", "expected"),
    [
        (GENERATION_ID, FRESH_ARTIFACT_ID, FRESH_PAGE_IDS, "generation_id"),
        (FRESH_GENERATION_ID, ARTIFACT_ID, FRESH_PAGE_IDS, "artifact_id"),
        (FRESH_GENERATION_ID, FRESH_ARTIFACT_ID, (PAGE_IDS[0], FRESH_PAGE_IDS[1]), "page_ids"),
    ],
)
def test_regeneration_rejects_reused_identities_without_mutating_predecessor(
    tmp_path: Path,
    generation_id: str,
    artifact_id: str,
    page_ids: tuple[str, ...],
    expected: str,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    predecessor = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    before = {
        path: path.read_bytes()
        for path in (predecessor.issuance_path, *predecessor.page_paths)
    }
    replacement = regeneration_record_set(
        generation_id=generation_id,
        artifact_id=artifact_id,
        page_ids=page_ids,
    )

    with pytest.raises(PrintableResponsePersistenceValidationError, match=expected):
        write_printable_response_record_set(tmp_path, paths.work_ref, replacement)

    assert {path: path.read_bytes() for path in before} == before


def test_regeneration_with_all_fresh_identities_preserves_predecessor_bytes(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    predecessor = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    before = {
        path: path.read_bytes()
        for path in (predecessor.issuance_path, *predecessor.page_paths)
    }

    replacement = write_printable_response_record_set(
        tmp_path, paths.work_ref, regeneration_record_set()
    )

    assert replacement.record_set.issuance.generation_id == FRESH_GENERATION_ID
    assert replacement.record_set.issuance.artifact_id == FRESH_ARTIFACT_ID
    assert replacement.record_set.issuance.issuance_id == FRESH_ISSUANCE_ID
    assert replacement.record_set.issuance.page_ids == FRESH_PAGE_IDS
    assert {path: path.read_bytes() for path in before} == before

def test_loading_remains_authoritative_after_roster_and_assignment_change(
    tmp_path: Path,
) -> None:
    paths, records = prepare_workspace(tmp_path)
    write_printable_response_record_set(tmp_path, paths.work_ref, records)
    changed = assignment()
    changed["title"] = "Later title"
    changed["updated_at"] = "2026-07-20T18:00:00+00:00"
    paths.assignment_path.write_text(json.dumps(changed), encoding="utf-8")
    write_class_roster(
        tmp_path,
        create_roster(
            CLASS_ID,
            [
                {
                    "student_id": "00999",
                    "last_name": "Other",
                    "first_name": "Learner",
                    "period": "2",
                }
            ],
        ),
        overwrite=True,
    )

    context = load_printable_response_page_context(
        tmp_path, paths.work_ref, PAGE_IDS[0]
    )
    assert context.student_id == STUDENT_ID
    assert context.issuance.assignment_snapshot.title == assignment()["title"]


def test_revision_guarded_lifecycle_changes_only_issuance_bytes(tmp_path: Path) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    page_bytes = tuple(path.read_bytes() for path in persisted.page_paths)

    issued = transition_printable_response_issuance(
        tmp_path,
        paths.work_ref,
        ISSUANCE_ID,
        expected_revision=1,
        new_status="issued",
        timestamp="2026-07-19T18:31:00+00:00",
    )
    assert issued.lifecycle.status == "issued"
    assert issued.lifecycle.revision == 2
    with pytest.raises(PrintableResponseRevisionConflictError):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status="invalidated",
            timestamp="2026-07-19T18:32:00+00:00",
            reason="Synthetic administrative decision",
        )
    invalidated = transition_printable_response_issuance(
        tmp_path,
        paths.work_ref,
        ISSUANCE_ID,
        expected_revision=2,
        new_status="invalidated",
        timestamp="2026-07-19T18:32:00+00:00",
        reason="Synthetic administrative decision",
    )
    assert invalidated.lifecycle.revision == 3
    assert tuple(path.read_bytes() for path in persisted.page_paths) == page_bytes


def test_lifecycle_rejects_bytes_changed_after_revision_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    original_replace = persistence._atomic_replace_issuance
    competing_bytes = b"synthetic competing lifecycle write\n"

    def compete_then_replace(
        path: Path,
        issuance: object,
        *,
        expected_bytes: bytes,
    ) -> None:
        path.write_bytes(competing_bytes)
        original_replace(path, issuance, expected_bytes=expected_bytes)  # type: ignore[arg-type]

    monkeypatch.setattr(persistence, "_atomic_replace_issuance", compete_then_replace)
    with pytest.raises(PrintableResponseRevisionConflictError, match="changed"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status="issued",
            timestamp="2026-07-19T18:31:00+00:00",
        )

    assert persisted.issuance_path.read_bytes() == competing_bytes
    assert not list(persisted.issuance_path.parent.glob("*.tmp"))


def test_lifecycle_temporary_cleanup_failure_is_surfaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    original_bytes = persisted.issuance_path.read_bytes()
    original_unlink = Path.unlink

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("synthetic replacement failure")

    def fail_temporary_unlink(
        path: Path, missing_ok: bool = False
    ) -> None:
        if path.suffix == ".tmp":
            raise OSError("synthetic cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(os, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_temporary_unlink)
    with pytest.raises(PrintableResponseLifecycleCleanupError) as caught:
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status="issued",
            timestamp="2026-07-19T18:31:00+00:00",
        )

    assert ".tmp" in str(caught.value)
    assert "synthetic replacement failure" in str(caught.value)
    assert "synthetic cleanup failure" in str(caught.value)
    assert persisted.issuance_path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "transition_case",
    [
        "prepared_to_issued",
        "prepared_to_cancelled",
        "prepared_to_invalidated",
        "issued_to_superseded",
        "issued_to_invalidated",
    ],
)
def test_every_allowed_persisted_transition_preserves_all_page_bytes(
    tmp_path: Path, transition_case: str
) -> None:
    paths, records = prepare_workspace(tmp_path)
    persisted = write_printable_response_record_set(tmp_path, paths.work_ref, records)
    tracked_pages = list(persisted.page_paths)
    before = {path: path.read_bytes() for path in tracked_pages}

    if transition_case.startswith("issued_to_"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status="issued",
            timestamp="2026-07-19T18:31:00+00:00",
        )
        if transition_case == "issued_to_superseded":
            replacement = write_printable_response_record_set(
                tmp_path, paths.work_ref, additional_copy_record_set()
            )
            tracked_pages.extend(replacement.page_paths)
            before.update({path: path.read_bytes() for path in replacement.page_paths})
            transition_printable_response_issuance(
                tmp_path,
                paths.work_ref,
                FRESH_ISSUANCE_ID,
                expected_revision=1,
                new_status="issued",
                timestamp="2026-07-19T19:31:00+00:00",
            )
            result = transition_printable_response_issuance(
                tmp_path,
                paths.work_ref,
                ISSUANCE_ID,
                expected_revision=2,
                new_status="superseded",
                timestamp="2026-07-19T19:32:00+00:00",
                reason="Fresh issued replacement",
                replacement_issuance_id=FRESH_ISSUANCE_ID,
            )
        else:
            result = transition_printable_response_issuance(
                tmp_path,
                paths.work_ref,
                ISSUANCE_ID,
                expected_revision=2,
                new_status="invalidated",
                timestamp="2026-07-19T18:32:00+00:00",
                reason="Synthetic integrity decision",
            )
    else:
        new_status = transition_case.removeprefix("prepared_to_")
        result = transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status=new_status,
            timestamp="2026-07-19T18:31:00+00:00",
            reason=(
                "Synthetic terminal decision"
                if new_status in {"cancelled", "invalidated"}
                else None
            ),
        )

    assert result.lifecycle.status == transition_case.rsplit("_to_", 1)[1]
    assert {path: path.read_bytes() for path in tracked_pages} == before


def test_supersession_replacement_rules_are_enforced(tmp_path: Path) -> None:
    paths, records = prepare_workspace(tmp_path)
    write_printable_response_record_set(tmp_path, paths.work_ref, records)
    transition_printable_response_issuance(
        tmp_path,
        paths.work_ref,
        ISSUANCE_ID,
        expected_revision=1,
        new_status="issued",
        timestamp="2026-07-19T18:31:00+00:00",
    )

    with pytest.raises(PrintableResponseNotFoundError):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=2,
            new_status="superseded",
            timestamp="2026-07-19T19:32:00+00:00",
            reason="Missing replacement",
            replacement_issuance_id=FRESH_ISSUANCE_ID,
        )

    replacement = write_printable_response_record_set(
        tmp_path, paths.work_ref, additional_copy_record_set()
    )
    with pytest.raises(PrintableResponseLifecycleError, match="already be issued"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=2,
            new_status="superseded",
            timestamp="2026-07-19T19:32:00+00:00",
            reason="Prepared replacement",
            replacement_issuance_id=FRESH_ISSUANCE_ID,
        )

    transition_printable_response_issuance(
        tmp_path,
        paths.work_ref,
        FRESH_ISSUANCE_ID,
        expected_revision=1,
        new_status="issued",
        timestamp="2026-07-19T19:31:00+00:00",
    )
    with pytest.raises(PrintableResponseLifecycleError, match="itself"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=2,
            new_status="superseded",
            timestamp="2026-07-19T19:32:00+00:00",
            reason="Self replacement",
            replacement_issuance_id=ISSUANCE_ID,
        )

    replacement_issuance = load_printable_response_issuance(
        tmp_path, paths.work_ref, FRESH_ISSUANCE_ID
    )
    mismatched = replace(replacement_issuance, student_id="00999")
    replacement.issuance_path.write_bytes(
        canonical_printable_response_json(mismatched.to_mapping())
    )
    with pytest.raises(PrintableResponseLifecycleError, match="share class"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=2,
            new_status="superseded",
            timestamp="2026-07-19T19:32:00+00:00",
            reason="Wrong student replacement",
            replacement_issuance_id=FRESH_ISSUANCE_ID,
        )


def test_lifecycle_rejects_timestamp_before_stored_timestamp(tmp_path: Path) -> None:
    paths, records = prepare_workspace(tmp_path)
    write_printable_response_record_set(tmp_path, paths.work_ref, records)
    with pytest.raises(PrintableResponseLifecycleError, match="precedes"):
        transition_printable_response_issuance(
            tmp_path,
            paths.work_ref,
            ISSUANCE_ID,
            expected_revision=1,
            new_status="issued",
            timestamp="2026-07-19T18:29:00+00:00",
        )
