from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from quillan.academic_result_manifest import (
    QuillanAcademicResultManifestDecodeError,
    QuillanAcademicResultManifestValidationError,
    manifest_from_json_bytes,
    manifest_from_mapping,
    manifest_to_canonical_json_bytes,
    manifest_to_mapping,
)

FIXTURE = Path("tests/fixtures/publication/quillan_academic_result_manifest_v1.json")
ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64


def _text(disposition: str = "absent", text: str | None = None) -> dict[str, object]:
    return {"disposition": disposition, "text": text}


def _source(path: str, digest: str, version: str) -> dict[str, object]:
    return {"relative_path": path, "sha256": digest, "contract_version": version}


def valid_mapping() -> dict[str, Any]:
    return {
        "record_type": "quillan_academic_result_manifest",
        "contract_version": "quillan_academic_result_manifest_v1",
        "producer_module_id": "quillan",
        "generated_at": "2026-01-15T17:00:00Z",
        "record_set": {"record_set_id": "villainy_results", "revision": 1},
        "work": {
            "module_id": "quillan",
            "class_id": "english12_p3",
            "work_id": "villainy_essay",
        },
        "source_snapshot": _source("assignment.json", ZERO, "2"),
        "assignment": {
            "assignment_id": "villainy_essay",
            "title": "Villainy Final Essay",
            "writing_type": "literary_analysis",
            "student_prompt": "Explain how the author develops villainy.",
            "standards_profile_id": "english12_2023_njsls_ela",
            "focus_standard_ids": [
                "njsls-ela:RL.CR.9-10.1",
                "njsls-ela:W.AW.9-10.1",
            ],
            "review_unit": {
                "type": "paragraph",
                "singular_label": "Paragraph",
                "plural_label": "Paragraphs",
            },
            "rating_scale": {
                "scale_id": "quillan_analysis_v1",
                "levels": [
                    {
                        "value": 0,
                        "label": "Beginning",
                        "description": "Limited evidence.",
                    },
                    {
                        "value": 2,
                        "label": "Developing",
                        "description": "Partial evidence.",
                    },
                    {
                        "value": 4,
                        "label": "Secure",
                        "description": "Consistent evidence.",
                    },
                ],
            },
            "basic_requirements": {
                "paragraphs_min": 4,
                "paragraphs_max": None,
                "word_count_min": 800,
                "word_count_max": 1500,
                "required_elements": ["claim", "textual evidence"],
            },
            "minimum_requirement_policy": {"allow_return_without_full_review": True},
        },
        "students": [
            {
                "student_id": "student_001",
                "source_snapshot": {
                    "submission": _source(
                        "submissions/student_001/submission.json", ONE, "1"
                    ),
                    "review": _source("submissions/student_001/review.json", TWO, "2"),
                },
                "submission": {
                    "class_id": "english12_p3",
                    "assignment_id": "villainy_essay",
                    "student_id": "student_001",
                    "submission_state": "reviewed",
                    "entry_method": "pds2_response_pages",
                    "expected_pages": 1,
                    "digital_provenance": {
                        "issuance_id": "iss_00000000000000000000000000000001",
                        "generation_id": "gen_00000000000000000000000000000001",
                        "artifact_id": "art_00000000000000000000000000000001",
                        "expected_page_ids": ["pg_00000000000000000000000000000001"],
                        "evidence_references": [
                            {
                                "page_id": "pg_00000000000000000000000000000001",
                                "evidence_id": "obs_00000000000000000000000000000001",
                                "observation_id": "obs_00000000000000000000000000000001",
                                "route_id": "rt_00000000000000000000000000000001",
                                "issuance_id": "iss_00000000000000000000000000000001",
                                "generation_id": "gen_00000000000000000000000000000001",
                                "artifact_id": "art_00000000000000000000000000000001",
                                "source_page_number": 1,
                                "source_scan_id": "scan_001",
                                "source_sha256": "3" * 64,
                                "routed_evidence_sha256": "4" * 64,
                            }
                        ],
                    },
                },
                "review": {
                    "class_id": "english12_p3",
                    "assignment_id": "villainy_essay",
                    "student_id": "student_001",
                    "review_state": "ratings_complete",
                    "minimum_requirement_outcome": {
                        "status": "met",
                        "returned_without_full_review": False,
                        "updated_at": "2026-01-15T15:00:00Z",
                        "teacher_note": _text("withheld"),
                    },
                    "review_units": [
                        {
                            "unit_id": "paragraph_1",
                            "sequence": 1,
                            "label": "Paragraph 1",
                            "unit_type": "paragraph",
                            "standard_observations": [
                                {
                                    "observation_id": "observation_0001",
                                    "standard_id": "njsls-ela:RL.CR.9-10.1",
                                    "applicable": True,
                                    "evidence_present": True,
                                    "rating": 2,
                                    "rationale": _text(
                                        "included", "The claim is present."
                                    ),
                                    "include_in_feedback": True,
                                    "updated_at": "2026-01-15T15:10:00Z",
                                },
                                {
                                    "observation_id": "observation_0002",
                                    "standard_id": "njsls-ela:W.AW.9-10.1",
                                    "applicable": False,
                                    "evidence_present": None,
                                    "rating": None,
                                    "rationale": _text(),
                                    "include_in_feedback": False,
                                    "updated_at": "2026-01-15T15:11:00Z",
                                },
                            ],
                        },
                        {
                            "unit_id": "paragraph_2",
                            "sequence": 2,
                            "label": "Paragraph 2",
                            "unit_type": "paragraph",
                            "standard_observations": [
                                {
                                    "observation_id": "observation_0003",
                                    "standard_id": "njsls-ela:RL.CR.9-10.1",
                                    "applicable": True,
                                    "evidence_present": False,
                                    "rating": None,
                                    "rationale": _text(),
                                    "include_in_feedback": False,
                                    "updated_at": "2026-01-15T15:12:00Z",
                                }
                            ],
                        },
                    ],
                    "overall_standard_ratings": [
                        {
                            "standard_id": "njsls-ela:RL.CR.9-10.1",
                            "rating": 0,
                            "rationale": _text("withheld"),
                            "include_in_feedback": True,
                            "updated_at": "2026-01-15T16:00:00Z",
                        }
                    ],
                    "feedback": {
                        "include_review_unit_observations": True,
                        "include_overall_standard_ratings": True,
                        "standard_feedback": [
                            {
                                "standard_id": "njsls-ela:RL.CR.9-10.1",
                                "include_overall_rating": True,
                                "include_overall_rationale": False,
                                "included_observation_ids": ["observation_0001"],
                                "comments": [
                                    {
                                        "feedback_comment_id": "feedback_comment_0001",
                                        "text": _text(
                                            "included", "Clarify the central idea."
                                        ),
                                        "include_in_feedback": True,
                                        "created_at": "2026-01-15T16:05:00Z",
                                    }
                                ],
                            }
                        ],
                    },
                },
            },
            {
                "student_id": "student_002",
                "source_snapshot": {
                    "submission": _source(
                        "submissions/student_002/submission.json", "5" * 64, "1"
                    ),
                    "review": _source(
                        "submissions/student_002/review.json", "6" * 64, "2"
                    ),
                },
                "submission": {
                    "class_id": "english12_p3",
                    "assignment_id": "villainy_essay",
                    "student_id": "student_002",
                    "submission_state": "unreviewed",
                    "entry_method": "plain_paper_manual",
                    "expected_pages": None,
                    "digital_provenance": None,
                },
                "review": {
                    "class_id": "english12_p3",
                    "assignment_id": "villainy_essay",
                    "student_id": "student_002",
                    "review_state": "returned_without_full_review",
                    "minimum_requirement_outcome": {
                        "status": "returned_without_full_review",
                        "returned_without_full_review": True,
                        "updated_at": "2026-01-15T14:00:00Z",
                        "teacher_note": _text("withheld"),
                    },
                    "review_units": [],
                    "overall_standard_ratings": [],
                    "feedback": {
                        "include_review_unit_observations": False,
                        "include_overall_standard_ratings": False,
                        "standard_feedback": [],
                    },
                },
            },
        ],
    }


