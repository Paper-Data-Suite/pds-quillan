"""Typed failures exposed by Quillan's installed-module boundary."""


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
    "QuillanSourceMissingError",
    "QuillanSourcePageError",
    "QuillanSourceTypeUnsupportedError",
    "QuillanTargetIntegrityError",
]
