"""Issue #415 resubmission inbox and explicit evidence-resolution coverage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, cast

from pds_core.module_dispatch import RouteDispatchRequest, RouteDispatchSuccess
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import RouteResolution
from pds_core.scan_retention import retain_source_scan
import pytest

import quillan.response_page_observations as observation_module
import quillan.review_read_context as read_context_module

from quillan.assignment_summary_context import feedback_status
from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.pds_module import get_module_profile
from quillan.response_page_observation_persistence import (
    PersistedQuillanPageObservation,
    persist_quillan_page_observation,
)
from quillan.resubmission_inbox import (
    assignment_resubmission_inbox_to_dict,
    build_assignment_resubmission_inbox,
)
from quillan.review_record import build_empty_review_record
from quillan.review_dashboard import build_assignment_review_dashboard
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.route_handler import handle_quillan_response_page_route
from quillan.submission_evidence_resolution import (
    SubmissionEvidenceResolutionError,
    dismiss_submission_evidence_candidate,
    select_submission_evidence_candidate,
)
from quillan.submission_evidence_validation import (
    evidence_matches_observation,
    expected_evidence_projection,
    selected_evidence_fingerprint,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_manifest_paths import write_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_exact_verified_submission_evidence,
)
from tests.review_test_support import (
    ASSIGNMENT_ID as REPRESENTATIVE_ASSIGNMENT_ID,
    CLASS_ID as REPRESENTATIVE_CLASS_ID,
    _write_assignment,
)
from tests.test_route_handler import route_context
from tests.test_selected_review_read_amplification_issue414 import (
    TOTAL_OBSERVATIONS,
    _prepare as _prepare_representative_class,
)

T1 = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _persist_scan(
    root: Path,
    resolution: RouteResolution,
    *,
    name: str,
    content: bytes,
    timestamp: datetime,
) -> PersistedQuillanPageObservation:
    source = root / name
    source.write_bytes(content)
    retained = retain_source_scan(root, source, intake_timestamp=timestamp)
    result = handle_quillan_response_page_route(resolution, retained, 1)
    request = RouteDispatchRequest(resolution.locator, retained, 1)
    success = RouteDispatchSuccess(
        request=request,
        profile=get_module_profile(),
        resolution=resolution,
        module_result=result,
    )
    outcome = QuillanScanPageOutcome(
        source_page_number=1,
        terminal_category="dispatch_success",
        retained_source=retained,
        raw_payload_text="PDS2 synthetic",
        locator=resolution.locator,
        decode_method="synthetic",
        dispatch_request=request,
        dispatch_outcome=success,
    )
    return persist_quillan_page_observation(root, outcome)


def _prepare_initial_and_rescan(
    tmp_path: Path,
) -> tuple[
    RouteResolution,
    PersistedQuillanPageObservation,
    PersistedQuillanPageObservation,
    Path,
]:
    resolution, _ = route_context(tmp_path)
    identity = resolution.locator
    _write_assignment(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.work_id,
    )
    write_route_registration(tmp_path, resolution.registration)
    first = _persist_scan(
        tmp_path,
        resolution,
        name="initial.png",
        content=b"same bytes are allowed",
        timestamp=T1,
    )
    assembled = assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    ).assembled[0]
    second = _persist_scan(
        tmp_path,
        resolution,
        name="rescan.png",
        content=b"same bytes are allowed",
        timestamp=T2,
    )
    return resolution, first, second, assembled.manifest_path


def test_later_physical_intake_is_actionable_even_when_bytes_match(
    tmp_path: Path,
) -> None:
    resolution, first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator

    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    awaiting = build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    )

    assert len(awaiting.items) == 1
    assert awaiting.items[0].assembly_state == "awaiting_assembly"
    assert awaiting.items[0].candidate_evidence is not None
    assert awaiting.items[0].candidate_evidence.evidence_id == second.observation.observation_id
    assert before == {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    }

    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    inbox = build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    )
    assert inbox.student_count == 1
    assert inbox.page_count == 1
    assert len(inbox.items) == 1
    item = inbox.items[0]
    assert item.selected_evidence is not None
    assert item.selected_evidence.evidence_id == first.observation.observation_id
    assert item.candidate_evidence is not None
    assert item.candidate_evidence.evidence_id == second.observation.observation_id
    payload = assignment_resubmission_inbox_to_dict(inbox)
    assert payload["record_type"] == "quillan_assignment_resubmission_inbox"
    assert str(tmp_path) not in json.dumps(payload)
    assert load_submission_manifest(manifest_path)["pages"][0][
        "selected_evidence_id"
    ] == first.observation.observation_id


def test_initial_intake_and_invalid_review_without_rescan_are_not_inbox_items(
    tmp_path: Path,
) -> None:
    resolution, _ = route_context(tmp_path)
    identity = resolution.locator
    _write_assignment(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.work_id,
    )
    write_route_registration(tmp_path, resolution.registration)
    first = _persist_scan(
        tmp_path,
        resolution,
        name="initial.png",
        content=b"initial evidence",
        timestamp=T1,
    )
    assert not build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    ).items

    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    invalid_review = review_record_path(
        tmp_path,
        identity.class_id,
        identity.work_id,
        first.observation.student_id,
    )
    invalid_review.parent.mkdir(parents=True, exist_ok=True)
    invalid_review.write_text("not json", encoding="utf-8")
    assert not build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    ).items


def test_candidate_cannot_be_dismissed_without_authoritative_selection(
    tmp_path: Path,
) -> None:
    resolution, _ = route_context(tmp_path)
    identity = resolution.locator
    _write_assignment(
        tmp_path,
        class_id=identity.class_id,
        assignment_id=identity.work_id,
    )
    write_route_registration(tmp_path, resolution.registration)
    _persist_scan(
        tmp_path,
        resolution,
        name="first.png",
        content=b"first",
        timestamp=T1,
    )
    second = _persist_scan(
        tmp_path,
        resolution,
        name="second.png",
        content=b"second",
        timestamp=T2,
    )
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )

    with pytest.raises(
        SubmissionEvidenceResolutionError,
        match="authoritative selected evidence",
    ):
        dismiss_submission_evidence_candidate(
            tmp_path,
            identity.class_id,
            identity.work_id,
            second.observation.student_id,
            1,
            second.observation.observation_id,
        )


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    (
        ("retained_source", "source_scan_id", "scan_contradictory_source"),
        ("module_details", "route_id", "rt_ffffffffffffffffffffffffffffffff"),
        ("module_details", "routed_evidence_sha256", "0" * 64),
        ("module_details", "routed_evidence_kind", "rendered_pdf_page_png"),
    ),
)
def test_full_observation_projection_is_shared_by_inbox_and_resolution(
    tmp_path: Path,
    section: str,
    field: str,
    replacement: object,
) -> None:
    resolution, _first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    manifest = load_submission_manifest(manifest_path)
    candidate = next(
        evidence
        for evidence in manifest["pages"][0]["evidence"]
        if evidence["evidence_id"] == second.observation.observation_id
    )
    candidate[section][field] = replacement
    write_submission_manifest(manifest_path, manifest, overwrite=True)

    inbox = build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    )
    assert [item.attention_code for item in inbox.items] == [
        "candidate_evidence_observation_mismatch"
    ]
    with pytest.raises(
        SubmissionEvidenceResolutionError,
        match="strictly verified observation",
    ):
        select_submission_evidence_candidate(
            tmp_path,
            identity.class_id,
            identity.work_id,
            second.observation.student_id,
            1,
            second.observation.observation_id,
        )


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    (
        ("retained_source", "retained_source_path", "different/source.png"),
        ("module_details", "generation_id", "gen_ffffffffffffffffffffffffffffffff"),
        ("module_details", "artifact_id", "art_ffffffffffffffffffffffffffffffff"),
        ("module_details", "total_pages", 2),
        ("module_details", "page_role", "continuation"),
        ("module_details", "routed_evidence_kind", "rendered_pdf_page_png"),
    ),
)
def test_shared_projection_validator_covers_all_observation_provenance(
    tmp_path: Path,
    section: str,
    field: str,
    replacement: object,
) -> None:
    _resolution, _first, second, _manifest_path = _prepare_initial_and_rescan(
        tmp_path
    )
    evidence = expected_evidence_projection(
        second.observation,
        duplicate_number=1,
        evidence_role="candidate",
        evidence_state="active",
    )
    evidence[section][field] = replacement
    assert not evidence_matches_observation(evidence, second.observation)


def test_exact_open_reverifies_bytes_after_inbox_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, _first, second, _manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    inbox = build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    )
    item = inbox.items[0]
    opened_paths: list[Path] = []

    def open_locally(path: Path) -> Path:
        opened_paths.append(path)
        return path

    monkeypatch.setattr("quillan.evidence_opening.open_local_path", open_locally)
    opened = open_exact_verified_submission_evidence(
        tmp_path,
        identity.class_id,
        identity.work_id,
        item.student_id,
        page_number=1,
        evidence_id=second.observation.observation_id,
    )
    assert opened.evidence_id == second.observation.observation_id
    assert len(opened_paths) == 1

    evidence_path = tmp_path.joinpath(*Path(second.observation.routed_evidence_path).parts)
    evidence_path.write_bytes(b"tampered after render")
    with pytest.raises(SubmissionReviewOpeningError, match="verify routed observations"):
        open_exact_verified_submission_evidence(
            tmp_path,
            identity.class_id,
            identity.work_id,
            item.student_id,
            page_number=1,
            evidence_id=second.observation.observation_id,
        )
    assert len(opened_paths) == 1


def test_feedback_chronology_selection_and_dismissal_are_explicit(
    tmp_path: Path,
) -> None:
    resolution, first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    review = build_empty_review_record(
        class_id=identity.class_id,
        assignment_id=identity.work_id,
        student_id=first.observation.student_id,
        created_at="2026-09-17T12:00:00+00:00",
    )
    review["updated_at"] = "2026-09-18T12:00:00+00:00"
    feedback_path = manifest_path.parent / "exports" / "feedback.pdf"
    feedback_path.parent.mkdir(parents=True)
    feedback_path.write_bytes(b"feedback")
    review["exports"]["feedback_pdf"] = {
        "path": feedback_path.relative_to(tmp_path).as_posix(),
        "generated_at": "2026-09-18T12:00:00+00:00",
        "source_review_updated_at": "2026-09-18T12:00:00+00:00",
        "module_details": {
            "source_selected_evidence_fingerprint": selected_evidence_fingerprint(
                load_submission_manifest(manifest_path)
            )
        },
    }
    write_review_record(
        review_record_path(
            tmp_path,
            identity.class_id,
            identity.work_id,
            first.observation.student_id,
        ),
        review,
    )

    inbox = build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    )
    assert inbox.items[0].temporal_classification == "new_after_feedback"
    manifest_before_selection = load_submission_manifest(manifest_path)
    assert feedback_status(
        tmp_path,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            manifest_before_selection
        ),
    )[1] == "present"

    selected = select_submission_evidence_candidate(
        tmp_path,
        identity.class_id,
        identity.work_id,
        first.observation.student_id,
        1,
        second.observation.observation_id,
        timestamp="2026-09-24T12:00:00+00:00",
    )
    assert selected.previous_selected_evidence_id == first.observation.observation_id
    manifest = load_submission_manifest(manifest_path)
    page = manifest["pages"][0]
    assert page["selected_evidence_id"] == second.observation.observation_id
    assert {item["evidence_id"] for item in page["evidence"]} == {
        first.observation.observation_id,
        second.observation.observation_id,
    }
    assert not build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    ).items
    assert feedback_status(
        tmp_path,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(manifest),
    )[1:] == (
        "stale",
        "true",
        ("feedback_pdf_stale", "feedback_pdf_stale_selected_evidence"),
    )
    dashboard = build_assignment_review_dashboard(
        tmp_path, identity.class_id, identity.work_id
    )
    student = next(
        item
        for item in dashboard.students
        if item.student_id == first.observation.student_id
    )
    assert student.feedback_pdf_status == "stale"

    third = _persist_scan(
        tmp_path,
        resolution=resolution,
        name="third.png",
        content=b"third physical scan",
        timestamp=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
    )
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    dismiss_submission_evidence_candidate(
        tmp_path,
        identity.class_id,
        identity.work_id,
        first.observation.student_id,
        1,
        third.observation.observation_id,
        timestamp="2026-09-26T12:00:00+00:00",
    )
    assert not build_assignment_resubmission_inbox(
        tmp_path, identity.class_id, identity.work_id
    ).items
    manifest = load_submission_manifest(manifest_path)
    dismissed = next(
        item
        for item in manifest["pages"][0]["evidence"]
        if item["evidence_id"] == third.observation.observation_id
    )
    assert dismissed["evidence_role"] == "excluded"
    assert dismissed["evidence_state"] == "excluded"


def test_candidate_assembly_and_dismissal_do_not_stale_feedback(
    tmp_path: Path,
) -> None:
    resolution, first, second, manifest_path = _prepare_initial_and_rescan(tmp_path)
    identity = resolution.locator
    initial_manifest = load_submission_manifest(manifest_path)
    fingerprint = selected_evidence_fingerprint(initial_manifest)
    assemble_quillan_submission_manifests(
        tmp_path, identity.class_id, identity.work_id
    )
    assembled_manifest = load_submission_manifest(manifest_path)
    assert selected_evidence_fingerprint(assembled_manifest) == fingerprint

    review = build_empty_review_record(
        class_id=identity.class_id,
        assignment_id=identity.work_id,
        student_id=first.observation.student_id,
        created_at="2026-09-17T12:00:00+00:00",
    )
    review["updated_at"] = "2026-09-18T12:00:00+00:00"
    feedback_path = manifest_path.parent / "exports" / "feedback.pdf"
    feedback_path.parent.mkdir(parents=True)
    feedback_path.write_bytes(b"feedback")
    review["exports"]["feedback_pdf"] = {
        "path": feedback_path.relative_to(tmp_path).as_posix(),
        "generated_at": "2026-09-18T12:00:00+00:00",
        "source_review_updated_at": "2026-09-18T12:00:00+00:00",
        "module_details": {
            "source_selected_evidence_fingerprint": fingerprint,
        },
    }
    write_review_record(
        review_record_path(
            tmp_path,
            identity.class_id,
            identity.work_id,
            first.observation.student_id,
        ),
        review,
    )
    assert feedback_status(
        tmp_path,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            assembled_manifest
        ),
    )[1] == "present"

    dismiss_submission_evidence_candidate(
        tmp_path,
        identity.class_id,
        identity.work_id,
        first.observation.student_id,
        1,
        second.observation.observation_id,
        timestamp="2026-09-24T12:00:00+00:00",
    )
    dismissed_manifest = load_submission_manifest(manifest_path)
    assert dismissed_manifest["updated_at"] == "2026-09-24T12:00:00+00:00"
    assert selected_evidence_fingerprint(dismissed_manifest) == fingerprint
    assert feedback_status(
        tmp_path,
        review,
        "feedback_pdf",
        feedback_path,
        selected_evidence_fingerprint=selected_evidence_fingerprint(
            dismissed_manifest
        ),
    )[1] == "present"


def test_one_inbox_build_reuses_one_bounded_assignment_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_representative_class(tmp_path)
    counts = {"assignment": 0, "roster": 0, "group": 0, "verify": 0}
    read_context_any = cast(Any, read_context_module)
    observation_any = cast(Any, observation_module)
    original_assignment = read_context_any.load_quillan_assignment_context
    original_roster = read_context_any.load_class_roster
    original_group = read_context_any.group_response_page_observations_by_student
    original_verify = observation_any.verify_contextual_routed_page_evidence

    def counted(name: str, function: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            counts[name] += 1
            return function(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(
        read_context_any,
        "load_quillan_assignment_context",
        counted("assignment", original_assignment),
    )
    monkeypatch.setattr(
        read_context_any,
        "load_class_roster",
        counted("roster", original_roster),
    )
    monkeypatch.setattr(
        read_context_any,
        "group_response_page_observations_by_student",
        counted("group", original_group),
    )
    monkeypatch.setattr(
        observation_any,
        "verify_contextual_routed_page_evidence",
        counted("verify", original_verify),
    )

    build_assignment_resubmission_inbox(
        tmp_path, REPRESENTATIVE_CLASS_ID, REPRESENTATIVE_ASSIGNMENT_ID
    )

    assert counts == {
        "assignment": 1,
        "roster": 1,
        "group": 1,
        "verify": TOTAL_OBSERVATIONS,
    }
