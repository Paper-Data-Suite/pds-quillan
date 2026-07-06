"""Tests for legacy comment helper fail-closed behavior under v2 reviews."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quillan.comment_bank_writing import write_comment_bank
from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_record_paths import review_record_path

BANK_ID = "general_writing"


def _bank() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "comment_bank",
        "bank_id": BANK_ID,
        "label": "General Writing",
        "description": "Synthetic comments.",
        "writing_types": ["essay"],
        "categories": [{"category_id": "claims", "label": "Claims"}],
        "comments": [
            {
                "comment_id": "clear_claim",
                "label": "Clear claim",
                "text": "Your claim is clear.",
                "category_id": "claims",
                "student_facing": True,
                "include_in_feedback_default": True,
                "tags": [],
                "standard_ids": [],
                "criterion_ids": [],
                "hotwords": [],
                "module_details": {},
            }
        ],
        "module_details": {},
    }


def _write_bank(workspace: Path) -> Path:
    return write_comment_bank(workspace, _bank())


def test_add_review_comment_fails_closed_without_creating_v1_record(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReviewCommentError, match="schema version 2"):
        add_review_comment(
            tmp_path,
            "english12_p3_synthetic",
            "essay_01_synthetic",
            "00107",
            bank_id=BANK_ID,
            comment_id="clear_claim",
        )

    assert not review_record_path(
        tmp_path,
        "english12_p3_synthetic",
        "essay_01_synthetic",
        "00107",
    ).exists()
