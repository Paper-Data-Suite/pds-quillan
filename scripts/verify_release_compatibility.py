"""Verify the Quillan v0.9.0 release compatibility boundary."""

from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path
from typing import get_args

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

import quillan.academic_result_artifacts as artifacts
import quillan.academic_result_reader as reader
from quillan._version import __version__
from quillan.pds_contract import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_MODULE_ID,
)
from quillan.pds_module import get_module_profile
from quillan.pds_publication import get_publication_producer_profile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "0.9.0"
LEGACY_VERSION = "0.8.9"
EXPECTED_CORE_SPECIFIER = SpecifierSet(">=0.6,<0.7")
EXPECTED_CAPABILITIES = frozenset({"standards_ratings"})
EXPECTED_ARTIFACT_KINDS = frozenset(
    {"student_work", "feedback_pdf", "feedback_markdown"}
)
SIBLING_DISTRIBUTIONS = frozenset(
    {"pds-meridian", "pds-vitrine", "pds-scoreform", "pds-concord", "pds-portia"}
)
SIBLING_IMPORT_ROOTS = frozenset(
    {
        "meridian",
        "pds_meridian",
        "vitrine",
        "pds_vitrine",
        "scoreform",
        "pds_scoreform",
        "concord",
        "pds_concord",
        "portia",
        "pds_portia",
    }
)
ACTIVE_VERSION_FILES = (
    Path("quillan/_version.py"),
    Path("README.md"),
    Path("SECURITY.md"),
    Path("docs/development_plan.md"),
    Path("docs/release_process.md"),
    Path("docs/release_checklist.md"),
    Path("docs/data_contracts.md"),
    Path("docs/cli_contract.md"),
    Path("docs/v0.9.0_release_compatibility.md"),
    Path("docs/releases/v0.9.0.md"),
    Path("docs/releases/v0.9.0_acceptance_matrix.md"),
    Path("docs/physical_acceptance_v0.9.0.md"),
    Path("scripts/inspect_release_artifacts.py"),
    Path("scripts/persist_release_artifacts.py"),
    Path("scripts/run_installed_acceptance.py"),
    Path("scripts/run_visual_acceptance.py"),
    Path("scripts/validate_release_candidate.ps1"),
    Path("scripts/verify_installed_producer_acceptance.py"),
)
HISTORICAL_RELEASE_FILES = (
    Path("docs/releases/v0.8.9.md"),
    Path("docs/releases/v0.8.9_acceptance_matrix.md"),
    Path("docs/physical_acceptance_v0.8.9.md"),
)
LEGACY_ALLOWED_LINES = {
    Path("docs/v0.9.0_release_compatibility.md"): (
        "v0.8.9 remains the Core 0.5 PDS2 release.",
    ),
    Path("docs/release_checklist.md"): (
        "Quillan 0.9.0 while v0.8.9 history remains unchanged.",
    ),
}


class ReleaseCompatibilityError(RuntimeError):
    """Raised when the v0.9.0 release boundary is inconsistent."""


def _read(relative: Path) -> str:
    path = PROJECT_ROOT / relative
    if not path.is_file():
        raise ReleaseCompatibilityError(f"missing required release file: {relative}")
    return path.read_text(encoding="utf-8")


def _import_root(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name.split(".", 1)[0] for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module.split(".", 1)[0],)
    return ()


def _validate_active_legacy_mentions(relative: Path, text: str) -> None:
    actual = tuple(
        line.strip() for line in text.splitlines() if LEGACY_VERSION in line
    )
    expected = LEGACY_ALLOWED_LINES.get(relative, ())
    if actual != expected:
        raise ReleaseCompatibilityError(
            f"active release surface has unexpected 0.8.9 context: {relative}"
        )


def validate_release_identity() -> None:
    project = tomllib.loads(_read(Path("pyproject.toml")))["project"]
    if project.get("name") != "quillan" or __version__ != RELEASE_VERSION:
        raise ReleaseCompatibilityError(
            "distribution/runtime version must be quillan 0.9.0"
        )
    for relative in ACTIVE_VERSION_FILES:
        text = _read(relative)
        if RELEASE_VERSION not in text:
            raise ReleaseCompatibilityError(
                f"active release surface lacks 0.9.0: {relative}"
            )
        _validate_active_legacy_mentions(relative, text)

    for relative in HISTORICAL_RELEASE_FILES:
        if LEGACY_VERSION not in _read(relative):
            raise ReleaseCompatibilityError(
                f"historical v0.8.9 release evidence lost its identity: {relative}"
            )

    changelog = _read(Path("CHANGELOG.md"))
    release_heading = "## 0.9.0 - Unreleased"
    legacy_heading = "## 0.8.9 - 2026-07-23"
    if release_heading not in changelog or legacy_heading not in changelog:
        raise ReleaseCompatibilityError(
            "changelog must preserve both v0.9.0 preparation and v0.8.9 history"
        )
    if changelog.index(release_heading) > changelog.index(legacy_heading):
        raise ReleaseCompatibilityError(
            "v0.9.0 changelog entry must precede historical v0.8.9 evidence"
        )


