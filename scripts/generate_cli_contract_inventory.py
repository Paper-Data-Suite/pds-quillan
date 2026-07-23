"""Regenerate the authoritative machine-readable argparse inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from quillan.cli_app.inventory import inventory_document, inventory_parser
from quillan.cli_app.parser import build_parser


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "cli_contract_inventory.json",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    document = inventory_document(inventory_parser(build_parser()))
    output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
