"""Teacher-facing workflows for starter review materials."""

from __future__ import annotations

from pathlib import Path

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.starter_materials import (
    StarterInstallSummary,
    StarterMaterial,
    StarterMaterialError,
    StarterValidationResult,
    discover_starter_materials,
    install_starter_materials,
    summarize_install_impact,
    target_path_for_material,
    validate_all_starter_materials,
)


def launch_starter_materials_menu() -> int:
    """Launch the starter-materials submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Starter Materials")
            print(
                "Starter materials help teachers and developers test Quillan "
                "or begin with editable review-material examples."
            )
            print()
            print(
                "They include small synthetic examples and NJ ELA starter "
                "comment banks, tag banks, and rubrics."
            )
            print()
            print("1. Preview starter materials")
            print("2. Validate starter materials")
            print("3. Install all starter materials")
            print("4. Install selected starter materials")
            print("5. Back")
            print()

            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "5"}:
                return 0
            workflows = {
                "1": prompt_preview_starter_materials,
                "2": prompt_validate_starter_materials,
                "3": prompt_install_all_starter_materials,
                "4": prompt_install_selected_starter_materials,
            }
            workflow = workflows.get(choice)
            if workflow is None:
                print("Invalid selection. Please enter a number from 1 to 5.")
            else:
                clear_screen()
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting starter materials menu.")
        return 0


def prompt_preview_starter_materials() -> int:
    """Preview starter materials grouped by material type."""
    from quillan.menu import print_menu_header

    print_menu_header("Preview Starter Materials")
    materials = discover_starter_materials()
    _print_material_groups(materials, workspace_root=_workspace_root_or_cwd())
    return 0


def prompt_validate_starter_materials() -> int:
    """Validate every starter-material source file."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Starter Materials")
    materials = discover_starter_materials()
    results = validate_all_starter_materials(materials)
    _print_validation_results(results)
    return 0 if all(result.is_valid for result in results) else 1


def prompt_install_all_starter_materials() -> int:
    """Prompt for and install all valid starter materials."""
    from quillan.menu import print_menu_header

    print_menu_header("Install Starter Materials")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    materials = discover_starter_materials()
    print(
        "This will copy starter comment banks, tag banks, and rubrics into "
        "the active workspace."
    )
    print()
    _print_target_folders()
    print(
        "These files are examples and editable starting points only. They do "
        "not create assignments, rosters, scans, submissions, review records, "
        "exports, or pds-core standards."
    )
    print()
    print("1. Install")
    print("2. Back")
    print()
    if input("Select an option: ").strip() != "1":
        print("Starter material installation canceled. No files were changed.")
        return 1
    return _confirm_and_install(workspace_root, materials)


def prompt_install_selected_starter_materials() -> int:
    """Prompt for and install selected starter materials."""
    from quillan.menu import print_menu_header

    print_menu_header("Install Selected Starter Materials")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    materials = discover_starter_materials()
    for index, material in enumerate(materials, start=1):
        print(f"{index}. {material.display_name}")
    print()
    selection = input("Enter numbers, comma-separated, or B to go back: ").strip()
    if selection == "" or selection.casefold() == "b":
        print(
            "Selected starter material installation canceled. "
            "No files were changed."
        )
        return 1
    selected = _parse_selection(selection, materials)
    if selected is None:
        print("Invalid selection. Please enter listed numbers separated by commas.")
        return 1
    return _confirm_and_install(workspace_root, selected)


