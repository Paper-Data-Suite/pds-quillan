"""Generate and mechanically inspect the installed v0.8.9 layout matrix."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict
import zipfile

from pdf2image import convert_from_path
from PIL import Image, ImageDraw
from pds_core.classes import write_class_roster
from pds_core.pds2 import parse_pds2_payload
from pds_core.route_registrations import resolve_route_registration
from pds_core.rosters import create_roster
from pypdf import PdfReader

from quillan.assignment_workflows import build_assignment_config, write_assignment_config
from quillan.printable_response_generation import build_printable_response_artifact_plan, execute_printable_response_artifact, select_printable_response_predecessors
from quillan.printable_response_packet import generate_printable_response_packet, plan_printable_response_packet
from quillan.printable_response_routes import build_printable_response_route_set
from quillan.qr_decode import decode_qr_payload_from_image_path

STANDARD_ID = "synthetic:W.VISUAL.1"
RENDER_DPI = 200


class VisualOptions(TypedDict, total=False):
    students: list[dict[str, str]]
    pages: int
    title: str
    class_id: str
    assignment_id: str
    regenerate: bool
    limitation: str
    class_label: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assignment(class_id: str, assignment_id: str, title: str) -> dict[str, Any]:
    return build_assignment_config(
        assignment_id=assignment_id,
        title=title,
        class_id=class_id,
        writing_type="argument",
        student_prompt="Write a harmless synthetic visual response.",
        standards_profile_id="synthetic_visual_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={"type": "paragraph", "singular_label": "paragraph", "plural_label": "paragraphs"},
        rating_scale={"scale_id": "synthetic", "levels": [{"value": 1, "label": "Synthetic", "description": "Synthetic."}]},
        basic_requirements={"paragraphs_min": 1},
        minimum_requirement_policy={"allow_return_without_full_review": True},
    )


def _case(root: Path, name: str, *, students: list[dict[str, str]], pages: int, title: str = "Synthetic Visual Response", class_id: str | None = None, assignment_id: str | None = None, regenerate: bool = False, limitation: str | None = None, class_label: str | None = None) -> tuple[dict[str, object], list[Path]]:
    workspace = root / name / "workspace"
    class_id = class_id or f"class_{name}"
    assignment_id = assignment_id or f"assignment_{name}"
    write_class_roster(workspace, create_roster(class_id, students))
    write_assignment_config(workspace, class_id, _assignment(class_id, assignment_id, title))
    packet_plan = plan_printable_response_packet(workspace, class_id, assignment_id, pages_per_student=pages)
    if class_label is None:
        first = generate_printable_response_packet(packet_plan)
    else:
        predecessors = select_printable_response_predecessors(packet_plan.workspace_root, packet_plan.work_ref, packet_plan.students)
        artifact = build_printable_response_artifact_plan(workspace_root=packet_plan.workspace_root, work_ref=packet_plan.work_ref, assignment=packet_plan.assignment, students=packet_plan.students, pages_per_student=pages, output_path=packet_plan.output_path, predecessors=predecessors)
        records = tuple(replace(record, issuance=replace(record.issuance, class_label=class_label)) for record in artifact.record_sets)
        routes = tuple(build_printable_response_route_set(record, tuple(route.locator.route_id for route in old_routes)) for record, old_routes in zip(records, artifact.route_sets, strict=True))
        artifact = replace(artifact, record_sets=records, route_sets=routes)
        first = execute_printable_response_artifact(artifact, output_relative_path=packet_plan.output_relative_path, expected_output_digest=None, overwrite=False)
    result = first
    regenerated = False
    if regenerate:
        result = generate_printable_response_packet(plan_printable_response_packet(workspace, class_id, assignment_id, pages_per_student=pages), overwrite=True)
        assert first.generation_id != result.generation_id
        assert set(first.page_ids).isdisjoint(result.page_ids)
        assert set(first.route_ids).isdisjoint(result.route_ids)
        regenerated = True

    reader = PdfReader(str(result.output_path))
    assert len(reader.pages) == len(students) * pages
    images = convert_from_path(str(result.output_path), dpi=RENDER_DPI, grayscale=True)
    assert len(images) == len(reader.pages)
    rendered: list[Path] = []
    qr_results: list[dict[str, object]] = []
    for index, (page, image, page_id, route_id) in enumerate(zip(reader.pages, images, result.page_ids, result.route_ids, strict=True), start=1):
        assert float(page.mediabox.width) == 612.0
        assert float(page.mediabox.height) == 792.0
        assert image.size == (1700, 2200)
        image_path = root / name / f"page-{index:02d}.png"
        image.save(image_path)
        rendered.append(image_path)
        decoded = decode_qr_payload_from_image_path(image_path)
        assert decoded.error is None and decoded.raw_payload_text is not None
        locator = parse_pds2_payload(decoded.raw_payload_text)
        resolution = resolve_route_registration(workspace, locator)
        assert locator.route_id == route_id
        assert resolution.registration.target.record_id == page_id
        text = page.extract_text()
        assert f"Page ID: {page_id}" in text
        assert f"Route ID: {route_id}" in text
        assert "Student ID:" in text and "Page " in text
        if class_label is not None:
            assert f"Class: {class_label} ({class_id})" in text
        qr_results.append({"page": index, "page_id": page_id, "route_id": route_id, "decode": "PASS", "method": decoded.decode_method})
    return ({"case": name, "packet": str(result.output_path), "sha256": _sha256(result.output_path), "page_count": len(reader.pages), "letter_points": [612, 792], "render_dpi": RENDER_DPI, "render_pixels": [1700, 2200], "qr": qr_results, "regenerated": regenerated, "visual_result": "PASS" if limitation is None else "PASS WITH DOCUMENTED LIMITATION", "limitation": limitation}, rendered)


def _contact_sheet(paths: list[tuple[str, Path]], destination: Path) -> None:
    thumb_width, thumb_height = 425, 550
    columns = 3
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("L", (columns * thumb_width, rows * (thumb_height + 28)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(paths):
        image = Image.open(path).convert("L")
        image.thumbnail((thumb_width, thumb_height))
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + 28)
        sheet.paste(image, (x, y + 24))
        draw.text((x + 4, y + 4), label, fill="black")
    sheet.save(destination)


def _write_visual_archive(
    destination: Path, entries: list[tuple[str, Path]]
) -> dict[str, object]:
    """Write collision-free visual evidence without flattened member names."""
    names = [name for name, _ in entries]
    if len(names) != len(set(names)):
        raise ValueError("Visual evidence archive member names must be unique.")
    if destination.exists():
        raise ValueError("Refusing to overwrite a visual evidence archive.")
    if not all(path.is_file() for _, path in entries):
        raise ValueError("Every visual evidence archive source must be a file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in entries:
            archive.write(path, arcname=name)
    with zipfile.ZipFile(destination) as archive:
        written = archive.namelist()
    assert written == names
    assert len(written) == len(set(written))
    return {
        "path": str(destination),
        "sha256": _sha256(destination),
        "member_count": len(written),
        "unique_member_count": len(set(written)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-wheel", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    source_wheel = args.source_wheel.resolve(strict=True)
    assert source_wheel.is_file()
    output.mkdir(parents=True, exist_ok=False)
    def basic(
        student_id: str = "00107",
        first: str = "Avery",
        last: str = "Example",
    ) -> list[dict[str, str]]:
        return [
            {
                "student_id": student_id,
                "first_name": first,
                "last_name": last,
                "period": "3",
            }
        ]
    specifications: tuple[tuple[str, VisualOptions], ...] = (
        ("one-student-one-page", dict(students=basic(), pages=1)),
        ("several-students-one-page", dict(students=[{"student_id": f"00{i}", "first_name": f"Student{i}", "last_name": "Synthetic", "period": "3"} for i in range(101, 104)], pages=1)),
        ("two-continuation-pages", dict(students=basic(), pages=2)),
        ("three-continuation-pages", dict(students=basic(), pages=3)),
        ("leading-zero-id", dict(students=basic("00002"), pages=1)),
        ("long-assignment-title", dict(students=basic(), pages=1, title="A Very Long Synthetic Assignment Title Designed to Exercise Safe Header Truncation Without Overlap or Clipping")),
        ("long-student-name", dict(students=basic(first="Alexandria-Cassandra", last="Longsyntheticfamilyname-Withsuffix"), pages=1)),
        ("class-label-differs", dict(students=basic(), pages=1, class_id="english_10_period_2", class_label="English 10 Period 2")),
        ("long-valid-identifiers", dict(students=basic(), pages=1, class_id="synthetic_class_identifier_2026_period_03", assignment_id="synthetic_assignment_identifier_release_0089")),
        ("regenerated-identities", dict(students=basic(), pages=1, regenerate=True)),
    )
    results: list[dict[str, object]] = []
    contact_paths: list[tuple[str, Path]] = []
    archive_entries: list[tuple[str, Path]] = []
    for name, options in specifications:
        result, rendered = _case(output, name, **options)
        results.append(result)
        contact_paths.extend((f"{name} p{index}", path) for index, path in enumerate(rendered, start=1))
        archive_entries.extend(
            (f"{name}/page-{index:02d}.png", path)
            for index, path in enumerate(rendered, start=1)
        )
        archive_entries.append(
            (f"{name}/printable_response_pages.pdf", Path(str(result["packet"])))
        )
    contact = output / "visual-matrix-contact-sheet.png"
    _contact_sheet(contact_paths, contact)
    archive_entries.insert(0, ("contact-sheet.png", contact))
    archive = _write_visual_archive(args.archive.resolve(), archive_entries)
    report = {
        "source_wheel": str(source_wheel),
        "source_wheel_sha256": _sha256(source_wheel),
        "installed_visual_matrix": results,
        "contact_sheet": str(contact),
        "visual_archive": archive,
        "physical_acceptance": "PENDING OWNER",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
