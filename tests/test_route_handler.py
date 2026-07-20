"""Direct one-page Quillan route-handler tests."""

from dataclasses import replace
import copy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from pds_core.routing_models import (
    ModuleWorkRef,
    RouteLocator,
    RouteRegistration,
    RouteResolution,
)
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan
from pds_core.scan_routes import build_retained_source_filename
from pds_core.route_registrations import write_route_registration
import pytest

from quillan.module_errors import (
    QuillanDispatchResultError,
    QuillanIssuanceAuthorizationError,
    QuillanRouteContextError,
    QuillanTargetIntegrityError,
)
import quillan.route_handler as route_handler
from quillan.printable_response_persistence import canonical_printable_response_json
from quillan.printable_response_records import (
    PrintableResponseRecordSet,
    transition_printable_response_lifecycle,
)
from quillan.printable_response_routes import build_printable_response_page_route
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.retained_source import validate_quillan_retained_source
from quillan.route_handler import handle_quillan_response_page_route
from quillan.work_paths import quillan_work_paths
from tests.test_printable_response_records import record_set


def route_context(
    root: Path, *, status: str = "issued", pages: int = 1
) -> tuple[RouteResolution, RetainedSourceScan]:
    records = record_set(pages=pages)
    if status != "prepared":
        terminal_reason = "synthetic lifecycle test"
        if status == "cancelled":
            lifecycle = transition_printable_response_lifecycle(
                records.issuance.lifecycle,
                new_status="cancelled",
                timestamp="2026-07-20T00:00:00+00:00",
                reason=terminal_reason,
            )
        else:
            lifecycle = transition_printable_response_lifecycle(
                records.issuance.lifecycle,
                new_status="issued",
                timestamp="2026-07-20T00:00:00+00:00",
            )
            if status in {"superseded", "invalidated"}:
                lifecycle = transition_printable_response_lifecycle(
                    lifecycle,
                    new_status=status,
                    timestamp="2026-07-20T01:00:00+00:00",
                    reason=terminal_reason,
                    replacement_issuance_id=(
                        "iss_ffffffffffffffffffffffffffffffff"
                        if status == "superseded"
                        else None
                    ),
                )
        records = PrintableResponseRecordSet(
            replace(records.issuance, lifecycle=lifecycle), records.pages
        )
    paths = quillan_work_paths(root, records.issuance.class_id, records.issuance.assignment_id)
    paths.response_page_records_dir.mkdir(parents=True)
    paths.response_page_issuances_dir.mkdir(parents=True)
    for page in records.pages:
        paths.response_page_records_dir.joinpath(f"{page.page_id}.json").write_bytes(
            canonical_printable_response_json(page.to_mapping())
        )
    paths.response_page_issuances_dir.joinpath(
        f"{records.issuance.issuance_id}.json"
    ).write_bytes(canonical_printable_response_json(records.issuance.to_mapping()))
    route = build_printable_response_page_route(
        records.pages[0], "rt_0123456789abcdef0123456789abcdef"
    )
    resolution = RouteResolution(
        locator=route.locator,
        registration=route.registration,
        class_root=paths.work_root.parents[3],
        module_root=paths.work_root.parents[1],
        work_root=paths.work_root,
    )
    timestamp = datetime(2026, 7, 20, tzinfo=timezone.utc)
    retained_filename = build_retained_source_filename(
        intake_timestamp=timestamp,
        original_filename="original.pdf",
        sha256_hex="a" * 64,
    )
    retained = root / "scans" / "source" / "2026-07-20" / retained_filename
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"synthetic")
    source = RetainedSourceScan(
        source_scan_id=f"scan_{retained.stem}",
        source_filename="original.pdf",
        source_sha256="a" * 64,
        retained_source_path=retained,
        retained_source_relative_path=retained.relative_to(root).as_posix(),
        intake_timestamp=timestamp,
        intake_date=date(2026, 7, 20),
    )
    return resolution, source


