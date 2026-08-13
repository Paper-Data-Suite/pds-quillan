"""Teacher-facing immutable Academic Result Manifest workflow."""

from __future__ import annotations

from pathlib import Path

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationContext,
    QuillanManifestGenerationError,
    QuillanManifestGenerationPartialSuccessError,
    StoredAcademicResultManifest,
    generate_academic_result_manifest,
    list_academic_result_manifest_revisions,
    load_academic_result_manifest_generation_context,
    load_academic_result_manifest_revision,
    validate_academic_result_manifest_revision,
)
from quillan.academic_work_registration import (
    QuillanAcademicWorkRegistrationError,
    load_current_quillan_academic_work_registration,
)
from quillan.assignment_picker import prompt_assignment_choice
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)
from quillan.work_paths import quillan_work_ref


def _represented_count(context: AcademicResultManifestGenerationContext) -> int:
    return sum(1 for item in context.native_students if item.result is not None)


def _print_history(revisions: tuple[StoredAcademicResultManifest, ...]) -> None:
    if not revisions:
        print("Manifest revisions: none")
        return
    print(f"Manifest revisions: {len(revisions)}")
    for stored in revisions:
        print(
            f"- revision {stored.revision}; generated {stored.manifest.generated_at.isoformat()}; "
            f"students {len(stored.manifest.students)}; sha256 {stored.sha256}"
        )


def _print_revision(stored: StoredAcademicResultManifest) -> None:
    manifest = stored.manifest
    print(f"Revision: {stored.revision}")
    print(f"Generated: {manifest.generated_at.isoformat()}")
    print(f"Manifest contract: {manifest.contract_version}")
    print(f"Record set: {manifest.record_set.record_set_id}")
    print(f"Assignment source: {manifest.source_snapshot.relative_path}")
    print(f"Assignment source SHA-256: {manifest.source_snapshot.sha256}")
    print(f"Represented students: {len(manifest.students)}")
    print(f"Manifest path: {stored.relative_path}")
    print(f"Manifest SHA-256: {stored.sha256}")


def _print_error(error: Exception) -> None:
    print(f"Error: {error}")
    if isinstance(error, QuillanManifestGenerationPartialSuccessError):
        state = error.state
        print("Warning: an immutable manifest revision may already be durable.")
        print(f"Operation: {state.operation}")
        print(f"Revision: {state.revision}")
        print(f"Manifest path: {state.relative_path}")
        if state.expected_sha256 is not None:
            print(f"Expected SHA-256: {state.expected_sha256}")
        print(f"Durable file exists: {'yes' if state.durable_file_exists else 'no'}")
        if state.lock_cleanup_failure is not None:
            print(
                "Generation lock cleanup failed: "
                f"{state.lock_cleanup_failure.relative_path}"
            )
        print("Validate producer storage before retrying.")


def _prompt_revision(
    revisions: tuple[StoredAcademicResultManifest, ...],
) -> int | None:
    if not revisions:
        print("No immutable manifest revisions exist.")
        return None
    response = input("Revision number: ").strip()
    navigation = parse_navigation_choice(response)
    if response == "" or navigation is NavigationChoice.BACK:
        return None
    if response.isdecimal():
        revision = int(response)
        if any(item.revision == revision for item in revisions):
            return revision
    print("Invalid revision selection.")
    return None


def _registration_status(
    workspace_root: Path, class_id: str, assignment_id: str
) -> str:
    try:
        current = load_current_quillan_academic_work_registration(
            workspace_root, class_id, assignment_id
        )
    except QuillanAcademicWorkRegistrationError:
        return "unavailable"
    if current is None:
        return "not registered"
    return f"registered revision {current.registration_revision}"


def launch_academic_result_manifest_menu() -> int:
    """Run the explicit teacher-controlled immutable manifest workflow."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        _print_error(error)
        return 1

    try:
        while True:
            clear_screen()
            print_menu_header("Academic Result Manifests")
            choice = prompt_assignment_choice(workspace_root)
            if choice is None:
                return 0

            work = quillan_work_ref(choice.class_id, choice.assignment_id)
            try:
                context = load_academic_result_manifest_generation_context(
                    workspace_root, work
                )
                revisions = list_academic_result_manifest_revisions(
                    workspace_root, work
                )
            except QuillanManifestGenerationError as error:
                _print_error(error)
                print()
                pause_for_user()
                continue

            clear_screen()
            print_menu_header("Academic Result Manifests")
            print(f"Class: {choice.class_id}")
            print(f"Assignment: {choice.assignment_id}")
            print(f"Assignment title: {context.assignment.title}")
            print(f"Represented native results ready: {_represented_count(context)}")
            print(
                "Academic Work Registration: "
                f"{_registration_status(workspace_root, choice.class_id, choice.assignment_id)}"
            )
            print()
            _print_history(revisions)
            print()
            print("1. Generate / exact replay")
            print("2. List revisions")
            print("3. Validate revision")
            print("4. Show revision summary")
            print_navigation_options()
            action = input("Select an option: ").strip()
            navigation = parse_navigation_choice(action)
            if action == "" or navigation is NavigationChoice.BACK:
                return 0

            if action == "1":
                print()
                print("Proposed operation:")
                print(
                    "Validate the current native assignment/result state and either "
                    "byte-exactly replay the immutable producer head or create the "
                    "next revision required by Quillan's revision policy."
                )
                print("This does not publish through Core and does not create a Grade.")
                confirmation = input(
                    "Type GENERATE to continue: "
                ).strip()
                if confirmation != "GENERATE":
                    print("Canceled: no manifest revision was generated.")
                    print()
                    pause_for_user()
                    continue
                try:
                    result = generate_academic_result_manifest(
                        workspace_root,
                        choice.class_id,
                        choice.assignment_id,
                    )
                except QuillanManifestGenerationError as error:
                    _print_error(error)
                    print()
                    pause_for_user()
                    continue
                print()
                print(f"Disposition: {result.disposition}")
                print(f"Reason: {result.reason}")
                print(f"Revision: {result.revision}")
                print(f"Manifest path: {result.relative_path}")
                print(f"Manifest SHA-256: {result.sha256}")
                print(f"Represented students: {len(result.manifest.students)}")
                print()
                pause_for_user()
                continue

            if action == "2":
                print()
                _print_history(revisions)
                print()
                pause_for_user()
                continue

            if action in {"3", "4"}:
                revision = _prompt_revision(revisions)
                if revision is None:
                    print()
                    pause_for_user()
                    continue
                try:
                    if action == "3":
                        stored = validate_academic_result_manifest_revision(
                            workspace_root, work, revision
                        )
                        print()
                        print("Manifest revision is valid.")
                    else:
                        stored = load_academic_result_manifest_revision(
                            workspace_root, work, revision
                        )
                        print()
                    _print_revision(stored)
                except QuillanManifestGenerationError as error:
                    _print_error(error)
                print()
                pause_for_user()
                continue

            print(f"Invalid selection. {navigation_hint()}")
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting Academic Result Manifests.")
        return 0


__all__ = ["launch_academic_result_manifest_menu"]