def validate_core_and_sibling_dependencies() -> None:
    project = tomllib.loads(_read(Path("pyproject.toml")))["project"]
    dependencies = tuple(Requirement(value) for value in project["dependencies"])
    core = tuple(
        value for value in dependencies if canonicalize_name(value.name) == "pds-core"
    )
    if len(core) != 1 or core[0].specifier != EXPECTED_CORE_SPECIFIER:
        raise ReleaseCompatibilityError(
            "Quillan must require exactly pds-core>=0.6,<0.7"
        )
    if core[0].url is not None or core[0].marker is not None or core[0].extras:
        raise ReleaseCompatibilityError(
            "Core requirement must be ordinary and unconditional"
        )
    siblings = {canonicalize_name(value) for value in SIBLING_DISTRIBUTIONS}
    if any(canonicalize_name(value.name) in siblings for value in dependencies):
        raise ReleaseCompatibilityError("Quillan has a sibling runtime dependency")


def validate_sibling_import_isolation() -> None:
    offenders: list[str] = []
    for path in sorted((PROJECT_ROOT / "quillan").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for root in _import_root(node):
                if root in SIBLING_IMPORT_ROOTS:
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)}:"
                        f"{getattr(node, 'lineno', '?')}"
                    )
    if offenders:
        raise ReleaseCompatibilityError(
            "production imports sibling modules: " + ", ".join(offenders)
        )


def validate_routing_and_producer_profiles() -> None:
    routing = get_module_profile()
    if (
        routing.module_id != "quillan"
        or routing.supported_core_routing_contract_versions != frozenset({"1"})
        or routing.supported_qr_schemas != frozenset({"PDS2"})
        or routing.supported_route_registration_schema_versions != frozenset({"1"})
        or routing.dispatchable_route_statuses != frozenset({"active"})
    ):
        raise ReleaseCompatibilityError("routing profile changed")

    profile = get_publication_producer_profile()
    if len(profile.publication_contracts) != 1:
        raise ReleaseCompatibilityError("publication producer profile changed")
    support = profile.publication_contracts[0]
    if (
        QUILLAN_MODULE_ID != "quillan"
        or profile.module_id != QUILLAN_MODULE_ID
        or profile.supported_core_publication_schema_versions != frozenset({"1"})
        or QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION != "quillan_academic_work_v1"
        or profile.supported_academic_work_contract_versions
        != frozenset({QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION})
        or support.publication_kind != "academic_result_set"
        or ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
        != "quillan_academic_result_manifest_v1"
        or support.manifest_contract_versions
        != frozenset({ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION})
        or support.supported_capabilities != EXPECTED_CAPABILITIES
        or support.source_record_contracts != ()
        or support.allows_missing_source_record is not True
    ):
        raise ReleaseCompatibilityError("publication producer profile changed")


def validate_reader_and_artifact_boundaries() -> None:
    required_reader = {
        "read_academic_result_manifest",
        "validate_academic_result_manifest",
        "lookup_academic_result_student",
        "lookup_academic_result_overall_rating",
    }
    if not required_reader.issubset(reader.__all__):
        raise ReleaseCompatibilityError("reader public surface is incomplete")
    forbidden = (
        "latest",
        "best",
        "official",
        "grade",
        "proficiency",
        "mastery",
        "portfolio",
    )
    if any(
        any(part in name.lower() for part in forbidden) for name in reader.__all__
    ):
        raise ReleaseCompatibilityError(
            "consumer policy leaked into reader public surface"
        )
    artifact_kinds = frozenset(get_args(artifacts.AcademicResultArtifactKind))
    if artifact_kinds != EXPECTED_ARTIFACT_KINDS:
        raise ReleaseCompatibilityError("artifact kinds changed")
    signature = inspect.signature(artifacts.read_authorized_academic_result_artifacts)
    if tuple(signature.parameters) != (
        "workspace_root",
        "manifest",
        "student_id",
        "artifact_kind",
        "purpose",
        "authorization_gate",
    ):
        raise ReleaseCompatibilityError(
            "artifact resolver public identity boundary changed"
        )
    source = inspect.getsource(artifacts.read_authorized_academic_result_artifacts)
    if source.index("_authorize(") > source.index("canonical_workspace_root("):
        raise ReleaseCompatibilityError(
            "artifact authorization no longer precedes workspace I/O"
        )


def validate_release_compatibility() -> None:
    validate_release_identity()
    validate_core_and_sibling_dependencies()
    validate_sibling_import_isolation()
    validate_routing_and_producer_profiles()
    validate_reader_and_artifact_boundaries()


def main() -> int:
    try:
        validate_release_compatibility()
    except (
        OSError,
        SyntaxError,
        KeyError,
        ValueError,
        ReleaseCompatibilityError,
    ) as error:
        print(f"Release compatibility audit failed: {error}")
        return 1
    print("Quillan v0.9.0 compatibility: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