def test_direct_handler_returns_authoritative_identity_without_writes(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = handle_quillan_response_page_route(resolution, source, 1)
    assert result.route_id == resolution.locator.route_id
    assert result.page_id == resolution.registration.target.record_id
    assert result.student_id == "00107"
    assert not result.is_continuation
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_direct_handler_requires_issued_lifecycle(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path, status="prepared")
    with pytest.raises(QuillanIssuanceAuthorizationError):
        handle_quillan_response_page_route(resolution, source, 1)


def test_direct_handler_rejects_wrong_call_types() -> None:
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(object(), object(), True)  # type: ignore[arg-type]


def test_handler_rejects_validator_result_that_contradicts_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)

    def substitute(
        result: QuillanResponsePageDispatchResult,
    ) -> QuillanResponsePageDispatchResult:
        return replace(result, student_id="other_student")

    monkeypatch.setattr(
        route_handler,
        "validate_quillan_response_page_dispatch_result",
        substitute,
    )
    with pytest.raises(QuillanDispatchResultError):
        handle_quillan_response_page_route(resolution, source, 1)


def test_unexpected_loader_runtime_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)

    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("programming failure")

    monkeypatch.setattr(route_handler, "load_printable_response_page_context", fail)
    with pytest.raises(RuntimeError, match="programming failure"):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize(
    "status",
    ["issued", "prepared", "cancelled", "superseded", "invalidated"],
)
def test_complete_lifecycle_matrix_is_nonmutating(
    tmp_path: Path, status: str
) -> None:
    resolution, source = route_context(tmp_path, status=status)
    route_path = write_route_registration(tmp_path, resolution.registration)
    tracked = tuple(path for path in tmp_path.rglob("*") if path.is_file())
    before = {path: path.read_bytes() for path in tracked}
    if status == "issued":
        result = handle_quillan_response_page_route(resolution, source, 1)
        assert result.page_id == resolution.registration.target.record_id
    else:
        with pytest.raises(QuillanIssuanceAuthorizationError):
            handle_quillan_response_page_route(resolution, source, 1)
    assert route_path.read_bytes() == before[route_path]
    assert {path: path.read_bytes() for path in tracked} == before


def test_fabricated_and_noncanonical_resolution_roots_are_rejected(
    tmp_path: Path,
) -> None:
    resolution, source = route_context(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    fabricated = (
        replace(resolution, class_root=tmp_path / "classes" / "other"),
        replace(resolution, module_root=tmp_path / "classes" / "other" / "modules" / "quillan"),
        replace(resolution, work_root=resolution.work_root.with_name("other")),
        replace(resolution, work_root=outside),
        replace(
            resolution,
            class_root=Path("classes") / resolution.locator.class_id,
            module_root=Path("classes") / resolution.locator.class_id / "modules" / "quillan",
            work_root=Path("classes") / resolution.locator.class_id / "modules" / "quillan" / "work" / resolution.locator.work_id,
        ),
    )
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("external", encoding="utf-8")
    for invalid in fabricated:
        with pytest.raises(QuillanRouteContextError):
            handle_quillan_response_page_route(invalid, source, 1)
    assert sentinel.read_text(encoding="utf-8") == "external"


def test_missing_and_file_roots_are_rejected(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    missing = resolution.work_root / "missing"
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(
            replace(resolution, work_root=missing), source, 1
        )
    for root_field in ("class_root", "module_root", "work_root"):
        invalid_root = tmp_path / f"{root_field}.file"
        invalid_root.write_text("sentinel", encoding="utf-8")
        invalid = copy.copy(resolution)
        object.__setattr__(invalid, root_field, invalid_root)
        with pytest.raises(QuillanRouteContextError):
            handle_quillan_response_page_route(invalid, source, 1)


def test_missing_and_malformed_target_records_have_preserved_causes(
    tmp_path: Path,
) -> None:
    resolution, source = route_context(tmp_path)
    paths = quillan_work_paths(
        tmp_path, resolution.locator.class_id, resolution.locator.work_id
    )
    page_path = paths.response_page_records_dir / (
        resolution.registration.target.record_id + ".json"
    )
    original = page_path.read_bytes()
    page_path.unlink()
    with pytest.raises(QuillanTargetIntegrityError) as missing:
        handle_quillan_response_page_route(resolution, source, 1)
    assert missing.value.__cause__ is not None
    page_path.write_bytes(b"{malformed")
    with pytest.raises(QuillanTargetIntegrityError) as malformed:
        handle_quillan_response_page_route(resolution, source, 1)
    assert malformed.value.__cause__ is not None
    page_path.write_bytes(original)


def test_current_assignment_and_roster_are_never_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)
    class_root = resolution.class_root
    (class_root / "roster.csv").write_text(
        "class_id,student_id,last_name,first_name,period\n"
        "other,other,Wrong,Student,9\n",
        encoding="utf-8",
    )
    assignment_path = resolution.work_root / "assignment.json"
    assignment_path.write_text(json.dumps({"contradictory": True}), encoding="utf-8")

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mutable current-data loader was called")

    for module_name, names in (
        ("quillan.assignments", ("load_assignment_config",)),
        ("pds_core.rosters", ("load_class_roster",)),
        ("quillan.assignment_discovery", ("discover_assignments",)),
    ):
        module = __import__(module_name, fromlist=["unused"])
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)
    result = handle_quillan_response_page_route(resolution, source, 1)
    assert result.student_id == "00107"


