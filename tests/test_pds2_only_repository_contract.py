"""Repository-level enforcement for Quillan's PDS2-only runtime."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parents[1]
CONTRACT_TEST_PATH = Path(__file__).resolve()

REMOVED_MODULES = (
    "quillan.evidence_filing",
    "quillan.routing_review",
    "quillan.storage",
    "quillan.submissions",
)
REMOVED_SYMBOLS = frozenset(
    {
        "AssignmentRoutedEvidenceDiscovery",
        "AssignmentSubmissionAssemblyResult",
        "DecodedResponsePage",
        "QrImageDecodeResult",
        "RoutePlan",
        "RoutingReviewRecord",
        "ScanIntakePageResult",
        "ScanIntakeSourceResult",
        "ScanIntakeSummary",
        "SkippedRoutedEvidenceFile",
        "build_response_payload",
        "decode_qr_payload_from_image",
        "discover_assignment_routed_evidence",
        "discover_assignment_routed_evidence_status",
        "file_routed_response_evidence",
        "load_submission_metadata",
        "parse_response_payload",
        "plan_decoded_response_route",
    }
)
PDS1_ALLOWLIST = {
    "CHANGELOG.md": "concise removal history",
    "tests/test_cli_decode_scan.py": "safe unsupported-schema output coverage",
    "tests/test_cli_contract_docs.py": "active-documentation rejection guard",
    "tests/test_pds2_scan_intake.py": "hostile unsupported-schema boundary coverage",
    "tests/test_pds2_only_repository_contract.py": "contract inventory and allowlist",
}
_UNQUALIFIED_ASSIGNMENT_TREE = re.compile(
    r"(?:^|/)classes/[^/]+/assignments/[^/]+(?:/|$)", re.IGNORECASE
)


def _python_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for parent in (ROOT / "quillan", ROOT / "tests")
            for path in parent.rglob("*.py")
        )
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def analyze_removed_contract_references(
    path: Path, source: str
) -> tuple[str, ...]:
    """Return removed imports and symbol references, excluding only this file."""
    if path.resolve() == CONTRACT_TEST_PATH:
        return ()
    tree = ast.parse(source, filename=str(path))
    relative = _display_path(path)
    failures: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in REMOVED_MODULES:
                    failures.append(f"{relative}:{node.lineno}: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module in REMOVED_MODULES:
                failures.append(f"{relative}:{node.lineno}: {node.module}")
            for alias in node.names:
                if alias.name in REMOVED_SYMBOLS:
                    failures.append(f"{relative}:{node.lineno}: {alias.name}")
        elif isinstance(node, (ast.Name, ast.Attribute)):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in REMOVED_SYMBOLS:
                failures.append(f"{relative}:{node.lineno}: {name}")
    return tuple(failures)


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return node.attr if parent is None else f"{parent}.{node.attr}"
    return None


def _render_path_part(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.replace("\\", "/")
    if isinstance(node, ast.Name):
        return f"{{{node.id}}}"
    if isinstance(node, ast.JoinedStr):
        rendered: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                rendered.append(value.value)
            else:
                rendered.append("{value}")
        return "".join(rendered).replace("\\", "/")
    return "{value}"


def _division_parts(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return (*_division_parts(node.left), *_division_parts(node.right))
    return (node,)


def _contains_unqualified_assignment_tree(parts: tuple[ast.AST, ...]) -> bool:
    rendered = "/".join(_render_path_part(part).strip("/") for part in parts)
    rendered = re.sub(r"/+", "/", rendered)
    return _UNQUALIFIED_ASSIGNMENT_TREE.search(rendered) is not None


def analyze_unqualified_assignment_paths(
    source: str, *, filename: str = "<synthetic>"
) -> tuple[str, ...]:
    """Find ordinary constructions of the removed unqualified work tree."""
    tree = ast.parse(source, filename=filename)
    findings: list[str] = []
    for node in ast.walk(tree):
        parts: tuple[ast.AST, ...] | None = None
        kind: str | None = None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts = _division_parts(node)
            kind = "path division"
        elif isinstance(node, ast.Call):
            call_name = _dotted_name(node.func)
            if call_name in {"Path", "pathlib.Path"}:
                parts = tuple(node.args)
                kind = "Path call"
            elif call_name is not None and call_name.endswith(".joinpath"):
                parts = tuple(node.args)
                kind = "joinpath call"
            elif call_name in {"os.path.join", "posixpath.join", "ntpath.join"}:
                parts = tuple(node.args)
                kind = "path join call"
        elif isinstance(node, (ast.Constant, ast.JoinedStr)):
            parts = (node,)
            kind = "path text"
        if parts is not None and _contains_unqualified_assignment_tree(parts):
            findings.append(f"{filename}:{getattr(node, 'lineno', 0)}: {kind}")
    return tuple(dict.fromkeys(findings))


def test_removed_modules_are_not_importable() -> None:
    for module_name in REMOVED_MODULES:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


def test_python_imports_and_symbols_exclude_removed_contracts() -> None:
    failures = [
        failure
        for path in _python_files()
        for failure in analyze_removed_contract_references(
            path, path.read_text(encoding="utf-8")
        )
    ]
    assert failures == []


def test_removed_symbol_analyzer_excludes_only_its_own_file(
    tmp_path: Path,
) -> None:
    source = "value = AssignmentSubmissionAssemblyResult\n"
    assert analyze_removed_contract_references(CONTRACT_TEST_PATH, source) == ()
    other = tmp_path / "test_contract_copy.py"
    assert analyze_removed_contract_references(other, source) == (
        f"{_display_path(other)}:1: AssignmentSubmissionAssemblyResult",
    )


def test_runtime_never_constructs_unqualified_assignment_tree() -> None:
    failures = [
        failure
        for path in (ROOT / "quillan").rglob("*.py")
        for failure in analyze_unqualified_assignment_paths(
            path.read_text(encoding="utf-8"), filename=path.relative_to(ROOT).as_posix()
        )
    ]
    assert failures == []


@pytest.mark.parametrize(
    ("filename", "source"),
    (
        ("C:/probe/division.py", 'target = root / "classes" / class_id / "assignments" / assignment_id'),
        ("/tmp/probe/path.py", 'target = Path(root, "classes", class_id, "assignments", assignment_id)'),
        ("C:\\probe\\joinpath.py", 'target = root.joinpath("classes", class_id, "assignments", assignment_id)'),
        ("/tmp/probe/os_join.py", 'target = os.path.join(root, "classes", class_id, "assignments", assignment_id)'),
        ("C:/probe/literal.py", 'target = "classes/<class_id>/assignments/<assignment_id>"'),
        ("/tmp/probe/fstring.py", 'target = f"classes/{class_id}/assignments/{assignment_id}"'),
        ("C:\\probe\\windows_literal.py", 'target = r"classes\\class_a\\assignments\\assignment_a"'),
    ),
)
def test_unqualified_path_analyzer_detects_supported_syntaxes(
    filename: str, source: str
) -> None:
    assert analyze_unqualified_assignment_paths(source, filename=filename)


@pytest.mark.parametrize(
    "source",
    (
        'target = root / "classes" / class_id / "modules" / "quillan" / "work" / assignment_id',
        'target = Path(root, "classes", class_id, "roster.csv")',
        'target = "classes/<class_id>/modules/quillan/work/<assignment_id>/"',
        'target = f"classes/{class_id}/modules/quillan/work/{assignment_id}/"',
    ),
)
def test_unqualified_path_analyzer_accepts_current_paths(source: str) -> None:
    assert analyze_unqualified_assignment_paths(source) == ()


def test_pds1_literal_matches_are_narrowly_allowlisted() -> None:
    roots = (
        ROOT / "quillan",
        ROOT / "tests",
        ROOT / "docs",
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
    )
    matches: list[tuple[str, int]] = []
    for root in roots:
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".md"}:
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "PDS1" in line:
                    matches.append((path.relative_to(ROOT).as_posix(), line_number))
    unexpected = [match for match in matches if match[0] not in PDS1_ALLOWLIST]
    assert unexpected == []
    assert {path for path, _line in matches} == set(PDS1_ALLOWLIST)


def test_canonical_modules_do_not_export_removed_names() -> None:
    modules = (
        importlib.import_module("quillan.assignment_submission_assembly"),
        importlib.import_module("quillan.pds2_scan_intake"),
        importlib.import_module("quillan.qr_decode"),
        importlib.import_module("quillan.scan_intake_summary"),
        importlib.import_module("quillan.work_paths"),
    )
    exposed = [
        f"{module.__name__}.{name}"
        for module in modules
        for name in REMOVED_SYMBOLS
        if hasattr(module, name) or name in getattr(module, "__all__", ())
    ]
    assert exposed == []
