from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Callable

import pytest

import quillan.academic_result_reader as reader_module
from quillan.academic_result_manifest import (
    AcademicResultManifest,
    EvidenceReference,
    OverallStandardRating,
    ReviewUnit,
    SourceRecordSnapshot,
    StandardFeedback,
    StandardObservation,
    StudentResult,
    manifest_from_json_bytes,
)
from quillan.academic_result_reader import (
    QuillanAcademicResultReaderDecodeError,
    QuillanAcademicResultReaderNotFoundError,
    QuillanAcademicResultReaderValidationError,
    lookup_academic_result_evidence_reference,
    lookup_academic_result_observation,
    lookup_academic_result_overall_rating,
    lookup_academic_result_review_unit,
    lookup_academic_result_source,
    lookup_academic_result_standard_feedback,
    lookup_academic_result_student,
    read_academic_result_manifest,
    validate_academic_result_manifest,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "publication"
    / "quillan_academic_result_manifest_v1.json"
)

EXPECTED_PUBLIC = {
    "AcademicResultManifest",
    "AcademicResultSourceName",
    "EvidenceReference",
    "OverallStandardRating",
    "QuillanAcademicResultReaderDecodeError",
    "QuillanAcademicResultReaderError",
    "QuillanAcademicResultReaderNotFoundError",
    "QuillanAcademicResultReaderValidationError",
    "ReviewUnit",
    "SourceRecordSnapshot",
    "StandardFeedback",
    "StandardObservation",
    "StudentResult",
    "lookup_academic_result_evidence_reference",
    "lookup_academic_result_observation",
    "lookup_academic_result_overall_rating",
    "lookup_academic_result_review_unit",
    "lookup_academic_result_source",
    "lookup_academic_result_standard_feedback",
    "lookup_academic_result_student",
    "read_academic_result_manifest",
    "validate_academic_result_manifest",
}


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def fixture_manifest() -> AcademicResultManifest:
    return read_academic_result_manifest(fixture_bytes())


def test_public_reader_exports_exact_stable_surface() -> None:
    assert set(reader_module.__all__) == EXPECTED_PUBLIC
    assert reader_module.AcademicResultManifest is AcademicResultManifest


def test_canonical_fixture_reads_through_existing_contract() -> None:
    raw = fixture_bytes()
    assert read_academic_result_manifest(raw) == manifest_from_json_bytes(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: json.dumps(
            json.loads(raw),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
        lambda raw: (
            json.dumps(
                dict(reversed(list(json.loads(raw).items()))),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8"),
        lambda raw: raw.removesuffix(b"\n"),
        lambda raw: raw + b" ",
        lambda raw: raw.replace(
            b"2026-01-15T17:00:00Z",
            b"2026-01-15T17:00:00+00:00",
            1,
        ),
    ],
    ids=[
        "minified",
        "top-level-key-order",
        "missing-final-newline",
        "trailing-space",
        "timestamp-rendering",
    ],
)
def test_semantically_valid_noncanonical_bytes_fail_closed(
    mutation: Callable[[bytes], bytes],
) -> None:
    with pytest.raises(
        QuillanAcademicResultReaderValidationError, match="not canonical"
    ):
        read_academic_result_manifest(mutation(fixture_bytes()))


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff",
        b'{"record_type":"a","record_type":"b"}',
        b'{"number":NaN}',
    ],
)
def test_decode_failures_are_normalized_without_payload_leak(raw: bytes) -> None:
    with pytest.raises(
        QuillanAcademicResultReaderDecodeError, match="bytes are invalid"
    ) as caught:
        read_academic_result_manifest(raw)
    assert str(caught.value) == "Academic-result manifest bytes are invalid."


def test_reader_requires_exact_immutable_bytes_type() -> None:
    with pytest.raises(
        QuillanAcademicResultReaderValidationError, match="immutable bytes"
    ):
        read_academic_result_manifest("not bytes")  # type: ignore[arg-type]
    with pytest.raises(
        QuillanAcademicResultReaderValidationError, match="immutable bytes"
    ):
        read_academic_result_manifest(bytearray(fixture_bytes()))  # type: ignore[arg-type]


