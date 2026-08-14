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
_ALLOWED_RUNTIME_REFERENCES = (
    _EXPLICIT_MANIFEST_GENERATION_REFERENCES
    | {_REPUBLICATION_LIFECYCLE_REFERENCE}
)


def test_durable_manifest_generation_has_only_explicit_runtime_references() -> None:
    references: list[str] = []
    for path in sorted(QUILLAN.rglob("*.py")):
        relative = path.relative_to(QUILLAN)
        text = path.read_text(encoding="utf-8")
        if "generate_academic_result_manifest" not in text:
            continue
        if relative not in _ALLOWED_RUNTIME_REFERENCES:
            references.append(relative.as_posix())
    assert references == []


def test_publication_lifecycle_generation_reference_is_republication_only() -> None:
    source = (QUILLAN / _REPUBLICATION_LIFECYCLE_REFERENCE).read_text(
        encoding="utf-8"
    )
    assert source.count("generate_academic_result_manifest(") == 1
    assert "republish_after_withdrawal=True" in source


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
        if relative in _ALLOWED_RUNTIME_REFERENCES:
            continue
        if needle in path.read_text(encoding="utf-8"):
            imports.append(relative.as_posix())
    assert imports == []
