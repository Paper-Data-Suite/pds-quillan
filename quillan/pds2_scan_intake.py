"""Retain-once PDS2 intake and ordered PDS Core module dispatch."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, TypeAlias

from pds_core.identifiers import IdentifierValidationError
from pds_core.module_dispatch import (
    RouteDispatchFailure,
    RouteDispatchOutcome,
    RouteDispatchRequest,
    RouteDispatchSuccess,
    dispatch_routes,
)
from pds_core.module_profiles import (
    ModuleDiscoveryError,
    ModuleProfile,
    ModuleRegistry,
    ModuleRegistryError,
    UnsupportedModuleError,
    build_module_registry,
)
from pds_core.pds2 import (
    PDS2_MAX_PAYLOAD_BYTES,
    Pds2PayloadError,
    parse_pds2_payload,
)
from pds_core.routing_models import (
    ModuleRecordRef,
    RouteLocator,
    RouteRegistration,
    RouteResolution,
    RoutingModelError,
)
from pds_core.scan_failure_metadata import (
    RoutingFailureMetadata,
    is_routing_failure_category,
)
from pds_core.scan_retention import (
    RetainedSourceScan,
    SourceRetentionError,
    retain_source_scan,
)

from quillan.module_errors import (
    QuillanDispatchIntegrationError,
    QuillanPayloadParsingError,
    QuillanQrDetectionError,
    QuillanRequestConstructionError,
    QuillanScanIntakeError,
    QuillanScanPreflightError,
    QuillanScanRegistryError,
    QuillanScanReviewPersistenceError,
    QuillanSourceMissingError,
    QuillanSourcePageError,
    QuillanSourceTypeUnsupportedError,
)
from quillan.qr_decode import (
    QrPayloadDetectionResult,
    detect_qr_payload,
    validate_qr_payload_detection_result,
)
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.retained_scan_pages import (
    SUPPORTED_SCAN_EXTENSIONS,
    load_retained_page_for_qr,
    retained_source_page_count,
)

FailureStage: TypeAlias = Literal[
    "source_page_loading",
    "qr_detection",
    "payload_parsing",
    "request_construction",
    "core_outcome_validation",
    "quillan_result_validation",
]
TerminalCategory: TypeAlias = Literal[
    "dispatch_success",
    "core_dispatch_failure",
    "pre_dispatch_failure",
    "quillan_integration_failure",
]
SourceType: TypeAlias = Literal["image", "pdf"]
BatchStatus: TypeAlias = Literal[
    "complete_success",
    "partial_success",
    "zero_success",
    "source_failure",
    "integration_failure",
    "review_persistence_failure",
]

_PRE_DISPATCH_STAGES = frozenset(
    {
        "source_page_loading",
        "qr_detection",
        "payload_parsing",
        "request_construction",
    }
)


@dataclass(frozen=True, slots=True)
class RoutingReviewRecord:
    """One verified, immutable Core-v2 failure occurrence."""

    failure_id: str
    metadata: RoutingFailureMetadata
    metadata_path: Path
    metadata_relative_path: str
    source_page_number: int | None
    origin: str
    retained_source: RetainedSourceScan
    workspace_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RoutingFailureMetadata):
            raise ValueError("metadata must be RoutingFailureMetadata.")
        if self.failure_id != self.metadata.failure_id:
            raise ValueError("failure_id must agree with metadata.")
        if self.metadata.schema_version != "2":
            raise ValueError("review metadata must use schema version 2.")
        if (
            not isinstance(self.workspace_root, Path)
            or not self.workspace_root.is_absolute()
            or self.workspace_root.resolve(strict=False) != self.workspace_root
        ):
            raise ValueError("workspace_root must be an absolute canonical Path.")
        if not isinstance(self.metadata_path, Path) or not self.metadata_path.is_absolute():
            raise ValueError("metadata_path must be an absolute Path.")
        expected_relative = f"scans/review/{self.failure_id}.json"
        expected_path = self.workspace_root / Path(expected_relative)
        if self.metadata_relative_path != expected_relative:
            raise ValueError("metadata_relative_path must be the exact Core review path.")
        if self.metadata_path != expected_path:
            raise ValueError("metadata_path must be the exact workspace review path.")
        _optional_positive_integer(self.source_page_number, "source_page_number")
        if self.source_page_number != self.metadata.source_page_number:
            raise ValueError("source page must agree with metadata.")
        if not isinstance(self.origin, str) or not self.origin:
            raise ValueError("origin must be nonempty text.")
        if self.metadata.module_details.get("failure_origin") != self.origin:
            raise ValueError("origin must agree with metadata failure_origin.")
        if type(self.retained_source) is not RetainedSourceScan:
            raise ValueError("retained_source must be RetainedSourceScan.")
        retained = self.retained_source
        if (
            self.metadata.source_filename != retained.source_filename
            or self.metadata.source_scan_id != retained.source_scan_id
            or self.metadata.source_sha256 != retained.source_sha256
            or self.metadata.retained_source_path
            != retained.retained_source_relative_path
        ):
            raise ValueError("metadata must agree with exact retained provenance.")

    @property
    def failure_metadata_path(self) -> Path:
        return self.metadata_path

    @property
    def failure_metadata_relative_path(self) -> str:
        return self.metadata_relative_path

    @property
    def failure_category(self) -> str:
        return self.metadata.failure_category

    @property
    def failure_message(self) -> str:
        return self.metadata.failure_message


PersistedQuillanScanFailure = RoutingReviewRecord


@dataclass(frozen=True, slots=True)
class QuillanFailurePersistenceError:
    source_page_number: int | None
    origin: str
    error: QuillanScanReviewPersistenceError
    durable_path: Path | None = None

    def __post_init__(self) -> None:
        _optional_positive_integer(self.source_page_number, "source_page_number")
        if not isinstance(self.origin, str) or not self.origin:
            raise ValueError("origin must be nonempty text.")
        if not isinstance(self.error, QuillanScanReviewPersistenceError):
            raise ValueError("error must be QuillanScanReviewPersistenceError.")
        if self.durable_path is not None and (
            not isinstance(self.durable_path, Path)
            or not self.durable_path.is_absolute()
        ):
            raise ValueError("durable_path must be an absolute Path or None.")


@dataclass(frozen=True, slots=True)
class QuillanFailurePersistenceBatch:
    persisted: tuple[PersistedQuillanScanFailure, ...]
    failures: tuple[QuillanFailurePersistenceError, ...]

    def __post_init__(self) -> None:
        if type(self.persisted) is not tuple or type(self.failures) is not tuple:
            raise ValueError("persistence collections must be immutable tuples.")
        if any(not isinstance(item, RoutingReviewRecord) for item in self.persisted):
            raise ValueError("persisted members must be RoutingReviewRecord.")
        if any(not isinstance(item, QuillanFailurePersistenceError) for item in self.failures):
            raise ValueError("failure members have the wrong type.")
        ids = tuple(item.failure_id for item in self.persisted)
        paths = tuple(item.metadata_path for item in self.persisted)
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("persisted IDs and paths must be unique.")
        persisted_occurrences = {
            (item.source_page_number, item.origin) for item in self.persisted
        }
        failed_occurrences = {
            (item.source_page_number, item.origin) for item in self.failures
        }
        if len(persisted_occurrences) != len(self.persisted):
            raise ValueError("persisted occurrence keys must be unique.")
        if len(failed_occurrences) != len(self.failures):
            raise ValueError("failed occurrence keys must be unique.")
        if persisted_occurrences & failed_occurrences:
            raise ValueError("one occurrence cannot be both persisted and failed.")


@dataclass(frozen=True, slots=True)
class QuillanScanPageOutcome:
    source_page_number: int
    terminal_category: TerminalCategory
    retained_source: RetainedSourceScan
    raw_payload_text: str | None = None
    locator: RouteLocator | None = None
    decode_method: str | None = None
    dispatch_request: RouteDispatchRequest | None = None
    dispatch_outcome: RouteDispatchOutcome | None = None
    failure_stage: FailureStage | None = None
    failure_category: str | None = None
    error: Exception | None = None
    review_record: RoutingReviewRecord | None = None
    review_error: QuillanFailurePersistenceError | None = None

    def __post_init__(self) -> None:
        _positive_integer(self.source_page_number, "source_page_number")
        if not isinstance(self.retained_source, RetainedSourceScan):
            raise ValueError("retained_source must be RetainedSourceScan.")
        if self.raw_payload_text is not None and not isinstance(self.raw_payload_text, str):
            raise ValueError("raw_payload_text must be text or None.")
        if self.locator is not None and not isinstance(self.locator, RouteLocator):
            raise ValueError("locator must be RouteLocator or None.")
        if self.decode_method is not None and not isinstance(self.decode_method, str):
            raise ValueError("decode_method must be text or None.")
        if self.locator is not None and self.raw_payload_text is None:
            raise ValueError("locator requires exact raw payload text.")
        if self.dispatch_request is not None:
            if type(self.dispatch_request) is not RouteDispatchRequest:
                raise ValueError("dispatch_request has the wrong type.")
            _validate_request_alignment(self, self.dispatch_request)
        if self.dispatch_outcome is not None:
            if type(self.dispatch_outcome) not in {
                RouteDispatchSuccess,
                RouteDispatchFailure,
            }:
                raise ValueError("dispatch_outcome has the wrong type.")
            if self.dispatch_request is None:
                raise ValueError("dispatch outcome requires a request.")
        if self.review_record is not None and not isinstance(
            self.review_record, RoutingReviewRecord
        ):
            raise ValueError("review_record has the wrong type.")
        if self.review_error is not None and not isinstance(
            self.review_error, QuillanFailurePersistenceError
        ):
            raise ValueError("review_error has the wrong type.")
        if self.review_record is not None and self.review_error is not None:
            raise ValueError("review record and review error are mutually exclusive.")
        if self.review_record is not None and (
            self.review_record.source_page_number != self.source_page_number
            or self.review_record.retained_source is not self.retained_source
            or self.review_record.metadata.scope != "page"
        ):
            raise ValueError("review record contradicts page provenance.")
        if self.review_error is not None and (
            self.review_error.source_page_number != self.source_page_number
            or self.review_error.origin != _page_failure_origin(self)
        ):
            raise ValueError("review error contradicts the page occurrence.")
        if self.review_record is not None and (
            self.review_record.origin != _page_failure_origin(self)
        ):
            raise ValueError("review record contradicts the page occurrence.")

        if self.terminal_category == "dispatch_success":
            if (
                type(self.dispatch_outcome) is not RouteDispatchSuccess
                or self.dispatch_request is None
                or self.failure_stage is not None
                or self.failure_category is not None
                or self.error is not None
                or self.review_record is not None
                or self.review_error is not None
            ):
                raise ValueError("dispatch_success has contradictory fields.")
            _validate_outcome_request(self.dispatch_outcome, self.dispatch_request)
        elif self.terminal_category == "core_dispatch_failure":
            if (
                type(self.dispatch_outcome) is not RouteDispatchFailure
                or self.dispatch_request is None
                or not isinstance(self.dispatch_outcome.error, Exception)
                or self.failure_stage is not None
                or self.failure_category is not None
                or self.error is not None
            ):
                raise ValueError("core_dispatch_failure has contradictory fields.")
            _validate_outcome_request(self.dispatch_outcome, self.dispatch_request)
        elif self.terminal_category == "pre_dispatch_failure":
            if (
                self.dispatch_request is not None
                or self.dispatch_outcome is not None
                or self.failure_stage not in _PRE_DISPATCH_STAGES
                or not is_routing_failure_category(self.failure_category)
            ):
                raise ValueError("pre_dispatch_failure has contradictory fields.")
            if self.failure_stage == "payload_parsing":
                if not isinstance(
                    self.error,
                    (Pds2PayloadError, QuillanPayloadParsingError),
                ):
                    raise ValueError("payload parsing failure has the wrong error type.")
            elif not isinstance(self.error, QuillanScanIntakeError):
                raise ValueError("pre-dispatch failure has the wrong error type.")
        elif self.terminal_category == "quillan_integration_failure":
            if (
                self.failure_stage not in {
                    "core_outcome_validation",
                    "quillan_result_validation",
                }
                or not isinstance(self.error, QuillanDispatchIntegrationError)
                or self.failure_category != "processing_error"
            ):
                raise ValueError("integration failure has contradictory fields.")
            if self.failure_stage == "core_outcome_validation" and self.dispatch_request is None:
                raise ValueError("Core integration failure requires a request.")
            if (
                self.failure_stage == "quillan_result_validation"
                and type(self.dispatch_outcome) is not RouteDispatchSuccess
            ):
                raise ValueError("Quillan result failure requires a Core success.")
        else:
            raise ValueError("terminal_category is invalid.")


@dataclass(frozen=True, slots=True)
class QuillanScanSourceResult:
    source_path: Path
    source_filename: str
    source_type: SourceType
    retained_source: RetainedSourceScan | None
    pages: tuple[QuillanScanPageOutcome, ...]
    registry_module_ids: tuple[str, ...]
    source_error: Exception | None = None
    scan_review_record: RoutingReviewRecord | None = None
    scan_review_error: QuillanFailurePersistenceError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise ValueError("source_path must be a Path.")
        if not isinstance(self.source_filename, str) or self.source_path.name != self.source_filename:
            raise ValueError("source filename must agree with source_path.")
        if self.source_type not in {"image", "pdf"}:
            raise ValueError("source_type is invalid.")
        if type(self.pages) is not tuple or any(
            not isinstance(page, QuillanScanPageOutcome) for page in self.pages
        ):
            raise ValueError("pages must be an immutable page-outcome tuple.")
        _validate_registry_ids(self.registry_module_ids)
        if self.scan_review_record is not None and not isinstance(
            self.scan_review_record, RoutingReviewRecord
        ):
            raise ValueError("scan_review_record has the wrong type.")
        if self.scan_review_error is not None and not isinstance(
            self.scan_review_error, QuillanFailurePersistenceError
        ):
            raise ValueError("scan_review_error has the wrong type.")
        if self.scan_review_record is not None and self.scan_review_error is not None:
            raise ValueError("source review record and error are mutually exclusive.")
        if (
            self.scan_review_error is not None
            and self.scan_review_error.source_page_number is not None
        ):
            raise ValueError("source review error must be scan-scoped.")

        if self.retained_source is None:
            if self.pages or not isinstance(self.source_error, Exception):
                raise ValueError("pre-retention failure requires only a source error.")
            if self.scan_review_record is not None or self.scan_review_error is not None:
                raise ValueError("pre-retention failures cannot have review persistence.")
        elif self.source_error is not None:
            if self.pages:
                raise ValueError("retained source failure cannot contain pages.")
            if self.scan_review_record is not None and (
                self.scan_review_record.source_page_number is not None
                or self.scan_review_record.origin != "source_page_loading"
                or self.scan_review_record.metadata.scope != "scan"
            ):
                raise ValueError("source review record must be scan-scoped.")
            if self.scan_review_error is not None and (
                self.scan_review_error.origin != "source_page_loading"
            ):
                raise ValueError("source review error has the wrong origin.")
        else:
            if not self.pages:
                raise ValueError("enumerated source requires a positive page tuple.")
            if self.scan_review_record is not None or self.scan_review_error is not None:
                raise ValueError("enumerated sources cannot have scan-scoped review persistence.")
        if self.retained_source is not None:
            if type(self.retained_source) is not RetainedSourceScan:
                raise ValueError("retained_source must be an exact RetainedSourceScan.")
            if self.retained_source.source_filename != self.source_filename:
                raise ValueError("retained source filename contradicts selected source.")
            if (
                Path(self.retained_source.source_filename).suffix.lower()
                != self.source_path.suffix.lower()
                or self.retained_source.retained_source_path.suffix.lower()
                != self.source_path.suffix.lower()
            ):
                raise ValueError("retained source extension contradicts selected source.")
            if any(page.retained_source is not self.retained_source for page in self.pages):
                raise ValueError("every page must share the exact retained object.")
            if self.scan_review_record is not None and (
                self.scan_review_record.retained_source is not self.retained_source
            ):
                raise ValueError("source review record must share retained provenance.")
        numbers = tuple(page.source_page_number for page in self.pages)
        if numbers != tuple(range(1, len(numbers) + 1)):
            raise ValueError("pages must be complete, ordered, and one-based.")
        if self.source_type == "pdf" and self.source_path.suffix.lower() != ".pdf":
            raise ValueError("PDF source type requires a .pdf extension.")
        if (
            self.retained_source is not None
            and self.source_type == "image"
            and self.source_path.suffix.lower() not in SUPPORTED_SCAN_EXTENSIONS - {".pdf"}
        ):
            raise ValueError("retained image source has an unsupported extension.")
        if self.source_type == "image" and len(self.pages) > 1:
            raise ValueError("an image source can enumerate only physical page one.")

    @property
    def complete_success(self) -> bool:
        return self.source_error is None and all(
            page.terminal_category == "dispatch_success"
            and page.review_error is None
            for page in self.pages
        )


@dataclass(frozen=True, slots=True)
class QuillanScanIntakeSummary:
    source_results: tuple[QuillanScanSourceResult, ...]
    registry_module_ids: tuple[str, ...]
    skipped_unsupported_count: int = 0
    skipped_nonfile_count: int = 0

    def __post_init__(self) -> None:
        if type(self.source_results) is not tuple or any(
            not isinstance(source, QuillanScanSourceResult)
            for source in self.source_results
        ):
            raise ValueError("source_results must be an immutable source tuple.")
        _validate_registry_ids(self.registry_module_ids)
        _nonnegative_integer(self.skipped_unsupported_count, "skipped_unsupported_count")
        _nonnegative_integer(self.skipped_nonfile_count, "skipped_nonfile_count")
        if any(
            source.registry_module_ids != self.registry_module_ids
            for source in self.source_results
        ):
            raise ValueError("every source must agree with the batch registry IDs.")
        if (
            self.dispatch_success_count
            + self.core_dispatch_failure_count
            + self.pre_dispatch_failure_count
            + self.quillan_integration_failure_count
            != self.total_source_pages
        ):
            raise ValueError("terminal page counts must equal enumerated pages.")

    @property
    def source_count(self) -> int:
        return len(self.source_results)

    @property
    def retained_source_count(self) -> int:
        return sum(x.retained_source is not None for x in self.source_results)

    @property
    def source_failure_count(self) -> int:
        return sum(x.source_error is not None for x in self.source_results)

    @property
    def total_source_pages(self) -> int:
        return len(self.pages)

    @property
    def decoded_payload_count(self) -> int:
        return sum(page.raw_payload_text is not None for page in self.pages)

    @property
    def valid_locator_count(self) -> int:
        return sum(page.locator is not None for page in self.pages)

    def _terminal_count(self, category: TerminalCategory) -> int:
        return sum(page.terminal_category == category for page in self.pages)

    @property
    def dispatch_success_count(self) -> int:
        return self._terminal_count("dispatch_success")

    @property
    def core_dispatch_failure_count(self) -> int:
        return self._terminal_count("core_dispatch_failure")

    @property
    def pre_dispatch_failure_count(self) -> int:
        return self._terminal_count("pre_dispatch_failure")

    @property
    def quillan_integration_failure_count(self) -> int:
        return self._terminal_count("quillan_integration_failure")

    @property
    def quillan_success_count(self) -> int:
        return self.successful_pages_by_module.get("quillan", 0)

    @property
    def other_module_success_count(self) -> int:
        return self.dispatch_success_count - self.quillan_success_count

    @property
    def successful_pages_by_module(self) -> Mapping[str, int]:
        counts = Counter(
            page.locator.module_id
            for page in self.pages
            if page.terminal_category == "dispatch_success"
            and page.locator is not None
        )
        return dict(sorted(counts.items()))

    @property
    def review_record_count(self) -> int:
        return sum(page.review_record is not None for page in self.pages) + sum(
            source.scan_review_record is not None for source in self.source_results
        )

    @property
    def review_persistence_failure_count(self) -> int:
        return sum(page.review_error is not None for page in self.pages) + sum(
            source.scan_review_error is not None for source in self.source_results
        )

    @property
    def pages(self) -> tuple[QuillanScanPageOutcome, ...]:
        return tuple(page for source in self.source_results for page in source.pages)

    @property
    def batch_status(self) -> BatchStatus:
        if self.review_persistence_failure_count:
            return "review_persistence_failure"
        if self.quillan_integration_failure_count:
            return "integration_failure"
        if self.source_failure_count:
            return "source_failure"
        if self.total_source_pages and self.dispatch_success_count == self.total_source_pages:
            return "complete_success"
        if self.dispatch_success_count:
            return "partial_success"
        return "zero_success"

    @property
    def complete_success(self) -> bool:
        return self.batch_status == "complete_success"

    @property
    def partial_success(self) -> bool:
        return self.batch_status == "partial_success"

    @property
    def zero_success(self) -> bool:
        return self.batch_status == "zero_success"


@dataclass(frozen=True, slots=True)
class _DispatchPlan:
    source_page_number: int
    retained_source: RetainedSourceScan
    raw_payload_text: str
    locator: RouteLocator
    decode_method: str | None
    request: RouteDispatchRequest


def build_quillan_scan_registry() -> ModuleRegistry:
    """Build one fresh application-owned installed module registry."""
    try:
        registry = build_module_registry(discover_installed=True)
        registry.require("quillan")
        return validate_quillan_scan_registry(registry)
    except (ModuleDiscoveryError, ModuleRegistryError, UnsupportedModuleError) as error:
        raise QuillanScanRegistryError(
            f"Could not build scan module registry: {error}"
        ) from error


def validate_quillan_scan_registry(registry: object) -> ModuleRegistry:
    """Validate an injected registry without mutating it."""
    try:
        if not isinstance(registry, ModuleRegistry):
            raise ModuleRegistryError("registry must be a ModuleRegistry.")
        registry.require("quillan")
        _validate_registry_ids(registry.module_ids())
        return registry
    except (ModuleRegistryError, UnsupportedModuleError, ValueError) as error:
        raise QuillanScanRegistryError(
            f"Invalid scan module registry: {error}"
        ) from error


def validate_scan_workspace(workspace_root: Path) -> Path:
    """Return one canonical, existing, non-link workspace root."""
    if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
        raise QuillanScanPreflightError(
            "workspace_root must be an absolute Path."
        )
    try:
        canonical = workspace_root.resolve(strict=True)
        if canonical != workspace_root:
            raise ValueError("workspace_root must already be canonical")
        _validate_path_chain(canonical)
        if not canonical.is_dir():
            raise ValueError("workspace_root must be an ordinary directory")
        return canonical
    except (OSError, RuntimeError, ValueError) as error:
        raise QuillanScanPreflightError(
            f"Invalid workspace_root: {error}"
        ) from error


def validate_scan_source(source_file: str | Path) -> Path:
    """Return one canonical readable supported ordinary source file."""
    if not isinstance(source_file, (str, Path)):
        raise QuillanScanPreflightError("source_file must be a str or Path.")
    supplied = Path(source_file)
    try:
        if not os.path.lexists(supplied):
            raise QuillanSourceMissingError(f"Source does not exist: {supplied}")
        canonical = supplied.resolve(strict=True)
        _validate_path_chain(supplied.absolute())
        if _is_link_like(supplied) or not canonical.is_file():
            raise QuillanSourceTypeUnsupportedError(
                "Source must be a safe ordinary file."
            )
        if canonical.suffix.lower() not in SUPPORTED_SCAN_EXTENSIONS:
            raise QuillanSourceTypeUnsupportedError(
                f"Unsupported scan extension: {canonical.suffix or '(none)'}"
            )
        if not os.access(canonical, os.R_OK):
            raise QuillanScanPreflightError("Source file is not readable.")
        return canonical
    except QuillanScanPreflightError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise QuillanScanPreflightError(f"Invalid source file: {error}") from error


def validate_scan_folder(source_folder: str | Path) -> Path:
    """Return one canonical, existing, non-link source folder."""
    if not isinstance(source_folder, (str, Path)):
        raise QuillanScanPreflightError("source_folder must be a str or Path.")
    supplied = Path(source_folder)
    try:
        if not os.path.lexists(supplied):
            raise QuillanSourceMissingError(
                f"Source folder does not exist: {supplied}"
            )
        canonical = supplied.resolve(strict=True)
        _validate_path_chain(supplied.absolute())
        if _is_link_like(supplied) or not canonical.is_dir():
            raise QuillanSourceTypeUnsupportedError(
                "Source folder must be a safe ordinary directory."
            )
        return canonical
    except QuillanScanPreflightError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise QuillanScanPreflightError(f"Invalid source folder: {error}") from error


def classify_pds2_payload_error(raw_payload_text: str, error: Exception) -> str:
    """Map a strict Core parse failure without interpreting partial fields."""
    if not isinstance(raw_payload_text, str) or not isinstance(error, Exception):
        raise TypeError("payload classification requires text and an Exception.")
    declared_schema, separator, _remainder = raw_payload_text.partition("|")
    if (
        separator
        and declared_schema != "PDS2"
        and _is_declared_schema_token(declared_schema)
    ):
        return "payload_schema_unsupported"
    try:
        if len(raw_payload_text.encode("ascii")) > PDS2_MAX_PAYLOAD_BYTES:
            return "payload_too_large"
    except UnicodeEncodeError:
        pass
    if _exception_chain_contains(
        error,
        (IdentifierValidationError, RoutingModelError),
    ):
        return "identifier_invalid"
    return "payload_invalid"


def process_quillan_scan_source(
    source_file: str | Path,
    *,
    workspace_root: Path,
    registry: ModuleRegistry | None = None,
) -> QuillanScanSourceResult:
    """Preflight, retain exactly once, dispatch, then preserve failures."""
    source_hint = _source_hint(source_file)
    source_type = _source_type(source_hint)
    registry_ids: tuple[str, ...] = ()
    try:
        root = validate_scan_workspace(workspace_root)
    except (QuillanScanPreflightError, QuillanScanRegistryError) as error:
        return QuillanScanSourceResult(
            source_hint,
            source_hint.name,
            source_type,
            None,
            (),
            registry_ids,
            error,
        )
    if registry is not None:
        try:
            selected_registry = validate_quillan_scan_registry(registry)
            registry_ids = selected_registry.module_ids()
        except QuillanScanRegistryError as error:
            return QuillanScanSourceResult(
                source_hint,
                source_hint.name,
                source_type,
                None,
                (),
                registry_ids,
                error,
            )
    try:
        source = validate_scan_source(source_file)
        source_type = _source_type(source)
        if registry is None:
            selected_registry = build_quillan_scan_registry()
            registry_ids = selected_registry.module_ids()
    except (QuillanScanPreflightError, QuillanScanRegistryError) as error:
        return QuillanScanSourceResult(
            source_hint,
            source_hint.name,
            source_type,
            None,
            (),
            registry_ids,
            error,
        )
    try:
        retained = retain_source_scan(root, source)
    except Exception as error:
        retention_error = (
            error
            if isinstance(error, SourceRetentionError)
            else SourceRetentionError(f"Unexpected source retention failure: {error}")
        )
        if retention_error is not error:
            retention_error.__cause__ = error
        return QuillanScanSourceResult(
            source,
            source.name,
            source_type,
            None,
            (),
            registry_ids,
            retention_error,
        )

    try:
        result = dispatch_retained_quillan_scan(
            root,
            retained,
            registry=selected_registry,
            source_path=source,
        )
    except Exception as error:
        source_error = QuillanSourcePageError(
            f"Unexpected retained source processing failure: {error}"
        )
        source_error.__cause__ = error
        result = QuillanScanSourceResult(
            source,
            source.name,
            source_type,
            retained,
            (),
            registry_ids,
            source_error,
        )
    from quillan.scan_review_preservation import (
        preserve_and_attach_quillan_scan_failures,
    )

    return preserve_and_attach_quillan_scan_failures(root, result)


def dispatch_retained_quillan_scan(
    workspace_root: Path,
    retained_source: RetainedSourceScan,
    *,
    registry: ModuleRegistry,
    source_path: Path | None = None,
) -> QuillanScanSourceResult:
    """Enumerate every retained page and assign one terminal outcome to each."""
    root = validate_scan_workspace(workspace_root)
    selected_registry = validate_quillan_scan_registry(registry)
    if type(retained_source) is not RetainedSourceScan:
        raise QuillanScanPreflightError(
            "retained_source must be an exact RetainedSourceScan."
        )
    if source_path is not None and not isinstance(source_path, Path):
        raise QuillanScanPreflightError("source_path must be a Path or None.")
    source = Path(retained_source.source_filename) if source_path is None else source_path
    if source.name != retained_source.source_filename:
        raise QuillanScanPreflightError(
            "source_path must agree with retained source filename."
        )
    source_type = _source_type(source)
    try:
        page_count = retained_source_page_count(
            retained_source,
            workspace_root=root,
        )
    except Exception as error:
        page_error = _source_page_error(
            error,
            "Retained source page enumeration failed",
        )
        return QuillanScanSourceResult(
            source,
            source.name,
            source_type,
            retained_source,
            (),
            selected_registry.module_ids(),
            page_error,
        )

    terminal_pages: dict[int, QuillanScanPageOutcome] = {}
    plans: list[_DispatchPlan] = []
    for page_number in range(1, page_count + 1):
        try:
            image = load_retained_page_for_qr(
                retained_source,
                page_number,
                workspace_root=root,
            )
        except Exception as error:
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "source_page_loading",
                "source_unreadable",
                _source_page_error(error, "Retained page loading failed"),
            )
            continue

        try:
            detection = detect_qr_payload(image)
        except Exception as error:
            detection_error = QuillanQrDetectionError(
                f"Unexpected QR detection failure: {error}"
            )
            detection_error.__cause__ = error
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "qr_detection",
                "payload_unreadable",
                detection_error,
            )
            continue
        try:
            detection = validate_qr_payload_detection_result(detection)
        except Exception as error:
            detection_error = QuillanQrDetectionError(
                f"QR detector returned an invalid result: {error}"
            )
            detection_error.__cause__ = error
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "qr_detection",
                "payload_unreadable",
                detection_error,
            )
            continue
        if detection.raw_payload_text is None:
            detection_error = _qr_detection_error(detection)
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "qr_detection",
                getattr(detection_error, "failure_category", "payload_missing"),
                detection_error,
                decode_method=detection.decode_method,
            )
            continue

        raw = detection.raw_payload_text
        try:
            locator = parse_pds2_payload(raw)
        except Exception as error:
            parsing_error = (
                error
                if isinstance(error, Pds2PayloadError)
                else _payload_parsing_error(error)
            )
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "payload_parsing",
                classify_pds2_payload_error(raw, error),
                parsing_error,
                raw=raw,
                decode_method=detection.decode_method,
            )
            continue
        try:
            request = RouteDispatchRequest(
                locator=locator,
                retained_source=retained_source,
                source_page_number=page_number,
            )
        except Exception as error:
            request_error = QuillanRequestConstructionError(
                f"Could not construct Core dispatch request: {error}"
            )
            request_error.__cause__ = error
            terminal_pages[page_number] = _predispatch(
                page_number,
                retained_source,
                "request_construction",
                "processing_error",
                request_error,
                raw=raw,
                locator=locator,
                decode_method=detection.decode_method,
            )
            continue
        plans.append(
            _DispatchPlan(
                page_number,
                retained_source,
                raw,
                locator,
                detection.decode_method,
                request,
            )
        )

    if plans:
        try:
            outcomes = dispatch_routes(
                root,
                selected_registry,
                tuple(plan.request for plan in plans),
            )
        except Exception as error:
            integration = QuillanDispatchIntegrationError(
                f"Core batch dispatch raised unexpectedly: {error}"
            )
            integration.__cause__ = error
            for plan in plans:
                terminal_pages[plan.source_page_number] = _integration_page(
                    plan,
                    integration,
                    None,
                    "core_outcome_validation",
                )
        else:
            if not isinstance(outcomes, tuple) or len(outcomes) != len(plans):
                integration = QuillanDispatchIntegrationError(
                    "Core batch output is not an exactly aligned outcome tuple."
                )
                for index, plan in enumerate(plans):
                    safe_outcome = _safe_positional_outcome(outcomes, index, plan)
                    terminal_pages[plan.source_page_number] = _integration_page(
                        plan,
                        integration,
                        safe_outcome,
                        "core_outcome_validation",
                    )
            else:
                for plan, outcome in zip(plans, outcomes, strict=True):
                    terminal_pages[plan.source_page_number] = _integrate_outcome(
                        plan,
                        outcome,
                    )

    pages = tuple(terminal_pages[number] for number in range(1, page_count + 1))
    return QuillanScanSourceResult(
        source,
        source.name,
        source_type,
        retained_source,
        pages,
        selected_registry.module_ids(),
    )


def process_quillan_scan_folder(
    source_folder: str | Path,
    *,
    workspace_root: Path,
    registry: ModuleRegistry | None = None,
) -> QuillanScanIntakeSummary:
    """Process supported direct children while containing every source failure."""
    root = validate_scan_workspace(workspace_root)
    folder = validate_scan_folder(source_folder)
    selected_registry = (
        build_quillan_scan_registry()
        if registry is None
        else validate_quillan_scan_registry(registry)
    )
    module_ids = selected_registry.module_ids()
    results: list[QuillanScanSourceResult] = []
    unsupported = 0
    nonfile = 0
    try:
        children = sorted(
            folder.iterdir(),
            key=lambda path: (path.name.casefold(), path.name),
        )
    except Exception as error:
        raise QuillanScanPreflightError(
            f"Could not enumerate source folder: {error}"
        ) from error
    for child in children:
        suffix_supported = child.suffix.lower() in SUPPORTED_SCAN_EXTENSIONS
        try:
            unsafe_child = _is_link_like(child) or not child.is_file()
        except Exception as error:
            nonfile += 1
            if suffix_supported:
                child_error = QuillanSourceTypeUnsupportedError(
                    f"Could not inspect supported source child: {error}"
                )
                child_error.__cause__ = error
                results.append(
                    QuillanScanSourceResult(
                        child,
                        child.name,
                        _source_type(child),
                        None,
                        (),
                        module_ids,
                        child_error,
                    )
                )
            continue
        if unsafe_child:
            nonfile += 1
            if suffix_supported:
                results.append(
                    QuillanScanSourceResult(
                        child,
                        child.name,
                        _source_type(child),
                        None,
                        (),
                        module_ids,
                        QuillanSourceTypeUnsupportedError(
                            "Supported-extension child is not a safe ordinary file."
                        ),
                    )
                )
            continue
        if not suffix_supported:
            unsupported += 1
            continue
        try:
            result = process_quillan_scan_source(
                child,
                workspace_root=root,
                registry=selected_registry,
            )
        except Exception as error:
            contained = QuillanScanPreflightError(
                f"Unexpected selected-source failure: {error}"
            )
            contained.__cause__ = error
            result = QuillanScanSourceResult(
                child,
                child.name,
                _source_type(child),
                None,
                (),
                module_ids,
                contained,
            )
        results.append(result)
    return QuillanScanIntakeSummary(
        tuple(results),
        module_ids,
        unsupported,
        nonfile,
    )


def _integrate_outcome(
    plan: _DispatchPlan,
    outcome: object,
) -> QuillanScanPageOutcome:
    if not isinstance(outcome, (RouteDispatchSuccess, RouteDispatchFailure)) or type(
        outcome
    ) not in {RouteDispatchSuccess, RouteDispatchFailure}:
        return _integration_page(
            plan,
            QuillanDispatchIntegrationError(
                "Core returned an unsupported outcome object."
            ),
            None,
            "core_outcome_validation",
        )
    try:
        _validate_outcome_request(outcome, plan.request)
        if type(outcome) is RouteDispatchFailure:
            if not isinstance(outcome.error, Exception):
                raise QuillanDispatchIntegrationError(
                    "Core failure does not carry an Exception."
                )
            return _terminal_from_plan(
                plan,
                "core_dispatch_failure",
                outcome,
            )
    except Exception as error:
        return _integration_page(
            plan,
            _integration_error(error, "Core outcome request validation failed"),
            outcome,
            "core_outcome_validation",
        )

    assert isinstance(outcome, RouteDispatchSuccess)
    safe_module_id: str | None = None
    try:
        profile = outcome.profile
        if type(profile) is not ModuleProfile:
            raise QuillanDispatchIntegrationError(
                "Core success profile has the wrong runtime type."
            )
        module_id = profile.module_id
        if not isinstance(module_id, str) or not module_id:
            raise QuillanDispatchIntegrationError(
                "Core success profile has no usable module ID."
            )
        safe_module_id = module_id
        if module_id != plan.locator.module_id:
            raise QuillanDispatchIntegrationError(
                "Core success profile contradicts the submitted locator."
            )
        resolution = outcome.resolution
        if type(resolution) is not RouteResolution:
            raise QuillanDispatchIntegrationError(
                "Core success resolution has the wrong runtime type."
            )
        if resolution.locator != plan.locator:
            raise QuillanDispatchIntegrationError(
                "Core resolution locator contradicts the request."
            )
        registration = resolution.registration
        if type(registration) is not RouteRegistration:
            raise QuillanDispatchIntegrationError(
                "Core success registration has the wrong runtime type."
            )
        if registration.locator != plan.locator:
            raise QuillanDispatchIntegrationError(
                "Core registration locator contradicts the request."
            )
        target = registration.target
        if type(target) is not ModuleRecordRef:
            raise QuillanDispatchIntegrationError(
                "Core success target has the wrong runtime type."
            )
        if target.module_id != module_id:
            raise QuillanDispatchIntegrationError(
                "Core registration target contradicts the profile module."
            )
    except Exception as error:
        return _integration_page(
            plan,
            _integration_error(error, "Core success validation failed"),
            outcome,
            "core_outcome_validation",
        )

    if safe_module_id == "quillan":
        try:
            result = validate_quillan_response_page_dispatch_result(
                outcome.module_result
            )
            _validate_quillan_success(result, plan.request)
        except Exception as error:
            return _integration_page(
                plan,
                _integration_error(error, "Quillan success result is invalid"),
                outcome,
                "quillan_result_validation",
            )
    return _terminal_from_plan(plan, "dispatch_success", outcome)


def _validate_quillan_success(
    result: QuillanResponsePageDispatchResult,
    request: RouteDispatchRequest,
) -> None:
    retained = request.retained_source
    comparisons = (
        (result.route_id, request.locator.route_id, "route_id"),
        (result.class_id, request.locator.class_id, "class_id"),
        (result.assignment_id, request.locator.work_id, "assignment_id"),
        (result.source_scan_id, retained.source_scan_id, "source_scan_id"),
        (result.source_filename, retained.source_filename, "source_filename"),
        (
            result.source_page_number,
            request.source_page_number,
            "source_page_number",
        ),
        (
            result.retained_source_path,
            retained.retained_source_path,
            "retained_source_path",
        ),
        (
            result.retained_source_relative_path,
            retained.retained_source_relative_path,
            "retained_source_relative_path",
        ),
        (result.source_sha256, retained.source_sha256, "source_sha256"),
        (result.intake_timestamp, retained.intake_timestamp, "intake_timestamp"),
        (result.intake_date, retained.intake_date, "intake_date"),
    )
    for actual, expected, field_name in comparisons:
        if actual != expected:
            raise QuillanDispatchIntegrationError(
                f"Quillan result contradicts request field {field_name}."
            )


def _terminal_from_plan(
    plan: _DispatchPlan,
    category: Literal["dispatch_success", "core_dispatch_failure"],
    outcome: RouteDispatchOutcome,
) -> QuillanScanPageOutcome:
    return QuillanScanPageOutcome(
        source_page_number=plan.source_page_number,
        terminal_category=category,
        retained_source=plan.retained_source,
        raw_payload_text=plan.raw_payload_text,
        locator=plan.locator,
        decode_method=plan.decode_method,
        dispatch_request=plan.request,
        dispatch_outcome=outcome,
    )


def _integration_page(
    plan: _DispatchPlan,
    error: QuillanDispatchIntegrationError,
    outcome: RouteDispatchOutcome | None,
    stage: Literal["core_outcome_validation", "quillan_result_validation"],
) -> QuillanScanPageOutcome:
    return QuillanScanPageOutcome(
        source_page_number=plan.source_page_number,
        terminal_category="quillan_integration_failure",
        retained_source=plan.retained_source,
        raw_payload_text=plan.raw_payload_text,
        locator=plan.locator,
        decode_method=plan.decode_method,
        dispatch_request=plan.request,
        dispatch_outcome=outcome,
        failure_stage=stage,
        failure_category="processing_error",
        error=error,
    )


def _predispatch(
    number: int,
    retained: RetainedSourceScan,
    stage: Literal[
        "source_page_loading",
        "qr_detection",
        "payload_parsing",
        "request_construction",
    ],
    category: str,
    error: Exception,
    *,
    raw: str | None = None,
    locator: RouteLocator | None = None,
    decode_method: str | None = None,
) -> QuillanScanPageOutcome:
    return QuillanScanPageOutcome(
        source_page_number=number,
        terminal_category="pre_dispatch_failure",
        retained_source=retained,
        raw_payload_text=raw,
        locator=locator,
        decode_method=decode_method,
        failure_stage=stage,
        failure_category=category,
        error=error,
    )


def _validate_request_alignment(
    page: QuillanScanPageOutcome,
    request: RouteDispatchRequest,
) -> None:
    if (
        request.locator != page.locator
        or request.source_page_number != page.source_page_number
        or request.retained_source is not page.retained_source
    ):
        raise ValueError("dispatch request contradicts exact page provenance.")


def _validate_outcome_request(
    outcome: RouteDispatchOutcome,
    request: RouteDispatchRequest,
) -> None:
    returned_request = outcome.request
    if type(returned_request) is not RouteDispatchRequest:
        raise QuillanDispatchIntegrationError(
            "Core outcome request has the wrong type."
        )
    if returned_request != request:
        raise QuillanDispatchIntegrationError(
            "Core outcome request differs from the submitted request."
        )
    if returned_request.retained_source is not request.retained_source:
        raise QuillanDispatchIntegrationError(
            "Core outcome substituted the retained-source object."
        )
    if returned_request.locator != request.locator:
        raise QuillanDispatchIntegrationError(
            "Core outcome substituted the locator."
        )
    if returned_request.source_page_number != request.source_page_number:
        raise QuillanDispatchIntegrationError(
            "Core outcome substituted the physical source page."
        )


def _safe_positional_outcome(
    outcomes: object,
    index: int,
    plan: _DispatchPlan,
) -> RouteDispatchOutcome | None:
    if not isinstance(outcomes, tuple) or index >= len(outcomes):
        return None
    candidate = outcomes[index]
    if not isinstance(candidate, (RouteDispatchSuccess, RouteDispatchFailure)) or type(
        candidate
    ) not in {RouteDispatchSuccess, RouteDispatchFailure}:
        return None
    try:
        _validate_outcome_request(candidate, plan.request)
    except Exception:
        return None
    return candidate


def _source_page_error(error: Exception, prefix: str) -> QuillanSourcePageError:
    if isinstance(error, QuillanSourcePageError):
        return error
    wrapped = QuillanSourcePageError(f"{prefix}: {error}")
    wrapped.__cause__ = error
    return wrapped


def _qr_detection_error(
    detection: QrPayloadDetectionResult,
) -> QuillanQrDetectionError:
    source_error = detection.error
    message = str(source_error) if isinstance(source_error, Exception) else "No QR payload could be decoded."
    error = QuillanQrDetectionError(
        message,
        failure_category=getattr(
            source_error,
            "failure_category",
            "payload_missing",
        ),
    )
    if isinstance(source_error, Exception):
        error.__cause__ = source_error
    return error


def _payload_parsing_error(error: Exception) -> QuillanPayloadParsingError:
    wrapped = QuillanPayloadParsingError(
        f"Unexpected Core PDS2 parsing failure: {error}"
    )
    wrapped.__cause__ = error
    return wrapped


def _integration_error(
    error: Exception,
    prefix: str,
) -> QuillanDispatchIntegrationError:
    if isinstance(error, QuillanDispatchIntegrationError):
        return error
    wrapped = QuillanDispatchIntegrationError(f"{prefix}: {error}")
    wrapped.__cause__ = error
    return wrapped


def _exception_chain_contains(
    error: BaseException,
    classes: tuple[type[BaseException], ...],
) -> bool:
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, classes):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return False


def _is_declared_schema_token(value: str) -> bool:
    return (
        bool(value)
        and value.isascii()
        and len(value) <= 32
        and all(character.isalnum() or character in {"_", "-"} for character in value)
    )


def _page_failure_origin(page: QuillanScanPageOutcome) -> str:
    if page.terminal_category == "dispatch_success":
        raise ValueError("successful pages have no review occurrence origin.")
    if page.terminal_category == "core_dispatch_failure":
        return "core_dispatch"
    return page.failure_stage or "dispatch_integration"


def _validate_registry_ids(value: object) -> tuple[str, ...]:
    if type(value) is not tuple or any(not isinstance(item, str) for item in value):
        raise ValueError("registry module IDs must be an immutable text tuple.")
    ids = value
    if ids != tuple(sorted(set(ids))):
        raise ValueError("registry module IDs must be deterministic and unique.")
    return ids


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


def _optional_positive_integer(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _positive_integer(value, field_name)


def _nonnegative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative integer.")
    return value


def _source_hint(value: object) -> Path:
    return Path(value) if isinstance(value, (str, Path)) else Path("invalid-source")


def _source_type(path: Path) -> SourceType:
    return "pdf" if path.suffix.lower() == ".pdf" else "image"


def _validate_path_chain(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            raise ValueError(f"path component does not exist: {current}")
        if _is_link_like(current):
            raise ValueError(f"path contains a symlink or junction: {current}")


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


__all__ = [
    "BatchStatus",
    "FailureStage",
    "PersistedQuillanScanFailure",
    "QuillanFailurePersistenceBatch",
    "QuillanFailurePersistenceError",
    "QuillanScanIntakeSummary",
    "QuillanScanPageOutcome",
    "QuillanScanSourceResult",
    "RoutingReviewRecord",
    "SUPPORTED_SCAN_EXTENSIONS",
    "SourceType",
    "TerminalCategory",
    "build_quillan_scan_registry",
    "classify_pds2_payload_error",
    "dispatch_retained_quillan_scan",
    "process_quillan_scan_folder",
    "process_quillan_scan_source",
    "validate_quillan_scan_registry",
    "validate_scan_folder",
    "validate_scan_source",
    "validate_scan_workspace",
]
