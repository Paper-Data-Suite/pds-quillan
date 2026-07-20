"""Managed printable-response renderer and layout tests."""

from dataclasses import replace
from pathlib import Path

from pypdf import PdfReader
import pytest

from quillan.printable_response import (
    PrintableResponseRenderError,
    render_printable_response_pdf,
)
from quillan.printable_response_packet import (
    generate_printable_response_packet,
    plan_printable_response_packet,
)
from quillan.printable_response_generation import (
    build_printable_response_artifact_plan,
    select_printable_response_predecessors,
)
from quillan.printable_response_persistence import (
    PersistedPrintableResponseRecordSet,
    write_printable_response_record_set,
)
from quillan.printable_response_routes import (
    PersistedPrintableResponseRouteSet,
    RegisteredPrintableResponsePageRoute,
    persist_printable_response_route_set,
)
from pds_core.routes import route_registration_path
from quillan.work_paths import (
    initialize_managed_work_layout,
    quillan_work_paths,
    quillan_work_ref,
)
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)


def test_managed_packet_layout_uses_immutable_identity_and_order(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    result = generate_printable_response_packet(
        plan_printable_response_packet(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2
        )
    )
    assert result.success
    reader = PdfReader(str(result.output_path))
    assert len(reader.pages) == 4
    texts = tuple(page.extract_text() for page in reader.pages)
    assert "Avery Zulu" in texts[0]
    assert "Student ID: 00107" in texts[0]
    assert "Page 1 of 2" in texts[0]
    assert "Page 2 of 2" in texts[1]
    assert "Morgan Alpha" in texts[2]
    assert "Student ID: 00002" in texts[2]
    assert f"Page ID: {result.page_ids[0]}" in texts[0]
    assert f"Route ID: {result.route_ids[0]}" in texts[0]
    assert all("Private synthetic directions" not in text for text in texts)


def test_renderer_has_no_unmanaged_mapping_bypass(tmp_path: Path) -> None:
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            tmp_path.resolve(),
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
            tmp_path / "unsafe.pdf",
            ({"page": "raw"},),
        )
    assert not (tmp_path / "unsafe.pdf").exists()


@pytest.mark.parametrize("invalid_root", [None, object(), 42, []])
def test_renderer_rejects_wrong_root_types_as_render_errors(
    tmp_path: Path,
    invalid_root: object,
) -> None:
    destination = tmp_path / "unchanged.pdf"
    destination.write_bytes(b"unchanged renderer destination")
    with pytest.raises(PrintableResponseRenderError, match="workspace_root"):
        render_printable_response_pdf(
            invalid_root,  # type: ignore[arg-type]
            object(),
            destination,
            object(),
        )
    assert destination.read_bytes() == b"unchanged renderer destination"
    assert tuple(tmp_path.iterdir()) == (destination,)


def persisted_render_packet(tmp_path: Path):  # type: ignore[no-untyped-def]
    packet = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    predecessors = select_printable_response_predecessors(
        packet.workspace_root, packet.work_ref, packet.students
    )
    artifact = build_printable_response_artifact_plan(
        workspace_root=packet.workspace_root,
        work_ref=packet.work_ref,
        assignment=packet.assignment,
        students=packet.students,
        pages_per_student=1,
        output_path=packet.output_path,
        predecessors=predecessors,
    )
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    records = write_printable_response_record_set(
        tmp_path, packet.work_ref, artifact.record_sets[0]
    )
    routes = persist_printable_response_route_set(
        tmp_path, packet.work_ref, records, artifact.route_sets[0]
    )
    artifact.temporary_path.write_bytes(b"owned temporary sentinel")
    return packet, artifact, records, routes


def test_renderer_rejects_claimed_but_unpersisted_records_before_truncation(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    packet = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    predecessors = select_printable_response_predecessors(
        packet.workspace_root, packet.work_ref, packet.students
    )
    artifact = build_printable_response_artifact_plan(
        workspace_root=packet.workspace_root,
        work_ref=packet.work_ref,
        assignment=packet.assignment,
        students=packet.students,
        pages_per_student=1,
        output_path=packet.output_path,
        predecessors=predecessors,
    )
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    artifact.temporary_path.write_bytes(b"unchanged")
    claimed = PersistedPrintableResponseRecordSet(
        artifact.record_sets[0],
        tmp_path / "claimed-issuance.json",
        tuple(tmp_path / page.page_id for page in artifact.record_sets[0].pages),
    )
    planned_route = artifact.route_sets[0][0]
    claimed_routes = PersistedPrintableResponseRouteSet(
        artifact.record_sets[0],
        (
            RegisteredPrintableResponsePageRoute(
                planned_route,
                route_registration_path(tmp_path, planned_route.locator),
            ),
        ),
    )
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            tmp_path.resolve(),
            packet.work_ref,
            artifact.temporary_path,
            ((claimed, claimed_routes),),
        )
    assert artifact.temporary_path.read_bytes() == b"unchanged"


def test_renderer_rejects_missing_persisted_page_before_truncation(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact, records, routes = persisted_render_packet(tmp_path)
    records.page_paths[0].unlink()
    before = artifact.temporary_path.read_bytes()
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            tmp_path.resolve(), packet.work_ref, artifact.temporary_path, ((records, routes),)
        )
    assert artifact.temporary_path.read_bytes() == before


def test_renderer_rejects_noncanonical_registered_path_before_truncation(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact, records, routes = persisted_render_packet(tmp_path)
    fabricated_route = replace(
        routes.routes[0], registration_path=tmp_path / "fabricated-route.json"
    )
    fabricated = PersistedPrintableResponseRouteSet(
        routes.record_set, (fabricated_route,)
    )
    before = artifact.temporary_path.read_bytes()
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            tmp_path.resolve(), packet.work_ref, artifact.temporary_path, ((records, fabricated),)
        )
    assert artifact.temporary_path.read_bytes() == before


def test_renderer_rejects_route_authority_from_another_workspace(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_packet_workspace(first)
    packet, artifact, records, routes = persisted_render_packet(first)
    write_packet_workspace(second)
    second_paths = quillan_work_paths(second, CLASS_ID, ASSIGNMENT_ID)
    initialize_managed_work_layout(second_paths)
    destination = second_paths.templates_dir / artifact.temporary_path.name
    destination.write_bytes(b"other workspace sentinel")
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            second.resolve(), packet.work_ref, destination, ((records, routes),)
        )
    assert destination.read_bytes() == b"other workspace sentinel"


def test_renderer_rejects_wrong_destination_without_creation(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    wrong = tmp_path / "wrong.pdf"
    with pytest.raises(PrintableResponseRenderError):
        render_printable_response_pdf(
            tmp_path.resolve(),
            quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
            wrong,
            (),
        )
    assert not wrong.exists()
