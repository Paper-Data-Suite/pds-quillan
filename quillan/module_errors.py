"""Typed failures exposed by Quillan's installed-module boundary."""

from pathlib import Path


class QuillanModuleError(Exception):
    """Base failure raised through Quillan's installed module boundary."""


class QuillanRegistrationValidationError(QuillanModuleError, ValueError):
    """A Core registration violates Quillan's structural route contract."""


class QuillanRouteContextError(QuillanModuleError):
    """A direct handler call or resolved Core path context is invalid."""


class QuillanTargetIntegrityError(QuillanModuleError):
    """The route registration and immutable Quillan records disagree."""


class QuillanIssuanceAuthorizationError(QuillanModuleError):
    """The immutable issuance is not currently authorized for handling."""


class QuillanRetainedSourceError(QuillanModuleError):
    """Retained-source provenance or source-page meaning is invalid."""


class QuillanDispatchResultError(QuillanModuleError, ValueError):
    """A response-page dispatch result violates its runtime contract."""


class QuillanScanIntakeError(Exception):
    """Base failure for retained PDS2 scan intake."""


class QuillanScanPreflightError(QuillanScanIntakeError, ValueError):
    """A workspace or selected source fails preflight."""


class QuillanScanRegistryError(QuillanScanIntakeError):
    """The application-owned installed module registry is unusable."""


class QuillanSourceMissingError(QuillanScanPreflightError):
    """A selected source is missing."""


class QuillanSourceTypeUnsupportedError(QuillanScanPreflightError):
    """A selected source has an unsupported or unsafe filesystem type."""


class QuillanSourcePageError(QuillanScanIntakeError):
    """A retained physical page cannot be enumerated or loaded."""


class QuillanPdfDependencyError(QuillanSourcePageError):
    """PDF support or Poppler is unavailable."""


class QuillanPdfPageCountError(QuillanSourcePageError):
    """A retained PDF page count cannot be established."""


class QuillanPdfPageConversionError(QuillanSourcePageError):
    """One requested retained PDF page cannot be converted."""


class QuillanPageImageError(QuillanSourcePageError):
    """A retained or converted page is not valid BGR image data."""


class QuillanQrDetectionError(QuillanScanIntakeError):
    """A retained page has no readable QR payload."""

    def __init__(
        self,
        message: str,
        *,
        failure_category: str = "payload_unreadable",
    ) -> None:
        super().__init__(message)
        self.failure_category = failure_category


class QuillanPayloadParsingError(QuillanScanIntakeError):
    """Core rejected the exact decoded payload text."""


class QuillanRequestConstructionError(QuillanScanIntakeError):
    """A parsed locator could not become a Core dispatch request."""


class QuillanDispatchIntegrationError(QuillanScanIntakeError):
    """Core dispatch output or a Quillan-owned success is contradictory."""


class QuillanScanReviewPersistenceError(QuillanScanIntakeError):
    """An actionable post-retention failure could not be preserved."""


class QuillanObservationError(Exception):
    """Base failure for immutable response-page observations."""


class QuillanObservationValidationError(QuillanObservationError, ValueError):
    """An observation or its serialized representation is invalid."""


class QuillanObservationAuthorityError(QuillanObservationError):
    """A page outcome is not authoritative for observation creation."""


class QuillanRoutedEvidenceError(QuillanObservationError):
    """Routed page evidence could not be safely materialized."""


class QuillanRoutedEvidenceMissingError(QuillanRoutedEvidenceError):
    """The canonical routed evidence file is missing."""


class QuillanRoutedEvidenceIntegrityError(QuillanRoutedEvidenceError):
    """Routed evidence exists but contradicts immutable metadata."""


class QuillanRoutedEvidencePathError(QuillanRoutedEvidenceError):
    """A routed-evidence path or one of its ancestors is unsafe."""


class QuillanObservationPersistenceError(QuillanObservationError):
    """An observation/evidence transaction could not be completed."""

    possible_observation_path: Path | None
    possible_evidence_path: Path | None

    def __init__(
        self,
        message: str,
        *,
        possible_observation_path: Path | None = None,
        possible_evidence_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.possible_observation_path = possible_observation_path
        self.possible_evidence_path = possible_evidence_path


class QuillanObservationIntegrityError(QuillanObservationPersistenceError):
    """Existing observation or evidence state contradicts immutable identity."""


class QuillanObservationDiscoveryError(QuillanObservationError):
    """The canonical observation collection contains invalid state."""

    category: str
    original_error: Exception

    def __init__(self, category: str, message: str, original_error: Exception) -> None:
        super().__init__(message)
        self.category = category
        self.original_error = original_error


class QuillanSubmissionObservationAssemblyError(Exception):
    """Base failure for issuance-based observation assembly."""


class QuillanCategorizedAssemblyError(QuillanSubmissionObservationAssemblyError):
    """An assembly validation failure with an exact public category."""

    category: str

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


__all__ = [
    "QuillanDispatchResultError",
    "QuillanDispatchIntegrationError",
    "QuillanIssuanceAuthorizationError",
    "QuillanModuleError",
    "QuillanPayloadParsingError",
    "QuillanPageImageError",
    "QuillanPdfDependencyError",
    "QuillanPdfPageConversionError",
    "QuillanPdfPageCountError",
    "QuillanQrDetectionError",
    "QuillanRequestConstructionError",
    "QuillanRegistrationValidationError",
    "QuillanRetainedSourceError",
    "QuillanRouteContextError",
    "QuillanScanIntakeError",
    "QuillanScanPreflightError",
    "QuillanScanRegistryError",
    "QuillanScanReviewPersistenceError",
    "QuillanObservationAuthorityError",
    "QuillanObservationDiscoveryError",
    "QuillanObservationError",
    "QuillanObservationIntegrityError",
    "QuillanObservationPersistenceError",
    "QuillanObservationValidationError",
    "QuillanCategorizedAssemblyError",
    "QuillanRoutedEvidenceError",
    "QuillanRoutedEvidenceIntegrityError",
    "QuillanRoutedEvidenceMissingError",
    "QuillanRoutedEvidencePathError",
    "QuillanSubmissionObservationAssemblyError",
    "QuillanSourceMissingError",
    "QuillanSourcePageError",
    "QuillanSourceTypeUnsupportedError",
    "QuillanTargetIntegrityError",
]
