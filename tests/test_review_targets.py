"""Tests for shared review target helpers."""

from __future__ import annotations

import pytest

from quillan.review_targets import (
    ReviewTargetError,
    format_review_target,
    parse_paragraph_selection,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2", 2),
        ("2-4", [2, 3, 4]),
        ("2,4,6", [2, 4, 6]),
        ("2, 4-6", [2, 4, 5, 6]),
    ],
)
def test_parse_paragraph_selection(raw: str, expected: int | list[int]) -> None:
    assert parse_paragraph_selection(raw) == expected


@pytest.mark.parametrize("raw", ["0", "-1", "3-2", "2,,4", "two", "2.5", "2,2"])
def test_parse_paragraph_selection_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ReviewTargetError):
        parse_paragraph_selection(raw)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"location": {"type": "paragraph", "value": 2}}, "Paragraph 2"),
        (
            {"location": {"type": "paragraph", "value": [2, 3, 4]}},
            "Paragraphs 2-4",
        ),
        ({"page_number": 1}, "Page 1"),
        (
            {"page_number": 1, "location": {"type": "paragraph", "value": [2, 3]}},
            "Page 1, paragraphs 2-3",
        ),
        ({"evidence_id": "evidence_001"}, "Evidence evidence_001"),
        (
            {"page_number": 1, "evidence_id": "evidence_001"},
            "Page 1, Evidence evidence_001",
        ),
        (
            {
                "page_number": 1,
                "evidence_id": "evidence_001",
                "location": {"type": "paragraph", "value": [2, 3]},
            },
            "Page 1, paragraphs 2-3, Evidence evidence_001",
        ),
        (
            {
                "evidence_id": "evidence_001",
                "location": {"type": "paragraph", "value": [2, 3]},
            },
            "Paragraphs 2-3, Evidence evidence_001",
        ),
        (
            {"location": {"type": "whole_submission", "value": None}},
            "Whole submission",
        ),
        ({}, "Not specified"),
    ],
)
def test_format_review_target(item: dict[str, object], expected: str) -> None:
    assert format_review_target(item) == expected