def _append_pds2_evidence_reference(
    mapping: dict[str, Any],
    *,
    page_id: str = "pg_00000000000000000000000000000001",
    source_scan_id: str = "scan_001",
    source_page_number: int = 1,
    source_sha256: str = "3" * 64,
) -> None:
    digital = mapping["students"][0]["submission"]["digital_provenance"]
    reference = copy.deepcopy(digital["evidence_references"][0])
    reference.update(
        page_id=page_id,
        evidence_id="obs_00000000000000000000000000000002",
        observation_id="obs_00000000000000000000000000000002",
        route_id="rt_00000000000000000000000000000002",
        source_scan_id=source_scan_id,
        source_page_number=source_page_number,
        source_sha256=source_sha256,
        routed_evidence_sha256="7" * 64,
    )
    digital["evidence_references"].append(reference)


def test_normative_fixture_round_trips_byte_exactly() -> None:
    fixture = FIXTURE.read_bytes()
    manifest = manifest_from_json_bytes(fixture)
    assert manifest_to_canonical_json_bytes(manifest) == fixture
    assert manifest_from_mapping(manifest_to_mapping(manifest)) == manifest


def test_full_review_preserves_native_scale_and_missing_overall_rating() -> None:
    manifest = manifest_from_mapping(valid_mapping())
    assert [level.value for level in manifest.assignment.rating_scale.levels] == [
        0,
        2,
        4,
    ]
    assert manifest.students[0].review.overall_standard_ratings[0].rating == 0
    assert {
        item.standard_id
        for item in manifest.students[0].review.overall_standard_ratings
    } == {"njsls-ela:RL.CR.9-10.1"}
    assert (
        manifest.students[0].review.review_units[0].standard_observations[1].applicable
        is False
    )
    evidence_absent = (
        manifest.students[0].review.review_units[1].standard_observations[0]
    )
    assert evidence_absent.applicable is True
    assert evidence_absent.evidence_present is False
    assert evidence_absent.rating is None