def _confirm_and_install(
    workspace_root: Path,
    materials: tuple[StarterMaterial, ...],
) -> int:
    validation = validate_all_starter_materials(materials)
    invalid = [result for result in validation if not result.is_valid]
    if invalid:
        _print_validation_results(validation)
        print()
        print("Installation aborted because one or more starter files are invalid.")
        return 1

    summary = summarize_install_impact(workspace_root, materials)
    _print_install_summary(summary)
    choice = input("Select an option: ").strip()
    if choice == "1":
        overwrite = False
    elif choice == "2":
        confirmation = input(
            "Type OVERWRITE to replace existing starter-material files: "
        ).strip()
        if confirmation != "OVERWRITE":
            print("Overwrite canceled. Existing files were not changed.")
            return 1
        overwrite = True
    else:
        print("Starter material installation canceled. No files were changed.")
        return 1

    try:
        result = install_starter_materials(
            workspace_root,
            materials,
            overwrite=overwrite,
        )
    except StarterMaterialError as error:
        print(f"Error: {error}")
        return 1

    print()
    print(f"Installed files: {len(result.installed)}")
    print(f"Skipped existing files: {len(result.skipped_existing)}")
    for path in result.installed:
        print(f"- {path.relative_to(workspace_root).as_posix()}")
    return 0


def _print_material_groups(
    materials: tuple[StarterMaterial, ...],
    *,
    workspace_root: Path,
) -> None:
    groups = (
        ("Comment Banks", "comment_bank"),
        ("Tag Banks", "tag_bank"),
        ("Rubrics / Scoring Profiles", "rubric"),
    )
    index = 1
    for heading, kind in groups:
        print(heading)
        for material in [item for item in materials if item.kind == kind]:
            print(f"{index}. {material.display_name}")
            print(f"   ID: {material.material_id}")
            print(
                "   Writing assignment types: "
                f"{', '.join(material.writing_types)}"
            )
            if material.kind == "rubric":
                print(f"   Criteria: {material.item_count}")
            elif material.kind == "tag_bank":
                print(
                    f"   Categories: {material.categories_count}; "
                    f"Tags: {material.item_count}"
                )
            else:
                print(
                    f"   Categories: {material.categories_count}; "
                    f"Comments: {material.item_count}"
                )
            print(f"   Source: {material.source_path}")
            print(f"   Target: {_workspace_relative_target(workspace_root, material)}")
            index += 1
        print()


def _print_validation_results(
    results: tuple[StarterValidationResult, ...],
) -> None:
    print("Starter material validation")
    print()
    groups = (
        ("Comment Banks:", "comment_bank"),
        ("Tag Banks:", "tag_bank"),
        ("Rubrics:", "rubric"),
    )
    for heading, kind in groups:
        print(heading)
        for result in results:
            if result.material.kind != kind:
                continue
            status = "OK" if result.is_valid else "INVALID"
            print(f"{status} {result.material.source_path.name}")
            if result.error:
                print(f"  Error: {result.error}")
        print()


def _print_target_folders() -> None:
    print("Target folders:")
    print("shared/comment_banks/")
    print("shared/tag_banks/")
    print("shared/rubrics/")
    print()


def _print_install_summary(summary: StarterInstallSummary) -> None:
    print("Install summary:")
    print()
    print(f"New files: {summary.new_files}")
    print(f"Existing files that would be skipped: {summary.existing_files}")
    print(f"Existing files that would require overwrite: {summary.overwrite_files}")
    print()
    print("1. Install new files only")
    print("2. Install and overwrite existing files")
    print("3. Back")
    print()


def _parse_selection(
    selection: str,
    materials: tuple[StarterMaterial, ...],
) -> tuple[StarterMaterial, ...] | None:
    selected: list[StarterMaterial] = []
    seen: set[int] = set()
    for raw_item in selection.split(","):
        item = raw_item.strip()
        if not item.isdigit():
            return None
        index = int(item)
        if not 1 <= index <= len(materials):
            return None
        if index not in seen:
            selected.append(materials[index - 1])
            seen.add(index)
    return tuple(selected) if selected else None


def _workspace_relative_target(
    workspace_root: Path,
    material: StarterMaterial,
) -> str:
    return target_path_for_material(workspace_root, material).relative_to(
        workspace_root
    ).as_posix()


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _workspace_root_or_cwd() -> Path:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError:
        return Path.cwd()
