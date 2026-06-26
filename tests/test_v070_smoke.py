"""End-to-end smoke coverage for the v0.7 teacher review/export workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

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
from quillan.review_comments import add_review_comment
from quillan.review_notes import add_review_note
from quillan.review_record import load_review_record
from quillan.review_scores import set_review_score
from quillan.review_tags import add_review_tag
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
            "assignment_id": ASSIGNMENT_ID,
            "title": "Synthetic Villainy Essay",
            "class_ids": [CLASS_ID],
            "writing_type": "literary_analysis",
            "standards_profile_id": PROFILE_ID,
            "tagging_mode": "focus",
            "focus_standards": [STANDARD_ID],
            "basic_requirements": {},
            "rubric_id": "synthetic_rubric",
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
    assert review["review_state"] == "in_progress"
    assert [note["text"] for note in review["notes"]] == [
        "Private synthetic teacher note."
    ]
    assert submission_path.read_bytes() == submission_before_review

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
    review = load_review_record(review_path)
    assert review["tags"] == [
        {
            "tag_id": "tag_0001",
            "label": "Synthetic evidence needs development",
            "polarity": "developing",
            "created_at": TAG_AT,
            "module_details": {},
            "standard_id": STANDARD_ID,
            "page_number": 1,
            "evidence_id": page["selected_evidence_id"],
        }
    ]
    assert review["scores"] == []
    assert review["comments"] == []

    selected_comment = add_review_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        bank_id=BANK_ID,
        comment_id=COMMENT_ID,
        created_at=COMMENT_AT,
    )
    assert selected_comment.include_in_feedback is True
    review = load_review_record(review_path)
    comment = review["comments"][0]
    assert comment["source"] == "comment_bank"
    assert comment["bank_id"] == BANK_ID
    assert comment["comment_id"] == COMMENT_ID
    assert comment["label"] == "Explain the evidence"
    assert comment["text"] == comment_text
    assert comment["standard_id"] == STANDARD_ID
    assert comment["include_in_feedback"] is True
    assert comment_bank_path.read_bytes() == bank_before_review

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
    review = load_review_record(review_path)
    score = review["scores"][0]
    assert score["criterion_id"] == "evidence"
    assert score["score"] == 3
    assert score["max_score"] == 4
    forbidden_score_fields = {
        "overall_score",
        "percentage",
        "grade",
        "mastery_level",
        "ai_score",
        "ai_feedback",
    }
    assert forbidden_score_fields.isdisjoint(review)
    assert forbidden_score_fields.isdisjoint(score)
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
    assert comment_text in feedback_text
    assert "- Use of Evidence: 3 / 4" in feedback_text
    for private_value in (
        "Private synthetic teacher note.",
        "Synthetic evidence needs development",
        "Private synthetic score note.",
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
    assert class_row["row_status"] == "ready"
    assert class_row["score_count"] == "1"
    assert class_row["selected_comment_count"] == "1"
    assert class_row["included_comment_count"] == "1"
    assert class_row["tag_count"] == "1"
    assert class_row["note_count"] == "1"
    assert class_row["feedback_export_exists"] == "true"
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
    standards_row = standards_rows[0]
    assert standards_row["standard_id"] == STANDARD_ID
    assert standards_row["tag_count"] == "1"
    assert standards_row["developing_tag_count"] == "1"
    assert standards_row["positive_tag_count"] == "0"
    assert standards_row["negative_tag_count"] == "0"
    assert standards_row["neutral_tag_count"] == "0"
    assert standards_row["selected_comment_count"] == "1"
    assert standards_row["included_comment_count"] == "1"
    assert standards_row["excluded_comment_count"] == "0"
    assert not {"score_count", "total_score", "total_max_score"} & set(
        standards_row
    )
    for path, original in canonical_before_exports.items():
        assert path.read_bytes() == original