def test_plain_paper_and_return_disposition_have_no_fabricated_rating_or_evidence() -> (
    None
):
    student = manifest_from_mapping(valid_mapping()).students[1]
    assert student.submission.digital_provenance is None
    assert student.submission.expected_pages is None
    assert student.review.review_state == "returned_without_full_review"
    assert student.review.overall_standard_ratings == ()


def test_current_style_standard_id_round_trips_without_normalization() -> None:
    expected = "njsls-ela:RL.CR.9-10.1"
    mapping = valid_mapping()
    mapping["assignment"]["standards_profile_id"] = "njsls-ela:grade-9-10"
    mapping["assignment"]["rating_scale"]["scale_id"] = "quillan:analysis.v1"
    manifest = manifest_from_mapping(mapping)
    assert manifest.assignment.focus_standard_ids[0] == expected
    assert (
        manifest.students[0].review.review_units[0].standard_observations[0].standard_id
        == expected
    )
    assert (
        manifest.students[0].review.overall_standard_ratings[0].standard_id == expected
    )
    assert (
        manifest.students[0].review.feedback.standard_feedback[0].standard_id
        == expected
    )
    assert manifest.assignment.standards_profile_id == "njsls-ela:grade-9-10"
    assert manifest.assignment.rating_scale.scale_id == "quillan:analysis.v1"
    encoded = manifest_to_canonical_json_bytes(manifest)
    assert expected.encode("utf-8") in encoded
    assert manifest_from_json_bytes(encoded) == manifest


@pytest.mark.parametrize("invalid", ["", "   "])
def test_blank_standard_id_is_rejected(invalid: str) -> None:
    mapping = valid_mapping()
    mapping["assignment"]["focus_standard_ids"][0] = invalid
    with pytest.raises(QuillanAcademicResultManifestValidationError, match="nonempty"):
        manifest_from_mapping(mapping)


