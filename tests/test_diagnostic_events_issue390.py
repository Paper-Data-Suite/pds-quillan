"""Issue #390 Slice 1 tests for privacy-conscious local diagnostics."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import quillan.diagnostic_events as diagnostics
from quillan.diagnostic_events import (
    DEFAULT_EVENT_RETENTION_LIMIT,
    DiagnosticEvent,
    DiagnosticEventStorageError,
    DiagnosticEventValidationError,
    build_diagnostic_event,
    diagnostic_event_path,
    diagnostic_events_dir,
    list_diagnostic_events,
    load_diagnostic_event,
    record_diagnostic_event,
    sanitize_diagnostic_path,
    try_record_diagnostic_event,
    validate_diagnostic_event,
)


CLASS_ID = "class_a"
ASSIGNMENT_ID = "assignment_a"
BASE_TIME = datetime(2026, 8, 24, 23, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fixed_core_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quillan.diagnostic_events._installed_core_version",
        lambda: "0.6.3",
    )


def _event(
    root: Path,
    *,
    event_id: str = "diag_00000000000000000000000000000001",
    occurred_at: datetime = BASE_TIME,
    code: str = "invalid_review_record",
    path: Path | None = None,
    exception: BaseException | None = None,
) -> DiagnosticEvent:
    return build_diagnostic_event(
        component="review",
        workflow="persist_review",
        stage="validate_input",
        outcome="failure",
        code=code,
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        exception=exception,
        workspace_root=root if path is not None else None,
        path=path,
        occurred_at=occurred_at,
        event_id=event_id,
    )


def test_build_event_uses_fixed_safe_contract(tmp_path: Path) -> None:
    event = _event(
        tmp_path,
        exception=RuntimeError(
            "REAL-STUDENT-WRITING-SENTINEL "
            "C:\\Users\\Teacher Name\\private\\review.json"
        ),
    )

    assert event.schema_version == "1"
    assert event.module == "quillan"
    assert event.record_type == "diagnostic_event"
    assert event.quillan_version == "0.10.3"
    assert event.core_version == "0.6.3"
    assert event.category == "review"
    assert event.code == "invalid_review_record"
    assert event.exception_type == "RuntimeError"
    assert event.safe_summary == (
        "Review record failed structural or identity validation."
    )
    assert "REAL-STUDENT" not in repr(event)
    assert "Teacher Name" not in repr(event)


def test_unknown_vocabularies_and_codes_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(DiagnosticEventValidationError):
        build_diagnostic_event(
            component="analytics",
            workflow="persist_review",
            stage="validate_input",
            outcome="failure",
            code="invalid_review_record",
            occurred_at=BASE_TIME,
        )
    with pytest.raises(DiagnosticEventValidationError):
        build_diagnostic_event(
            component="review",
            workflow="student_Avery_Rivera",
            stage="validate_input",
            outcome="failure",
            code="invalid_review_record",
            occurred_at=BASE_TIME,
        )
    with pytest.raises(DiagnosticEventValidationError):
        build_diagnostic_event(
            component="review",
            workflow="persist_review",
            stage="validate_input",
            outcome="failure",
            code="free_form_PRIVATE_NOTE",
            occurred_at=BASE_TIME,
        )


def test_safe_summary_cannot_be_replaced_with_free_text(tmp_path: Path) -> None:
    event = _event(tmp_path)
    unsafe = replace(
        event,
        safe_summary="PRIVATE-TEACHER-NOTE-SENTINEL",
    )
    with pytest.raises(DiagnosticEventValidationError):
        validate_diagnostic_event(unsafe)


def test_workspace_path_redacts_student_segment(tmp_path: Path) -> None:
    raw = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / "student_secret"
        / "review.json"
    )
    assert sanitize_diagnostic_path(
        tmp_path,
        raw,
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
    ) == (
        "classes/class_a/modules/quillan/work/assignment_a/"
        "submissions/<student>/review.json"
    )


def test_workspace_path_redacts_raw_scan_filename(tmp_path: Path) -> None:
    raw = tmp_path / "scans" / "Avery Rivera - Essay Scan.pdf"
    assert sanitize_diagnostic_path(tmp_path, raw) == "scans/<source>"


def test_outside_workspace_path_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-private.txt"
    with pytest.raises(DiagnosticEventValidationError):
        sanitize_diagnostic_path(tmp_path, outside)


def test_unsanitized_student_path_cannot_be_loaded_as_event_context(
    tmp_path: Path,
) -> None:
    event = _event(tmp_path)
    unsafe = replace(
        event,
        path_context=(
            "classes/class_a/modules/quillan/work/assignment_a/"
            "submissions/student_secret/review.json"
        ),
    )
    with pytest.raises(DiagnosticEventValidationError):
        validate_diagnostic_event(unsafe)


def test_record_creates_only_quillan_diagnostic_chain_and_exact_event(
    tmp_path: Path,
) -> None:
    event = _event(tmp_path)

    result = record_diagnostic_event(tmp_path, event)

    expected_dir = (
        tmp_path / "shared" / "quillan" / "diagnostics" / "events"
    )
    expected_path = expected_dir / f"{event.event_id}.json"
    assert diagnostic_events_dir(tmp_path) == expected_dir
    assert diagnostic_event_path(tmp_path, event.event_id) == expected_path
    assert result.relative_path == (
        f"shared/quillan/diagnostics/events/{event.event_id}.json"
    )
    assert expected_path.is_file()
    assert load_diagnostic_event(tmp_path, event.event_id) == event


def test_persisted_bytes_exclude_raw_exception_and_privacy_sentinels(
    tmp_path: Path,
) -> None:
    raw_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / "student_private"
        / "review.json"
    )
    event = _event(
        tmp_path,
        path=raw_path,
        exception=RuntimeError(
            "Avery Rivera\n"
            "REAL-STUDENT-WRITING-SENTINEL\n"
            "PRIVATE-TEACHER-NOTE-SENTINEL\n"
            "FEEDBACK-BODY-SENTINEL\n"
            "PDS2|full|qr|payload|sentinel\n"
            "C:\\Users\\Teacher Name\\Documents\\private"
        ),
    )

    result = record_diagnostic_event(tmp_path, event)
    data = (tmp_path / result.relative_path).read_text(encoding="utf-8")

    for forbidden in (
        "Avery Rivera",
        "REAL-STUDENT-WRITING-SENTINEL",
        "PRIVATE-TEACHER-NOTE-SENTINEL",
        "FEEDBACK-BODY-SENTINEL",
        "PDS2|full|qr|payload|sentinel",
        "Teacher Name",
        "student_private",
    ):
        assert forbidden not in data
    assert "<student>" in data


def test_event_file_is_immutable_and_same_id_cannot_overwrite(
    tmp_path: Path,
) -> None:
    event = _event(tmp_path)
    record_diagnostic_event(tmp_path, event)
    path = diagnostic_event_path(tmp_path, event.event_id)
    original = path.read_bytes()

    with pytest.raises(DiagnosticEventStorageError):
        record_diagnostic_event(tmp_path, event)

    assert path.read_bytes() == original


def test_list_missing_directory_is_empty_and_read_only(tmp_path: Path) -> None:
    before = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))

    listing = list_diagnostic_events(tmp_path)

    after = tuple(sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")))
    assert listing.events == ()
    assert listing.warning_codes == ()
    assert before == after == ()


def test_list_is_newest_first_and_bounded(tmp_path: Path) -> None:
    for index in range(3):
        record_diagnostic_event(
            tmp_path,
            _event(
                tmp_path,
                event_id=f"diag_{index + 1:032x}",
                occurred_at=BASE_TIME + timedelta(seconds=index),
            ),
        )

    listing = list_diagnostic_events(tmp_path, limit=2)

    assert [event.event_id for event in listing.events] == [
        "diag_00000000000000000000000000000003",
        "diag_00000000000000000000000000000002",
    ]
    with pytest.raises(DiagnosticEventValidationError):
        list_diagnostic_events(tmp_path, limit=0)
    with pytest.raises(DiagnosticEventValidationError):
        list_diagnostic_events(tmp_path, limit=diagnostics.MAX_EVENT_LIST_LIMIT + 1)


def test_malformed_and_unknown_entries_are_reported_but_not_modified(
    tmp_path: Path,
) -> None:
    event = _event(tmp_path)
    record_diagnostic_event(tmp_path, event)
    directory = diagnostic_events_dir(tmp_path)
    malformed = directory / "diag_ffffffffffffffffffffffffffffffff.json"
    malformed.write_text('{"schema_version":"1",', encoding="utf-8")
    unknown = directory / "teacher_private.txt"
    unknown.write_text("do not delete", encoding="utf-8")
    before_malformed = malformed.read_bytes()
    before_unknown = unknown.read_bytes()

    listing = list_diagnostic_events(tmp_path)

    assert listing.events == (event,)
    assert "invalid_diagnostic_event" in listing.warning_codes
    assert "unexpected_diagnostic_entry" in listing.warning_codes
    assert malformed.read_bytes() == before_malformed
    assert unknown.read_bytes() == before_unknown


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "shared" / "quillan" / "diagnostics" / "events"
    directory.mkdir(parents=True)
    event_id = "diag_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    path = directory / f"{event_id}.json"
    path.write_text(
        '{"schema_version":"1","schema_version":"1"}\n',
        encoding="utf-8",
    )

    with pytest.raises(DiagnosticEventStorageError):
        load_diagnostic_event(tmp_path, event_id)


def test_unknown_schema_fields_are_rejected(tmp_path: Path) -> None:
    event = _event(tmp_path)
    data = json.loads(diagnostics._serialize_event(event))
    data["PRIVATE_NOTE"] = "PRIVATE-TEACHER-NOTE-SENTINEL"
    directory = tmp_path / "shared" / "quillan" / "diagnostics" / "events"
    directory.mkdir(parents=True)
    path = directory / f"{event.event_id}.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(DiagnosticEventStorageError):
        load_diagnostic_event(tmp_path, event.event_id)


def test_retention_removes_only_oldest_proven_canonical_events(
    tmp_path: Path,
) -> None:
    events = []
    for index in range(4):
        event = _event(
            tmp_path,
            event_id=f"diag_{index + 1:032x}",
            occurred_at=BASE_TIME + timedelta(seconds=index),
        )
        record_diagnostic_event(tmp_path, event)
        events.append(event)

    directory = diagnostic_events_dir(tmp_path)
    malformed = directory / "diag_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.json"
    malformed.write_text('{"bad":', encoding="utf-8")
    unrelated = directory / "leave-me-alone.txt"
    unrelated.write_text("unrelated", encoding="utf-8")

    removed = diagnostics._prune_retention(tmp_path, max_events=2)

    assert removed == 2
    assert not diagnostic_event_path(tmp_path, events[0].event_id).exists()
    assert not diagnostic_event_path(tmp_path, events[1].event_id).exists()
    assert diagnostic_event_path(tmp_path, events[2].event_id).is_file()
    assert diagnostic_event_path(tmp_path, events[3].event_id).is_file()
    assert malformed.read_text(encoding="utf-8") == '{"bad":'
    assert unrelated.read_text(encoding="utf-8") == "unrelated"


def test_default_retention_contract_is_bounded() -> None:
    assert DEFAULT_EVENT_RETENTION_LIMIT == 500


def test_try_record_failure_does_not_raise_or_repair_primary_state(
    tmp_path: Path,
) -> None:
    event = _event(tmp_path)
    shared = tmp_path / "shared"
    shared.write_text("not a directory", encoding="utf-8")

    attempt = try_record_diagnostic_event(tmp_path, event)

    assert attempt.recorded is False
    assert attempt.event_id == event.event_id
    assert attempt.warning_code == "diagnostic_write_failed"
    assert shared.read_text(encoding="utf-8") == "not a directory"


def test_reading_event_does_not_rewrite_bytes(tmp_path: Path) -> None:
    event = _event(tmp_path)
    record_diagnostic_event(tmp_path, event)
    path = diagnostic_event_path(tmp_path, event.event_id)
    before = path.read_bytes()

    assert load_diagnostic_event(tmp_path, event.event_id) == event
    assert list_diagnostic_events(tmp_path).events == (event,)

    assert path.read_bytes() == before


def test_event_timestamp_requires_canonical_aware_utc(tmp_path: Path) -> None:
    with pytest.raises(DiagnosticEventValidationError):
        _event(
            tmp_path,
            occurred_at=datetime(2026, 8, 24, 23, 0, 0),
        )

    event = _event(
        tmp_path,
        occurred_at=datetime(
            2026,
            8,
            24,
            19,
            0,
            0,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
    )
    assert event.occurred_at == "2026-08-24T23:00:00.000000Z"


def test_event_id_is_opaque_and_strict(tmp_path: Path) -> None:
    event = build_diagnostic_event(
        component="review",
        workflow="persist_review",
        stage="validate_input",
        outcome="failure",
        code="invalid_review_record",
        occurred_at=BASE_TIME,
    )
    assert event.event_id.startswith("diag_")
    assert len(event.event_id) == 37
    assert CLASS_ID not in event.event_id
    assert ASSIGNMENT_ID not in event.event_id

    with pytest.raises(DiagnosticEventValidationError):
        validate_diagnostic_event(replace(event, event_id="diag_Avery_Rivera"))


def test_diagnostic_module_has_no_network_or_telemetry_dependency() -> None:
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")
    forbidden = (
        "requests",
        "urllib",
        "httpx",
        "socket",
        "sentry",
        "opentelemetry",
        "analytics",
        "telemetry",
        "upload",
    )
    lowered = source.casefold()
    for token in forbidden:
        assert token not in lowered


def test_diagnostic_module_does_not_import_suite_runtime() -> None:
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")
    assert "paper_data_suite" not in source
    assert "pds-paper-data-suite" not in source


def test_path_context_requires_matching_class_and_assignment(tmp_path: Path) -> None:
    raw = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    with pytest.raises(DiagnosticEventValidationError):
        sanitize_diagnostic_path(
            tmp_path,
            raw,
            class_id="other_class",
            assignment_id=ASSIGNMENT_ID,
        )
    with pytest.raises(DiagnosticEventValidationError):
        sanitize_diagnostic_path(
            tmp_path,
            raw,
            class_id=CLASS_ID,
            assignment_id="other_assignment",
        )
