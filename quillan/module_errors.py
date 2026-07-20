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


__all__ = [
    "QuillanDispatchResultError",
    "QuillanIssuanceAuthorizationError",
    "QuillanModuleError",
    "QuillanRegistrationValidationError",
    "QuillanRetainedSourceError",
    "QuillanRouteContextError",
    "QuillanTargetIntegrityError",
]
