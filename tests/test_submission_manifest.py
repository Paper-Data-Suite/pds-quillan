"""Tests for v0.6 submission manifest loading and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)

EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "submissions"
    / "submission_manifest_synthetic.json"
)


def _retained_source() -> dict[str, Any]:
    return {
        "source_scan_id": "scan_001",
        "source_filename": "teacher_scan.pdf",
        "source_sha256": "a" * 64,
        "retained_source_path": "scans/source/2026-06-20/teacher_scan.pdf",
        "source_page_number": 1,
    }


def _candidate(
    evidence_id: str = "evidence_001",
    *,
    role: str = "selected",
    retained_source: object = None,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "routed_evidence_path": f"classes/example/scans/{evidence_id}.pdf",
        "evidence_role": role,
        "evidence_state": "active",
        "duplicate_number": None,
        "created_at": "2026-06-20T00:01:00+00:00",
        "retained_source": retained_source,
        "module_details": {},
    }


def _manifest(*, pages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": "english12_p3_synthetic",
        "assignment_id": "essay_01_synthetic",
        "student_id": "00107",
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [] if pages is None else pages,
        "created_at": "2026-06-20T00:00:00+00:00",
        "updated_at": "2026-06-20T00:00:00+00:00",
        "module_details": {},
    }


def _present_page() -> dict[str, Any]:
    return {
        "page_number": 1,
        "page_state": "present",
        "selected_evidence_id": "evidence_001",
        "evidence": [_candidate(retained_source=_retained_source())],
    }


def _write_manifest(tmp_path: Path, manifest: object) -> Path:
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_synthetic_example_loads_successfully() -> None:
    manifest = load_submission_manifest(EXAMPLE_PATH)

    assert [page["page_state"] for page in manifest["pages"]] == [
        "present",
        "missing",
        "duplicate",
    ]


def test_minimal_manifest_with_empty_pages_loads(tmp_path: Path) -> None:
    manifest = _manifest()

    assert load_submission_manifest(_write_manifest(tmp_path, manifest)) == manifest


def test_present_missing_and_duplicate_pages_validate() -> None:
    manifest = _manifest(
        pages=[
            _present_page(),
            {
                "page_number": 2,
                "page_state": "missing",
                "selected_evidence_id": None,
                "evidence": [],
            },
            {
                "page_number": 3,
                "page_state": "duplicate",
                "selected_evidence_id": None,
                "evidence": [
                    _candidate("evidence_002", role="candidate"),
                    _candidate("evidence_003", role="candidate"),
                ],
            },
        ]
    )

    validate_submission_manifest(manifest)


def test_missing_file_invalid_json_and_wrong_root_raise(tmp_path: Path) -> None:
    with pytest.raises(SubmissionManifestError, match="not found"):
        load_submission_manifest(tmp_path / "missing.json")

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{bad json", encoding="utf-8")
    with pytest.raises(SubmissionManifestError, match="not valid JSON"):
        load_submission_manifest(invalid_path)

    with pytest.raises(SubmissionManifestError, match="JSON object"):
        load_submission_manifest(_write_manifest(tmp_path, []))


@pytest.mark.parametrize("field", list(_manifest()))
def test_missing_top_level_field_raises(field: str) -> None:
    manifest = _manifest()
    del manifest[field]

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2"),
        ("module", "other"),
        ("record_type", "legacy_submission"),
        ("class_id", "../class"),
        ("assignment_id", "bad assignment"),
        ("student_id", ""),
        ("expected_pages", 0),
        ("expected_pages", True),
        ("submission_state", "scored"),
        ("pages", {}),
        ("created_at", "2026-06-20T00:00:00"),
        ("updated_at", "not-a-timestamp"),
        ("module_details", []),
    ],
)
def test_invalid_top_level_field_raises(field: str, value: object) -> None:
    manifest = _manifest()
    manifest[field] = value

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(manifest)


@pytest.mark.parametrize(
    "field", ["page_number", "page_state", "selected_evidence_id", "evidence"]
)
def test_missing_page_field_raises(field: str) -> None:
    page = _present_page()
    del page[field]

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("page_number", 0),
        ("page_number", True),
        ("page_state", "reviewed"),
        ("selected_evidence_id", ""),
        ("evidence", {}),
    ],
)
def test_invalid_page_field_raises(field: str, value: object) -> None:
    page = _present_page()
    page[field] = value

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


def test_duplicate_page_numbers_raise() -> None:
    first = _present_page()
    second = copy.deepcopy(first)
    second["evidence"][0]["evidence_id"] = "evidence_002"
    second["selected_evidence_id"] = "evidence_002"

    with pytest.raises(SubmissionManifestError, match="Duplicate page_number"):
        validate_submission_manifest(_manifest(pages=[first, second]))


@pytest.mark.parametrize(
    "page",
    [
        {
            "page_number": 1,
            "page_state": "missing",
            "selected_evidence_id": None,
            "evidence": [_candidate(role="candidate")],
        },
        {
            "page_number": 1,
            "page_state": "present",
            "selected_evidence_id": None,
            "evidence": [],
        },
        {
            "page_number": 1,
            "page_state": "duplicate",
            "selected_evidence_id": None,
            "evidence": [_candidate(role="candidate")],
        },
    ],
    ids=["missing-with-evidence", "present-without-evidence", "duplicate-with-one"],
)
def test_incoherent_page_state_raises(page: dict[str, Any]) -> None:
    with pytest.raises(SubmissionManifestError):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    ("selected_id", "roles"),
    [
        ("missing", ["candidate"]),
        ("evidence_001", ["candidate"]),
        (None, ["selected"]),
        ("evidence_001", ["selected", "selected"]),
    ],
    ids=[
        "reference-not-found",
        "reference-without-role",
        "role-without-reference",
        "multiple-selected",
    ],
)
def test_invalid_evidence_selection_raises(
    selected_id: str | None, roles: list[str]
) -> None:
    evidence = [
        _candidate(f"evidence_{index:03d}", role=role)
        for index, role in enumerate(roles, start=1)
    ]
    page = {
        "page_number": 1,
        "page_state": "present",
        "selected_evidence_id": selected_id,
        "evidence": evidence,
    }

    with pytest.raises(SubmissionManifestError, match="selected"):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    "field",
    [
        "evidence_id",
        "routed_evidence_path",
        "evidence_role",
        "evidence_state",
        "duplicate_number",
        "created_at",
        "retained_source",
        "module_details",
    ],
)
def test_missing_evidence_field_raises(field: str) -> None:
    page = _present_page()
    del page["evidence"][0][field]

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_id", ""),
        ("routed_evidence_path", "../evidence.pdf"),
        ("evidence_role", "primary"),
        ("evidence_state", "reviewed"),
        ("duplicate_number", 0),
        ("duplicate_number", True),
        ("created_at", "2026-06-20T00:01:00"),
        ("module_details", None),
    ],
)
def test_invalid_evidence_field_raises(field: str, value: object) -> None:
    page = _present_page()
    page["evidence"][0][field] = value

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


def test_duplicate_evidence_ids_across_pages_raise() -> None:
    first = _present_page()
    second = copy.deepcopy(first)
    second["page_number"] = 2

    with pytest.raises(SubmissionManifestError, match="Duplicate evidence_id"):
        validate_submission_manifest(_manifest(pages=[first, second]))


def test_null_retained_source_is_allowed() -> None:
    page = _present_page()
    page["evidence"][0]["retained_source"] = None
    validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    "field",
    [
        "source_scan_id",
        "source_filename",
        "source_sha256",
        "retained_source_path",
        "source_page_number",
    ],
)
def test_missing_retained_source_field_raises(field: str) -> None:
    page = _present_page()
    del page["evidence"][0]["retained_source"][field]

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_scan_id", ""),
        ("source_filename", "incoming/teacher_scan.pdf"),
        ("source_filename", r"incoming\teacher_scan.pdf"),
        ("source_sha256", "abc123"),
        ("retained_source_path", "/source.pdf"),
        ("source_page_number", 0),
        ("source_page_number", True),
    ],
)
def test_invalid_retained_source_field_raises(field: str, value: object) -> None:
    page = _present_page()
    page["evidence"][0]["retained_source"][field] = value

    with pytest.raises(SubmissionManifestError, match=field):
        validate_submission_manifest(_manifest(pages=[page]))


UNSAFE_PATHS = [
    "/absolute/file.pdf",
    r"C:\absolute\file.pdf",
    r"C:drive-relative\file.pdf",
    r"\root-relative\file.pdf",
    "../file.pdf",
    "folder/../file.pdf",
    "./file.pdf",
    "folder/./file.pdf",
    "",
    "path\0file.pdf",
]


@pytest.mark.parametrize("unsafe_path", UNSAFE_PATHS)
def test_unsafe_routed_evidence_path_raises(unsafe_path: str) -> None:
    page = _present_page()
    page["evidence"][0]["routed_evidence_path"] = unsafe_path

    with pytest.raises(SubmissionManifestError, match="routed_evidence_path"):
        validate_submission_manifest(_manifest(pages=[page]))


@pytest.mark.parametrize("unsafe_path", UNSAFE_PATHS)
def test_unsafe_retained_source_path_raises(unsafe_path: str) -> None:
    page = _present_page()
    page["evidence"][0]["retained_source"]["retained_source_path"] = unsafe_path

    with pytest.raises(SubmissionManifestError, match="retained_source_path"):
        validate_submission_manifest(_manifest(pages=[page]))
