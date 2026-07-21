"""Load physical pages exclusively from one #337-validated retained source."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from pds_core.scan_retention import RetainedSourceScan

from quillan.module_errors import (
    QuillanPageImageError,
    QuillanPdfDependencyError,
    QuillanPdfPageConversionError,
    QuillanPdfPageCountError,
    QuillanRetainedSourceError,
    QuillanSourcePageError,
)
from quillan.retained_source import validate_quillan_retained_source

SUPPORTED_IMAGE_EXTENSIONS: Final = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
)
SUPPORTED_SCAN_EXTENSIONS: Final = frozenset(
    {*SUPPORTED_IMAGE_EXTENSIONS, ".pdf"}
)


def retained_source_page_count(
    retained_source: RetainedSourceScan,
    *,
    workspace_root: Path,
) -> int:
    """Return a positive physical page count after #337 provenance validation."""
    path = _validated_page_path(retained_source, workspace_root, 1)
    if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        return 1
    if path.suffix.lower() != ".pdf":
        raise QuillanSourcePageError("Retained source type is unsupported.")

    pdfinfo_from_path, _, exceptions = _load_pdf2image()
    info_not_installed, page_count_error, syntax_error, timeout_error = exceptions
    try:
        info = pdfinfo_from_path(str(path))
        count = info.get("Pages")
    except info_not_installed as error:
        raise QuillanPdfDependencyError(
            "Poppler PDF tools are not installed or discoverable."
        ) from error
    except timeout_error as error:
        raise QuillanPdfPageCountError(
            "Timed out while inspecting retained PDF pages."
        ) from error
    except (page_count_error, syntax_error) as error:
        raise QuillanPdfPageCountError(
            f"Could not inspect retained PDF pages: {error}"
        ) from error
    except Exception as error:
        raise QuillanPdfPageCountError(
            f"Unexpected retained PDF page-count failure: {error}"
        ) from error
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise QuillanPdfPageCountError(
            "Retained PDF must report a positive non-Boolean page count."
        )
    return count


def load_retained_page_for_qr(
    retained_source: RetainedSourceScan,
    source_page_number: int,
    *,
    workspace_root: Path,
) -> NDArray[np.uint8]:
    """Load exactly one retained physical page as three-channel BGR data."""
    path = _validated_page_path(
        retained_source,
        workspace_root,
        source_page_number,
    )
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        try:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        except (cv2.error, OSError) as error:
            raise QuillanPageImageError(
                f"Could not load retained image: {error}"
            ) from error
        except Exception as error:
            raise QuillanPageImageError(
                f"Unexpected retained image loading failure: {error}"
            ) from error
        return _validated_bgr(image)
    if suffix != ".pdf":
        raise QuillanSourcePageError("Retained source type is unsupported.")

    _, convert_from_path, exceptions = _load_pdf2image()
    info_not_installed, page_count_error, syntax_error, timeout_error = exceptions
    try:
        pages = convert_from_path(
            str(path),
            first_page=source_page_number,
            last_page=source_page_number,
        )
    except info_not_installed as error:
        raise QuillanPdfDependencyError(
            "Poppler PDF tools are not installed or discoverable."
        ) from error
    except timeout_error as error:
        raise QuillanPdfPageConversionError(
            f"Timed out converting retained PDF page {source_page_number}."
        ) from error
    except (page_count_error, syntax_error) as error:
        raise QuillanPdfPageConversionError(
            f"Could not convert retained PDF page {source_page_number}: {error}"
        ) from error
    except Exception as error:
        raise QuillanPdfPageConversionError(
            "Unexpected retained PDF page conversion failure for page "
            f"{source_page_number}: {error}"
        ) from error
    if not isinstance(pages, list) or len(pages) != 1:
        raise QuillanPdfPageConversionError(
            "PDF conversion did not return exactly one requested page."
        )
    try:
        rgb = np.asarray(pages[0].convert("RGB"), dtype=np.uint8)
        image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (AttributeError, TypeError, ValueError, cv2.error) as error:
        raise QuillanPageImageError(
            "Converted PDF page is not valid RGB image data."
        ) from error
    except Exception as error:
        raise QuillanPageImageError(
            f"Unexpected converted-page image failure: {error}"
        ) from error
    return _validated_bgr(image)


def _load_pdf2image(
) -> tuple[Any, Any, tuple[type[BaseException], ...]]:
    """Load optional PDF support only when a retained PDF is processed."""
    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
        from pdf2image.exceptions import (
            PDFInfoNotInstalledError,
            PDFPageCountError,
            PDFPopplerTimeoutError,
            PDFSyntaxError,
        )
    except ImportError as error:
        raise QuillanPdfDependencyError(
            "PDF intake requires the optional pdf2image package."
        ) from error
    except Exception as error:
        raise QuillanPdfDependencyError(
            f"Unexpected PDF dependency loading failure: {error}"
        ) from error
    return (
        pdfinfo_from_path,
        convert_from_path,
        (
            PDFInfoNotInstalledError,
            PDFPageCountError,
            PDFSyntaxError,
            PDFPopplerTimeoutError,
        ),
    )


def _validated_page_path(
    retained_source: object,
    workspace_root: Path,
    source_page_number: object,
) -> Path:
    try:
        validated = validate_quillan_retained_source(
            retained_source,
            workspace_root=workspace_root,
            source_page_number=source_page_number,
        )
    except QuillanRetainedSourceError as error:
        raise QuillanSourcePageError(str(error)) from error
    except Exception as error:
        raise QuillanSourcePageError(
            f"Unexpected retained-source validation failure: {error}"
        ) from error
    return validated.retained_source.retained_source_path


def _validated_bgr(image: object) -> NDArray[np.uint8]:
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or image.size == 0
    ):
        raise QuillanPageImageError(
            "Page image must be nonempty uint8 three-channel BGR data."
        )
    return cast(NDArray[np.uint8], image)


__all__ = [
    "SUPPORTED_IMAGE_EXTENSIONS",
    "SUPPORTED_SCAN_EXTENSIONS",
    "load_retained_page_for_qr",
    "retained_source_page_count",
]
