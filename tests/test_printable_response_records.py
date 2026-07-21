"""Contract tests for immutable printable-response records."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

from pds_core.rosters import StudentRecord
from pds_core.routing_models import ModuleRecordRef
import pytest

import quillan.printable_response_persistence as response_persistence
import quillan.printable_response_records as response_records
from quillan.pds_contract import RESPONSE_PAGE_CONTRACT_VERSION
from quillan.printable_response_records import (
    PrintableResponseIssuance,
    PrintableResponseLifecycle,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    build_printable_response_record_set,
    generate_generation_id,
    printable_response_issuance_from_mapping,
    printable_response_page_from_mapping,
    response_page_target,
    transition_printable_response_lifecycle,
    validate_artifact_id,
    validate_generation_id,
    validate_issuance_id,
    validate_page_id,
)

GENERATION_ID = "gen_0123456789abcdef0123456789abcdef"
ARTIFACT_ID = "art_0123456789abcdef0123456789abcdef"
ISSUANCE_ID = "iss_0123456789abcdef0123456789abcdef"
PAGE_IDS = (
    "pg_0123456789abcdef0123456789abcdef",
    "pg_1123456789abcdef0123456789abcdef",
    "pg_2123456789abcdef0123456789abcdef",
)
NOW = datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc)


def assignment() -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": "literary_analysis",
        "title": "Coming-of-Age Literary Analysis",
        "class_ids": ["english10_p2"],
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


def student(student_id: str = "00107") -> StudentRecord:
    return StudentRecord(
        "english10_p2", student_id, "Student", "Sample", "2", {}
    )


def record_set(*, pages: int = 3, reason: str = "initial") -> PrintableResponseRecordSet:
    return build_printable_response_record_set(
        "english10_p2",
        assignment(),
        student(),
        generation_id=GENERATION_ID,
        artifact_id=ARTIFACT_ID,
        output_kind="class_packet_pdf",
        reason=reason,
        predecessor_issuance_id=(ISSUANCE_ID[:-1] + "e" if reason == "regeneration" else None),
        pages_per_student=pages,
        issuance_id=ISSUANCE_ID,
        page_ids=PAGE_IDS[:pages],
        class_label="English 10 Period 2",
        clock=lambda: NOW,
    )


@pytest.mark.parametrize(
    ("validator", "valid"),
    [
        (validate_generation_id, GENERATION_ID),
        (validate_artifact_id, ARTIFACT_ID),
        (validate_issuance_id, ISSUANCE_ID),
        (validate_page_id, PAGE_IDS[0]),
    ],
)
def test_exact_identifier_contract(
    validator: Callable[[object], str], valid: str
) -> None:
    assert validator(valid) == valid
    for invalid in (valid.upper(), valid[:-1], valid + "0", "../unsafe", True, 1, None):
        with pytest.raises(PrintableResponseRecordValidationError):
            validator(invalid)


def test_generator_uses_exactly_128_bits_and_is_injectable() -> None:
    calls: list[int] = []

    def token_hex(size: int) -> str:
        calls.append(size)
        return "a" * 32

    assert generate_generation_id(token_hex) == "gen_" + "a" * 32
    assert calls == [16]


def test_builder_is_pure_complete_frozen_and_preserves_zero_id(
    tmp_path: Path,
) -> None:
    records = record_set()
    assert records.issuance.student_id == "00107"
    assert records.issuance.page_ids == PAGE_IDS
    assert [page.logical_page for page in records.pages] == [1, 2, 3]
    assert [page.page_role for page in records.pages] == [
        "response_start",
        "continuation",
        "continuation",
    ]
    assert {page.created_at for page in records.pages} == {
        records.issuance.lifecycle.created_at
    }
    assert records.issuance.student_snapshot.display_name == "Sample Student"
    with pytest.raises(FrozenInstanceError):
        records.pages[0].page_id = PAGE_IDS[1]  # type: ignore[misc]
    assert list(tmp_path.iterdir()) == []


def test_exact_mapping_round_trip_and_unknown_missing_rejection() -> None:
    records = record_set()
    issuance_mapping = records.issuance.to_mapping()
    page_mapping = records.pages[0].to_mapping()
    assert PrintableResponseIssuance.from_mapping(issuance_mapping) == records.issuance
    assert printable_response_page_from_mapping(page_mapping) == records.pages[0]
    assert isinstance(issuance_mapping["page_ids"], list)
    for mapping, loader in (
        ({**issuance_mapping, "unknown": 1}, printable_response_issuance_from_mapping),
        ({key: value for key, value in page_mapping.items() if key != "page_id"}, printable_response_page_from_mapping),
    ):
        with pytest.raises(PrintableResponseRecordValidationError):
            loader(mapping)


def test_mapping_rejects_boolean_integer_and_nonstandard_role() -> None:
    page = record_set().pages[0].to_mapping()
    page["logical_page"] = True
    with pytest.raises(PrintableResponseRecordValidationError):
        printable_response_page_from_mapping(page)
    page = record_set().pages[0].to_mapping()
    page["page_role"] = "continuation"
    with pytest.raises(PrintableResponseRecordValidationError):
        printable_response_page_from_mapping(page)


def test_generation_context_rules_and_self_predecessor() -> None:
    with pytest.raises(PrintableResponseRecordValidationError):
        build_printable_response_record_set(
            "english10_p2",
            assignment(),
            student(),
            generation_id=GENERATION_ID,
            artifact_id=ARTIFACT_ID,
            output_kind="class_packet_pdf",
            reason="initial",
            predecessor_issuance_id=ISSUANCE_ID,
            pages_per_student=1,
            issuance_id=ISSUANCE_ID,
            page_ids=PAGE_IDS[:1],
        )
    with pytest.raises(PrintableResponseRecordValidationError, match="itself"):
        build_printable_response_record_set(
            "english10_p2",
            assignment(),
            student(),
            generation_id=GENERATION_ID,
            artifact_id=ARTIFACT_ID,
            output_kind="class_packet_pdf",
            reason="regeneration",
            predecessor_issuance_id=ISSUANCE_ID,
            pages_per_student=1,
            issuance_id=ISSUANCE_ID,
            page_ids=PAGE_IDS[:1],
        )


def test_lifecycle_allows_only_governed_transitions() -> None:
    lifecycle = record_set(pages=1).issuance.lifecycle
    issued = transition_printable_response_lifecycle(
        lifecycle, new_status="issued", timestamp="2026-07-19T18:31:00+00:00"
    )
    assert issued.status == "issued"
    assert issued.revision == 2
    assert issued.issued_at == issued.updated_at
    with pytest.raises(PrintableResponseRecordValidationError):
        transition_printable_response_lifecycle(
            issued, new_status="cancelled", timestamp="2026-07-19T18:32:00+00:00"
        )


def _allowed_lifecycle_examples() -> dict[str, PrintableResponseLifecycle]:
    prepared = record_set(pages=1).issuance.lifecycle
    issued = transition_printable_response_lifecycle(
        prepared,
        new_status="issued",
        timestamp="2026-07-19T18:31:00+00:00",
    )
    return {
        "prepared": prepared,
        "issued": issued,
        "cancelled": transition_printable_response_lifecycle(
            prepared,
            new_status="cancelled",
            timestamp="2026-07-19T18:31:00+00:00",
            reason="Preparation abandoned",
        ),
        "superseded": transition_printable_response_lifecycle(
            issued,
            new_status="superseded",
            timestamp="2026-07-19T18:32:00+00:00",
            reason="Fresh issued copy",
            replacement_issuance_id=ISSUANCE_ID[:-1] + "e",
        ),
        "invalidated": transition_printable_response_lifecycle(
            issued,
            new_status="invalidated",
            timestamp="2026-07-19T18:32:00+00:00",
            reason="Synthetic integrity decision",
        ),
    }


@pytest.mark.parametrize(
    ("start", "allowed"),
    [
        ("prepared", {"issued", "cancelled", "invalidated"}),
        ("issued", {"superseded", "invalidated"}),
        ("cancelled", set()),
        ("superseded", set()),
        ("invalidated", set()),
    ],
)
def test_every_forbidden_lifecycle_transition_is_rejected(
    start: str, allowed: set[str]
) -> None:
    lifecycle = _allowed_lifecycle_examples()[start]
    for new_status in {"prepared", "issued", "cancelled", "superseded", "invalidated"} - allowed:
        with pytest.raises(PrintableResponseRecordValidationError, match="not allowed"):
            transition_printable_response_lifecycle(
                lifecycle,
                new_status=new_status,
                timestamp="2026-07-19T18:33:00+00:00",
                reason=("Terminal reason" if new_status in {"cancelled", "superseded", "invalidated"} else None),
                replacement_issuance_id=(
                    ISSUANCE_ID[:-1] + "e" if new_status == "superseded" else None
                ),
            )


@pytest.mark.parametrize("terminal_status", ["cancelled", "invalidated"])
def test_terminal_transition_requires_nonempty_reason(terminal_status: str) -> None:
    prepared = record_set(pages=1).issuance.lifecycle
    with pytest.raises(PrintableResponseRecordValidationError, match="reason"):
        transition_printable_response_lifecycle(
            prepared,
            new_status=terminal_status,
            timestamp="2026-07-19T18:31:00+00:00",
            reason="",
        )


def test_issued_prohibits_reason_and_superseded_requires_replacement() -> None:
    prepared = record_set(pages=1).issuance.lifecycle
    with pytest.raises(PrintableResponseRecordValidationError, match="reason"):
        transition_printable_response_lifecycle(
            prepared,
            new_status="issued",
            timestamp="2026-07-19T18:31:00+00:00",
            reason="not allowed",
        )
    issued = transition_printable_response_lifecycle(
        prepared,
        new_status="issued",
        timestamp="2026-07-19T18:31:00+00:00",
    )
    with pytest.raises(PrintableResponseRecordValidationError):
        transition_printable_response_lifecycle(
            issued,
            new_status="superseded",
            timestamp="2026-07-19T18:32:00+00:00",
            reason="Replacement missing",
        )
    with pytest.raises(PrintableResponseRecordValidationError, match="reason"):
        transition_printable_response_lifecycle(
            issued,
            new_status="superseded",
            timestamp="2026-07-19T18:32:00+00:00",
            reason="",
            replacement_issuance_id=ISSUANCE_ID[:-1] + "e",
        )


@pytest.mark.parametrize(
    ("status", "revision", "issued_at"),
    [
        ("issued", 3, "2026-07-19T18:31:00+00:00"),
        ("cancelled", 3, None),
        ("superseded", 2, "2026-07-19T18:31:00+00:00"),
        ("invalidated", 3, None),
        ("invalidated", 2, "2026-07-19T18:31:00+00:00"),
    ],
)
def test_persisted_lifecycle_revision_must_match_transition_history(
    status: str, revision: int, issued_at: str | None
) -> None:
    terminal = status != "issued"
    with pytest.raises(PrintableResponseRecordValidationError, match="revision"):
        PrintableResponseLifecycle(
            status=status,
            revision=revision,
            created_at=NOW.isoformat(),
            updated_at="2026-07-19T18:32:00+00:00",
            issued_at=issued_at,
            ended_at="2026-07-19T18:32:00+00:00" if terminal else None,
            reason="Synthetic terminal reason" if terminal else None,
            replacement_issuance_id=(
                ISSUANCE_ID[:-1] + "e" if status == "superseded" else None
            ),
        )


def test_builder_rejects_student_not_normalized_by_roster_contract() -> None:
    with pytest.raises(PrintableResponseRecordValidationError, match="normalized"):
        build_printable_response_record_set(
            "english10_p2",
            assignment(),
            StudentRecord(
                "english10_p2",
                "00107",
                " Student ",
                "Sample",
                "2",
                {"email": "sample@example.test"},
            ),
            generation_id=GENERATION_ID,
            artifact_id=ARTIFACT_ID,
            output_kind="class_packet_pdf",
            reason="initial",
            pages_per_student=1,
            issuance_id=ISSUANCE_ID,
            page_ids=PAGE_IDS[:1],
        )


def test_builder_accepts_optional_roster_fields_without_serializing_them() -> None:
    optional_fields = {
        "email": "sample@example.test",
        "grade_level": "10",
    }
    roster_student = StudentRecord(
        class_id="english10_p2",
        student_id="00107",
        last_name="Student",
        first_name="Sample",
        period="2",
        extra_fields=optional_fields,
    )

    records = build_printable_response_record_set(
        "english10_p2",
        assignment(),
        roster_student,
        generation_id=GENERATION_ID,
        artifact_id=ARTIFACT_ID,
        output_kind="class_packet_pdf",
        reason="initial",
        pages_per_student=1,
        issuance_id=ISSUANCE_ID,
        page_ids=PAGE_IDS[:1],
        clock=lambda: NOW,
    )

    assert records.issuance.student_id == "00107"
    assert records.issuance.student_snapshot.to_mapping() == {
        "display_name": "Sample Student",
        "last_name": "Student",
        "first_name": "Sample",
        "period": "2",
    }
    serialized = (records.issuance.to_mapping(), records.pages[0].to_mapping())
    for mapping in serialized:
        assert "email" not in mapping
        assert "grade_level" not in mapping
        assert "extra_fields" not in mapping
        assert "sample@example.test" not in repr(mapping)
    assert dict(roster_student.extra_fields) == optional_fields


@pytest.mark.parametrize("invalid", [None, {}, [], object()])
def test_public_record_set_validator_rejects_wrong_model_types(
    invalid: object,
) -> None:
    with pytest.raises(
        PrintableResponseRecordValidationError,
        match="record_set must be a PrintableResponseRecordSet",
    ):
        response_records.validate_printable_response_record_set(invalid)


@pytest.mark.parametrize("invalid", [None, {}, object()])
def test_public_mapping_converters_reject_wrong_model_types(
    invalid: object,
) -> None:
    with pytest.raises(PrintableResponseRecordValidationError, match="issuance"):
        response_records.printable_response_issuance_to_mapping(invalid)
    with pytest.raises(PrintableResponseRecordValidationError, match="page"):
        response_records.printable_response_page_to_mapping(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("output_kind", []),
        ("reason", {}),
    ],
)
def test_generation_context_malformed_enum_types_are_typed(
    field: str, value: object
) -> None:
    mapping = record_set(pages=1).issuance.generation_context.to_mapping()
    mapping[field] = value
    with pytest.raises(PrintableResponseRecordValidationError):
        response_records.PrintableResponseGenerationContext.from_mapping(mapping)


def test_exact_mapping_rejects_non_string_keys_without_builtin_type_error() -> None:
    mapping: dict[object, object] = {
        "output_kind": "class_packet_pdf",
        "reason": "initial",
        "predecessor_issuance_id": None,
        1: "unexpected",
    }
    with pytest.raises(PrintableResponseRecordValidationError, match="keys"):
        response_records.PrintableResponseGenerationContext.from_mapping(mapping)


def test_transition_rejects_unhashable_new_status_through_typed_error() -> None:
    with pytest.raises(PrintableResponseRecordValidationError, match="new_status"):
        transition_printable_response_lifecycle(
            record_set(pages=1).issuance.lifecycle,
            new_status=[],  # type: ignore[arg-type]
            timestamp="2026-07-19T18:31:00+00:00",
        )


def test_new_modules_keep_pds2_only_schema_and_narrow_public_api() -> None:
    root = Path(response_records.__file__).parent
    sources = {
        name: (root / name).read_text(encoding="utf-8")
        for name in (
            "printable_response_records.py",
            "printable_response_persistence.py",
        )
    }
    forbidden_imports = (
        "pds_core." + "pds1",
        "pds_core." + "qr_payload",
        "quillan.payloads",
    )
    assert all(
        forbidden not in source
        for source in sources.values()
        for forbidden in forbidden_imports
    )
    page_mapping = record_set(pages=1).pages[0].to_mapping()
    assert set(page_mapping).isdisjoint(
        {
            "route_id",
            "qr_payload",
            "scan_id",
            "evidence",
            "evidence_state",
            "submission",
            "submission_state",
        }
    )
    assert "with_printable_response_lifecycle" not in response_records.__all__
    assert not hasattr(response_records, "with_printable_response_lifecycle")
    assert all(
        "page" not in name or all(word not in name for word in ("update", "overwrite"))
        for name in response_persistence.__all__
    )
    assert record_set(pages=1).pages[0].schema_version == RESPONSE_PAGE_CONTRACT_VERSION
    assert response_page_target(PAGE_IDS[0]).contract_version == RESPONSE_PAGE_CONTRACT_VERSION
    target_constructors = [
        name
        for name in response_records.__all__
        if name == "response_page_target"
    ]
    assert target_constructors == ["response_page_target"]
    assert sum(source.count("def response_page_target(") for source in sources.values()) == 1


def test_page_target_is_exact_and_side_effect_free(tmp_path: Path) -> None:
    target = response_page_target(record_set(pages=1).pages[0])
    assert target == ModuleRecordRef(
        "quillan", "response_page", PAGE_IDS[0], RESPONSE_PAGE_CONTRACT_VERSION
    )
    assert list(tmp_path.iterdir()) == []