def test_invalid_semantic_manifest_is_wrapped_without_sensitive_value() -> None:
    data = json.loads(fixture_bytes())
    data["students"][0]["submission"]["student_id"] = "student_secret"
    raw = (
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")
    with pytest.raises(QuillanAcademicResultReaderDecodeError) as caught:
        read_academic_result_manifest(raw)
    assert "student_secret" not in str(caught.value)
    assert "student_001" not in str(caught.value)


def test_existing_manifest_model_validates_without_mutation() -> None:
    manifest = fixture_manifest()
    assert validate_academic_result_manifest(manifest) is manifest
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        validate_academic_result_manifest(object())  # type: ignore[arg-type]


def test_source_lookup_returns_exact_embedded_snapshots_without_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = fixture_manifest()

    def forbidden_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("source lookup must not open native files")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    assignment = lookup_academic_result_source(manifest, "assignment")
    submission = lookup_academic_result_source(
        manifest, "submission", student_id="student_001"
    )
    review = lookup_academic_result_source(
        manifest, "review", student_id="student_001"
    )
    assert isinstance(assignment, SourceRecordSnapshot)
    assert assignment is manifest.source_snapshot
    assert submission is manifest.students[0].source_snapshot.submission
    assert review is manifest.students[0].source_snapshot.review


def test_source_lookup_rejects_unknown_or_incomplete_combinations() -> None:
    manifest = fixture_manifest()
    with pytest.raises(QuillanAcademicResultReaderValidationError, match="source must"):
        lookup_academic_result_source(manifest, "native_file")  # type: ignore[arg-type]
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_source(
            manifest, "assignment", student_id="student_001"
        )
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_source(manifest, "submission")
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_source(manifest, "review")


def test_student_lookup_returns_exact_student() -> None:
    manifest = fixture_manifest()
    student = lookup_academic_result_student(manifest, "student_001")
    assert isinstance(student, StudentResult)
    assert student is manifest.students[0]


def test_student_lookup_absence_and_invalid_id_are_privacy_safe() -> None:
    manifest = fixture_manifest()
    secret = "student_secret"
    with pytest.raises(QuillanAcademicResultReaderNotFoundError) as caught:
        lookup_academic_result_student(manifest, secret)
    assert secret not in str(caught.value)
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_student(manifest, "../unsafe")


def test_review_unit_lookup_is_exact_by_unit_id() -> None:
    manifest = fixture_manifest()
    unit = lookup_academic_result_review_unit(
        manifest, "student_001", "paragraph_2"
    )
    assert isinstance(unit, ReviewUnit)
    assert unit is manifest.students[0].review.review_units[1]
    assert unit.sequence == 2
    with pytest.raises(QuillanAcademicResultReaderNotFoundError):
        lookup_academic_result_review_unit(manifest, "student_001", "Paragraph 2")
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_review_unit(manifest, "student_001", "")


def test_observation_lookup_preserves_non_score_states_exactly() -> None:
    manifest = fixture_manifest()
    non_applicable = lookup_academic_result_observation(
        manifest, "student_001", "observation_0002"
    )
    no_evidence = lookup_academic_result_observation(
        manifest, "student_001", "observation_0003"
    )
    assert isinstance(non_applicable, StandardObservation)
    assert (non_applicable.applicable, non_applicable.evidence_present, non_applicable.rating) == (
        False,
        None,
        None,
    )
    assert (no_evidence.applicable, no_evidence.evidence_present, no_evidence.rating) == (
        True,
        False,
        None,
    )
    with pytest.raises(QuillanAcademicResultReaderNotFoundError):
        lookup_academic_result_observation(
            manifest, "student_001", "observation_missing"
        )


def test_overall_rating_lookup_preserves_native_lowest_rating_and_absence() -> None:
    manifest = fixture_manifest()
    standard = "njsls-ela:RL.CR.9-10.1"
    rating = lookup_academic_result_overall_rating(
        manifest, "student_001", standard
    )
    assert isinstance(rating, OverallStandardRating)
    assert rating is manifest.students[0].review.overall_standard_ratings[0]
    assert rating.standard_id == standard
    assert rating.rating == 0
    with pytest.raises(QuillanAcademicResultReaderNotFoundError):
        lookup_academic_result_overall_rating(
            manifest,
            "student_001",
            "njsls-ela:W.AW.9-10.1",
        )


def test_standard_id_lookup_preserves_exact_native_text() -> None:
    manifest = fixture_manifest()
    with pytest.raises(QuillanAcademicResultReaderNotFoundError):
        lookup_academic_result_overall_rating(
            manifest,
            "student_001",
            "NJSLS-ELA:RL.CR.9-10.1",
        )
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_overall_rating(manifest, "student_001", "\x00")


def test_standard_feedback_returns_public_composition_without_recovering_withheld_text() -> None:
    manifest = fixture_manifest()
    feedback = lookup_academic_result_standard_feedback(
        manifest,
        "student_001",
        "njsls-ela:RL.CR.9-10.1",
    )
    assert isinstance(feedback, StandardFeedback)
    assert feedback is manifest.students[0].review.feedback.standard_feedback[0]
    assert feedback.comments[0].text.disposition == "included"
    assert feedback.comments[0].text.text == "Clarify the central idea."
    overall = lookup_academic_result_overall_rating(
        manifest,
        "student_001",
        "njsls-ela:RL.CR.9-10.1",
    )
    assert overall.rationale.disposition == "withheld"
    assert overall.rationale.text is None
    assert manifest.students[0].review.minimum_requirement_outcome.teacher_note.disposition == (
        "withheld"
    )
    assert manifest.students[0].review.minimum_requirement_outcome.teacher_note.text is None


def test_evidence_reference_lookup_returns_only_public_selected_provenance() -> None:
    manifest = fixture_manifest()
    evidence_id = "obs_00000000000000000000000000000001"
    reference = lookup_academic_result_evidence_reference(
        manifest, "student_001", evidence_id
    )
    assert isinstance(reference, EvidenceReference)
    assert (
        reference
        is manifest.students[0].submission.digital_provenance.evidence_references[0]  # type: ignore[union-attr]
    )
    assert reference.evidence_id == evidence_id
    assert reference.routed_evidence_sha256 == "4" * 64
    assert not hasattr(reference, "routed_evidence_path")
    assert not hasattr(reference, "retained_source_path")
    assert not hasattr(reference, "source_filename")


def test_plain_paper_has_no_fabricated_evidence_reference() -> None:
    manifest = fixture_manifest()
    with pytest.raises(QuillanAcademicResultReaderNotFoundError):
        lookup_academic_result_evidence_reference(
            manifest,
            "student_002",
            "obs_00000000000000000000000000000001",
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "observation_0001",
        "obs_ABCDEF00000000000000000000000000",
        "obs_0000000000000000000000000000000",
    ],
)
def test_evidence_lookup_rejects_invalid_pds2_identifier(value: str) -> None:
    manifest = fixture_manifest()
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        lookup_academic_result_evidence_reference(
            manifest,
            "student_001",
            value,
        )