@pytest.mark.parametrize("root_field", ["class_root", "module_root", "work_root"])
def test_each_link_like_resolution_root_branch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_field: str,
) -> None:
    resolution, source = route_context(tmp_path)
    rejected = getattr(resolution, root_field)
    original = route_handler._is_link_like
    monkeypatch.setattr(
        route_handler,
        "_is_link_like",
        lambda path: path == rejected or original(path),
    )
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize("root_field", ["class_root", "module_root", "work_root"])
def test_real_symlinked_resolution_roots_are_rejected(
    tmp_path: Path, root_field: str
) -> None:
    resolution, source = route_context(tmp_path)
    link = getattr(resolution, root_field)
    target = tmp_path / f"symlink-target-{root_field}"
    shutil.move(str(link), str(target))
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink creation unavailable: {error}")
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize("root_field", ["class_root", "module_root", "work_root"])
def test_real_junctioned_resolution_roots_are_rejected(
    tmp_path: Path, root_field: str
) -> None:
    resolution, source = route_context(tmp_path)
    junction = getattr(resolution, root_field)
    target = tmp_path / f"junction-target-{root_field}"
    shutil.move(str(junction), str(target))
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("page_id", "pg_ffffffffffffffffffffffffffffffff"),
        ("class_id", "other_class"),
        ("assignment_id", "other_assignment"),
        ("issuance_id", "iss_ffffffffffffffffffffffffffffffff"),
        ("generation_id", "gen_ffffffffffffffffffffffffffffffff"),
        ("artifact_id", "art_ffffffffffffffffffffffffffffffff"),
        ("student_id", "other_student"),
        ("created_at", "2026-07-19T18:31:00+00:00"),
    ],
)
def test_page_record_identity_contradictions_are_target_failures(
    tmp_path: Path, field: str, value: str
) -> None:
    resolution, source = route_context(tmp_path)
    page_path = resolution.work_root / "response_pages" / "pages" / (
        resolution.registration.target.record_id + ".json"
    )
    mapping = json.loads(page_path.read_text(encoding="utf-8"))
    mapping[field] = value
    page_path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(QuillanTargetIntegrityError) as captured:
        handle_quillan_response_page_route(resolution, source, 1)
    assert captured.value.__cause__ is not None


