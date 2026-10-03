"""Shared CSV encoding contract for Quillan assignment reports."""

from __future__ import annotations

from typing import Final

# Spreadsheet-facing assignment reports use a UTF-8 BOM so common Windows
# spreadsheet applications reliably detect Unicode. Readers should use the same
# BOM-aware codec so the marker never becomes part of the first logical field.
REPORT_CSV_ENCODING: Final = "utf-8-sig"
