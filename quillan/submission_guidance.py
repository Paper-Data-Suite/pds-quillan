"""Teacher-facing guidance for submission records that are not ready to review."""

from __future__ import annotations


def missing_submission_guidance() -> str:
    """Explain the action required when routed evidence has no submission file."""
    return (
        "This submission is not review-ready yet. The scan was routed, but "
        "Quillan has not assembled the student's submission record. Choose "
        '"Assemble submissions" for this assignment, then return to review.'
    )