def test_reader_source_has_no_consumer_workspace_publication_or_io_boundary() -> None:
    source = Path("quillan/academic_result_reader.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in (
        "import meridian",
        "from meridian",
        "import vitrine",
        "from vitrine",
        "import scoreform",
        "from scoreform",
        "import concord",
        "from concord",
        "import portia",
        "from portia",
        "academic_result_manifest_generation",
        "academic_result_publication",
        "feedback_export",
        "record_context",
        "publication_storage",
        "academic_catalog",
        "registry_services",
    ):
        assert forbidden not in lowered
    assert "open(" not in source
    assert "Path(" not in source


def test_reader_public_functions_do_not_print_or_write(capsys: pytest.CaptureFixture[str]) -> None:
    manifest = fixture_manifest()
    lookup_academic_result_source(manifest, "assignment")
    lookup_academic_result_student(manifest, "student_001")
    lookup_academic_result_review_unit(manifest, "student_001", "paragraph_1")
    lookup_academic_result_observation(
        manifest, "student_001", "observation_0001"
    )
    lookup_academic_result_overall_rating(
        manifest, "student_001", "njsls-ela:RL.CR.9-10.1"
    )
    lookup_academic_result_standard_feedback(
        manifest, "student_001", "njsls-ela:RL.CR.9-10.1"
    )
    lookup_academic_result_evidence_reference(
        manifest,
        "student_001",
        "obs_00000000000000000000000000000001",
    )
    assert capsys.readouterr() == ("", "")
