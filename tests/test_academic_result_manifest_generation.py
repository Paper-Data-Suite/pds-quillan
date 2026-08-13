from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.academic_result_manifest import manifest_to_canonical_json_bytes
from quillan.academic_result_manifest_generation import (
    QuillanManifestGenerationConflictError,
    QuillanManifestGenerationIntegrityError,
    QuillanManifestGenerationValidationError,
    build_academic_result_manifest,
    discover_manifest_student_ids,
    load_academic_result_manifest_generation_context,
    verify_generation_context_unchanged,
)
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.review_record import build_empty_review_record, validate_review_record
from quillan.submission_manifest import validate_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.work_paths import (
    academic_result_manifest_relative_path,
    academic_result_manifest_revision_path,
    academic_result_manifests_dir,
    manifest_exports_dir,
    quillan_work_ref,
    review_record_path,
    submission_manifest_path,
)
from tests.observation_test_support import successful_image_page
from tests.review_test_support import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    TIMESTAMP,
    _write_assignment,
)

STANDARD_ID = "synthetic:W.A"
PROFILE_ID = "synthetic_profile"


def _write_standards(workspace: Path) -> None:
    library = StandardsLibrary(
        standards=(
            StandardDefinition(
                standard_id=STANDARD_ID,
                code="W.A",
                source="synthetic",
                short_name="Synthetic Writing",
                description="Synthetic writing standard for manifest tests.",
            ),
        ),
        profiles=(StandardsProfile(profile_id=PROFILE_ID, standards=(STANDARD_ID,)),),
    )
    write_workspace_standards_library(workspace, library)


def _plain_submission(
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {
            "submission_entry_method": "plain_paper_manual",
            "physical_evidence_status": "teacher_has_external_plain_paper",
            "created_by_workflow": "plain_paper_submission",
        },
    }


