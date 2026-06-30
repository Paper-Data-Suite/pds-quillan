"""Discovery, validation, and safe installation of synthetic starter materials."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from quillan.comment_banks import CommentBankError, load_comment_bank
from quillan.rubrics import RubricError, load_rubric
from quillan.tag_banks import TagBankError, load_tag_bank

MaterialKind = Literal["comment_bank", "tag_bank", "rubric"]

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "examples"
_KINDS: tuple[MaterialKind, ...] = ("comment_bank", "tag_bank", "rubric")
_SOURCE_DIRS: dict[MaterialKind, str] = {
    "comment_bank": "comment_banks",
    "tag_bank": "tag_banks",
    "rubric": "rubrics",
}
_TARGET_DIRS: dict[MaterialKind, str] = {
    "comment_bank": "shared/comment_banks",
    "tag_bank": "shared/tag_banks",
    "rubric": "shared/rubrics",
}
_STARTER_FILES: dict[MaterialKind, tuple[str, ...]] = {
    "comment_bank": (
        "general_written_response.json",
        "lab_report.json",
        "research_response.json",
        "reflection_journal.json",
        "creative_writing.json",
        "ela10_argument_writing.json",
        "ela10_informational_writing.json",
        "ela10_literary_analysis.json",
        "ela10_research_writing.json",
        "ela10_narrative_creative_writing.json",
        "ela10_reflection_short_response.json",
        "ela12_argument_writing.json",
        "ela12_informational_writing.json",
        "ela12_literary_analysis.json",
        "ela12_research_writing.json",
        "ela12_narrative_creative_writing.json",
        "ela12_reflection_short_response.json",
    ),
    "tag_bank": (
        "general_written_response_tags.json",
        "lab_report_tags.json",
        "research_tags.json",
        "reflection_tags.json",
        "creative_process_tags.json",
        "ela10_argument_writing_tags.json",
        "ela10_informational_writing_tags.json",
        "ela10_literary_analysis_tags.json",
        "ela10_research_writing_tags.json",
        "ela10_narrative_creative_writing_tags.json",
        "ela10_reflection_short_response_tags.json",
        "ela12_argument_writing_tags.json",
        "ela12_informational_writing_tags.json",
        "ela12_literary_analysis_tags.json",
        "ela12_research_writing_tags.json",
        "ela12_narrative_creative_writing_tags.json",
        "ela12_reflection_short_response_tags.json",
    ),
    "rubric": (
        "general_constructed_response.json",
        "lab_report.json",
        "research_project.json",
        "reflection_journal.json",
        "creative_project_reflection.json",
        "ela10_argument_writing_rubric.json",
        "ela10_informational_writing_rubric.json",
        "ela10_literary_analysis_rubric.json",
        "ela10_research_writing_rubric.json",
        "ela10_narrative_creative_writing_rubric.json",
        "ela10_reflection_short_response_rubric.json",
        "ela12_argument_writing_rubric.json",
        "ela12_informational_writing_rubric.json",
        "ela12_literary_analysis_rubric.json",
        "ela12_research_writing_rubric.json",
        "ela12_narrative_creative_writing_rubric.json",
        "ela12_reflection_short_response_rubric.json",
    ),
}
class StarterMaterialError(ValueError):
    """Raised when starter materials cannot be discovered or installed safely."""


@dataclass(frozen=True, slots=True)
class StarterMaterial:
    """One synthetic starter-material source file."""

    kind: MaterialKind
    source_path: Path
    title: str
    material_id: str
    writing_types: tuple[str, ...]
    categories_count: int
    item_count: int

    @property
    def display_name(self) -> str:
        return self.title


@dataclass(frozen=True, slots=True)
class StarterValidationResult:
    """Validation result for one starter-material source file."""

    material: StarterMaterial
    error: str | None

    @property
    def is_valid(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class StarterInstallSummary:
    """Overwrite impact for a pending starter-material install."""

    new_files: int
    existing_files: int
    overwrite_files: int


@dataclass(frozen=True, slots=True)
class StarterInstallResult:
    """Result of copying selected starter materials into a workspace."""

    installed: tuple[Path, ...]
    skipped_existing: tuple[Path, ...]


def starter_examples_root() -> Path:
    """Return the repository/package-relative starter examples directory."""
    return _SOURCE_ROOT


def discover_starter_materials() -> tuple[StarterMaterial, ...]:
    """Discover and validate starter-material metadata from source JSON files."""
    materials: list[StarterMaterial] = []
    for kind in _KINDS:
        directory = _SOURCE_ROOT / _SOURCE_DIRS[kind]
        for file_name in _STARTER_FILES[kind]:
            source_path = directory / file_name
            if not source_path.is_file():
                raise StarterMaterialError(
                    f"Starter material source file not found: {source_path}"
                )
            data = _load_material_data(kind, source_path)
            material_id = _material_id(kind, data)
            if material_id != source_path.stem:
                raise StarterMaterialError(
                    f"{source_path} has id {material_id!r}; expected "
                    f"{source_path.stem!r} from its filename."
                )
            materials.append(
                StarterMaterial(
                    kind=kind,
                    source_path=source_path,
                    title=str(data["title"]),
                    material_id=material_id,
                    writing_types=tuple(str(item) for item in data["writing_types"]),
                    categories_count=_categories_count(kind, data),
                    item_count=_item_count(kind, data),
                )
            )
    return tuple(materials)


def target_path_for_material(
    workspace_root: str | Path,
    material: StarterMaterial,
) -> Path:
    """Return the safe shared review-material target path for one material."""
    return Path(workspace_root) / _TARGET_DIRS[material.kind] / material.source_path.name


def validate_starter_material(material: StarterMaterial) -> StarterValidationResult:
    """Validate one starter-material source file with its runtime validator."""
    try:
        _load_material_data(material.kind, material.source_path)
    except (CommentBankError, TagBankError, RubricError, OSError) as error:
        return StarterValidationResult(material, str(error))
    return StarterValidationResult(material, None)


def validate_all_starter_materials(
    materials: tuple[StarterMaterial, ...] | None = None,
) -> tuple[StarterValidationResult, ...]:
    """Validate all discovered starter materials."""
    selected = discover_starter_materials() if materials is None else materials
    return tuple(validate_starter_material(material) for material in selected)


def summarize_install_impact(
    workspace_root: str | Path,
    materials: tuple[StarterMaterial, ...],
) -> StarterInstallSummary:
    """Summarize how many selected targets are new or already exist."""
    existing = sum(1 for material in materials if _target_exists(workspace_root, material))
    new = len(materials) - existing
    return StarterInstallSummary(
        new_files=new,
        existing_files=existing,
        overwrite_files=existing,
    )


def install_starter_materials(
    workspace_root: str | Path,
    materials: tuple[StarterMaterial, ...],
    *,
    overwrite: bool = False,
) -> StarterInstallResult:
    """Validate and copy selected starter materials into a workspace.

    Only shared comment-bank, tag-bank, and rubric folders are ever created.
    Existing files are skipped unless ``overwrite`` is true.
    """
    if not materials:
        return StarterInstallResult(installed=(), skipped_existing=())
    validation = validate_all_starter_materials(materials)
    invalid = [result for result in validation if not result.is_valid]
    if invalid:
        first = invalid[0]
        raise StarterMaterialError(
            f"Starter material is invalid: {first.material.source_path}: "
            f"{first.error}"
        )

    installed: list[Path] = []
    skipped: list[Path] = []
    for material in materials:
        target_path = target_path_for_material(workspace_root, material)
        if target_path.exists() and not overwrite:
            skipped.append(target_path)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(material.source_path, target_path)
        installed.append(target_path)
    return StarterInstallResult(
        installed=tuple(installed),
        skipped_existing=tuple(skipped),
    )


def _load_material_data(kind: MaterialKind, source_path: Path) -> dict[str, Any]:
    if kind == "comment_bank":
        return load_comment_bank(source_path)
    if kind == "tag_bank":
        return load_tag_bank(source_path)
    return load_rubric(source_path)


def _material_id(kind: MaterialKind, data: dict[str, Any]) -> str:
    field = {
        "comment_bank": "bank_id",
        "tag_bank": "tag_bank_id",
        "rubric": "rubric_id",
    }[kind]
    return str(data[field])


def _categories_count(kind: MaterialKind, data: dict[str, Any]) -> int:
    if kind == "rubric":
        return 0
    return len(data["categories"])


def _item_count(kind: MaterialKind, data: dict[str, Any]) -> int:
    field = {
        "comment_bank": "comments",
        "tag_bank": "tags",
        "rubric": "criteria",
    }[kind]
    return len(data[field])


def _target_exists(workspace_root: str | Path, material: StarterMaterial) -> bool:
    return target_path_for_material(workspace_root, material).exists()
