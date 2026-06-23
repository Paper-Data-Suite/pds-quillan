"""PDF page conversion for QR-aware scan intake."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

DEFAULT_PDF_DPI = 200


@dataclass(frozen=True, slots=True)
class PdfPageImage:
    """One converted PDF page as an OpenCV-compatible BGR image."""

    page_number: int
    image: object


@dataclass(frozen=True, slots=True)
class PdfPageConversionFailure:
    """Structured PDF conversion failure for routing-review preservation."""

    failure_category: str
    failure_message: str
    source_page_number: int | None = None
    module_details: dict[str, object] = field(default_factory=dict)


def iter_pdf_page_images(
    path: str | Path,
    *,
    dpi: int = DEFAULT_PDF_DPI,
) -> Iterator[PdfPageImage]:
    """Yield converted PDF pages as OpenCV BGR images.

    The pdf2image package delegates rendering to Poppler. Callers should catch
    ``PdfPageConversionError`` and preserve it through routing review metadata.
    """
    pdf_path = Path(path)
    try:
        from pdf2image import convert_from_path  # type: ignore[import-not-found]
        from pdf2image.exceptions import (  # type: ignore[import-not-found]
            PDFInfoNotInstalledError,
            PDFPageCountError,
            PDFPopplerTimeoutError,
            PDFSyntaxError,
        )
    except ImportError as error:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="processing_error",
                failure_message=(
                    "PDF conversion support is unavailable; install pdf2image."
                ),
                module_details={"failure_origin": "pdf_conversion"},
            )
        ) from error

    try:
        pages = convert_from_path(pdf_path, dpi=dpi)
    except PDFInfoNotInstalledError as error:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="source_unreadable",
                failure_message=(
                    "PDF could not be converted because Poppler is not installed "
                    "or is not on PATH."
                ),
                module_details={
                    "failure_origin": "pdf_conversion",
                    "reason": "poppler_missing",
                },
            )
        ) from error
    except (PDFPageCountError, PDFPopplerTimeoutError, PDFSyntaxError, OSError) as error:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="source_unreadable",
                failure_message=f"PDF could not be converted: {error}",
                module_details={"failure_origin": "pdf_conversion"},
            )
        ) from error
    except Exception as error:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="processing_error",
                failure_message=f"Unexpected PDF conversion failure: {error}",
                module_details={"failure_origin": "pdf_conversion"},
            )
        ) from error

    if not pages:
        raise PdfPageConversionError(
            PdfPageConversionFailure(
                failure_category="source_unreadable",
                failure_message="PDF did not contain any pages to process.",
                module_details={
                    "failure_origin": "pdf_conversion",
                    "reason": "zero_pages",
                },
            )
        )

    for page_number, page in enumerate(pages, start=1):
        yield PdfPageImage(
            page_number=page_number,
            image=_pil_page_to_bgr_image(page),
        )


class PdfPageConversionError(RuntimeError):
    """Raised when a PDF cannot be converted into page images."""

    def __init__(self, failure: PdfPageConversionFailure) -> None:
        super().__init__(failure.failure_message)
        self.failure = failure


def _pil_page_to_bgr_image(page: Any) -> NDArray[np.uint8]:
    rgb_page = page.convert("RGB")
    rgb_array = cast(NDArray[np.uint8], np.asarray(rgb_page))
    return cast(NDArray[np.uint8], cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR))
