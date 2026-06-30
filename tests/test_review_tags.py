"""Tests for teacher-entered structured review tags."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_tags import (
    AddedReviewTag,
    ReviewTagError,
    add_review_tag,
)
from quillan.storage import assignment_config_path
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
PROFILE_ID = "english_12_njsls_synthetic"
STANDARD_ID = "njsls-ela:W.AW.11-12.1"
REVISION_STANDARD_ID = "njsls-ela:W.WP.11-12.4"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_TAG_TIMESTAMP = "2026-06-22T13:35:00-04:00"
SECOND_TAG_TIMESTAMP = "2026-06-22T14:00:00-04:00"


def _manifest() -> dict[str, Any]:
    def evidence(evidence_id: str, page_number: int) -> dict[str, Any]:
        return {
            "evidence_id": evidence_id,
            "routed_evidence_path": (
                f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/"
                f"response_00107_pg_{page_number:03d}.pdf"
            ),
            "evidence_role": "selected",
            "evidence_state": "active",
            "duplicate_number": None,
            "created_at": ORIGINAL_TIMESTAMP,
            "retained_source": {
                "source_scan_id": f"scan_{page_number:03d}",
                "source_filename": f"source_{page_number}.pdf",
                "source_sha256": str(page_number) * 64,
                "retained_source_path": (
                    f"routing/source_scans/scan_{page_number:03d}/"
                    f"source_{page_number}.pdf"
                ),
                "source_page_number": page_number,
            },
            "module_details": {},
        }

    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 2,
        "submission_state": "unreviewed",
        "pages": [
            {
                "page_number": page_number,
                "page_state": "present",
                "selected_evidence_id": f"evidence_{page_number:03d}",
                "evidence": [evidence(f"evidence_{page_number:03d}", page_number)],
            }
            for page_number in (1, 2)
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {"preserve": True},
    }


def _review(state: str = "not_started") -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_review",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "submission_manifest_path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        "review_state": state,
        "notes": [
            {
                "note_id": "note_0001",
                "text": "Existing note.",
                "created_at": ORIGINAL_TIMESTAMP,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "tags": [
            {
                "tag_id": "tag_0001",
                "label": "Existing tag",
                "polarity": "neutral",
                "created_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "comments": [
            {
                "comment_record_id": "comment_0001",
                "label": "Existing comment",
                "text": "Existing selected language.",
                "source": "custom",
                "include_in_feedback": True,
                "created_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {"preserve": True},
    }


def _assignment() -> dict[str, Any]:
    return {
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "standards_profile_id": PROFILE_ID,
        "tagging_mode": "focus",
        "focus_standards": [STANDARD_ID],
        "basic_requirements": {},
        "rubric_id": "argument_4pt",
    }


def _standards_library() -> StandardsLibrary:
    return StandardsLibrary(
        standards=(
            StandardDefinition(
                standard_id=STANDARD_ID,
                code="W.AW.11-12.1",
                source="NJSLS",
                short_name="Argument Writing",
                description="Use claims, reasoning, and evidence.",
                subject="English Language Arts",
                course="English 12",
                domain="Writing",
                available_modules=("quillan",),
            ),
            StandardDefinition(
                standard_id=REVISION_STANDARD_ID,
                code="W.WP.11-12.4",
                source="NJSLS",
                short_name="Writing Process",
                description="Develop and strengthen writing.",
                subject="English Language Arts",
                course="English 12",
                domain="Writing",
                available_modules=("quillan",),
            ),
        ),
        profiles=(
            StandardsProfile(
                profile_id=PROFILE_ID,
                standards=(STANDARD_ID, REVISION_STANDARD_ID),
                subject="English Language Arts",
                course="English 12",
                source="NJSLS",
                title="Synthetic English 12",
            ),
        ),
    )


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _write_manifest(
    workspace: Path, manifest: dict[str, Any] | None = None
) -> Path:
    path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    return write_submission_manifest(
        path, _manifest() if manifest is None else manifest
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_review_record(path, review)


def _write_profile_context(workspace: Path) -> None:
    _write_json(
        assignment_config_path(workspace, CLASS_ID, ASSIGNMENT_ID),
        _assignment(),
    )
    write_workspace_standards_library(workspace, _standards_library())


def test_creates_structured_tag_without_mutating_submission_or_evidence(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    evidence_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00107_pg_001.pdf"
    )
    retained_path = (
        tmp_path / "routing" / "source_scans" / "scan_001" / "source_1.pdf"
    )
    evidence_path.parent.mkdir(parents=True)
    retained_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"routed evidence")
    retained_path.write_bytes(b"retained source")
    original_manifest = manifest_path.read_bytes()

    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="  Clear central claim  ",
        polarity="positive",
        page_number=1,
        evidence_id="evidence_001",
        location_type="paragraph",
        location_value=2,
        created_at=FIRST_TAG_TIMESTAMP,
    )

    expected_relative_path = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    )
    assert result == AddedReviewTag(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        review_record_path=review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ),
        review_record_relative_path=expected_relative_path,
        tag_id="tag_0001",
        polarity="positive",
        review_state="in_progress",
        created_at=FIRST_TAG_TIMESTAMP,
    )
    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert written["submission_manifest_path"] == expected_relative_path.replace(
        "review.json", "submission.json"
    )
    assert written["review_state"] == "in_progress"
    assert written["notes"] == written["scores"] == written["comments"] == []
    assert written["created_at"] == written["updated_at"] == FIRST_TAG_TIMESTAMP
    assert written["tags"] == [
        {
            "tag_id": "tag_0001",
            "label": "Clear central claim",
            "polarity": "positive",
            "created_at": FIRST_TAG_TIMESTAMP,
            "module_details": {},
            "page_number": 1,
            "evidence_id": "evidence_001",
            "location": {"type": "paragraph", "value": 2},
        }
    ]
    assert manifest_path.read_bytes() == original_manifest
    assert evidence_path.read_bytes() == b"routed evidence"
    assert retained_path.read_bytes() == b"retained source"


def test_add_review_tag_stores_multiple_paragraph_target(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Explain evidence",
        polarity="developing",
        page_number=1,
        location_type="paragraph",
        location_value=[2, 3, 4],
        created_at=FIRST_TAG_TIMESTAMP,
    )

    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert written["tags"][0]["page_number"] == 1
    assert written["tags"][0]["location"] == {
        "type": "paragraph",
        "value": [2, 3, 4],
    }


def test_appends_tag_and_preserves_existing_review_sections(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    original = _review()
    path = _write_review(tmp_path, copy.deepcopy(original))

    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Second tag",
        polarity="neutral",
        created_at=SECOND_TAG_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.tag_id == "tag_0002"
    assert written["tags"][:-1] == original["tags"]
    for field in ("notes", "scores", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["created_at"] == original["created_at"]
    assert written["updated_at"] == SECOND_TAG_TIMESTAMP
    assert written["review_state"] == "in_progress"


@pytest.mark.parametrize(
    ("initial_state", "expected_state"),
    [
        ("not_started", "in_progress"),
        ("in_progress", "in_progress"),
        ("ready_for_export", "ready_for_export"),
        ("exported", "exported"),
    ],
)
def test_append_uses_narrow_review_state_transition(
    tmp_path: Path,
    initial_state: str,
    expected_state: str,
) -> None:
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review(initial_state))

    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="State tag",
        polarity="neutral",
        created_at=SECOND_TAG_TIMESTAMP,
    )

    assert result.review_state == expected_state


def test_tag_id_uses_highest_conforming_sequence(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["tags"].extend(
        [
            {
                "tag_id": "custom-tag",
                "label": "Custom",
                "polarity": "neutral",
                "created_at": ORIGINAL_TIMESTAMP,
                "module_details": {},
            },
            {
                "tag_id": "tag_0004",
                "label": "Later",
                "polarity": "neutral",
                "created_at": ORIGINAL_TIMESTAMP,
                "module_details": {},
            },
        ]
    )
    _write_review(tmp_path, review)

    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Next",
        polarity="neutral",
        created_at=SECOND_TAG_TIMESTAMP,
    )

    assert result.tag_id == "tag_0005"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"label": " "}, "label"),
        ({"polarity": "mixed"}, "polarity"),
        ({"severity": -1}, "severity"),
        ({"severity": True}, "severity"),
        ({"teacher_note": " "}, "teacher_note"),
        ({"page_number": 0}, "page_number"),
        ({"evidence_id": " "}, "evidence_id"),
        ({"location_type": "word", "location_value": 1}, "location_type"),
        ({"location_value": 1}, "requires location_type"),
        (
            {"location_type": "paragraph", "location_value": "two"},
            "positive integer",
        ),
        (
            {"location_type": "paragraph", "location_value": [2, 2]},
            "more than once",
        ),
        (
            {"location_type": "whole_submission", "location_value": 1},
            "must be omitted",
        ),
        (
            {
                "location_type": "page",
                "location_value": 2,
                "page_number": 1,
            },
            "agree",
        ),
        (
            {"location_type": "page", "location_value": 3},
            "does not exist",
        ),
    ],
)
def test_invalid_tag_input_is_rejected_without_writing(
    tmp_path: Path,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    _write_manifest(tmp_path)
    arguments: dict[str, Any] = {
        "label": "Valid label",
        "polarity": "neutral",
        "created_at": FIRST_TAG_TIMESTAMP,
    }
    arguments.update(kwargs)

    with pytest.raises(ReviewTagError, match=message):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            **arguments,
        )

    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


@pytest.mark.parametrize(
    ("page_number", "evidence_id", "message"),
    [
        (3, None, "does not exist"),
        (None, "missing", "does not exist"),
        (1, "evidence_002", "occurs on page 2"),
    ],
)
def test_invalid_manifest_reference_is_rejected(
    tmp_path: Path,
    page_number: int | None,
    evidence_id: str | None,
    message: str,
) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewTagError, match=message):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Reference tag",
            polarity="neutral",
            page_number=page_number,
            evidence_id=evidence_id,
            created_at=FIRST_TAG_TIMESTAMP,
        )


@pytest.mark.parametrize(
    ("page_number", "evidence_id"),
    [(1, None), (None, "evidence_002")],
)
def test_individual_valid_manifest_reference_is_accepted(
    tmp_path: Path,
    page_number: int | None,
    evidence_id: str | None,
) -> None:
    _write_manifest(tmp_path)

    add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Reference tag",
        polarity="neutral",
        page_number=page_number,
        evidence_id=evidence_id,
        created_at=FIRST_TAG_TIMESTAMP,
    )


def test_whole_submission_and_named_location_are_accepted(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Whole submission",
        polarity="positive",
        location_type="whole_submission",
        created_at=FIRST_TAG_TIMESTAMP,
    )
    add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Conclusion",
        polarity="developing",
        location_type="section",
        location_value=" conclusion ",
        created_at=SECOND_TAG_TIMESTAMP,
    )
    written = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert written["tags"][0]["location"]["value"] is None
    assert written["tags"][1]["location"]["value"] == "conclusion"


def test_profile_standard_reference_is_validated_without_default_severity(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    _write_profile_context(tmp_path)

    add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Evidence needs more explanation",
        polarity="developing",
        standard_id=STANDARD_ID,
        comment_id="evidence_needs_explanation",
        created_at=FIRST_TAG_TIMESTAMP,
    )

    written = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert "severity" not in written["tags"][0]


def test_profile_allows_non_focus_standard(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_profile_context(tmp_path)

    add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Revision observation",
        polarity="neutral",
        standard_id=REVISION_STANDARD_ID,
        created_at=FIRST_TAG_TIMESTAMP,
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"standard_id": "missing"}, "unknown standard IDs"),
        ({"comment_id": "comment"}, "requires standard_id"),
    ],
)
def test_invalid_profile_reference_is_rejected(
    tmp_path: Path,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    _write_manifest(tmp_path)
    _write_profile_context(tmp_path)
    arguments: dict[str, Any] = {
        "label": "Evidence needs more explanation",
        "polarity": "developing",
        "created_at": FIRST_TAG_TIMESTAMP,
    }
    arguments.update(kwargs)

    with pytest.raises(ReviewTagError, match=message):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            **arguments,
        )


def test_standard_reference_requires_assignment_and_profile(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    with pytest.raises(ReviewTagError, match="assignment config"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Standard tag",
            polarity="neutral",
            standard_id=STANDARD_ID,
            created_at=FIRST_TAG_TIMESTAMP,
        )


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-time",
        "2026-06-22T13:30:00",
        datetime(2026, 6, 22, 13, 30),
        123,
    ],
)
def test_invalid_timestamp_is_rejected(tmp_path: Path, timestamp: object) -> None:
    _write_manifest(tmp_path)
    with pytest.raises(ReviewTagError, match="timezone-aware"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Timestamp tag",
            polarity="neutral",
            created_at=timestamp,  # type: ignore[arg-type]
        )


def test_timezone_aware_datetime_is_normalized(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    timestamp = datetime(2026, 6, 22, 17, 30, tzinfo=timezone.utc)
    result = add_review_tag(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        label="Timestamp tag",
        polarity="neutral",
        created_at=timestamp,
    )
    assert result.created_at == timestamp.isoformat()


def test_missing_submission_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewTagError, match="not review-ready yet"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Missing",
            polarity="neutral",
            created_at=FIRST_TAG_TIMESTAMP,
        )


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_invalid_existing_record_is_rejected_without_review_write(
    tmp_path: Path, record_kind: str
) -> None:
    manifest_path = _write_manifest(tmp_path)
    record_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    if record_kind == "submission":
        manifest_path.write_text("{", encoding="utf-8")
    else:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text("{", encoding="utf-8")
    original = record_path.read_bytes() if record_path.exists() else None

    with pytest.raises(ReviewTagError, match="not valid JSON"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Invalid record",
            polarity="neutral",
            created_at=FIRST_TAG_TIMESTAMP,
        )

    assert (
        record_path.read_bytes() if record_path.exists() else None
    ) == original


@pytest.mark.parametrize(
    ("record_kind", "field", "value"),
    [
        ("submission", "class_id", "other_class"),
        ("submission", "assignment_id", "other_assignment"),
        ("submission", "student_id", "00108"),
        ("review", "class_id", "other_class"),
        ("review", "assignment_id", "other_assignment"),
        ("review", "student_id", "00108"),
    ],
)
def test_identity_mismatch_is_rejected(
    tmp_path: Path,
    record_kind: str,
    field: str,
    value: str,
) -> None:
    manifest = _manifest()
    review = _review()
    if record_kind == "submission":
        manifest[field] = value
    else:
        review[field] = value
        review["submission_manifest_path"] = (
            f"classes/{review['class_id']}/assignments/"
            f"{review['assignment_id']}/submissions/{review['student_id']}/"
            "submission.json"
        )
    _write_manifest(tmp_path, manifest)
    if record_kind == "review":
        _write_review(tmp_path, review)

    with pytest.raises(ReviewTagError, match=field):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Mismatch",
            polarity="neutral",
            created_at=FIRST_TAG_TIMESTAMP,
        )