def test_observation_standard_outside_assignment_focus_set_is_rejected() -> None:
    mapping = valid_mapping()
    mapping["students"][0]["review"]["review_units"][0]["standard_observations"][0][
        "standard_id"
    ] = "njsls-ela:RL.CR.9-10.99"
    with pytest.raises(
        QuillanAcademicResultManifestValidationError,
        match="not an assignment Focus Standard",
    ):
        manifest_from_mapping(mapping)


@pytest.mark.parametrize("target", ["observation", "overall"])
@pytest.mark.parametrize("rating", [True, False, 1.0])
def test_native_ratings_reject_boolean_and_float_types(
    target: str, rating: object
) -> None:
    mapping = valid_mapping()
    if rating is True or rating == 1.0:
        mapping["assignment"]["rating_scale"]["levels"].append(
            {"value": 1, "label": "Emerging", "description": "Some evidence."}
        )
    review = mapping["students"][0]["review"]
    if target == "observation":
        review["review_units"][0]["standard_observations"][0]["rating"] = rating
    else:
        review["overall_standard_ratings"][0]["rating"] = rating
    with pytest.raises(QuillanAcademicResultManifestValidationError, match="integer"):
        manifest_from_mapping(mapping)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda d, r: d.update(issuance_id="issuance_001"), "iss_"),
        (lambda d, r: d.update(generation_id="generation_001"), "gen_"),
        (lambda d, r: d.update(artifact_id="artifact_001"), "art_"),
        (lambda d, r: d.update(expected_page_ids=["page_001"]), "pg_"),
        (lambda d, r: r.update(page_id="page_001"), "pg_"),
        (lambda d, r: r.update(evidence_id="evidence_001"), "obs_"),
        (lambda d, r: r.update(observation_id="observation_001"), "obs_"),
        (lambda d, r: r.update(route_id="route_001"), "rt_"),
        (
            lambda d, r: r.update(
                observation_id="obs_00000000000000000000000000000002"
            ),
            "must equal observation_id",
        ),
        (
            lambda d, r: r.update(page_id="pg_00000000000000000000000000000002"),
            "not an expected page",
        ),
        (
            lambda d, r: r.update(issuance_id="iss_00000000000000000000000000000002"),
            "provenance envelope",
        ),
        (
            lambda d, r: r.update(generation_id="gen_00000000000000000000000000000002"),
            "provenance envelope",
        ),
        (
            lambda d, r: r.update(artifact_id="art_00000000000000000000000000000002"),
            "provenance envelope",
        ),
        (lambda d, r: r.update(source_scan_id=None), "safe identifier"),
        (lambda d, r: r.update(source_page_number=None), "integer"),
        (lambda d, r: r.update(source_sha256=None), "lowercase"),
        (lambda d, r: r.update(source_page_number=True), "integer"),
        (lambda d, r: r.update(source_page_number=0), "at least 1"),
        (lambda d, r: r.update(source_sha256="A" * 64), "lowercase"),
    ],
)
def test_pds2_identity_and_retained_source_contract_is_strict(
    mutation: object, match: str
) -> None:
    mapping = valid_mapping()
    digital = mapping["students"][0]["submission"]["digital_provenance"]
    reference = digital["evidence_references"][0]
    mutation(digital, reference)  # type: ignore[operator]
    with pytest.raises(QuillanAcademicResultManifestValidationError, match=match):
        manifest_from_mapping(mapping)


def test_retained_source_page_cannot_map_to_contradictory_page_ids() -> None:
    mapping = valid_mapping()
    digital = mapping["students"][0]["submission"]["digital_provenance"]
    second_page_id = "pg_00000000000000000000000000000002"
    digital["expected_page_ids"].append(second_page_id)
    mapping["students"][0]["submission"]["expected_pages"] = 2
    _append_pds2_evidence_reference(mapping, page_id=second_page_id)

    with pytest.raises(
        QuillanAcademicResultManifestValidationError,
        match="retained source page cannot represent contradictory page IDs",
    ):
        manifest_from_mapping(mapping)