def _review(
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
) -> dict[str, Any]:
    return build_empty_review_record(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        created_at=TIMESTAMP,
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_plain_submission(
    workspace: Path,
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
) -> Path:
    value = _plain_submission(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    validate_submission_manifest(value)
    work_ref = quillan_work_ref(class_id, assignment_id)
    path = submission_manifest_path(workspace, work_ref, student_id)
    _write_json(path, value)
    return path


def _write_review(
    workspace: Path,
    value: dict[str, Any],
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
) -> Path:
    validate_review_record(value)
    work_ref = quillan_work_ref(class_id, assignment_id)
    path = review_record_path(workspace, work_ref, student_id)
    _write_json(path, value)
    return path


def _prepare_plain_pair(workspace: Path) -> None:
    _write_assignment(workspace)
    _write_standards(workspace)
    _write_plain_submission(workspace)
    _write_review(workspace, _review())


def test_manifest_work_paths_are_revision_addressed_and_side_effect_free(
    tmp_path: Path,
) -> None:
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    expected = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
        "exports/manifests/academic_results/7.json"
    )

    assert academic_result_manifest_relative_path(work, 7) == expected
    assert academic_result_manifest_revision_path(tmp_path, work, 7) == tmp_path.joinpath(
        *PurePosixPath(expected).parts
    )
    assert manifest_exports_dir(tmp_path, work).name == "manifests"
    assert academic_result_manifests_dir(tmp_path, work).name == "academic_results"
    assert not academic_result_manifests_dir(tmp_path, work).exists()

    with pytest.raises(ValueError, match="positive non-Boolean"):
        academic_result_manifest_revision_path(tmp_path, work, True)
    with pytest.raises(ValueError, match="positive non-Boolean"):
        academic_result_manifest_relative_path(work, 0)


def test_empty_submission_population_builds_empty_manifest(tmp_path: Path) -> None:
    assignment_path = _write_assignment(tmp_path)
    _write_standards(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    context = load_academic_result_manifest_generation_context(tmp_path, work)
    manifest = build_academic_result_manifest(
        context,
        record_set_revision=1,
        generated_at=datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc),
    )

    assert context.submissions_dir_present is False
    assert context.native_students == ()
    assert manifest.students == ()
    assert manifest.record_set.record_set_id == "academic_results"
    assert manifest.source_snapshot.sha256 == hashlib.sha256(
        assignment_path.read_bytes()
    ).hexdigest()
    assert manifest.source_snapshot.relative_path == "assignment.json"


def test_plain_paper_pair_is_represented_with_exact_source_hashes(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    context = load_academic_result_manifest_generation_context(tmp_path, work)
    manifest = build_academic_result_manifest(
        context,
        record_set_revision=3,
        generated_at=datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc),
    )

    assert [student.student_id for student in manifest.students] == [STUDENT_ID]
    student = manifest.students[0]
    assert student.submission.entry_method == "plain_paper_manual"
    assert student.submission.expected_pages is None
    assert student.submission.digital_provenance is None
    assert student.source_snapshot.submission.relative_path == (
        f"submissions/{STUDENT_ID}/submission.json"
    )
    assert student.source_snapshot.review.relative_path == (
        f"submissions/{STUDENT_ID}/review.json"
    )
    submission = submission_manifest_path(tmp_path, work, STUDENT_ID)
    review = review_record_path(tmp_path, work, STUDENT_ID)
    assert student.source_snapshot.submission.sha256 == hashlib.sha256(
        submission.read_bytes()
    ).hexdigest()
    assert student.source_snapshot.review.sha256 == hashlib.sha256(
        review.read_bytes()
    ).hexdigest()
    assert manifest.record_set.revision == 3


def test_plain_paper_requires_exact_native_provenance_markers(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    submission = _plain_submission()
    submission["module_details"]["created_by_workflow"] = "other_workflow"
    validate_submission_manifest(submission)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    _write_json(submission_manifest_path(tmp_path, work, STUDENT_ID), submission)
    _write_review(tmp_path, _review())

    with pytest.raises(
        QuillanManifestGenerationValidationError, match="provenance markers"
    ):
        load_academic_result_manifest_generation_context(tmp_path, work)


def test_submission_without_review_is_validated_but_not_represented(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    _write_plain_submission(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    context = load_academic_result_manifest_generation_context(tmp_path, work)

    assert len(context.native_students) == 1
    state = context.native_students[0]
    assert state.student_id == STUDENT_ID
    assert state.submission_source is None
    assert state.review_source is None
    assert state.result is None
    assert context.students == ()


def test_orphan_review_fails_closed(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    _write_review(tmp_path, _review())
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    with pytest.raises(
        QuillanManifestGenerationIntegrityError, match="native student result"
    ):
        load_academic_result_manifest_generation_context(tmp_path, work)


def test_direct_nonstudent_child_fails_discovery(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    submissions = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
    )
    submissions.mkdir(parents=True)
    (submissions / "unexpected.txt").write_text("x", encoding="utf-8")

    with pytest.raises(
        QuillanManifestGenerationValidationError, match="unexpected direct child"
    ):
        discover_manifest_student_ids(tmp_path, work)


def test_standards_profile_is_required_and_focus_order_is_preserved(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    with pytest.raises(
        QuillanManifestGenerationValidationError, match="standards"
    ):
        load_academic_result_manifest_generation_context(tmp_path, work)

    _write_standards(tmp_path)
    context = load_academic_result_manifest_generation_context(tmp_path, work)
    assert context.assignment.focus_standard_ids == (STANDARD_ID,)


def test_context_recheck_detects_formatting_only_assignment_change(
    tmp_path: Path,
) -> None:
    assignment_path = _write_assignment(tmp_path)
    _write_standards(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    context = load_academic_result_manifest_generation_context(tmp_path, work)
    before = assignment_path.read_bytes()

    assignment_path.write_bytes(before + b"\n")

    with pytest.raises(QuillanManifestGenerationConflictError, match="changed"):
        verify_generation_context_unchanged(context)


def test_review_text_is_projected_without_private_field_leakage(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    _write_plain_submission(tmp_path)
    review = _review()
    review["review_state"] = "ratings_complete"
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "local_observation_1",
                    "standard_id": STANDARD_ID,
                    "applicable": True,
                    "evidence_present": True,
                    "rating": 1,
                    "rationale": "Student-facing observation rationale.",
                    "include_in_feedback": False,
                    "updated_at": TIMESTAMP,
                    "module_details": {"private": "do not publish"},
                }
            ],
            "module_details": {"private": "do not publish"},
        }
    ]
    review["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_ID,
            "rating": 1,
            "rationale": "Teacher-only overall rationale.",
            "include_in_feedback": True,
            "updated_at": TIMESTAMP,
            "module_details": {"private": "do not publish"},
        }
    ]
    review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": "Teacher-only minimum note.",
        "updated_at": TIMESTAMP,
    }
    review["feedback"] = {
        "include_review_unit_observations": True,
        "include_overall_standard_ratings": True,
        "standard_feedback": [
            {
                "standard_id": STANDARD_ID,
                "include_overall_rating": True,
                "include_overall_rationale": False,
                "included_observation_ids": ["local_observation_1"],
                "comments": [
                    {
                        "feedback_comment_id": "comment_included",
                        "source": "custom",
                        "text": "Included student comment.",
                        "reusable_comment_id": None,
                        "save_for_reuse": False,
                        "include_in_feedback": True,
                        "created_at": TIMESTAMP,
                        "module_details": {"private": "do not publish"},
                    },
                    {
                        "feedback_comment_id": "comment_private",
                        "source": "custom",
                        "text": "Unselected private comment.",
                        "reusable_comment_id": None,
                        "save_for_reuse": False,
                        "include_in_feedback": False,
                        "created_at": TIMESTAMP,
                        "module_details": {},
                    },
                ],
                "module_details": {"private": "do not publish"},
            }
        ],
    }
    review["private_notes"] = [
        {
            "private_note_id": "private_1",
            "text": "Never publish this private note.",
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_review(tmp_path, review)

    context = load_academic_result_manifest_generation_context(
        tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    )
    manifest = build_academic_result_manifest(
        context,
        record_set_revision=1,
        generated_at=datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc),
    )
    projected = manifest.students[0].review

    observation = projected.review_units[0].standard_observations[0]
    assert observation.rationale.disposition == "included"
    assert observation.rationale.text == "Student-facing observation rationale."
    assert projected.overall_standard_ratings[0].rationale.disposition == "withheld"
    assert projected.minimum_requirement_outcome.teacher_note.disposition == "withheld"
    comments = projected.feedback.standard_feedback[0].comments
    assert [comment.feedback_comment_id for comment in comments] == ["comment_included"]
    encoded = manifest_to_canonical_json_bytes(manifest)
    assert b"Never publish this private note" not in encoded
    assert b"Unselected private comment" not in encoded
    assert b'"module_details"' not in encoded


def test_review_rating_must_belong_to_assignment_native_scale(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    _write_plain_submission(tmp_path)
    review = _review()
    review["review_state"] = "ratings_complete"
    review["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_ID,
            "rating": 99,
            "rationale": None,
            "include_in_feedback": False,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_review(tmp_path, review)

    with pytest.raises(
        QuillanManifestGenerationValidationError, match="assignment rating scale"
    ):
        load_academic_result_manifest_generation_context(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
        )


def test_return_without_full_review_must_be_allowed_by_assignment(tmp_path: Path) -> None:
    assignment_path = _write_assignment(tmp_path)
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment["minimum_requirement_policy"]["allow_return_without_full_review"] = False
    _write_json(assignment_path, assignment)
    _write_standards(tmp_path)
    _write_plain_submission(tmp_path)
    review = _review()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Please complete the required elements.",
        "updated_at": TIMESTAMP,
    }
    _write_review(tmp_path, review)

    with pytest.raises(
        QuillanManifestGenerationValidationError, match="forbids"
    ):
        load_academic_result_manifest_generation_context(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
        )


def _prepare_pds2_pair(tmp_path: Path) -> tuple[str, str, str, Path, Path]:
    outcome = successful_image_page(tmp_path)
    persisted = persist_quillan_page_observation(tmp_path, outcome)
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not assembled.failures
    _write_standards(tmp_path)
    review = _review(
        class_id=observation.class_id,
        assignment_id=observation.assignment_id,
        student_id=observation.student_id,
    )
    _write_review(
        tmp_path,
        review,
        class_id=observation.class_id,
        assignment_id=observation.assignment_id,
        student_id=observation.student_id,
    )
    retained = tmp_path.joinpath(*PurePosixPath(observation.retained_source_path).parts)
    routed = tmp_path.joinpath(*PurePosixPath(observation.routed_evidence_path).parts)
    return (
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
        retained,
        routed,
    )


def test_selected_pds2_evidence_is_validated_and_projected(tmp_path: Path) -> None:
    class_id, assignment_id, student_id, _, _ = _prepare_pds2_pair(tmp_path)
    context = load_academic_result_manifest_generation_context(
        tmp_path, quillan_work_ref(class_id, assignment_id)
    )
    assert [student.student_id for student in context.students] == [student_id]
    digital = context.students[0].submission.digital_provenance
    assert digital is not None
    assert len(digital.evidence_references) == 1
    reference = digital.evidence_references[0]
    assert reference.evidence_id == reference.observation_id
    assert reference.source_sha256
    assert reference.routed_evidence_sha256


def test_changed_retained_bytes_fail_selected_evidence_integrity(tmp_path: Path) -> None:
    class_id, assignment_id, _, retained, _ = _prepare_pds2_pair(tmp_path)
    retained.write_bytes(retained.read_bytes() + b"tampered")

    with pytest.raises(
        QuillanManifestGenerationIntegrityError, match="retained-source bytes"
    ):
        load_academic_result_manifest_generation_context(
            tmp_path, quillan_work_ref(class_id, assignment_id)
        )


def test_changed_routed_bytes_fail_selected_evidence_integrity(tmp_path: Path) -> None:
    class_id, assignment_id, _, _, routed = _prepare_pds2_pair(tmp_path)
    routed.write_bytes(routed.read_bytes() + b"tampered")

    with pytest.raises(
        QuillanManifestGenerationIntegrityError, match="routed evidence"
    ):
        load_academic_result_manifest_generation_context(
            tmp_path, quillan_work_ref(class_id, assignment_id)
        )


def test_pure_builder_rejects_naive_generation_time(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)
    context = load_academic_result_manifest_generation_context(
        tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    )
    with pytest.raises(
        QuillanManifestGenerationValidationError, match="timezone-aware"
    ):
        build_academic_result_manifest(
            context,
            record_set_revision=1,
            generated_at=datetime(2026, 8, 12, 20, 0),
        )
