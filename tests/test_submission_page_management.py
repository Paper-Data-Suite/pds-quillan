"""Tests for teacher-controlled submission page management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

import quillan.submission_page_management as page_management
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_page_management import (
    SubmissionPageManagementError,
    exclude_submission_page,
    load_submission_page_context,
    mark_submission_page_needs_rescan,
    restore_excluded_submission_page,
)
from tests.observation_test_support import successful_pdf_pages
from tests.review_test_support import _review, _write_assignment

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
TIMESTAMP = "2026-06-22T12:00:00+00:00"


@pytest.fixture(autouse=True)
def canonical_assignment(tmp_path: Path) -> None:
    _write_assignment(tmp_path)


def _evidence(
    evidence_id: str, page_number: int, *, role: str = "selected"
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "routed_evidence_path": (
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/scans/"
            f"response_{STUDENT_ID}_pg_{page_number:03d}_{evidence_id}.pdf"
        ),
        "evidence_role": role,
        "evidence_state": "active",
        "duplicate_number": None,
        "created_at": TIMESTAMP,
        "retained_source": None,
        "module_details": {},
    }


def _write_manifest(root: Path) -> Path:
    manifest = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 3,
        "submission_state": "unreviewed",
        "pages": [
            {
                "page_number": 1,
                "page_state": "present",
                "selected_evidence_id": "evidence_001",
                "evidence": [_evidence("evidence_001", 1)],
            },
            {
                "page_number": 2,
                "page_state": "duplicate",
                "selected_evidence_id": None,
                "evidence": [
                    _evidence("evidence_002a", 2, role="candidate"),
                    _evidence("evidence_002b", 2, role="candidate"),
                ],
            },
            {
                "page_number": 3,
                "page_state": "excluded",
                "selected_evidence_id": None,
                "evidence": [
                    {
                        **_evidence("evidence_003", 3, role="excluded"),
                        "evidence_state": "excluded",
                    }
                ],
            },
        ],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }
    path = submission_manifest_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    written = write_submission_manifest(path, manifest)
    for page in cast(list[dict[str, Any]], manifest["pages"]):
        for evidence in page["evidence"]:
            evidence_path = root / evidence["routed_evidence_path"]
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_bytes(b"evidence")
    return written


def _read(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_exclude_page_preserves_evidence_files_and_excludes_manifest_records(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)
    evidence_before = {item: item.read_bytes() for item in tmp_path.rglob("*.pdf")}

    result = exclude_submission_page(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1)

    manifest = _read(path)
    page = manifest["pages"][0]
    assert result.page_state == "excluded"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "excluded"
    assert page["evidence"][0]["evidence_state"] == "excluded"
    assert page["evidence"][0]["module_details"]["quillan_before_page_exclusion"] == {
        "evidence_role": "selected",
        "evidence_state": "active",
    }
    assert evidence_before == {
        item: item.read_bytes() for item in tmp_path.rglob("*.pdf")
    }


def test_restore_single_excluded_page_selects_only_unambiguous_evidence(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)

    result = restore_excluded_submission_page(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 3
    )

    manifest = _read(path)
    page = manifest["pages"][2]
    assert result.page_state == "present"
    assert page["selected_evidence_id"] == "evidence_003"
    assert page["evidence"][0]["evidence_role"] == "selected"
    assert page["evidence"][0]["evidence_state"] == "active"


def test_restore_recovers_preserved_duplicate_evidence_roles(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)

    exclude_submission_page(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 2)
    result = restore_excluded_submission_page(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 2
    )

    manifest = _read(path)
    page = manifest["pages"][1]
    assert result.page_state == "duplicate"
    assert page["selected_evidence_id"] is None
    assert [item["evidence_role"] for item in page["evidence"]] == [
        "candidate",
        "candidate",
    ]
    assert [item["evidence_state"] for item in page["evidence"]] == [
        "active",
        "active",
    ]
    assert all(
        "quillan_before_page_exclusion" not in item["module_details"]
        for item in page["evidence"]
    )


def test_restore_preserves_prior_damaged_evidence_state(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)
    manifest = _read(path)
    manifest["pages"][0]["evidence"][0]["evidence_state"] = "damaged"
    write_submission_manifest(path, manifest, overwrite=True)

    exclude_submission_page(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1)
    result = restore_excluded_submission_page(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1
    )

    manifest = _read(path)
    page = manifest["pages"][0]
    assert result.page_state == "needs_rescan"
    assert page["selected_evidence_id"] == "evidence_001"
    assert page["evidence"][0]["evidence_role"] == "selected"
    assert page["evidence"][0]["evidence_state"] == "damaged"


def test_mark_page_needs_rescan_preserves_review_record(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)
    review_path = path.with_name("review.json")
    review_path.write_text(
        json.dumps(_review("observations_in_progress", STUDENT_ID)), encoding="utf-8"
    )
    before = review_path.read_bytes()

    result = mark_submission_page_needs_rescan(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1
    )

    manifest = _read(path)
    page = manifest["pages"][0]
    assert result.page_state == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "candidate"
    assert page["evidence"][0]["evidence_state"] == "needs_rescan"
    assert review_path.read_bytes() == before


def test_invalid_page_number_fails_without_writing(
    tmp_path: Path,
) -> None:
    path = _write_manifest(tmp_path)
    before = path.read_bytes()

    with pytest.raises(SubmissionPageManagementError, match="Page 99"):
        exclude_submission_page(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 99)

    assert path.read_bytes() == before


def test_non_integer_page_number_fails_without_type_error(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    before = path.read_bytes()

    with pytest.raises(SubmissionPageManagementError, match="positive integer"):
        exclude_submission_page(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "1",  # type: ignore[arg-type]
        )

    assert path.read_bytes() == before


def test_write_os_error_is_wrapped_without_partial_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_manifest(tmp_path)
    before = path.read_bytes()

    def fail_write(*_args: object, **_kwargs: object) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(
        page_management, "update_quillan_submission_manifest", fail_write
    )

    with pytest.raises(SubmissionPageManagementError, match="disk full"):
        exclude_submission_page(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1)

    assert path.read_bytes() == before


def test_observation_backed_exclude_rescan_restore_and_needs_rescan(
    tmp_path: Path,
) -> None:
    first_outcome, rescan_outcome = successful_pdf_pages(tmp_path)
    first = persist_quillan_page_observation(tmp_path, first_outcome)
    identity = first.observation
    created = assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.assignment_id
    ).assembled[0]
    _write_assignment(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.assignment_id,
    )
    assert (
        load_submission_page_context(
            tmp_path, identity.class_id, identity.assignment_id, identity.student_id
        ).present_count
        == 1
    )

    exclude_submission_page(
        tmp_path, identity.class_id, identity.assignment_id, identity.student_id, 1
    )
    excluded = load_submission_manifest(created.manifest_path)
    assert excluded["pages"][0]["page_state"] == "excluded"
    assert excluded["pages"][0]["evidence"][0]["module_details"][
        "quillan_before_page_exclusion"
    ] == {"evidence_role": "selected", "evidence_state": "active"}
    revision = excluded["module_details"]["assembly_revision"]

    second = persist_quillan_page_observation(tmp_path, rescan_outcome)
    merged_result = assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.assignment_id
    ).assembled[0]
    merged = load_submission_manifest(created.manifest_path)
    page = merged["pages"][0]
    assert merged_result.status == "updated"
    assert merged["module_details"]["assembly_revision"] == revision + 1
    assert page["page_state"] == "excluded"
    assert page["selected_evidence_id"] is None
    assert [item["evidence_role"] for item in page["evidence"]] == [
        "excluded",
        "candidate",
    ]
    assert page["evidence"][1]["evidence_id"] == second.observation.observation_id

    restore_excluded_submission_page(
        tmp_path, identity.class_id, identity.assignment_id, identity.student_id, 1
    )
    restored = load_submission_manifest(created.manifest_path)
    restored_page = restored["pages"][0]
    assert restored_page["page_state"] == "duplicate"
    assert restored_page["selected_evidence_id"] == identity.observation_id
    assert [item["evidence_role"] for item in restored_page["evidence"]] == [
        "selected",
        "candidate",
    ]

    mark_submission_page_needs_rescan(
        tmp_path, identity.class_id, identity.assignment_id, identity.student_id, 1
    )
    context = load_submission_page_context(
        tmp_path, identity.class_id, identity.assignment_id, identity.student_id
    )
    assert context.needs_rescan_count == 1
    before_retry = created.manifest_path.read_bytes()
    unchanged = assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.assignment_id
    ).assembled[0]
    assert unchanged.status == "unchanged"
    assert created.manifest_path.read_bytes() == before_retry
