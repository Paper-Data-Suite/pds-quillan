"""Shared review target parsing, normalization, and display helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from quillan.review_record import (
    ALLOWED_LOCATION_TYPES,
    FLEXIBLE_LOCATION_TYPES,
    INTEGER_LOCATION_TYPES,
)

_INTEGER = re.compile(r"\d+")
_RANGE = re.compile(r"(\d+)-(\d+)")


class ReviewTargetError(ValueError):
    """Raised when teacher-entered review target metadata is invalid."""


def parse_paragraph_selection(value: str) -> int | list[int]:
    """Parse teacher-entered paragraph numbers and ranges."""
    if not isinstance(value, str) or not value.strip():
        raise ReviewTargetError("Paragraph number(s) are required.")

    paragraphs: list[int] = []
    seen: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise ReviewTargetError("Paragraph entries must not be empty.")
        if range_match := _RANGE.fullmatch(part):
            start = _parse_positive_integer(range_match.group(1), "paragraph")
            end = _parse_positive_integer(range_match.group(2), "paragraph")
            if end < start:
                raise ReviewTargetError("Paragraph ranges must go from low to high.")
            candidates: Iterable[int] = range(start, end + 1)
        elif _INTEGER.fullmatch(part):
            candidates = (_parse_positive_integer(part, "paragraph"),)
        else:
            raise ReviewTargetError(
                "Use paragraph numbers and ranges such as 2, 2-4, or 2, 4-6."
            )

        for paragraph in candidates:
            if paragraph in seen:
                raise ReviewTargetError(
                    f"Paragraph {paragraph} was entered more than once."
                )
            seen.add(paragraph)
            paragraphs.append(paragraph)

    return paragraphs[0] if len(paragraphs) == 1 else paragraphs


def build_location(
    location_type: str | None,
    location_value: int | list[int] | str | None,
    page_number: int | None = None,
) -> dict[str, Any] | None:
    """Build the review-record location object used by tags and comments."""
    if location_type is None:
        if location_value is not None:
            raise ReviewTargetError("location_value requires location_type.")
        return None
    if location_type not in ALLOWED_LOCATION_TYPES:
        allowed = ", ".join(sorted(ALLOWED_LOCATION_TYPES))
        raise ReviewTargetError(
            f"Invalid location_type {location_type!r}. Allowed values: {allowed}."
        )
    normalized_value: Any
    if location_type == "whole_submission":
        if location_value is not None:
            raise ReviewTargetError(
                "location_value must be omitted for whole_submission."
            )
        return {"type": location_type, "value": None}
    if location_type == "paragraph":
        normalized_value = normalize_paragraph_location_value(location_value)
    elif location_type in INTEGER_LOCATION_TYPES:
        normalized_value = _validate_positive_integer(
            location_value, "location_value"
        )
    elif location_type in FLEXIBLE_LOCATION_TYPES:
        normalized_value = _normalize_flexible_location_value(location_value)
    else:
        raise ReviewTargetError(f"Unsupported location_type {location_type!r}.")

    if (
        location_type == "page"
        and page_number is not None
        and normalized_value != page_number
    ):
        raise ReviewTargetError("page location_value must agree with page_number.")
    return {"type": location_type, "value": normalized_value}


def normalize_paragraph_location_value(value: Any) -> int | list[int]:
    """Normalize paragraph locations to one int or a unique non-empty int list."""
    if isinstance(value, list):
        if not value:
            raise ReviewTargetError("paragraph location_value must not be empty.")
        seen: set[int] = set()
        normalized: list[int] = []
        for item in value:
            paragraph = _validate_positive_integer(item, "paragraph")
            if paragraph in seen:
                raise ReviewTargetError(
                    f"Paragraph {paragraph} was entered more than once."
                )
            seen.add(paragraph)
            normalized.append(paragraph)
        return normalized[0] if len(normalized) == 1 else normalized
    return _validate_positive_integer(value, "paragraph")


def target_fields(
    *,
    page_number: int | None = None,
    evidence_id: str | None = None,
    location_type: str | None = None,
    location_value: int | list[int] | str | None = None,
) -> dict[str, Any]:
    """Return review-record fields for optional target metadata."""
    _validate_optional_page_number(page_number)
    normalized_evidence = _normalize_optional_string(evidence_id, "evidence_id")
    location = build_location(location_type, location_value, page_number)
    fields: dict[str, Any] = {}
    if page_number is not None:
        fields["page_number"] = page_number
    if normalized_evidence is not None:
        fields["evidence_id"] = normalized_evidence
    if location is not None:
        fields["location"] = location
    return fields


def format_review_target(item: dict[str, Any]) -> str:
    """Format target metadata for terminal display."""
    page_number = item.get("page_number")
    location = item.get("location")
    evidence_id = item.get("evidence_id")

    location_type = location.get("type") if isinstance(location, dict) else None
    location_value = location.get("value") if isinstance(location, dict) else None

    if location_type == "whole_submission":
        return "Whole submission"
    parts: list[str] = []
    if location_type == "paragraph":
        paragraph_text = _format_paragraphs(location_value)
        if isinstance(page_number, int) and not isinstance(page_number, bool):
            parts.append(f"Page {page_number}")
            paragraph_text = paragraph_text.casefold()
        parts.append(paragraph_text)
    elif location_type == "page":
        if isinstance(location_value, int) and not isinstance(location_value, bool):
            parts.append(f"Page {location_value}")
    elif isinstance(page_number, int) and not isinstance(page_number, bool):
        parts.append(f"Page {page_number}")
    elif location_type is not None and location_value is not None:
        parts.append(f"{location_type.replace('_', ' ').title()}: {location_value}")
    if isinstance(evidence_id, str) and evidence_id.strip():
        parts.append(f"Evidence {evidence_id.strip()}")
    return ", ".join(parts) if parts else "Not specified"


def _format_paragraphs(value: Any) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return f"Paragraph {value}"
    if isinstance(value, list):
        paragraphs = [
            item for item in value if isinstance(item, int) and not isinstance(item, bool)
        ]
        if len(paragraphs) == 1:
            return f"Paragraph {paragraphs[0]}"
        return f"Paragraphs {_format_number_ranges(paragraphs)}"
    return "Paragraphs"


def _format_number_ranges(values: list[int]) -> str:
    ranges: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = value
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ", ".join(ranges)


def _normalize_flexible_location_value(value: Any) -> int | str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _validate_positive_integer(value, "location_value")


def _validate_optional_page_number(value: int | None) -> None:
    if value is not None:
        _validate_positive_integer(value, "page_number")


def _parse_positive_integer(value: str, field: str) -> int:
    return _validate_positive_integer(int(value), field)


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReviewTargetError(f"{field} must be a positive integer.")
    return value


def _normalize_optional_string(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ReviewTargetError(f"{field} must be a non-empty string.")
    return value.strip()
