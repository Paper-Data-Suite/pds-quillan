"""PDS1 payload helpers for Quillan documents."""

from __future__ import annotations

from pds_core.pds1 import PDS1_SCHEMA, build_pds1_payload
from pds_core.qr_payload import QrPayload


def build_response_payload(
    class_id: str,
    assignment_id: str,
    student_id: str,
    page: int,
) -> str:
    """Build a canonical PDS1 payload for a Quillan writing-response page."""
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("page must be a positive integer.")

    payload = QrPayload(
        schema=PDS1_SCHEMA,
        module="quillan",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        page=page,
        metadata={"doc": "response"},
    )
    return build_pds1_payload(payload)
