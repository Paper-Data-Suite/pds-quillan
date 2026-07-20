"""Tests for assembling routed evidence into submission manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from quillan.submission_assembly import (
    RoutedSubmissionEvidence,
    SubmissionAssemblyError,
    assemble_submission_manifest,
    build_submission_manifest,
)
from quillan.submission_manifest import (
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import SubmissionManifestPathError

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-20T12:00:00+00:00"


def _build(
    tmp_path: Path,
    evidence: list[RoutedSubmissionEvidence],
    **kwargs: Any,
) -> dict[str, Any]:
    return build_submission_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        evidence,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
        **kwargs,
    )


def _evidence(
    page_number: int,
    path: str | Path | None = None,
    **kwargs: Any,
) -> RoutedSubmissionEvidence:
    return RoutedSubmissionEvidence(
        page_number=page_number,
        routed_evidence_path=path or f"classes/example/page_{page_number}.pdf",
        **kwargs,
    )


def test_one_evidence_item_builds_valid_selected_present_page(
    tmp_path: Path,
) -> None:
    manifest = _build(tmp_path, [_evidence(1)])

    page = manifest["pages"][0]
    candidate = page["evidence"][0]
    assert manifest["submission_state"] == "unreviewed"
    assert page["page_state"] == "present"
    assert page["selected_evidence_id"] == "evidence_001"
    assert candidate["evidence_id"] == "evidence_001"
    assert candidate["evidence_role"] == "selected"
    assert candidate["retained_source"] is None
    validate_submission_manifest(manifest)


def test_expected_pages_add_missing_pages_and_keep_extras(tmp_path: Path) -> None:
    manifest = _build(
        tmp_path,
        [_evidence(3), _evidence(1)],
        expected_pages=2,
    )

    assert [page["page_number"] for page in manifest["pages"]] == [1, 2, 3]
    missing = manifest["pages"][1]
    assert missing == {
        "page_number": 2,
        "page_state": "missing",
        "selected_evidence_id": None,
        "evidence": [],
    }
    validate_submission_manifest(manifest)


def test_unknown_expected_pages_does_not_invent_missing_pages(
    tmp_path: Path,
) -> None:
    manifest = _build(tmp_path, [_evidence(3), _evidence(1)])

    assert [page["page_number"] for page in manifest["pages"]] == [1, 3]


def test_duplicate_page_is_ambiguous_and_deterministically_ordered(
    tmp_path: Path,
) -> None:
    manifest = _build(
        tmp_path,
        [
            _evidence(1, "z/page.pdf", duplicate_number=2),
            _evidence(1, "a/page.pdf"),
            _evidence(1, "b/page.pdf", duplicate_number=1),
        ],
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] is None
    assert [item["evidence_id"] for item in page["evidence"]] == [
        "evidence_001",
        "evidence_002",
        "evidence_003",
    ]
    assert [item["routed_evidence_path"] for item in page["evidence"]] == [
        "a/page.pdf",
        "b/page.pdf",
        "z/page.pdf",
    ]
    assert {item["evidence_role"] for item in page["evidence"]} == {"candidate"}
    validate_submission_manifest(manifest)


def test_single_replacement_is_preserved_without_selection(
    tmp_path: Path,
) -> None:
    manifest = _build(
        tmp_path, [_evidence(1, evidence_role="replacement")]
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "replacement"
    validate_submission_manifest(manifest)


def test_original_and_replacement_remain_ambiguous(tmp_path: Path) -> None:
    manifest = _build(
        tmp_path,
        [
            _evidence(1, "pages/original.pdf"),
            _evidence(
                1,
                "pages/replacement.pdf",
                evidence_role="replacement",
            ),
        ],
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] is None
    assert [item["evidence_role"] for item in page["evidence"]] == [
        "candidate",
        "replacement",
    ]
    assert len(page["evidence"]) == 2
    validate_submission_manifest(manifest)


@pytest.mark.parametrize("evidence_state", ["damaged", "needs_rescan"])
def test_problematic_single_evidence_requires_rescan(
    tmp_path: Path, evidence_state: str
) -> None:
    manifest = _build(
        tmp_path, [_evidence(1, evidence_state=evidence_state)]
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_state"] == evidence_state
    assert page["evidence"][0]["evidence_role"] == "candidate"
    validate_submission_manifest(manifest)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"evidence_role": "excluded"},
        {"evidence_state": "excluded"},
    ],
)
def test_single_excluded_evidence_is_preserved(
    tmp_path: Path, kwargs: dict[str, Any]
) -> None:
    manifest = _build(tmp_path, [_evidence(1, **kwargs)])

    page = manifest["pages"][0]
    assert page["page_state"] == "excluded"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "excluded"
    assert len(page["evidence"]) == 1
    validate_submission_manifest(manifest)


@pytest.mark.parametrize(
    "problematic",
    [
        {"evidence_state": "damaged"},
        {"evidence_role": "excluded"},
    ],
)
def test_mixed_evidence_preserves_all_candidates_without_selection(
    tmp_path: Path, problematic: dict[str, Any]
) -> None:
    manifest = _build(
        tmp_path,
        [
            _evidence(1, "pages/active.pdf"),
            _evidence(1, "pages/problematic.pdf", **problematic),
        ],
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] is None
    assert len(page["evidence"]) == 2
    assert {item["routed_evidence_path"] for item in page["evidence"]} == {
        "pages/active.pdf",
        "pages/problematic.pdf",
    }
    validate_submission_manifest(manifest)


def test_explicit_candidate_remains_unselected(tmp_path: Path) -> None:
    manifest = _build(
        tmp_path, [_evidence(1, evidence_role="candidate")]
    )

    page = manifest["pages"][0]
    assert page["page_state"] == "present"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "candidate"
    validate_submission_manifest(manifest)


def test_full_retained_source_is_preserved_with_nullable_source_page(
    tmp_path: Path,
) -> None:
    manifest = _build(
        tmp_path,
        [
            _evidence(
                1,
                retained_source_path="scans/source/2026-06-20/source.pdf",
                source_scan_id="scan_001",
                source_filename="source.pdf",
                source_sha256="a" * 64,
                source_page_number=None,
            )
        ],
    )

    assert manifest["pages"][0]["evidence"][0]["retained_source"] == {
        "source_scan_id": "scan_001",
        "source_filename": "source.pdf",
        "source_sha256": "a" * 64,
        "retained_source_path": "scans/source/2026-06-20/source.pdf",
        "source_page_number": None,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source_scan_id": "scan_001"},
        {"source_page_number": 1},
        {"retained_source_path": "scans/source/source.pdf"},
    ],
)
def test_partial_retained_source_raises(
    tmp_path: Path, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(SubmissionAssemblyError, match="partial"):
        _build(tmp_path, [_evidence(1, **kwargs)])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_scan_id", ""),
        ("source_filename", "folder/source.pdf"),
        ("source_sha256", "not-a-digest"),
        ("source_page_number", 0),
    ],
)
def test_invalid_retained_source_fields_raise(
    tmp_path: Path, field: str, value: Any
) -> None:
    kwargs: dict[str, Any] = {
        "retained_source_path": "scans/source/source.pdf",
        "source_scan_id": "scan_001",
        "source_filename": "source.pdf",
        "source_sha256": "a" * 64,
    }
    kwargs[field] = value

    with pytest.raises(SubmissionAssemblyError, match=field):
        _build(tmp_path, [_evidence(1, **kwargs)])


def test_paths_are_preserved_or_made_workspace_relative(tmp_path: Path) -> None:
    routed = tmp_path / "classes" / "class_a" / "page.pdf"
    retained = tmp_path / "scans" / "source" / "source.pdf"
    manifest = _build(
        tmp_path,
        [
            _evidence(
                1,
                path=routed,
                retained_source_path=retained,
                source_scan_id="scan_001",
                source_filename="source.pdf",
                source_sha256="b" * 64,
            ),
            _evidence(2, path=r"classes\class_a\page_2.pdf"),
        ],
    )

    first, second = (
        manifest["pages"][0]["evidence"][0],
        manifest["pages"][1]["evidence"][0],
    )
    assert first["routed_evidence_path"] == "classes/class_a/page.pdf"
    assert (
        first["retained_source"]["retained_source_path"]
        == "scans/source/source.pdf"
    )
    assert second["routed_evidence_path"] == r"classes\class_a\page_2.pdf"


@pytest.mark.parametrize("field", ["routed", "retained"])
def test_absolute_paths_outside_workspace_raise(
    tmp_path: Path, field: str
) -> None:
    outside = tmp_path.parent / "outside.pdf"
    kwargs: dict[str, Any] = {}
    routed: str | Path = "classes/page.pdf"
    if field == "routed":
        routed = outside
    else:
        kwargs = {
            "retained_source_path": outside,
            "source_scan_id": "scan_001",
            "source_filename": "outside.pdf",
            "source_sha256": "c" * 64,
        }

    with pytest.raises(SubmissionAssemblyError, match="workspace root"):
        _build(tmp_path, [_evidence(1, path=routed, **kwargs)])


def test_timestamps_are_preserved_normalized_and_default_to_utc(
    tmp_path: Path,
) -> None:
    aware = datetime(2026, 6, 20, 8, 30, tzinfo=timezone.utc)
    manifest = build_submission_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [_evidence(1, created_at=aware)],
        created_at="2026-06-20T08:00:00-04:00",
        updated_at=aware,
    )

    assert manifest["created_at"] == "2026-06-20T08:00:00-04:00"
    assert manifest["updated_at"] == aware.isoformat()
    assert manifest["pages"][0]["evidence"][0]["created_at"] == aware.isoformat()

    generated = build_submission_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, []
    )
    for field in ("created_at", "updated_at"):
        parsed = datetime.fromisoformat(generated[field])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"created_at": datetime(2026, 6, 20, 8, 0)},
        {"updated_at": "2026-06-20T08:00:00"},
    ],
)
def test_naive_manifest_timestamps_raise(
    tmp_path: Path, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(SubmissionAssemblyError, match="timezone-aware"):
        build_submission_manifest(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            [],
            **kwargs,
        )


def test_assemble_writes_canonical_reloadable_manifest_and_overwrite(
    tmp_path: Path,
) -> None:
    path = assemble_submission_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [_evidence(1)],
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )
    assert path == (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "submission.json"
    )
    assert load_submission_manifest(path)["pages"][0]["page_number"] == 1

    with pytest.raises(SubmissionManifestPathError, match="already exists"):
        assemble_submission_manifest(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            [_evidence(2)],
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
        )

    assemble_submission_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [_evidence(2)],
        overwrite=True,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )
    assert load_submission_manifest(path)["pages"][0]["page_number"] == 2


@pytest.mark.parametrize("value", [0, -1, True, "1"])
def test_invalid_page_numbers_raise(tmp_path: Path, value: Any) -> None:
    with pytest.raises(SubmissionAssemblyError, match="page_number"):
        _build(tmp_path, [_evidence(value)])


@pytest.mark.parametrize("value", [0, -1, True])
def test_invalid_duplicate_numbers_raise(tmp_path: Path, value: Any) -> None:
    with pytest.raises(SubmissionAssemblyError, match="duplicate_number"):
        _build(tmp_path, [_evidence(1, duplicate_number=value)])


@pytest.mark.parametrize("value", [0, -1, True])
def test_invalid_expected_pages_raise(tmp_path: Path, value: Any) -> None:
    with pytest.raises(SubmissionAssemblyError, match="expected_pages"):
        _build(tmp_path, [], expected_pages=value)


def test_invalid_evidence_state_and_module_details_raise(tmp_path: Path) -> None:
    with pytest.raises(SubmissionAssemblyError, match="evidence_state"):
        _build(tmp_path, [_evidence(1, evidence_state="reviewed")])
    with pytest.raises(SubmissionAssemblyError, match="JSON-compatible"):
        _build(tmp_path, [_evidence(1, module_details={"bad": object()})])


@pytest.mark.parametrize("value", ["selected", "primary", "", 1])
def test_invalid_caller_evidence_role_raises(
    tmp_path: Path, value: Any
) -> None:
    with pytest.raises(SubmissionAssemblyError, match="evidence_role"):
        _build(tmp_path, [_evidence(1, evidence_role=value)])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "../unsafe"),
        ("assignment_id", "bad assignment"),
        ("student_id", ""),
    ],
)
def test_invalid_identifiers_raise(
    tmp_path: Path, field: str, value: str
) -> None:
    identifiers = {
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
    }
    identifiers[field] = value

    with pytest.raises(SubmissionAssemblyError, match=field):
        build_submission_manifest(
            tmp_path,
            identifiers["class_id"],
            identifiers["assignment_id"],
            identifiers["student_id"],
            [],
        )
