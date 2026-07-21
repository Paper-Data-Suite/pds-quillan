"""Retain-once, parse-only PDS2 scan diagnostic."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from pds_core.pds2 import parse_pds2_payload, serialize_pds2_payload
from pds_core.routing_models import RouteLocator
from pds_core.scan_retention import retain_source_scan
from pds_core.workspace import resolve_workspace_root

from quillan.pds2_scan_intake import (
    classify_pds2_payload_error,
    validate_scan_source,
    validate_scan_workspace,
)
from quillan.qr_decode import (
    detect_qr_payload,
    validate_qr_payload_detection_result,
)
from quillan.retained_scan_pages import (
    load_retained_page_for_qr,
    retained_source_page_count,
)


@dataclass(frozen=True, slots=True)
class DecodedPds2Page:
    source_page_number: int
    raw_payload_text: str | None
    locator: RouteLocator | None
    decode_method: str | None
    failure_category: str | None = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_page_number, bool)
            or not isinstance(self.source_page_number, int)
            or self.source_page_number < 1
        ):
            raise ValueError("source_page_number must be positive.")
        if self.raw_payload_text is not None and not isinstance(
            self.raw_payload_text, str
        ):
            raise ValueError("raw payload must be text or None.")
        if self.locator is not None and not isinstance(self.locator, RouteLocator):
            raise ValueError("locator must be RouteLocator or None.")
        if self.decode_method is not None and not isinstance(self.decode_method, str):
            raise ValueError("decode method must be text or None.")
        if (self.failure_category is None) != (self.error is None):
            raise ValueError("failure category and error must occur together.")
        if self.locator is not None and (
            self.raw_payload_text is None or self.error is not None
        ):
            raise ValueError("successful locator state is contradictory.")


def decode_retained_pds2_scan(
    source_file: str | Path,
    *,
    workspace_root: Path,
) -> tuple[DecodedPds2Page, ...]:
    """Retain once and parse pages without registry construction or dispatch."""
    root = validate_scan_workspace(workspace_root)
    source = validate_scan_source(source_file)
    retained = retain_source_scan(root, source)
    page_count = retained_source_page_count(retained, workspace_root=root)
    pages: list[DecodedPds2Page] = []
    for number in range(1, page_count + 1):
        try:
            image = load_retained_page_for_qr(
                retained,
                number,
                workspace_root=root,
            )
        except Exception as error:
            pages.append(
                DecodedPds2Page(
                    number,
                    None,
                    None,
                    None,
                    "source_unreadable",
                    error,
                )
            )
            continue
        try:
            detection = detect_qr_payload(image)
        except Exception as error:
            pages.append(
                DecodedPds2Page(
                    number,
                    None,
                    None,
                    None,
                    "payload_unreadable",
                    error,
                )
            )
            continue
        try:
            detection = validate_qr_payload_detection_result(detection)
        except Exception as error:
            pages.append(
                DecodedPds2Page(
                    number,
                    None,
                    None,
                    None,
                    "payload_unreadable",
                    ValueError(f"QR detector returned an invalid result: {error}"),
                )
            )
            continue
        raw = detection.raw_payload_text
        if raw is None:
            detection_error = detection.error or ValueError(
                "No QR payload could be decoded."
            )
            pages.append(
                DecodedPds2Page(
                    number,
                    None,
                    None,
                    detection.decode_method,
                    getattr(
                        detection_error,
                        "failure_category",
                        "payload_missing",
                    ),
                    detection_error,
                )
            )
            continue
        try:
            locator = parse_pds2_payload(raw)
        except Exception as error:
            pages.append(
                DecodedPds2Page(
                    number,
                    raw,
                    None,
                    detection.decode_method,
                    classify_pds2_payload_error(raw, error),
                    error,
                )
            )
            continue
        pages.append(
            DecodedPds2Page(
                number,
                raw,
                locator,
                detection.decode_method,
            )
        )
    return tuple(pages)


def handle_decode_scan(args: argparse.Namespace) -> int:
    """Display strict PDS2 locators without resolution or dispatch."""
    print("PDS2 retained scan decode diagnostic")
    print(f"Source: {args.source_file}")
    try:
        pages = decode_retained_pds2_scan(
            args.source_file,
            workspace_root=resolve_workspace_root(),
        )
    except Exception as error:
        print(f"Decode failed: {error}")
        return 1
    success = True
    for page in pages:
        print()
        print(f"Source page: {page.source_page_number}")
        if page.locator is None:
            success = False
            print(f"Decode failed: {page.failure_category}")
            print(f"Reason: {page.error}")
            if page.raw_payload_text is not None and not args.hide_payload:
                print(f"Raw payload: {page.raw_payload_text}")
            continue
        locator = page.locator
        print("Schema: PDS2")
        print(f"Module: {locator.module_id}")
        print(f"Class: {locator.class_id}")
        print(f"Work: {locator.work_id}")
        print(f"Route: {locator.route_id}")
        if not args.hide_payload:
            print(f"Canonical payload: {serialize_pds2_payload(locator)}")
    return 0 if success and bool(pages) else 1


__all__ = [
    "DecodedPds2Page",
    "decode_retained_pds2_scan",
    "handle_decode_scan",
]