@pytest.mark.parametrize("mode", ["missing", "malformed", "incomplete", "reordered", "duplicate"])
def test_issuance_record_integrity_failures_are_typed(
    tmp_path: Path, mode: str
) -> None:
    resolution, source = route_context(tmp_path, pages=2)
    issuance_id = str(resolution.registration.module_details["issuance_id"])
    issuance_path = (
        resolution.work_root / "response_pages" / "issuances" / f"{issuance_id}.json"
    )
    if mode == "missing":
        issuance_path.unlink()
    elif mode == "malformed":
        issuance_path.write_bytes(b"{malformed")
    else:
        mapping = json.loads(issuance_path.read_text(encoding="utf-8"))
        page_ids = list(mapping["page_ids"])
        if mode == "incomplete":
            mapping["page_ids"] = page_ids[:1]
        elif mode == "reordered":
            mapping["page_ids"] = list(reversed(page_ids))
        else:
            mapping["page_ids"] = [page_ids[0], page_ids[0]]
        issuance_path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(QuillanTargetIntegrityError) as captured:
        handle_quillan_response_page_route(resolution, source, 1)
    assert captured.value.__cause__ is not None


def registration_copy(
    registration: RouteRegistration,
    *,
    target: object | None = None,
    created_at: str | None = None,
    details: dict[str, object] | None = None,
    fallback: str | None = None,
    locator: RouteLocator | None = None,
) -> RouteRegistration:
    return RouteRegistration(
        registration.schema_version,
        registration.locator if locator is None else locator,
        registration.target if target is None else target,  # type: ignore[arg-type]
        registration.created_at if created_at is None else created_at,
        registration.status,
        registration.human_fallback if fallback is None else fallback,
        registration.module_details if details is None else details,  # type: ignore[arg-type]
    )


def test_route_diagnostics_cannot_override_authoritative_page(
    tmp_path: Path,
) -> None:
    resolution, source = route_context(tmp_path)
    registration = resolution.registration
    details = registration.module_details
    fallback = registration.human_fallback
    other_page = "pg_ffffffffffffffffffffffffffffffff"
    cases = (
        registration_copy(
            registration,
            target=replace(registration.target, record_id=other_page),
            fallback=fallback.replace(registration.target.record_id, other_page),
        ),
        registration_copy(
            registration, created_at="2026-07-19T18:31:00+00:00"
        ),
        registration_copy(
            registration,
            details={
                **details,
                "issuance_id": "iss_ffffffffffffffffffffffffffffffff",
            },
        ),
        registration_copy(
            registration,
            details={**details, "logical_page": 2, "total_pages": 2},
            fallback=fallback.replace("page=1/1", "page=2/2"),
        ),
        registration_copy(
            registration,
            details={**details, "total_pages": 2},
            fallback=fallback.replace("page=1/1", "page=1/2"),
        ),
        registration_copy(
            registration,
            fallback=fallback.replace("student=00107", "student=other_student"),
        ),
    )
    for invalid_registration in cases:
        invalid = replace(resolution, registration=invalid_registration)
        with pytest.raises(QuillanTargetIntegrityError):
            handle_quillan_response_page_route(invalid, source, 1)


@pytest.mark.parametrize("identity", ["class", "work"])
def test_locator_identity_tampering_is_rejected_before_target_loading(
    tmp_path: Path, identity: str
) -> None:
    resolution, source = route_context(tmp_path)
    work = ModuleWorkRef(
        "quillan",
        "other_class" if identity == "class" else resolution.locator.class_id,
        "other_work" if identity == "work" else resolution.locator.work_id,
    )
    locator = RouteLocator("PDS2", work, resolution.locator.route_id)
    registration = registration_copy(resolution.registration, locator=locator)
    invalid = RouteResolution(
        locator,
        registration,
        resolution.class_root,
        resolution.module_root,
        resolution.work_root,
    )
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(invalid, source, 1)


