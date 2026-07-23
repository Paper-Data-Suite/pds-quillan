"""Probe an installed Quillan distribution outside its source checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import pkgutil
import subprocess
import sys
from typing import Any

EXPECTED_VERSION = "0.8.9"
CLASS_ID = "synthetic_release_class"
ASSIGNMENT_ID = "synthetic_release_digital"
STANDARD_ID = "synthetic:W.RELEASE.1"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    assert type(value) is dict, path
    return value


def _verify_digital_durable_state(
    workspace: Path, work_root: Path, *, expected_students: tuple[str, ...]
) -> dict[str, object]:
    """Discover and assert the successful digital workflow's durable records."""
    observations = tuple(
        _load_object(path)
        for path in sorted((work_root / "scans" / "observations").glob("*.json"))
    )
    assert len(observations) == 4
    assert all(item.get("record_type") == "response_page_observation" for item in observations)
    source_events = {
        (item["source_scan_id"], item["source_sha256"], item["retained_source_path"])
        for item in observations
    }
    assert len(source_events) == 1
    source_scan_id, source_sha256, retained_relative = next(iter(source_events))
    retained_path = workspace / str(retained_relative)
    assert retained_path.is_file()
    assert hashlib.sha256(retained_path.read_bytes()).hexdigest() == source_sha256
    retained_pages = {
        (item["source_scan_id"], item["source_page_number"])
        for item in observations
    }
    assert retained_pages == {(source_scan_id, page) for page in range(1, 5)}

    evidence_paths: set[Path] = set()
    for observation in observations:
        evidence = workspace / str(observation["routed_evidence_path"])
        assert evidence.is_file()
        assert hashlib.sha256(evidence.read_bytes()).hexdigest() == observation["routed_evidence_sha256"]
        evidence_paths.add(evidence.resolve())
    assert len(evidence_paths) == 4

    manifests: list[dict[str, Any]] = []
    manifest_paths: list[Path] = []
    for student_id in expected_students:
        path = work_root / "submissions" / student_id / "submission.json"
        manifest = _load_object(path)
        assert manifest["student_id"] == student_id
        assert manifest["expected_pages"] == 2
        assert len(manifest["pages"]) == 2
        assert [page["page_number"] for page in manifest["pages"]] == [1, 2]
        assert all(
            page["page_state"] == "present" and page["selected_evidence_id"]
            for page in manifest["pages"]
        )
        manifests.append(manifest)
        manifest_paths.append(path)
    assert len(manifests) == 2

    route_records = tuple(sorted((work_root / "routes").glob("*.json")))
    assert len(route_records) == 4
    post_dispatch = tuple(
        sorted((work_root / "scans" / "review" / "post_dispatch").glob("*.json"))
    )
    persistence_failures = tuple(sorted(work_root.rglob("*.lock")))
    assert not post_dispatch
    assert not persistence_failures
    return {
        "retained_source_events": len(source_events),
        "physical_retained_pages": len(retained_pages),
        "observations": len(observations),
        "routed_evidence_files": len(evidence_paths),
        "complete_submission_manifests": len(manifests),
        "route_registrations": len(route_records),
        "unresolved_persistence_failures": len(persistence_failures),
        "post_dispatch_occurrences": len(post_dispatch),
        "source_scan_id": source_scan_id,
        "manifest_paths": [str(path) for path in manifest_paths],
    }


