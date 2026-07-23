"""Focused durable-state tests for the installed acceptance helper."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_installed_acceptance import (
    _compare_retained_source_inventories,
    _retained_source_inventory,
    _verify_digital_durable_state,
    _verify_plain_paper_absence,
)


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _digital_fixture(root: Path) -> tuple[Path, Path]:
    work = root / "classes" / "class_1" / "modules" / "quillan" / "work" / "assignment_1"
    retained = root / "scans" / "source" / "2026-07-22" / "retained.pdf"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"synthetic retained source")
    source_sha = hashlib.sha256(retained.read_bytes()).hexdigest()
    for page in range(1, 5):
        evidence = work / "scans" / "evidence" / f"page-{page}.png"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_bytes(f"evidence {page}".encode())
        _write_json(
            work / "scans" / "observations" / f"obs_{page}.json",
            {
                "record_type": "response_page_observation",
                "source_scan_id": "scan_synthetic",
                "source_sha256": source_sha,
                "retained_source_path": retained.relative_to(root).as_posix(),
                "source_page_number": page,
                "routed_evidence_path": evidence.relative_to(root).as_posix(),
                "routed_evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            },
        )
        _write_json(work / "routes" / f"route_{page}.json", {"status": "active"})
    for index, student in enumerate(("00107", "00208"), start=0):
        pages = [
            {
                "page_number": page,
                "page_state": "present",
                "selected_evidence_id": f"obs_{index * 2 + page}",
            }
            for page in (1, 2)
        ]
        _write_json(
            work / "submissions" / student / "submission.json",
            {"student_id": student, "expected_pages": 2, "pages": pages},
        )
    return root, work


def test_digital_durable_counts_are_discovered_from_records(tmp_path: Path) -> None:
    workspace, work = _digital_fixture(tmp_path)
    result = _verify_digital_durable_state(
        workspace, work, expected_students=("00107", "00208")
    )
    assert result["retained_source_events"] == 1
    assert result["physical_retained_pages"] == 4
    assert result["observations"] == 4
    assert result["routed_evidence_files"] == 4
    assert result["complete_submission_manifests"] == 2
    assert result["unresolved_persistence_failures"] == 0
    assert result["post_dispatch_occurrences"] == 0


def test_digital_durable_assertions_reject_missing_evidence(tmp_path: Path) -> None:
    workspace, work = _digital_fixture(tmp_path)
    next((work / "scans" / "evidence").glob("*.png")).unlink()
    with pytest.raises(AssertionError):
        _verify_digital_durable_state(
            workspace, work, expected_students=("00107", "00208")
        )


def test_plain_paper_absence_accepts_review_only_records(tmp_path: Path) -> None:
    work = tmp_path / "classes" / "plain" / "modules" / "quillan" / "work" / "paper"
    (work / "response_pages").mkdir(parents=True)
    _write_json(work / "assignment.json", {"record_type": "assignment"})
    _write_json(
        work / "submissions" / "00309" / "submission.json",
        {
            "record_type": "submission_manifest",
            "module_details": {"submission_entry_method": "plain_paper_manual"},
            "pages": [],
        },
    )
    _write_json(
        work / "submissions" / "00309" / "review.json",
        {"record_type": "submission_review", "review_state": "exported"},
    )
    assert set(_verify_plain_paper_absence(tmp_path, work).values()) == {0}


def test_plain_paper_absence_rejects_digital_route_identity(tmp_path: Path) -> None:
    work = tmp_path / "classes" / "plain" / "modules" / "quillan" / "work" / "paper"
    _write_json(work / "assignment.json", {"record_type": "assignment"})
    _write_json(work / "routes" / "route.json", {"route_id": "route_1"})
    with pytest.raises(AssertionError):
        _verify_plain_paper_absence(tmp_path, work)


def _retained_fixture(workspace: Path) -> Path:
    retained = workspace / "scans" / "source" / "2026-07-23" / "retained.pdf"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"retained source before plain-paper work")
    return retained


def test_unchanged_workspace_retained_source_inventory_passes(tmp_path: Path) -> None:
    _retained_fixture(tmp_path)
    before = _retained_source_inventory(tmp_path)
    after = _retained_source_inventory(tmp_path)
    result = _compare_retained_source_inventories(before, after)
    assert result["retained_source_inventory_before"] == list(before)
    assert result["retained_source_inventory_after"] == list(after)
    assert result["retained_source_events_added"] == 0


def test_plain_paper_retained_source_addition_is_rejected(tmp_path: Path) -> None:
    _retained_fixture(tmp_path)
    before = _retained_source_inventory(tmp_path)
    added = tmp_path / "scans" / "source" / "2026-07-23" / "added.pdf"
    added.write_bytes(b"unexpected retained source")
    after = _retained_source_inventory(tmp_path)
    with pytest.raises(AssertionError):
        _compare_retained_source_inventories(before, after)


def test_plain_paper_retained_source_mutation_is_rejected(tmp_path: Path) -> None:
    retained = _retained_fixture(tmp_path)
    before = _retained_source_inventory(tmp_path)
    retained.write_bytes(b"mutated retained source")
    after = _retained_source_inventory(tmp_path)
    with pytest.raises(AssertionError):
        _compare_retained_source_inventories(before, after)


def test_retained_source_added_count_is_derived(tmp_path: Path) -> None:
    _retained_fixture(tmp_path)
    before = _retained_source_inventory(tmp_path)
    for name in ("added-a.pdf", "added-b.pdf"):
        (tmp_path / "scans" / "source" / "2026-07-23" / name).write_bytes(
            name.encode()
        )
    after = _retained_source_inventory(tmp_path)
    result = _compare_retained_source_inventories(
        before, after, require_unchanged=False
    )
    assert result["retained_source_events_added"] == 2
