"""Direct immutable Academic Result Manifest command handlers."""

from __future__ import annotations

import argparse
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_result_manifest_generation import (
    QuillanManifestGenerationError,
    QuillanManifestGenerationPartialSuccessError,
    StoredAcademicResultManifest,
    generate_academic_result_manifest,
    list_academic_result_manifest_revisions,
    load_academic_result_manifest_revision,
    validate_academic_result_manifest_revision,
)
from quillan.work_paths import quillan_work_ref


def _generated_at_text(stored: StoredAcademicResultManifest) -> str:
    return stored.manifest.generated_at.isoformat()


def _print_revision_summary(stored: StoredAcademicResultManifest) -> None:
    print(f"revision: {stored.revision}")
    print(f"generated_at: {_generated_at_text(stored)}")
    print(f"manifest path: {stored.relative_path}")
    print(f"manifest sha256: {stored.sha256}")
    print(f"represented student count: {len(stored.manifest.students)}")


def _print_revision_detail(stored: StoredAcademicResultManifest) -> None:
    manifest = stored.manifest
    print(f"module_id: {manifest.work.module_id}")
    print(f"class_id: {manifest.work.class_id}")
    print(f"assignment_id: {manifest.work.work_id}")
    print(f"record_set_id: {manifest.record_set.record_set_id}")
    print(f"revision: {stored.revision}")
    print(f"manifest contract: {manifest.contract_version}")
    print(f"generated_at: {_generated_at_text(stored)}")
    print(f"assignment source path: {manifest.source_snapshot.relative_path}")
    print(f"assignment source sha256: {manifest.source_snapshot.sha256}")
    print(f"represented student count: {len(manifest.students)}")
    print(f"manifest path: {stored.relative_path}")
    print(f"manifest sha256: {stored.sha256}")


def _error(action: str, error: Exception) -> int:
    print(f"Error: manifest {action}: {error}", file=sys.stderr)
    if isinstance(error, QuillanManifestGenerationPartialSuccessError):
        state = error.state
        print(
            "Warning: an immutable manifest revision may already be durable; "
            "validate producer storage before retrying.",
            file=sys.stderr,
        )
        print(f"operation: {state.operation}", file=sys.stderr)
        print(f"revision: {state.revision}", file=sys.stderr)
        print(f"manifest path: {state.relative_path}", file=sys.stderr)
        if state.expected_sha256 is not None:
            print(f"expected sha256: {state.expected_sha256}", file=sys.stderr)
        print(
            "durable file exists: "
            f"{'yes' if state.durable_file_exists else 'no'}",
            file=sys.stderr,
        )
        if state.lock_cleanup_failure is not None:
            print(
                "generation lock cleanup failed: "
                f"{state.lock_cleanup_failure.relative_path}",
                file=sys.stderr,
            )
    return 1


def handle_manifest_list(args: argparse.Namespace) -> int:
    """List privacy-minimized metadata for all immutable revisions."""
    try:
        root = resolve_workspace_root()
        work = quillan_work_ref(args.class_id, args.assignment_id)
        revisions = list_academic_result_manifest_revisions(root, work)
        if not revisions:
            print("manifest revisions: none")
            return 0
        print(f"manifest revisions: {len(revisions)}")
        for index, stored in enumerate(revisions):
            if index:
                print()
            _print_revision_summary(stored)
        return 0
    except (QuillanManifestGenerationError, WorkspaceRootError, ValueError) as error:
        return _error("list failed", error)


def handle_manifest_show(args: argparse.Namespace) -> int:
    """Show privacy-minimized producer metadata for one immutable revision."""
    try:
        root = resolve_workspace_root()
        work = quillan_work_ref(args.class_id, args.assignment_id)
        stored = load_academic_result_manifest_revision(root, work, args.revision)
        _print_revision_detail(stored)
        return 0
    except (QuillanManifestGenerationError, WorkspaceRootError, ValueError) as error:
        return _error("show failed", error)


def handle_manifest_validate(args: argparse.Namespace) -> int:
    """Strictly validate one immutable producer revision."""
    try:
        root = resolve_workspace_root()
        work = quillan_work_ref(args.class_id, args.assignment_id)
        stored = validate_academic_result_manifest_revision(
            root, work, args.revision
        )
        print("valid: yes")
        _print_revision_summary(stored)
        return 0
    except (QuillanManifestGenerationError, WorkspaceRootError, ValueError) as error:
        return _error("validation failed", error)


def handle_manifest_generate(args: argparse.Namespace) -> int:
    """Generate a new immutable revision or byte-exactly replay the producer head."""
    try:
        result = generate_academic_result_manifest(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
        )
        print(f"disposition: {result.disposition}")
        print(f"reason: {result.reason}")
        print(f"revision: {result.revision}")
        print(f"manifest path: {result.relative_path}")
        print(f"manifest sha256: {result.sha256}")
        print(f"represented student count: {len(result.manifest.students)}")
        return 0
    except (QuillanManifestGenerationError, WorkspaceRootError, ValueError) as error:
        return _error("generation failed", error)
