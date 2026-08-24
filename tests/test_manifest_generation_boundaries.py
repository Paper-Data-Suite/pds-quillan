"""Source-level regression for the explicit-only manifest generation boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUILLAN = ROOT / "quillan"

_EXPLICIT_MANIFEST_GENERATION_REFERENCES = {
    Path("academic_result_manifest_generation.py"),
    Path("cli_app/handlers/manifest.py"),
    Path("manifest_menu.py"),
}
_REPUBLICATION_LIFECYCLE_REFERENCE = Path("academic_result_publication.py")
_GUIDED_SHARE_GENERATION_REFERENCE = Path("share_results_menu.py")
_READ_ONLY_SHARE_STATUS_REFERENCE = Path("share_results.py")

_ALLOWED_DURABLE_GENERATION_REFERENCES = (
    _EXPLICIT_MANIFEST_GENERATION_REFERENCES
    | {
        _REPUBLICATION_LIFECYCLE_REFERENCE,
        _GUIDED_SHARE_GENERATION_REFERENCE,
    }
)
_ALLOWED_MANIFEST_GENERATION_IMPORTS = (
    _ALLOWED_DURABLE_GENERATION_REFERENCES
    | {_READ_ONLY_SHARE_STATUS_REFERENCE}
)


def test_durable_manifest_generation_has_only_explicit_runtime_references() -> None:
    references: list[str] = []
    for path in sorted(QUILLAN.rglob("*.py")):
        relative = path.relative_to(QUILLAN)
        text = path.read_text(encoding="utf-8")
        if "generate_academic_result_manifest" not in text:
            continue
        if relative not in _ALLOWED_DURABLE_GENERATION_REFERENCES:
            references.append(relative.as_posix())
    assert references == []


def test_publication_lifecycle_generation_reference_is_republication_only() -> None:
    source = (QUILLAN / _REPUBLICATION_LIFECYCLE_REFERENCE).read_text(
        encoding="utf-8"
    )
    assert source.count("generate_academic_result_manifest(") == 1
    assert "republish_after_withdrawal=True" in source


def test_guided_share_generation_reference_is_explicit_and_bounded() -> None:
    source = (QUILLAN / _GUIDED_SHARE_GENERATION_REFERENCE).read_text(
        encoding="utf-8"
    )
    assert source.count("generate_academic_result_manifest(") == 1
    assert 'input("Type GENERATE to continue: ")' in source


def test_read_only_share_status_never_generates_a_manifest() -> None:
    source = (QUILLAN / _READ_ONLY_SHARE_STATUS_REFERENCE).read_text(
        encoding="utf-8"
    )
    assert "generate_academic_result_manifest(" not in source
    assert "load_academic_result_manifest_generation_context(" in source
    assert "build_academic_result_manifest(" in source


def test_manifest_generation_never_uses_mutable_revision_update_primitive() -> None:
    source = (QUILLAN / "academic_result_manifest_generation.py").read_text(
        encoding="utf-8"
    )
    assert "revision_guarded_update" not in source
    assert "create_exclusive_record" in source


def test_ordinary_runtime_modules_do_not_import_manifest_generation() -> None:
    imports: list[str] = []
    needle = "quillan.academic_result_manifest_generation"
    for path in sorted(QUILLAN.rglob("*.py")):
        relative = path.relative_to(QUILLAN)
        if relative in _ALLOWED_MANIFEST_GENERATION_IMPORTS:
            continue
        if needle in path.read_text(encoding="utf-8"):
            imports.append(relative.as_posix())
    assert imports == []
