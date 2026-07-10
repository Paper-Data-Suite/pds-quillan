"""End-to-end smoke coverage for the v0.7 teacher review/export workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
)
from quillan.class_summary_export import export_class_review_summary
from quillan.feedback_export import export_student_feedback
from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_notes import add_review_note
from quillan.review_record import load_review_record
from quillan.review_scores import ReviewScoreError, set_review_score
from quillan.review_tags import ReviewTagError, add_review_tag
from quillan.standards_summary_export import export_standards_summary
from quillan.storage import assignment_config_path
from quillan.submission_manifest import (
    load_submission_manifest,
    validate_submission_manifest,
)

CLASS_ID = "english12_period3_synthetic"
ASSIGNMENT_ID = "villainy_final_essay_synthetic"
STUDENT_ID = "stu_0001"
PROFILE_ID = "english_12_synthetic"
STANDARD_ID = "njsls-ela:RL.CR.11-12.1"
BANK_ID = "general_writing_synthetic"
COMMENT_ID = "evidence_explanation_synthetic"
ASSEMBLED_AT = "2026-06-23T12:00:00+00:00"
NOTE_AT = "2026-06-23T12:10:00+00:00"
TAG_AT = "2026-06-23T12:20:00+00:00"
COMMENT_AT = "2026-06-23T12:30:00+00:00"
SCORE_AT = "2026-06-23T12:40:00+00:00"
EXPORTED_AT = "2026-06-23T12:50:00+00:00"


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_v070_synthetic_teacher_review_and_export_workflow(
    tmp_path: Path,
) -> None:
    assignment_path = assignment_config_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    _write_json(
        assignment_path,
        {
            "schema_version": "2",
            "module": "quillan",
            "record_type": "assignment",
            "assignment_id": ASSIGNMENT_ID,
            "title": "Synthetic Villainy Essay",
            "class_ids": [CLASS_ID],
            "writing_type": "literary_analysis",
            "student_prompt": "Analyze how the text develops villainy.",
            "standards_profile_id": PROFILE_ID,
            "focus_standard_ids": [STANDARD_ID],
            "review_unit": {
                "type": "paragraph",
                "singular_label": "paragraph",
                "plural_label": "paragraphs",
            },
            "rating_scale": {
                "scale_id": "standards_2_level",
                "levels": [
                    {
                        "value": 1,
                        "label": "Developing",
                        "description": "Limited evidence.",
                    }
                ],
            },
            "basic_requirements": {},
            "minimum_requirement_policy": {
                "allow_return_without_full_review": True,
            },
        },
    )
    write_workspace_standards_library(
        tmp_path,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="RL.CR.11-12.1",
                    source="NJSLS",
                    short_name="Citing evidence",
                    description="Cite evidence to support analysis.",
                    subject="English Language Arts",
                    course="Synthetic English 12",
                    domain="Reading Literature",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id=PROFILE_ID,
                    standards=(STANDARD_ID,),
                    subject="English Language Arts",
                    course="Synthetic English 12",
                    source="NJSLS",
                    title="Synthetic English 12",
                ),
            ),
        ),
    )
    comment_text = (
        "Explain how the selected evidence supports your central idea."
    )
    comment_bank_path = _write_json(
        tmp_path / "shared" / "comment_banks" / f"{BANK_ID}.json",
        {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "comment_bank",
            "bank_id": BANK_ID,
            "title": "Synthetic General Writing Comments",
            "description": "Local synthetic comments for the v0.7 smoke test.",
            "scope": "shared",
            "writing_types": ["literary_analysis"],
            "categories": [
                {
                    "category_id": "analysis",
                    "label": "Analysis",
                    "module_details": {},
                }
            ],
            "comments": [
                {
                    "comment_id": COMMENT_ID,
                    "label": "Explain the evidence",
                    "text": comment_text,
                    "category_id": "analysis",
                    "writing_types": ["literary_analysis"],
                    "standard_ids": [STANDARD_ID],
                    "criterion_ids": ["evidence"],
                    "polarity": "developing",
                    "include_in_feedback_default": True,
                    "student_facing": True,
                    "module_details": {},
                }
            ],
            "created_at": ASSEMBLED_AT,
            "updated_at": ASSEMBLED_AT,
            "module_details": {},
        },
    )

    scans_dir = assignment_path.parent / "scans"
    scans_dir.mkdir(parents=True)
    evidence_path = scans_dir / f"response_{STUDENT_ID}_pg_001.pdf"
    evidence_path.write_bytes(b"synthetic local essay evidence")

    assembly = assemble_assignment_submissions(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_pages=1,
        created_at=ASSEMBLED_AT,
        updated_at=ASSEMBLED_AT,
    )
    assert assembly.students_with_evidence == (STUDENT_ID,)
    assert len(assembly.written_manifests) == 1
    submission_path = assembly.written_manifests[0]
    submission = load_submission_manifest(submission_path)
    validate_submission_manifest(submission)
    assert (
        submission["class_id"],
        submission["assignment_id"],
        submission["student_id"],
    ) == (CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    page = submission["pages"][0]
    assert page["selected_evidence_id"] is not None
    assert len(page["evidence"]) == 1
    selected_evidence_path = (
        tmp_path / page["evidence"][0]["routed_evidence_path"]
    )
    assert selected_evidence_path == evidence_path
    assert selected_evidence_path.is_file()

    submission_before_review = submission_path.read_bytes()
    evidence_before_review = evidence_path.read_bytes()
    bank_before_review = comment_bank_path.read_bytes()

    added_note = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "Private synthetic teacher note.",
        created_at=NOTE_AT,
    )
    review_path = added_note.review_record_path
    review = load_review_record(review_path)
    assert review["review_state"] == "not_started"
    assert [note["text"] for note in review["private_notes"]] == [
        "Private synthetic teacher note."
    ]
    assert submission_path.read_bytes() == submission_before_review
    review_before_legacy_helpers = review_path.read_bytes()

    with pytest.raises(ReviewTagError, match="schema version 2"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Synthetic evidence needs development",
            polarity="developing",
            standard_id=STANDARD_ID,
            page_number=1,
            evidence_id=page["selected_evidence_id"],
            created_at=TAG_AT,
        )
    with pytest.raises(ReviewCommentError, match="schema version 2"):
        add_review_comment(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            bank_id=BANK_ID,
            comment_id=COMMENT_ID,
            created_at=COMMENT_AT,
        )
    with pytest.raises(ReviewScoreError, match="schema version 2"):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            criterion_id="evidence",
            label="Use of Evidence",
            score=3,
            max_score=4,
            teacher_note="Private synthetic score note.",
            updated_at=SCORE_AT,
        )
    assert review_path.read_bytes() == review_before_legacy_helpers
    review = load_review_record(review_path)
    assert "notes" not in review
    assert "tags" not in review
    assert "comments" not in review
    assert "scores" not in review
    forbidden_score_fields = {
        "overall_score",
        "percentage",
        "grade",
        "mastery_level",
        "ai_score",
        "ai_feedback",
    }
    assert forbidden_score_fields.isdisjoint(review)
    assert submission_path.read_bytes() == submission_before_review
    assert evidence_path.read_bytes() == evidence_before_review
    assert comment_bank_path.read_bytes() == bank_before_review

    canonical_before_exports = {
        submission_path: submission_path.read_bytes(),
        review_path: review_path.read_bytes(),
        comment_bank_path: comment_bank_path.read_bytes(),
        evidence_path: evidence_path.read_bytes(),
    }

    feedback = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORTED_AT,
    )
    assert feedback.feedback_path == (
        submission_path.parent / "exports" / "feedback.md"
    )
    feedback_text = feedback.feedback_path.read_text(encoding="utf-8")
    assert "No Focus Standard feedback selected." in feedback_text
    for private_value in (
        "Private synthetic teacher note.",
        comment_text,
        BANK_ID,
        COMMENT_ID,
        STANDARD_ID,
        "comment_bank",
    ):
        assert private_value not in feedback_text
    for path, original in canonical_before_exports.items():
        assert path.read_bytes() == original

    class_summary = export_class_review_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        created_at=EXPORTED_AT,
    )
    class_rows = _read_csv_rows(class_summary.summary_path)
    assert len(class_rows) == 1
    class_row = class_rows[0]
    assert class_row["student_id"] == STUDENT_ID
    assert class_row["review_valid"] == "true"
    assert class_row["review_state"] == "not_started"
    assert class_row["feedback_pdf_status"] == "missing"
    assert class_row["feedback_markdown_status"] == "unknown"
    assert class_row["warnings"] == "feedback_markdown_metadata_missing"
    assert "Private note" not in class_summary.summary_path.read_text(encoding="utf-8")
    for path, original in canonical_before_exports.items():
        assert path.read_bytes() == original

    standards_summary = export_standards_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        created_at=EXPORTED_AT,
    )
    standards_rows = _read_csv_rows(standards_summary.summary_path)
    assert len(standards_rows) == 1
    assert standards_rows[0]["standard_id"] == STANDARD_ID
    assert standards_rows[0]["students_reviewed_for_standard"] == "0"
    for path, original in canonical_before_exports.items():
        assert path.read_bytes() == original
