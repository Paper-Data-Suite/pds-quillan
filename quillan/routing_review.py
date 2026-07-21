"""Compatibility import for current Core-v2 scan-review occurrence records."""

from quillan.scan_review_preservation import (
    PersistedQuillanScanFailure,
    QuillanFailurePersistenceBatch,
    QuillanFailurePersistenceError,
    RoutingReviewRecord,
    preserve_quillan_scan_failures,
)

__all__ = [
    "PersistedQuillanScanFailure", "QuillanFailurePersistenceBatch",
    "QuillanFailurePersistenceError", "RoutingReviewRecord",
    "preserve_quillan_scan_failures",
]
