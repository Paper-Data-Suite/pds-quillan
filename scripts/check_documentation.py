"""Validate active Markdown links, anchors, UTF-8, and common mojibake."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE = ("\ufffd", "\u00c3", "\u00e2\u20ac", "\u00c2\u00a0")
LINK = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _anchor(value: str) -> str:
    value = re.sub(r"[`*_~]", "", value.strip().lower())
    value = re.sub(r"[^\w\- ]", "", value)
    return re.sub(r"[\s-]+", "-", value).strip("-")


def documentation_failures(root: Path = ROOT) -> tuple[str, ...]:
    """Return deterministic documentation-integrity failures."""
    failures: list[str] = []
    documents = sorted((*root.glob("*.md"), *(root / "docs").rglob("*.md")))
    for document in documents:
        relative = document.relative_to(root).as_posix()
        try:
            content = document.read_text(encoding="utf-8", errors="strict")
        except UnicodeError as exc:
            failures.append(f"{relative}: invalid UTF-8: {exc}")
            continue
        for sequence in MOJIBAKE:
            if sequence in content:
                failures.append(f"{relative}: malformed text sequence {sequence!r}")
        for raw_target in LINK.findall(content):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            path_text, separator, fragment = target.partition("#")
            target_path = document if not path_text else document.parent / unquote(path_text)
            if not target_path.exists():
                failures.append(f"{relative}: missing relative link target {target}")
                continue
            if separator and target_path.suffix.lower() == ".md":
                linked = target_path.read_text(encoding="utf-8", errors="strict")
                anchors = {_anchor(match) for match in HEADING.findall(linked)}
                if unquote(fragment).lower() not in anchors:
                    failures.append(f"{relative}: missing anchor {target}")
    return tuple(failures)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    failures = documentation_failures(args.root.resolve())
    if failures:
        print("\n".join(failures))
        return 1
    print("Documentation integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