def test_repeated_retained_source_page_with_same_page_id_is_valid() -> None:
    mapping = valid_mapping()
    _append_pds2_evidence_reference(mapping)
    manifest = manifest_from_mapping(mapping)
    references = manifest.students[0].submission.digital_provenance
    assert references is not None
    assert len(references.evidence_references) == 2
    assert (
        references.evidence_references[0].page_id
        == references.evidence_references[1].page_id
    )


def test_retained_scan_id_cannot_assert_different_source_digests() -> None:
    mapping = valid_mapping()
    _append_pds2_evidence_reference(mapping, source_sha256="8" * 64)
    with pytest.raises(
        QuillanAcademicResultManifestValidationError,
        match="retained source scan cannot assert contradictory SHA-256",
    ):
        manifest_from_mapping(mapping)


def test_different_retained_scan_ids_may_have_different_digests() -> None:
    mapping = valid_mapping()
    _append_pds2_evidence_reference(
        mapping,
        source_scan_id="scan_002",
        source_sha256="8" * 64,
    )
    manifest = manifest_from_mapping(mapping)
    digital = manifest.students[0].submission.digital_provenance
    assert digital is not None
    assert {item.source_scan_id for item in digital.evidence_references} == {
        "scan_001",
        "scan_002",
    }


def test_review_unit_type_must_match_assignment_configuration() -> None:
    mapping = valid_mapping()
    mapping["students"][0]["review"]["review_units"][0]["unit_type"] = "section"
    with pytest.raises(
        QuillanAcademicResultManifestValidationError,
        match="must equal assignment.review_unit.type",
    ):
        manifest_from_mapping(mapping)


def test_standard_feedback_cannot_reference_another_standards_observation() -> None:
    mapping = valid_mapping()
    feedback = mapping["students"][0]["review"]["feedback"]["standard_feedback"][0]
    feedback["standard_id"] = "njsls-ela:W.AW.9-10.1"
    with pytest.raises(
        QuillanAcademicResultManifestValidationError,
        match="only observations for its standard_id",
    ):
        manifest_from_mapping(mapping)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda m: m.update(extra=True), "invalid key set"),
        (lambda m: m["record_set"].update(revision=True), "integer"),
        (lambda m: m["source_snapshot"].update(sha256="A" * 64), "lowercase"),
        (
            lambda m: m["source_snapshot"].update(relative_path="../assignment.json"),
            "traversal",
        ),
        (
            lambda m: m["students"][0]["review"]["overall_standard_ratings"][0].update(
                rating=1
            ),
            "rating scale",
        ),
        (
            lambda m: m["students"][1]["submission"].update(expected_pages=1),
            "plain-paper",
        ),
    ],
)
def test_invalid_contract_data_is_rejected(mutation: object, match: str) -> None:
    mapping = copy.deepcopy(valid_mapping())
    mutation(mapping)  # type: ignore[operator]
    with pytest.raises(QuillanAcademicResultManifestValidationError, match=match):
        manifest_from_mapping(mapping)


def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected() -> None:
    with pytest.raises(QuillanAcademicResultManifestDecodeError, match="duplicate"):
        manifest_from_json_bytes(b'{"record_type":1,"record_type":2}')
    with pytest.raises(QuillanAcademicResultManifestDecodeError, match="nonfinite"):
        manifest_from_json_bytes(b'{"value":NaN}')


