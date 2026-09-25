"""Installed v0.10.3 acceptance for the resubmission/rescan inbox."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from pds_core.route_registrations import write_route_registration
from pds_core.scan_routes import build_retained_source_filename

from quillan.assignment_summary_context import feedback_status
from quillan.feedback_export import export_student_feedback_pdf
from quillan.printable_response_records import page_role_for_logical_page
from quillan.printable_response_persistence import (
    transition_printable_response_issuance,
    write_printable_response_record_set,
)
from quillan.printable_response_records import build_printable_response_record_set
from quillan.printable_response_routes import build_printable_response_page_route
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    canonical_response_page_observation_json,
    derive_observation_id,
)
from quillan.resubmission_inbox import build_assignment_resubmission_inbox
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_evidence_validation import selected_evidence_fingerprint
from quillan.submission_evidence_resolution import (
    select_submission_evidence_candidate,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_review_opening import (
    open_exact_verified_submission_evidence,
)
from quillan.work_paths import (
    quillan_work_ref,
    response_page_observation_path,
    routed_evidence_path,
    submission_manifest_path,
)

CLASS_ID = "issue415_installed_class"
ASSIGNMENT_ID = "issue415_installed_assignment"
STUDENT_ID = "00107"
T0 = "2026-09-15T12:00:00+00:00"
T1 = "2026-09-16T12:00:00+00:00"
EXPORT_TIME = "2026-09-18T12:00:00+00:00"
T2 = "2026-09-23T12:00:00+00:00"


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"{module_name} has no import origin")
    return Path(raw).resolve()


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Installed Resubmission Acceptance",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Synthetic installed acceptance.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["synthetic:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "synthetic_scale",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Synthetic level.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": T0,
        "updated_at": T0,
        "module_details": {},
    }


def _observation(
    workspace: Path, *, timestamp: str, source_number: int
) -> QuillanResponsePageObservation:
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    source_bytes = b"identical physical scan bytes"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    parsed = datetime.fromisoformat(timestamp)
    filename = build_retained_source_filename(
        intake_timestamp=parsed,
        original_filename="response.png",
        sha256_hex=source_sha,
    )
    retained = workspace / "scans" / "source" / parsed.date().isoformat() / filename
    retained.parent.mkdir(parents=True, exist_ok=True)
    retained.write_bytes(source_bytes)
    source_scan_id = f"scan_{retained.stem}"
    route_id = f"rt_{source_number:032x}"
    page_id = "pg_00000000000000000000000000000001"
    observation_id = derive_observation_id(
        source_scan_id, 1, route_id, page_id
    )
    evidence_path = routed_evidence_path(
        workspace,
        work_ref,
        "iss_00000000000000000000000000000001",
        STUDENT_ID,
        1,
        observation_id,
        ".png",
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(source_bytes)
    observation = QuillanResponsePageObservation(
        schema_version="1",
        observation_id=observation_id,
        record_type="response_page_observation",
        module_id="quillan",
        created_at=timestamp,
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        generation_id="gen_00000000000000000000000000000001",
        artifact_id="art_00000000000000000000000000000001",
        issuance_id="iss_00000000000000000000000000000001",
        page_id=page_id,
        route_id=route_id,
        logical_page=1,
        total_pages=1,
        page_role=page_role_for_logical_page(1),
        source_scan_id=source_scan_id,
        source_filename="response.png",
        source_page_number=1,
        retained_source_path=retained.relative_to(workspace).as_posix(),
        source_sha256=source_sha,
        intake_timestamp=timestamp,
        intake_date=parsed.date().isoformat(),
        routed_evidence_path=evidence_path.relative_to(workspace).as_posix(),
        routed_evidence_sha256=source_sha,
        routed_evidence_size_bytes=len(source_bytes),
        routed_evidence_kind="retained_image_copy",
        module_details={},
    )
    observation_path = response_page_observation_path(
        workspace, work_ref, observation_id
    )
    observation_path.parent.mkdir(parents=True, exist_ok=True)
    observation_path.write_bytes(canonical_response_page_observation_json(observation))
    return observation


def _prepare(workspace: Path) -> tuple[QuillanResponsePageObservation, ...]:
    if workspace.exists() and any(workspace.iterdir()):
        raise AssertionError("resubmission acceptance workspace must be empty")
    workspace.mkdir(parents=True, exist_ok=True)
    roster = create_roster(
        CLASS_ID,
        (
            {
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "2",
            },
        ),
    )
    write_class_roster(workspace, roster)
    assignment_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True, exist_ok=True)
    assignment = _assignment()
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    records = build_printable_response_record_set(
        CLASS_ID,
        assignment,
        roster.students[0],
        generation_id="gen_00000000000000000000000000000001",
        artifact_id="art_00000000000000000000000000000001",
        output_kind="class_packet_pdf",
        reason="initial",
        predecessor_issuance_id=None,
        pages_per_student=1,
        issuance_id="iss_00000000000000000000000000000001",
        page_ids=("pg_00000000000000000000000000000001",),
        clock=lambda: datetime.fromisoformat(T0),
    )
    write_printable_response_record_set(workspace, work_ref, records)
    transition_printable_response_issuance(
        workspace,
        work_ref,
        records.issuance.issuance_id,
        expected_revision=1,
        new_status="issued",
        timestamp=T0,
    )
    for source_number in (1, 2):
        route = build_printable_response_page_route(
            records.pages[0], f"rt_{source_number:032x}"
        )
        write_route_registration(workspace, route.registration)
    original = _observation(workspace, timestamp=T1, source_number=1)
    first_assembly = assemble_quillan_submission_manifests(
        workspace, CLASS_ID, ASSIGNMENT_ID, timestamp=T1
    )
    if len(first_assembly.assembled) != 1 or first_assembly.failures:
        raise AssertionError("initial installed assembly failed")
    manifest_path = submission_manifest_path(workspace, work_ref, STUDENT_ID)
    initial_manifest = load_submission_manifest(manifest_path)
    if initial_manifest["pages"][0]["selected_evidence_id"] != original.observation_id:
        raise AssertionError("initial assembly did not select original evidence")

    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=T0,
    )
    review["review_state"] = "returned_without_full_review"
    review["updated_at"] = EXPORT_TIME
    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 1,
            "met": False,
            "teacher_note": "Synthetic installed acceptance return.",
            "updated_at": EXPORT_TIME,
            "module_details": {},
        }
    ]
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Please revise and resubmit.",
        "updated_at": EXPORT_TIME,
    }
    write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )
    exported = export_student_feedback_pdf(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
        include_markdown_companion=True,
    )
    exported_review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    initial_fingerprint = selected_evidence_fingerprint(initial_manifest)
    if feedback_status(
        workspace,
        exported_review,
        "feedback_pdf",
        exported.feedback_pdf_path,
        selected_evidence_fingerprint=initial_fingerprint,
    )[1] != "present":
        raise AssertionError("freshly exported installed feedback is not current")

    candidate = _observation(workspace, timestamp=T2, source_number=2)
    awaiting = build_assignment_resubmission_inbox(workspace, CLASS_ID, ASSIGNMENT_ID)
    if len(awaiting.items) != 1 or awaiting.items[0].assembly_state != "awaiting_assembly":
        raise AssertionError("later installed scan was not awaiting assembly")
    if feedback_status(
        workspace,
        exported_review,
        "feedback_pdf",
        exported.feedback_pdf_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            load_submission_manifest(manifest_path)
        ),
    )[1] != "present":
        raise AssertionError("unassembled candidate incorrectly staled feedback")

    second_assembly = assemble_quillan_submission_manifests(
        workspace, CLASS_ID, ASSIGNMENT_ID, timestamp=T2
    )
    if len(second_assembly.assembled) != 1 or second_assembly.failures:
        raise AssertionError("rescan installed assembly failed")
    assembled_manifest = load_submission_manifest(manifest_path)
    if selected_evidence_fingerprint(assembled_manifest) != initial_fingerprint:
        raise AssertionError("candidate assembly changed authoritative selection")
    if feedback_status(
        workspace,
        exported_review,
        "feedback_pdf",
        exported.feedback_pdf_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            assembled_manifest
        ),
    )[1] != "present":
        raise AssertionError("assembled candidate incorrectly staled feedback")
    return original, candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-quillan-version", required=True)
    parser.add_argument("--expected-core-version", required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    if metadata.version("quillan") != args.expected_quillan_version:
        raise AssertionError("installed Quillan version mismatch")
    if metadata.version("pds-core") != args.expected_core_version:
        raise AssertionError("installed Core version mismatch")
    for module_name in ("quillan", "pds_core"):
        if _module_origin(module_name).is_relative_to(repository):
            raise AssertionError(f"{module_name} import is source-shadowed")

    workspace = args.workspace.resolve()
    original, candidate = _prepare(workspace)
    inbox = build_assignment_resubmission_inbox(
        workspace, CLASS_ID, ASSIGNMENT_ID
    )
    if len(inbox.items) != 1 or inbox.items[0].temporal_classification != "new_after_feedback":
        raise AssertionError("installed inbox did not classify later evidence")
    item = inbox.items[0]
    if item.selected_evidence is None or item.candidate_evidence is None:
        raise AssertionError("installed inbox omitted comparison identities")
    opened_paths: list[Path] = []

    def record_open(path: Path) -> Path:
        opened_paths.append(path)
        return path

    with patch("quillan.evidence_opening.open_local_path", side_effect=record_open):
        for evidence in (original, candidate):
            opened = open_exact_verified_submission_evidence(
                workspace,
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                page_number=1,
                evidence_id=evidence.observation_id,
            )
            if opened.evidence_id != evidence.observation_id:
                raise AssertionError("installed exact opening changed evidence identity")
    if len(opened_paths) != 2:
        raise AssertionError("installed exact opening did not open both comparisons")

    select_submission_evidence_candidate(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        1,
        candidate.observation_id,
        timestamp="2026-09-24T12:00:00+00:00",
    )
    if build_assignment_resubmission_inbox(
        workspace, CLASS_ID, ASSIGNMENT_ID
    ).items:
        raise AssertionError("resolved installed inbox did not rebuild empty")
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.pdf"
    )
    if feedback_status(
        workspace,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            load_submission_manifest(
                submission_manifest_path(
                    workspace,
                    quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
                    STUDENT_ID,
                )
            )
        ),
    )[1] != "stale":
        raise AssertionError("installed feedback remained current after selection")
    print(
        json.dumps(
            {
                "status": "PASS",
                "quillan_version": args.expected_quillan_version,
                "core_version": args.expected_core_version,
                "initial_scan": original.observation_id,
                "candidate_scan": candidate.observation_id,
                "fresh_inbox_items": 0,
                "feedback_status": "stale",
                "exact_evidence_opens": len(opened_paths),
                "real_assembly_runs": 2,
                "real_feedback_pdf_export": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