def test_core_explicit_intake_date_override_is_accepted_end_to_end(
    tmp_path: Path,
) -> None:
    resolution, _ = route_context(tmp_path)
    source_path = tmp_path / "override-source.pdf"
    source_path.write_bytes(b"synthetic override source")
    retained = retain_source_scan(
        tmp_path,
        source_path,
        intake_timestamp=datetime(2026, 7, 20, 23, 30, tzinfo=timezone.utc),
        intake_date=date(2026, 7, 21),
    )
    before = retained
    retained_bytes = retained.retained_source_path.read_bytes()
    assert retained.retained_source_relative_path.startswith(
        "scans/source/2026-07-21/"
    )
    provenance = validate_quillan_retained_source(
        retained, workspace_root=tmp_path, source_page_number=1
    )
    assert provenance.retained_source is retained
    result = handle_quillan_response_page_route(resolution, retained, 1)
    assert validate_quillan_response_page_dispatch_result(result) is result
    assert result.intake_timestamp.date() == date(2026, 7, 20)
    assert result.intake_date == date(2026, 7, 21)
    assert retained == before
    assert retained.retained_source_path.read_bytes() == retained_bytes


@pytest.mark.parametrize(
    "status", ["prepared", "cancelled", "superseded", "invalidated"]
)
def test_unauthorized_lifecycle_precedes_retained_source_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    resolution, source = route_context(tmp_path, status=status)
    route_path = write_route_registration(tmp_path, resolution.registration)
    tracked = tuple(path for path in tmp_path.rglob("*") if path.is_file())
    before = {path: path.read_bytes() for path in tracked}
    calls = 0

    def forbidden(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("retained-source validation must not run")

    monkeypatch.setattr(route_handler, "validate_quillan_retained_source", forbidden)
    with pytest.raises(QuillanIssuanceAuthorizationError):
        handle_quillan_response_page_route(resolution, source, 1)
    assert calls == 0
    assert route_path.read_bytes() == before[route_path]
    assert {path: path.read_bytes() for path in tracked} == before


def test_invalid_route_and_target_precede_retained_source_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)
    calls = 0

    def forbidden(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("retained-source validation must not run")

    monkeypatch.setattr(route_handler, "validate_quillan_retained_source", forbidden)
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(
            replace(resolution, work_root=tmp_path / "fabricated"), source, 1
        )
    page_path = resolution.work_root / "response_pages" / "pages" / (
        resolution.registration.target.record_id + ".json"
    )
    page_path.unlink()
    with pytest.raises(QuillanTargetIntegrityError):
        handle_quillan_response_page_route(resolution, source, 1)
    assert calls == 0


def test_issued_context_invokes_retained_validation_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)
    original = getattr(route_handler, "validate_quillan_retained_source")
    calls = 0

    def counting(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(route_handler, "validate_quillan_retained_source", counting)
    handle_quillan_response_page_route(resolution, source, 1)
    assert calls == 1


def test_unexpected_resolution_runtime_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("programming failure")

    monkeypatch.setattr(route_handler, "_validate_root_chain", fail)
    with pytest.raises(RuntimeError, match="programming failure"):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize("component", ["classes", "modules", "work"])
def test_each_intermediate_route_link_branch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    component: str,
) -> None:
    resolution, source = route_context(tmp_path)
    paths = {
        "classes": tmp_path / "classes",
        "modules": resolution.class_root / "modules",
        "work": resolution.module_root / "work",
    }
    rejected = paths[component]
    original = route_handler._is_link_like
    monkeypatch.setattr(
        route_handler,
        "_is_link_like",
        lambda path: path == rejected or original(path),
    )
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(resolution, source, 1)


@pytest.mark.parametrize("component", ["classes", "modules", "work"])
def test_real_junctioned_intermediate_route_paths_are_rejected(
    tmp_path: Path, component: str
) -> None:
    resolution, source = route_context(tmp_path)
    paths = {
        "classes": tmp_path / "classes",
        "modules": resolution.class_root / "modules",
        "work": resolution.module_root / "work",
    }
    junction = paths[component]
    target = tmp_path / f"external-{component}"
    shutil.move(str(junction), str(target))
    sentinel = target / "sentinel.txt"
    sentinel.write_text("external sentinel", encoding="utf-8")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    with pytest.raises(QuillanRouteContextError):
        handle_quillan_response_page_route(resolution, source, 1)
    assert sentinel.read_text(encoding="utf-8") == "external sentinel"
