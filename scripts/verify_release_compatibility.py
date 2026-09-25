"""Verify the Quillan v0.10.3 patch-release compatibility boundary."""

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
from quillan.pds_operations import get_module_operations_profile
from quillan.pds_publication import get_publication_producer_profile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "0.10.3"
PREVIOUS_RELEASE_VERSION = "0.10.2"
PRIOR_RELEASE_VERSION = "0.10.1"
BASE_RELEASE_VERSION = "0.10.0"
EXPECTED_CORE_SPECIFIER = SpecifierSet(">=0.6.2,<0.7")
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
    Path("docs/data_contracts.md"),
    Path("docs/release_process.md"),
    Path("docs/release_checklist.md"),
    Path("docs/resubmission_inbox.md"),
    Path("docs/v0.10.3_installed_resubmission_inbox_acceptance.md"),
    Path("scripts/inspect_release_artifacts.py"),
    Path("scripts/persist_release_artifacts.py"),
    Path("scripts/run_installed_acceptance.py"),
    Path("scripts/validate_release_candidate.ps1"),
)

HISTORICAL_PREVIOUS_RELEASE_FILES = (
    Path("docs/v0.10.2_installed_selected_review_read_acceptance.md"),
)

HISTORICAL_PRIOR_RELEASE_FILES = (
    Path("docs/v0.10.1_installed_batch_feedback_acceptance.md"),
)

HISTORICAL_BASE_RELEASE_FILES = (
    Path("docs/v0.10.0_installed_class_set_acceptance.md"),
    Path("docs/physical_acceptance_v0.10.0.md"),
)

class ReleaseCompatibilityError(RuntimeError):
    """Raised when the v0.10.3 patch-release boundary is inconsistent."""


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


def validate_release_identity() -> None:
    project = tomllib.loads(_read(Path("pyproject.toml")))["project"]
    if project.get("name") != "quillan" or __version__ != RELEASE_VERSION:
        raise ReleaseCompatibilityError(
            "distribution/runtime version must be quillan 0.10.3"
        )

    for relative in ACTIVE_VERSION_FILES:
        text = _read(relative)
        if RELEASE_VERSION not in text:
            raise ReleaseCompatibilityError(
                f"active release surface lacks 0.10.3: {relative}"
            )

    for relative in HISTORICAL_PREVIOUS_RELEASE_FILES:
        text = _read(relative)
        if PREVIOUS_RELEASE_VERSION not in text:
            raise ReleaseCompatibilityError(
                f"historical v0.10.2 release evidence lost its identity: {relative}"
            )
    for relative in HISTORICAL_PRIOR_RELEASE_FILES:
        text = _read(relative)
        if PRIOR_RELEASE_VERSION not in text:
            raise ReleaseCompatibilityError(
                f"historical v0.10.1 release evidence lost its identity: {relative}"
            )
    for relative in HISTORICAL_BASE_RELEASE_FILES:
        text = _read(relative)
        if BASE_RELEASE_VERSION not in text:
            raise ReleaseCompatibilityError(
                f"historical v0.10.0 release evidence lost its identity: {relative}"
            )

    changelog = _read(Path("CHANGELOG.md"))
    candidate_heading = "## 0.10.3 - Unreleased"
    previous_heading = "## 0.10.2 - 2026-09-24"
    base_heading = "## 0.10.0 - 2026-08-26"
    if (
        candidate_heading not in changelog
        or previous_heading not in changelog
        or base_heading not in changelog
    ):
        raise ReleaseCompatibilityError(
            "changelog must preserve v0.10.3 candidate and released patch history"
        )
    if not (
        changelog.index(candidate_heading)
        < changelog.index(previous_heading)
        < changelog.index(base_heading)
    ):
        raise ReleaseCompatibilityError(
            "v0.10.3 candidate changelog entry must precede released history"
        )


def validate_core_and_sibling_dependencies() -> None:
    project = tomllib.loads(_read(Path("pyproject.toml")))["project"]
    dependencies = tuple(Requirement(value) for value in project["dependencies"])
    core = tuple(
        value for value in dependencies if canonicalize_name(value.name) == "pds-core"
    )
    if len(core) != 1 or core[0].specifier != EXPECTED_CORE_SPECIFIER:
        raise ReleaseCompatibilityError(
            "Quillan must require exactly pds-core>=0.6.2,<0.7"
        )
    if core[0].url is not None or core[0].marker is not None or core[0].extras:
        raise ReleaseCompatibilityError(
            "Core requirement must be ordinary and unconditional"
        )
    siblings = {canonicalize_name(value) for value in SIBLING_DISTRIBUTIONS}
    if any(canonicalize_name(value.name) in siblings for value in dependencies):
        raise ReleaseCompatibilityError("Quillan has a sibling runtime dependency")
    pdf = tuple(
        value for value in dependencies if canonicalize_name(value.name) == "pypdf"
    )
    if len(pdf) != 1 or pdf[0].specifier != SpecifierSet(">=5,<7"):
        raise ReleaseCompatibilityError(
            "Quillan must require exactly pypdf>=5,<7 for batch PDF assembly"
        )


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


def validate_routing_publication_and_operations_profiles() -> None:
    routing = get_module_profile()
    if (
        routing.module_id != "quillan"
        or routing.supported_core_routing_contract_versions != frozenset({"1"})
        or routing.supported_qr_schemas != frozenset({"PDS2"})
        or routing.supported_route_registration_schema_versions != frozenset({"1"})
        or routing.dispatchable_route_statuses != frozenset({"active"})
    ):
        raise ReleaseCompatibilityError("routing profile changed")

    publication = get_publication_producer_profile()
    if len(publication.publication_contracts) != 1:
        raise ReleaseCompatibilityError("publication producer profile changed")
    support = publication.publication_contracts[0]
    if (
        QUILLAN_MODULE_ID != "quillan"
        or publication.module_id != QUILLAN_MODULE_ID
        or publication.supported_core_publication_schema_versions != frozenset({"1"})
        or QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION != "quillan_academic_work_v1"
        or publication.supported_academic_work_contract_versions
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

    operations = get_module_operations_profile()
    if (
        operations.module_id != "quillan"
        or operations.supported_core_operations_contract_versions
        != frozenset({"1"})
        or operations.attention_provider is None
        or operations.readiness_provider is None
    ):
        raise ReleaseCompatibilityError("module-operations profile changed")


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
    signature = inspect.signature(
        artifacts.read_authorized_academic_result_artifacts
    )
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
    validate_routing_publication_and_operations_profiles()
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
    print("Quillan v0.10.3 compatibility: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