def _verify_plain_paper_absence(workspace: Path, work_root: Path) -> dict[str, object]:
    """Prove a plain-paper review invented no digital routing identity."""
    records = tuple(_load_object(path) for path in sorted(work_root.rglob("*.json")))
    forbidden_identity_fields = {
        "generation_id",
        "artifact_id",
        "issuance_id",
        "page_id",
        "route_id",
        "source_scan_id",
        "retained_source_path",
        "routed_evidence_path",
    }

    def contains_forbidden(value: object) -> bool:
        if isinstance(value, dict):
            return bool(forbidden_identity_fields.intersection(value)) or any(
                contains_forbidden(child) for child in value.values()
            )
        if isinstance(value, list):
            return any(contains_forbidden(child) for child in value)
        return False

    assert not any(contains_forbidden(record) for record in records)
    assert not tuple((work_root / "response_pages").rglob("*.json"))
    assert not tuple((work_root / "routes").glob("*.json"))
    assert not tuple((work_root / "scans" / "observations").glob("*.json"))
    assert not tuple((work_root / "scans" / "evidence").rglob("*"))
    assert not tuple(
        (work_root / "scans" / "review" / "post_dispatch").glob("*.json")
    )
    plain_relative = work_root.relative_to(workspace).as_posix()
    core_routes_for_work = [
        record
        for record in records
        if record.get("module_work_ref") == plain_relative
        or record.get("work_path") == plain_relative
    ]
    assert not core_routes_for_work
    return {
        "generation_records": 0,
        "output_artifact_records": 0,
        "issuance_records": 0,
        "response_page_records": 0,
        "core_route_registrations": 0,
        "page_observations": 0,
        "routed_evidence": 0,
        "post_dispatch_occurrences": 0,
    }


def _retained_source_inventory(workspace: Path) -> tuple[dict[str, object], ...]:
    """Inventory durable Core retained-source bytes beneath scans/source."""
    store = workspace / "scans" / "source"
    if not store.exists():
        return ()
    inventory: list[dict[str, object]] = []
    for path in sorted(store.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir() and not path.is_symlink():
            continue
        ordinary_file = path.is_file() and not path.is_symlink()
        record_identity: str | None = None
        if ordinary_file and path.suffix.casefold() == ".json":
            value = _load_object(path)
            for key in ("source_scan_id", "retained_source_id", "record_id"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    record_identity = candidate
                    break
        inventory.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "ordinary_file": ordinary_file,
                "size": path.stat().st_size if ordinary_file else None,
                "sha256": (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    if ordinary_file
                    else None
                ),
                "record_identity": record_identity,
            }
        )
    return tuple(inventory)


def _compare_retained_source_inventories(
    before: tuple[dict[str, object], ...],
    after: tuple[dict[str, object], ...],
    *,
    require_unchanged: bool = True,
) -> dict[str, object]:
    """Derive retained-source additions and optionally require exact equality."""
    before_paths = {str(item["path"]) for item in before}
    after_paths = {str(item["path"]) for item in after}
    result: dict[str, object] = {
        "retained_source_inventory_before": list(before),
        "retained_source_inventory_after": list(after),
        "retained_source_events_added": len(after_paths - before_paths),
    }
    if require_unchanged:
        assert after == before, result
    return result


