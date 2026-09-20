"""Issue #412 feedback distribution assembly service coverage."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from zipfile import ZipFile

import pytest
from pypdf import PdfReader, PdfWriter

import quillan._path_safety as path_safety
import quillan.batch_feedback_assembly as assembly
from quillan.batch_feedback_assembly import (
    BatchFeedbackAssemblyError,
    FeedbackAssemblyPlan,
    FeedbackAssemblyStudentPlan,
    build_feedback_assembly_plan,
    execute_feedback_assembly,
)
from quillan.review_work_queue import (
    AssignmentReviewWorkQueue,
    ReviewWorkQueueItem,
    WORK_QUEUE_CATEGORIES,
)
from quillan.feedback_export import export_student_feedback_pdf
from tests.review_test_support import _write_manifest, _write_review
from tests.test_feedback_pdf_export import (
    _feedback_ready_review,
    _write_assignment_with_rating_labels,
    _write_roster,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _queue(*ids: str) -> AssignmentReviewWorkQueue:
    items = tuple(
        ReviewWorkQueueItem(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id=student_id,
            display_name=f"Student {student_id}",
            category="complete",
            reason_code="feedback_export_current",
            warnings=(),
        )
        for student_id in ids
    )
    return AssignmentReviewWorkQueue(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=items,
        counts=tuple(
            (category, sum(item.category == category for item in items))
            for category in WORK_QUEUE_CATEGORIES
        ),
        unrostered_student_ids=(),
        warnings=(),
    )


def _pdf(*widths: float) -> bytes:
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=792)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def _relative(student_id: str) -> str:
    return (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
        f"submissions/{student_id}/exports/feedback.pdf"
    )


def _write_source(root: Path, student_id: str, data: bytes) -> None:
    path = root / _relative(student_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _plan_item(
    student_id: str,
    data: bytes | None,
    *,
    display_name: str | None = None,
    status: str = "current",
    reason: str = "current",
) -> FeedbackAssemblyStudentPlan:
    return FeedbackAssemblyStudentPlan(
        student_id=student_id,
        display_name=display_name or f"Student {student_id}",
        status=status,  # type: ignore[arg-type]
        reason_code=reason,
        source_relative_path=_relative(student_id),
        review_updated_at="2026-09-20T20:00:00+00:00" if data else None,
        source_review_updated_at="2026-09-20T20:00:00+00:00" if data else None,
        source_size=len(data) if data else None,
        source_sha256=sha256(data).hexdigest() if data else None,
        source_page_count=len(PdfReader(BytesIO(data)).pages) if data else None,
    )


def _plan(
    *items: FeedbackAssemblyStudentPlan,
    output: str = "both",
    duplex_safe: bool = False,
) -> FeedbackAssemblyPlan:
    return FeedbackAssemblyPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="whole_class",
        output=output,  # type: ignore[arg-type]
        duplex_safe=duplex_safe,
        roster_count=len(items),
        items=items,
    )


def test_whole_class_and_selected_planning_preserve_canonical_roster_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue("001", "002", "003")
    monkeypatch.setattr(assembly, "build_assignment_review_work_queue", lambda *a: queue)
    statuses = {
        "001": _plan_item("001", _pdf(101)),
        "002": _plan_item(
            "002", None, status="missing", reason="feedback_pdf_missing"
        ),
        "003": _plan_item(
            "003", None, status="stale", reason="feedback_pdf_stale"
        ),
    }
    monkeypatch.setattr(
        assembly, "_inspect_student", lambda root, item: statuses[item.student_id]
    )

    whole = build_feedback_assembly_plan(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, scope="whole_class", output="print"
    )
    selected = build_feedback_assembly_plan(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="selected",
        student_ids=("003", "001"),
        output="bundle",
    )

    assert [item.student_id for item in whole.items] == ["001", "002", "003"]
    assert whole.included_count == 1
    assert whole.reason_counts == (
        ("feedback_pdf_missing", 1),
        ("feedback_pdf_stale", 1),
    )
    assert [item.student_id for item in selected.items] == ["001", "003"]


def test_selected_scope_rejects_unknown_and_duplicate_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    with pytest.raises(BatchFeedbackAssemblyError, match="unknown roster"):
        build_feedback_assembly_plan(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            scope="selected",
            student_ids=("999",),
            output="print",
        )
    with pytest.raises(BatchFeedbackAssemblyError, match="must be unique"):
        build_feedback_assembly_plan(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            scope="selected",
            student_ids=("001", "001"),
            output="print",
        )


def test_current_canonical_feedback_is_included_without_mutating_records(
    tmp_path: Path,
) -> None:
    _write_roster(tmp_path)
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    review_path = _write_review(tmp_path, _feedback_ready_review())
    export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, "00107", created_at="2026-06-22T14:20:00+00:00"
    )
    before = review_path.read_bytes()

    plan = build_feedback_assembly_plan(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, scope="whole_class", output="print"
    )

    assert plan.included_count == 1
    assert plan.items[0].student_id == "00107"
    assert plan.items[0].status == "current"
    assert plan.items[0].source_relative_path.endswith(
        "/submissions/00107/exports/feedback.pdf"
    )
    assert review_path.read_bytes() == before


def test_both_outputs_share_one_validated_set_and_preserve_source_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _pdf(101, 102, 103)
    second = _pdf(201, 202)
    third = _pdf(301)
    sources = {
        "001": _plan_item("001", first, display_name="../Avery: Rivera"),
        "002": _plan_item("002", second, display_name="Sam Lee"),
        "003": _plan_item("003", third, display_name="Sam Lee"),
    }
    for student_id, data in (("001", first), ("002", second), ("003", third)):
        _write_source(tmp_path, student_id, data)
    monkeypatch.setattr(
        assembly,
        "build_assignment_review_work_queue",
        lambda *a: _queue("001", "002", "003"),
    )
    monkeypatch.setattr(
        assembly, "_inspect_student", lambda root, item: sources[item.student_id]
    )
    plan = _plan(*sources.values(), duplex_safe=True)
    before = {student_id: sha256(data).hexdigest() for student_id, data in (
        ("001", first), ("002", second), ("003", third)
    )}

    result = execute_feedback_assembly(
        tmp_path, plan, batch_id="20260920T211500Z"
    )

    assert result.included_student_ids == ("001", "002", "003")
    assert result.print_packet_page_count == 7
    assert result.sharing_bundle_pdf_count == 3
    packet = tmp_path / str(result.print_packet_relative_path)
    widths = [float(page.mediabox.width) for page in PdfReader(packet).pages]
    assert widths == [101, 102, 103, 103, 201, 202, 301]
    bundle = tmp_path / str(result.sharing_bundle_relative_path)
    with ZipFile(bundle) as archive:
        names = archive.namelist()
        assert names == [
            "Avery_Rivera_feedback.pdf",
            "Sam_Lee_feedback.pdf",
            "Sam_Lee_003_feedback.pdf",
        ]
        assert all("/" not in name and "\\" not in name for name in names)
        assert archive.read(names[0]) == first
        assert archive.read(names[1]) == second
        assert archive.read(names[2]) == third
    assert {
        student_id: sha256((tmp_path / _relative(student_id)).read_bytes()).hexdigest()
        for student_id in before
    } == before


def test_duplex_safe_adds_no_unnecessary_final_blank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = _pdf(111), _pdf(222)
    items = (_plan_item("001", first), _plan_item("002", second))
    _write_source(tmp_path, "001", first)
    _write_source(tmp_path, "002", second)
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001", "002")
    )
    monkeypatch.setattr(
        assembly, "_inspect_student", lambda root, item: items[int(item.student_id) - 1]
    )

    result = execute_feedback_assembly(
        tmp_path,
        _plan(*items, output="print", duplex_safe=True),
        batch_id="20260920T211501Z",
    )

    packet = tmp_path / str(result.print_packet_relative_path)
    assert [float(page.mediabox.width) for page in PdfReader(packet).pages] == [
        111,
        111,
        222,
    ]


def test_state_change_after_preview_excludes_changed_student_from_both_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = _pdf(111), _pdf(222)
    planned = (_plan_item("001", first), _plan_item("002", second))
    _write_source(tmp_path, "001", first)
    _write_source(tmp_path, "002", second)
    changed = _plan_item("001", _pdf(333))
    current = {"001": changed, "002": planned[1]}
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001", "002")
    )
    monkeypatch.setattr(
        assembly, "_inspect_student", lambda root, item: current[item.student_id]
    )

    result = execute_feedback_assembly(
        tmp_path, _plan(*planned), batch_id="20260920T211502Z"
    )

    assert result.included_student_ids == ("002",)
    assert [(item.student_id, item.reason_code) for item in result.exclusions] == [
        ("001", "state_changed")
    ]
    assert result.print_packet_page_count == 1
    with ZipFile(tmp_path / str(result.sharing_bundle_relative_path)) as archive:
        assert len(archive.namelist()) == 1
        assert archive.read(archive.namelist()[0]) == second


def test_output_collision_and_staging_failure_never_install_partial_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _pdf(111)
    item = _plan_item("001", data)
    _write_source(tmp_path, "001", data)
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    monkeypatch.setattr(assembly, "_inspect_student", lambda *a: item)
    plan = _plan(item)
    batch_root = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "feedback_batches"
    )
    collision = batch_root / "20260920T211503Z"
    collision.mkdir(parents=True)
    with pytest.raises(BatchFeedbackAssemblyError, match="Output collision"):
        execute_feedback_assembly(
            tmp_path, plan, batch_id="20260920T211503Z"
        )

    monkeypatch.setattr(
        assembly,
        "_write_sharing_bundle",
        lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic")),
    )
    failed = batch_root / "20260920T211504Z"
    with pytest.raises(BatchFeedbackAssemblyError, match="staging or final"):
        execute_feedback_assembly(
            tmp_path, plan, batch_id="20260920T211504Z"
        )
    assert not failed.exists()
    assert list(batch_root.glob(".20260920T211504Z.*.staging")) == []


def test_feedback_pdf_symlink_fails_closed_without_writing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _pdf(111)
    item = _plan_item("001", data)
    target = tmp_path / "feedback-target.pdf"
    target.write_bytes(data)
    source = tmp_path / _relative("001")
    source.parent.mkdir(parents=True)
    try:
        os.symlink(target, source)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    monkeypatch.setattr(assembly, "_inspect_student", lambda *a: item)

    with pytest.raises(BatchFeedbackAssemblyError, match="No current feedback PDFs"):
        execute_feedback_assembly(
            tmp_path, _plan(item), batch_id="20260920T211505Z"
        )

    assert target.read_bytes() == data
    assert not (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "feedback_batches"
    ).exists()


def test_feedback_batches_directory_symlink_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _pdf(111)
    item = _plan_item("001", data)
    _write_source(tmp_path, "001", data)
    target = tmp_path / "batch-output-target"
    target.mkdir()
    batches = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "feedback_batches"
    )
    batches.parent.mkdir(parents=True)
    try:
        os.symlink(target, batches, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    monkeypatch.setattr(assembly, "_inspect_student", lambda *a: item)

    with pytest.raises(BatchFeedbackAssemblyError, match="output path contains a link"):
        execute_feedback_assembly(
            tmp_path, _plan(item), batch_id="20260920T211506Z"
        )

    assert list(target.iterdir()) == []


def test_link_like_feedback_pdf_fails_closed_on_every_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _pdf(111)
    item = _plan_item("001", data)
    _write_source(tmp_path, "001", data)
    source = tmp_path / _relative("001")
    original_is_link_like = path_safety.is_link_like
    monkeypatch.setattr(
        assembly,
        "is_link_like",
        lambda path: Path(path) == source or original_is_link_like(path),
    )
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    monkeypatch.setattr(assembly, "_inspect_student", lambda *a: item)

    with pytest.raises(BatchFeedbackAssemblyError, match="No current feedback PDFs"):
        execute_feedback_assembly(
            tmp_path, _plan(item), batch_id="20260920T211507Z"
        )


def test_link_like_output_component_fails_closed_on_every_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _pdf(111)
    item = _plan_item("001", data)
    _write_source(tmp_path, "001", data)
    batches = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "feedback_batches"
    )
    batches.mkdir(parents=True)
    original_is_link_like = path_safety.is_link_like
    monkeypatch.setattr(
        assembly,
        "is_link_like",
        lambda path: Path(path) == batches or original_is_link_like(path),
    )
    monkeypatch.setattr(
        assembly, "build_assignment_review_work_queue", lambda *a: _queue("001")
    )
    monkeypatch.setattr(assembly, "_inspect_student", lambda *a: item)

    with pytest.raises(BatchFeedbackAssemblyError, match="output path contains a link"):
        execute_feedback_assembly(
            tmp_path, _plan(item), batch_id="20260920T211508Z"
        )

    assert list(batches.iterdir()) == []


def test_bundle_only_rejects_duplex_safe() -> None:
    with pytest.raises(BatchFeedbackAssemblyError, match="only to print"):
        assembly._validate_options("whole_class", "bundle", True, ())
