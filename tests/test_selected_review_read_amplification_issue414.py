"""Issue #414 representative selected-review read-amplification acceptance."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest
from pds_core.scan_routes import build_retained_source_filename

import quillan.response_page_observations as observation_module
import quillan.review_dashboard as dashboard_module
import quillan.review_menu as review_menu
import quillan.review_read_context as read_context_module
from quillan.printable_response_records import page_role_for_logical_page
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    canonical_response_page_observation_json,
    derive_observation_id,
)
from quillan.work_paths import (
    quillan_work_ref,
    response_page_observation_path,
    routed_evidence_path,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    _write_assignment,
    _write_json,
    _write_records,
)

STUDENT_IDS = tuple(f"{index:05d}" for index in range(1, 31))
PAGES_PER_STUDENT = 4
TOTAL_OBSERVATIONS = len(STUDENT_IDS) * PAGES_PER_STUDENT
TIMESTAMP = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _write_roster(root: Path) -> None:
    path = root / "classes" / CLASS_ID / "roster.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["class_id,student_id,last_name,first_name,period"]
    rows.extend(
        f"{CLASS_ID},{student_id},Student{index:02d},Synthetic{index:02d},3"
        for index, student_id in enumerate(STUDENT_IDS, start=1)
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _id(prefix: str, value: int) -> str:
    return f"{prefix}_{value:032x}"


def _write_review_records(root: Path) -> None:
    for index, student_id in enumerate(STUDENT_IDS, start=1):
        _, review_path, review = _write_records(root, student_id)
        export_path = (
            root
            / "classes"
            / CLASS_ID
            / "modules"
            / "quillan"
            / "work"
            / ASSIGNMENT_ID
            / "submissions"
            / student_id
            / "exports"
            / "feedback.pdf"
        )
        if index % 5 == 0:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_bytes(f"current feedback {student_id}".encode())
            relative = export_path.relative_to(root).as_posix()
            review["review_state"] = "exported"
            review["exports"]["feedback_pdf"] = {
                "path": relative,
                "generated_at": review["updated_at"],
                "source_review_updated_at": review["updated_at"],
                "module_details": {},
            }
            _write_json(review_path, review)
        elif index % 7 == 0:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_bytes(f"stale feedback {student_id}".encode())
            relative = export_path.relative_to(root).as_posix()
            review["exports"]["feedback_pdf"] = {
                "path": relative,
                "generated_at": review["updated_at"],
                "source_review_updated_at": "2026-06-20T12:30:00+00:00",
                "module_details": {},
            }
            _write_json(review_path, review)
        elif index % 3 == 0:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_bytes(f"metadata-free feedback {student_id}".encode())


def _write_observations(root: Path) -> None:
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    retained_bytes = b"representative retained source bytes"
    source_sha = hashlib.sha256(retained_bytes).hexdigest()
    source_filename = "representative_class_scan.pdf"
    retained_filename = build_retained_source_filename(
        intake_timestamp=TIMESTAMP,
        original_filename=source_filename,
        sha256_hex=source_sha,
    )
    retained_path = (
        root
        / "scans"
        / "source"
        / TIMESTAMP.date().isoformat()
        / retained_filename
    )
    retained_path.parent.mkdir(parents=True, exist_ok=True)
    retained_path.write_bytes(retained_bytes)
    source_scan_id = f"scan_{retained_path.stem}"
    retained_relative = retained_path.relative_to(root).as_posix()
    created_at = TIMESTAMP.isoformat()

    sequence = 0
    for student_index, student_id in enumerate(STUDENT_IDS, start=1):
        generation_id = _id("gen", student_index)
        artifact_id = _id("art", student_index)
        issuance_id = _id("iss", student_index)
        for logical_page in range(1, PAGES_PER_STUDENT + 1):
            sequence += 1
            page_id = _id("pg", sequence)
            route_id = _id("rt", sequence)
            observation_id = derive_observation_id(
                source_scan_id,
                sequence,
                route_id,
                page_id,
            )
            evidence = f"{student_id}:{logical_page}:verified evidence".encode()
            evidence_path = routed_evidence_path(
                root,
                work_ref,
                issuance_id,
                student_id,
                logical_page,
                observation_id,
                ".png",
            )
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_bytes(evidence)
            observation = QuillanResponsePageObservation(
                schema_version="1",
                observation_id=observation_id,
                record_type="response_page_observation",
                module_id="quillan",
                created_at=created_at,
                class_id=CLASS_ID,
                assignment_id=ASSIGNMENT_ID,
                student_id=student_id,
                generation_id=generation_id,
                artifact_id=artifact_id,
                issuance_id=issuance_id,
                page_id=page_id,
                route_id=route_id,
                logical_page=logical_page,
                total_pages=PAGES_PER_STUDENT,
                page_role=page_role_for_logical_page(logical_page),
                source_scan_id=source_scan_id,
                source_filename=source_filename,
                source_page_number=sequence,
                retained_source_path=retained_relative,
                source_sha256=source_sha,
                intake_timestamp=created_at,
                intake_date=TIMESTAMP.date().isoformat(),
                routed_evidence_path=evidence_path.relative_to(root).as_posix(),
                routed_evidence_sha256=hashlib.sha256(evidence).hexdigest(),
                routed_evidence_size_bytes=len(evidence),
                routed_evidence_kind="rendered_pdf_page_png",
                module_details={},
            )
            path = response_page_observation_path(
                root,
                work_ref,
                observation_id,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_response_page_observation_json(observation))


def _prepare(root: Path) -> None:
    _write_assignment(root)
    _write_roster(root)
    _write_review_records(root)
    _write_observations(root)


def test_representative_30_student_redraw_has_one_strict_evidence_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(tmp_path)
    before = _snapshot(tmp_path)
    counts = {
        "assignment": 0,
        "roster": 0,
        "observation_group": 0,
        "evidence_verify": 0,
    }

    original_assignment = read_context_module.load_quillan_assignment_context
    original_roster = read_context_module.load_class_roster
    original_group = read_context_module.group_response_page_observations_by_student
    original_verify = observation_module.verify_contextual_routed_page_evidence

    def counted_assignment(*args: object, **kwargs: object):
        counts["assignment"] += 1
        return original_assignment(*args, **kwargs)  # type: ignore[arg-type]

    def counted_roster(*args: object, **kwargs: object):
        counts["roster"] += 1
        return original_roster(*args, **kwargs)  # type: ignore[arg-type]

    def counted_group(*args: object, **kwargs: object):
        counts["observation_group"] += 1
        return original_group(*args, **kwargs)  # type: ignore[arg-type]

    def counted_verify(*args: object, **kwargs: object):
        counts["evidence_verify"] += 1
        return original_verify(*args, **kwargs)  # type: ignore[arg-type]

    def unexpected_legacy(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("representative redraw invoked a redundant legacy read")

    def unexpected_scan(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("routine navigation invoked scan-review diagnostics")

    monkeypatch.setattr(
        read_context_module,
        "load_quillan_assignment_context",
        counted_assignment,
    )
    monkeypatch.setattr(read_context_module, "load_class_roster", counted_roster)
    monkeypatch.setattr(
        read_context_module,
        "group_response_page_observations_by_student",
        counted_group,
    )
    monkeypatch.setattr(
        observation_module,
        "verify_contextual_routed_page_evidence",
        counted_verify,
    )
    monkeypatch.setattr(
        dashboard_module,
        "discover_scan_review_items",
        unexpected_scan,
    )
    monkeypatch.setattr(
        review_menu,
        "list_assignment_submission_status",
        unexpected_legacy,
    )
    monkeypatch.setattr(
        review_menu,
        "build_student_review_status",
        unexpected_legacy,
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation",
        unexpected_legacy,
    )
    monkeypatch.setattr(review_menu, "print_active_context", unexpected_legacy)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "b")

    assert review_menu._launch_selected_student_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_IDS[0],
    ) == 0

    assert counts == {
        "assignment": 1,
        "roster": 1,
        "observation_group": 1,
        "evidence_verify": TOTAL_OBSERVATIONS,
    }
    assert _snapshot(tmp_path) == before