def test_published_text_states_are_distinct_and_do_not_infer_policy() -> None:
    mapping = valid_mapping()
    student = mapping["students"][0]
    review = student["review"]
    observation = review["review_units"][0]["standard_observations"][0]
    overall = review["overall_standard_ratings"][0]
    comment = review["feedback"]["standard_feedback"][0]["comments"][0]
    observation["rationale"] = _text("absent")
    overall["rationale"] = _text("withheld")
    comment["text"] = _text("included", "Student-facing projection text.")

    manifest = manifest_from_mapping(mapping)
    assert (
        manifest.students[0]
        .review.review_units[0]
        .standard_observations[0]
        .rationale.disposition
        == "absent"
    )
    assert (
        manifest.students[0].review.overall_standard_ratings[0].rationale.disposition
        == "withheld"
    )
    assert (
        manifest.students[0]
        .review.feedback.standard_feedback[0]
        .comments[0]
        .text.disposition
        == "included"
    )


def test_withheld_and_absent_text_never_serialize_private_substitutes() -> None:
    mapping = valid_mapping()
    review = mapping["students"][0]["review"]
    review["minimum_requirement_outcome"]["teacher_note"] = _text("withheld")
    review["review_units"][0]["standard_observations"][0]["rationale"] = _text("absent")
    review["overall_standard_ratings"][0]["rationale"] = _text("withheld")
    review["feedback"]["standard_feedback"][0]["comments"][0]["text"] = _text(
        "withheld"
    )

    encoded = manifest_to_canonical_json_bytes(manifest_from_mapping(mapping))
    assert b'"disposition": "withheld"' in encoded
    assert b'"disposition": "absent"' in encoded
    assert b'"text": null' in encoded
    assert b"private substitute" not in encoded


def test_published_text_never_promotes_or_uses_empty_string() -> None:
    mapping = valid_mapping()
    rationale = mapping["students"][0]["review"]["review_units"][0][
        "standard_observations"
    ][0]["rationale"]
    rationale.update(disposition="withheld", text="native private rationale")
    with pytest.raises(
        QuillanAcademicResultManifestValidationError, match="must be null"
    ):
        manifest_from_mapping(mapping)

    mapping = valid_mapping()
    rationale = mapping["students"][0]["review"]["review_units"][0][
        "standard_observations"
    ][0]["rationale"]
    rationale.update(disposition="included", text="")
    with pytest.raises(QuillanAcademicResultManifestValidationError, match="nonempty"):
        manifest_from_mapping(mapping)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m["students"][0]["review"].update(private_notes=[]),
        lambda m: m.update(module_details={"private": True}),
        lambda m: m["students"][0]["review"]["review_units"][0][
            "standard_observations"
        ][0].update(module_details={"private": True}),
        lambda m: m["students"][0]["review"]["feedback"]["standard_feedback"][0][
            "comments"
        ][0].update(
            source="reusable_focus_standard_comment",
            reusable_comment_id="comment_source_001",
        ),
        lambda m: m["students"][0]["submission"]["digital_provenance"][
            "evidence_references"
        ][0].update(
            routed_evidence_path="scans/evidence/private.png",
            retained_source_path="scans/source/private.pdf",
        ),
        lambda m: m["students"][0]["review"].update(
            exports={"feedback_pdf": {"path": "private/feedback.pdf"}}
        ),
    ],
)
def test_privacy_sensitive_native_fields_are_not_in_the_v1_schema(
    mutation: object,
) -> None:
    mapping = copy.deepcopy(valid_mapping())
    mutation(mapping)  # type: ignore[operator]
    with pytest.raises(
        QuillanAcademicResultManifestValidationError, match="invalid key set"
    ):
        manifest_from_mapping(mapping)


def test_serialization_never_introduces_consumer_policy_fields() -> None:
    encoded = manifest_to_canonical_json_bytes(manifest_from_mapping(valid_mapping()))
    for prohibited in (
        b'"percentage"',
        b'"grade"',
        b'"proficiency"',
        b'"private_notes"',
        b'"student_name"',
    ):
        assert prohibited not in encoded


def _write_normative_fixture() -> None:
    """Development helper; the test suite never calls or exports this function."""
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_bytes(
        manifest_to_canonical_json_bytes(manifest_from_mapping(valid_mapping()))
    )


if __name__ == "__main__":
    _write_normative_fixture()