def _run(command: list[str], *, cwd: Path, env: dict[str, str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, input=stdin, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{command!r} failed: {result.stdout}\n{result.stderr}")
    return result


def _cli(arguments: list[str]) -> list[str]:
    return [
        sys.executable,
        "-c",
        "from quillan.cli import main; raise SystemExit(main())",
        *arguments,
    ]


def _exercise_complete_review(
    identity: list[str], *, class_id: str, assignment_id: str, work: Path,
    env: dict[str, str], comment: str,
) -> dict[str, object]:
    """Complete one representative review through supported direct commands."""
    commands = (
        ["requirements", "set-check", *identity, "--requirement-key", "paragraphs_min", "--met", "true"],
        ["requirements", "set-outcome", *identity, "--outcome", "met"],
        ["review-units", "set", *identity, "--count", "1"],
        ["observations", "set", *identity, "--unit-id", "paragraph_1", "--standard-id", STANDARD_ID, "--applicable", "true", "--evidence-present", "true", "--rating", "2", "--rationale", "Synthetic evidence is present.", "--include-in-feedback", "true"],
        ["observations", "mark-complete", *identity, "--yes"],
        ["ratings", "set", *identity, "--standard-id", STANDARD_ID, "--rating", "2", "--rationale", "Synthetic overall rating.", "--include-in-feedback", "true"],
        ["ratings", "mark-complete", *identity, "--yes"],
        ["feedback", "set-options", *identity, "--standard-id", STANDARD_ID, "--include-overall-rating", "true", "--include-overall-rationale", "true", "--observation-ids", "observation_0001"],
        ["feedback", "add-comment", *identity, "--standard-id", STANDARD_ID, "--text", comment, "--include-in-feedback", "true"],
        ["feedback", "mark-composed", *identity, "--yes"],
        ["add-note", *identity, "--text", "Synthetic private teacher note."],
        ["review-workflow", "set-state", *identity, "--state", "ready_for_export", "--yes"],
    )
    for command in commands:
        _run(_cli(command), cwd=work, env=env)
    workspace = Path(env["PDS_WORKSPACE_ROOT"])
    review_path = (
        workspace / "classes" / class_id / "modules" / "quillan" / "work"
        / assignment_id / "submissions" / identity[-1] / "review.json"
    )
    ready = _load_object(review_path)
    assert ready["review_state"] == "ready_for_export"
    assert ready["minimum_requirement_outcome"]["status"] == "met"
    assert len(ready["review_units"]) == 1
    assert len(ready["review_units"][0]["standard_observations"]) == 1
    assert len(ready["overall_standard_ratings"]) == 1
    assert ready["feedback"]["standard_feedback"][0]["comments"][0]["text"] == comment
    assert len(ready["private_notes"]) == 1

    _run(_cli(["export-feedback", *identity, "--format", "both"]), cwd=work, env=env)
    for export_command in (
        "export-student-performance-summary",
        "export-class-summary",
        "export-standards-summary",
    ):
        _run(_cli([export_command, class_id, assignment_id]), cwd=work, env=env)
    final = _load_object(review_path)
    assert final["review_state"] == "exported"
    for export in ("feedback_markdown", "feedback_pdf"):
        assert (workspace / final["exports"][export]["path"]).is_file()
    dashboard = json.loads(
        _run(
            _cli(["review-dashboard", class_id, assignment_id, "--format", "json"]),
            cwd=work,
            env=env,
        ).stdout
    )
    status = json.loads(
        _run(_cli(["review-status", *identity, "--format", "json"]), cwd=work, env=env).stdout
    )
    assert dashboard["schema_version"] == "2"
    assert status["schema_version"] == "1"
    return {
        "review_path": str(review_path),
        "workflow_state": final["review_state"],
        "minimum_requirement": final["minimum_requirement_outcome"]["status"],
        "review_units": len(final["review_units"]),
        "focus_standard_observations": len(final["review_units"][0]["standard_observations"]),
        "overall_ratings": len(final["overall_standard_ratings"]),
        "feedback_comments": len(final["feedback"]["standard_feedback"][0]["comments"]),
        "private_notes": len(final["private_notes"]),
        "dashboard_schema": dashboard["schema_version"],
        "student_status_schema": status["schema_version"],
    }


def _run_full_workflow(workspace: Path, *, work: Path, env: dict[str, str]) -> dict[str, object]:
    from pds_core.classes import write_class_roster
    from pds_core.rosters import create_roster
    from pds_core.standards import StandardDefinition, StandardsLibrary, StandardsProfile, write_workspace_standards_library
    from quillan.assignment_workflows import build_assignment_config, write_assignment_config
    from quillan.printable_response_packet import generate_printable_response_packet, plan_printable_response_packet

    env["PDS_WORKSPACE_ROOT"] = str(workspace)
    students = (
        {"student_id": "00107", "last_name": "Example", "first_name": "Avery", "period": "3"},
        {"student_id": "00208", "last_name": "Sample", "first_name": "Morgan", "period": "3"},
    )
    write_class_roster(workspace, create_roster(CLASS_ID, students))
    write_workspace_standards_library(
        workspace,
        StandardsLibrary(
            standards=(StandardDefinition(standard_id=STANDARD_ID, code="W.RELEASE.1", source="SYNTHETIC", short_name="Release Writing", description="Use synthetic evidence clearly.", subject="English Language Arts", course="Synthetic", domain="Writing", available_modules=("quillan",)),),
            profiles=(StandardsProfile(profile_id="synthetic_release_profile", standards=(STANDARD_ID,), subject="English Language Arts", course="Synthetic", source="SYNTHETIC", title="Synthetic Release Profile"),),
        ),
    )
    assignment = build_assignment_config(
        assignment_id=ASSIGNMENT_ID,
        title="Synthetic Installed Release Response",
        class_id=CLASS_ID,
        writing_type="argument",
        student_prompt="Write a harmless synthetic response.",
        standards_profile_id="synthetic_release_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={"type": "paragraph", "singular_label": "paragraph", "plural_label": "paragraphs"},
        rating_scale={"scale_id": "synthetic_two_level", "levels": [{"value": 1, "label": "Developing", "description": "Developing."}, {"value": 2, "label": "Meeting", "description": "Meeting."}]},
        basic_requirements={"paragraphs_min": 1},
        minimum_requirement_policy={"allow_return_without_full_review": True},
    )
    write_assignment_config(workspace, CLASS_ID, assignment)
    packet = generate_printable_response_packet(plan_printable_response_packet(workspace, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2))
    assert packet.success and packet.installed
    assert len(packet.issuance_ids) == 2
    assert len(packet.page_ids) == len(packet.route_ids) == 4
    route = _run(_cli(["route-scan", str(packet.output_path)]), cwd=work, env=env)
    assert "Dispatch successes by module: quillan=4" in route.stdout, route.stdout

    identity = [CLASS_ID, ASSIGNMENT_ID, "00107"]
    digital_root = (
        workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work"
        / ASSIGNMENT_ID
    )
    durable = _verify_digital_durable_state(
        workspace, digital_root, expected_students=("00107", "00208")
    )

    manifest_path = digital_root / "submissions" / "00107" / "submission.json"
    before_page = _load_object(manifest_path)["pages"][0]
    _run(_cli(["pages", "exclude", *identity, "--page", "1", "--yes"]), cwd=work, env=env)
    assert _load_object(manifest_path)["pages"][0]["page_state"] == "excluded"
    _run(_cli(["pages", "restore", *identity, "--page", "1", "--yes"]), cwd=work, env=env)
    assert _load_object(manifest_path)["pages"][0] == before_page

    import quillan.evidence_opening as evidence_opening
    from quillan.submission_review_opening import open_student_submission_for_review

    opened_paths: list[Path] = []
    original_open = getattr(evidence_opening, "open_local_path")

    def capture_open(path: str | Path) -> Path:
        resolved = Path(path).resolve()
        opened_paths.append(resolved)
        return resolved

    setattr(evidence_opening, "open_local_path", capture_open)
    try:
        opened = open_student_submission_for_review(
            workspace, CLASS_ID, ASSIGNMENT_ID, "00107", page_number=1
        )
    finally:
        setattr(evidence_opening, "open_local_path", original_open)
    assert opened.manifest_path == manifest_path
    selected_relative = before_page["evidence"][0]["routed_evidence_path"]
    assert opened_paths == [(workspace / selected_relative).resolve()]
    assert opened.opened_pages[0].evidence_relative_path == selected_relative

    digital_review = _exercise_complete_review(
        identity,
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        work=work,
        env=env,
        comment="Synthetic teacher feedback.",
    )

    retained_before_plain = _retained_source_inventory(workspace)
    plain_class = "synthetic_plain_class"
    plain_assignment = "synthetic_plain_assignment"
    write_class_roster(workspace, create_roster(plain_class, ({"student_id": "00309", "last_name": "Paper", "first_name": "Taylor", "period": "4"},)))
    plain = dict(assignment)
    plain.update({"assignment_id": plain_assignment, "class_ids": [plain_class], "title": "Synthetic Plain Paper Response"})
    write_assignment_config(workspace, plain_class, plain)
    _run(_cli(["create-plain-paper-submission", plain_class, plain_assignment, "00309", "--yes"]), cwd=work, env=env)
    plain_identity = [plain_class, plain_assignment, "00309"]
    plain_review = _exercise_complete_review(
        plain_identity,
        class_id=plain_class,
        assignment_id=plain_assignment,
        work=work,
        env=env,
        comment="Synthetic plain-paper teacher feedback.",
    )
    plain_root = (
        workspace / "classes" / plain_class / "modules" / "quillan" / "work"
        / plain_assignment
    )
    plain_absence = _verify_plain_paper_absence(workspace, plain_root)
    retained_after_plain = _retained_source_inventory(workspace)
    plain_absence.update(
        _compare_retained_source_inventories(
            retained_before_plain,
            retained_after_plain,
        )
    )

    qualified = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID
    assert qualified.is_dir()
    assert not (workspace / "classes" / CLASS_ID / "assignments").exists()
    return {
        "packet": str(packet.output_path),
        "generated_identity": {
            "issuances": len(packet.issuance_ids),
            "pages": len(packet.page_ids),
            "routes": len(packet.route_ids),
        },
        "digital_durable_state": durable,
        "identity_authoritative_opening": {
            "manifest": str(opened.manifest_path),
            "opened_paths": [str(path) for path in opened_paths],
        },
        "page_management": {"action": "exclude_restore", "restored": True},
        "digital_review": digital_review,
        "plain_paper_review": plain_review,
        "plain_paper_digital_absence": plain_absence,
        "module_qualified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--full-workflow", action="store_true")
    args = parser.parse_args()
    work = args.work.resolve()
    repository = args.repository.resolve()
    work.mkdir(parents=True, exist_ok=False)
    sentinel = work / "workspace-must-not-exist"
    env = os.environ.copy()
    env["PDS_WORKSPACE_ROOT"] = str(sentinel)
    env.pop("PYTHONPATH", None)

    distribution = metadata.distribution("quillan")
    assert distribution.version == EXPECTED_VERSION
    root = Path(str(distribution.locate_file(""))).resolve()
    import quillan
    import quillan.pds_module

    origins = [Path(quillan.__file__).resolve(), Path(quillan.pds_module.__file__).resolve()]
    assert all(not path.is_relative_to(repository) for path in origins), origins
    profiles = [entry for entry in distribution.entry_points if entry.group == "paper_data_suite.modules"]
    assert [(entry.name, entry.value) for entry in profiles] == [("quillan", "quillan.pds_module:get_module_profile")]
    profile = profiles[0].load()()
    assert profile.module_id == "quillan"

    modules = sorted(module.name for module in pkgutil.walk_packages(quillan.__path__, "quillan."))
    for module in modules:
        result = _run([sys.executable, "-c", f"import {module}"], cwd=work, env=env)
        assert result.stdout == "" and result.stderr == "", module
        assert not sentinel.exists(), module

    version = _run(_cli(["--version"]), cwd=work, env=env)
    assert version.stdout == "quillan 0.8.9\n" and version.stderr == ""
    for arguments in (["--help"], ["printable-responses", "--help"], ["workspace", "--help"]):
        result = _run(_cli(arguments), cwd=work, env=env)
        assert result.stdout and result.stderr == ""
    for arguments in ([], ["menu"]):
        result = _run(_cli(arguments), cwd=work, env=env, stdin="q\n")
        assert "Quit" in result.stdout and result.stderr == ""
    assert not sentinel.exists()
    workflow = _run_full_workflow(work / "workflow-workspace", work=work, env=env) if args.full_workflow else None
    print(json.dumps({"version": distribution.version, "distribution_root": str(root), "origins": [str(path) for path in origins], "module_count": len(modules), "module_profile": profile.module_id, "workspace_side_effects": False, "workflow": workflow}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
