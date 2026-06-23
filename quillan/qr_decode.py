"""Internal QR text decoding for local Quillan response-page images."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias, cast

import cv2
import numpy as np
from numpy.typing import NDArray

ImageArray: TypeAlias = NDArray[np.integer[Any] | np.floating[Any]]
QrCandidate: TypeAlias = tuple[str, ImageArray]

SUPPORTED_IMAGE_EXTENSIONS: Final = frozenset(
    {".jpeg", ".jpg", ".png", ".tif", ".tiff"}
)


@dataclass(frozen=True, slots=True)
class QrImageDecodeResult:
    """The decoded QR text or a structured local image-decoding failure."""

    payload_text: str | None
    failure_category: str | None = None
    failure_message: str | None = None
    successful_attempt: str | None = None


def decode_qr_payload_from_image_path(path: str | Path) -> QrImageDecodeResult:
    """Load a supported local image file and decode one QR payload."""
    source_path = Path(path)
    if not source_path.exists():
        return _failure("source_missing", "Image source does not exist.")
    if not source_path.is_file():
        return _failure(
            "source_unreadable",
            "Image source is not a regular file.",
        )
    if source_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return _failure(
            "source_type_unsupported",
            "Image source type is not supported.",
        )

    try:
        image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    except (cv2.error, OSError):
        return _failure(
            "source_unreadable",
            "Image source could not be read.",
        )

    if image is None:
        return _failure(
            "source_unreadable",
            "Image source could not be loaded as an image.",
        )
    return decode_qr_payload_from_image(image)


def decode_qr_payload_from_image(image: object) -> QrImageDecodeResult:
    """Decode one QR payload from an already-loaded OpenCV image."""
    if not isinstance(image, np.ndarray) or image.size == 0:
        return _failure(
            "source_unreadable",
            "Provided image is not a readable OpenCV image.",
        )

    try:
        detector = cv2.QRCodeDetector()
        candidates = _qr_candidate_images(cast(ImageArray, image))
        detector_error_seen = False
        for label, candidate in candidates:
            try:
                decoded = detector.detectAndDecode(candidate)
            except cv2.error:
                detector_error_seen = True
                continue

            if not isinstance(decoded, tuple) or not decoded:
                detector_error_seen = True
                continue
            payload_text = decoded[0]
            if not isinstance(payload_text, str):
                detector_error_seen = True
                continue
            if payload_text:
                return QrImageDecodeResult(
                    payload_text=payload_text,
                    successful_attempt=label,
                )
        if detector_error_seen:
            return _failure(
                "payload_unreadable",
                "QR detection failed for one or more image candidates.",
            )
    except Exception:
        return _failure(
            "processing_error",
            "Image processing failed during QR decoding.",
        )

    return _failure(
        "payload_missing",
        "No QR payload could be decoded from the image.",
    )


def _failure(category: str, message: str) -> QrImageDecodeResult:
    return QrImageDecodeResult(
        payload_text=None,
        failure_category=category,
        failure_message=message,
    )


def _qr_candidate_images(image: ImageArray) -> Iterator[QrCandidate]:
    """Yield a deterministic, bounded sequence of QR decode candidates."""
    yield from _basic_preprocess_attempts(image)

    crops = list(_upper_right_crop_candidates(image))
    for crop_index, (crop_label, crop) in enumerate(crops, start=1):
        for label, candidate in _basic_preprocess_attempts(crop):
            yield f"crop {crop_index} {crop_label} {label}", candidate

    for scale in (1.5, 2.0, 3.0):
        yield (
            f"raw {scale:g}x upscale",
            _resize(image, scale),
        )

    for crop_index, (crop_label, crop) in enumerate(crops, start=1):
        if crop_label != "tight":
            continue
        for label, candidate in _tight_crop_attempts(crop):
            yield f"crop {crop_index} {crop_label} {label}", candidate


def _basic_preprocess_attempts(image: ImageArray) -> Iterator[QrCandidate]:
    yield "raw", image

    gray = _as_grayscale(image)
    if image.ndim != 2:
        yield "grayscale", gray

    blurred = cast(
        ImageArray,
        cv2.GaussianBlur(gray, (3, 3), 0),
    )
    yield (
        "otsu threshold",
        cast(
            ImageArray,
            cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY | cv2.THRESH_OTSU,
            )[1],
        ),
    )
    yield (
        "otsu inverted threshold",
        cast(
            ImageArray,
            cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
            )[1],
        ),
    )
    yield (
        "adaptive threshold",
        cast(
            ImageArray,
            cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                5,
            ),
        ),
    )
    yield (
        "binary threshold",
        cast(
            ImageArray,
            cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)[1],
        ),
    )


def _upper_right_crop_candidates(image: ImageArray) -> Iterator[QrCandidate]:
    """Yield crops around Quillan's one-inch upper-right response-page QR."""
    height, width = image.shape[:2]
    bounds = (
        ("broad", 0.62, 0.00, 1.00, 0.32),
        ("header", 0.72, 0.00, 1.00, 0.24),
        ("focused", 0.76, 0.01, 0.99, 0.20),
        ("tight", 0.79, 0.02, 0.98, 0.18),
    )

    for label, left, top, right, bottom in bounds:
        x1 = max(0, int(width * left))
        y1 = max(0, int(height * top))
        x2 = min(width, int(width * right))
        y2 = min(height, int(height * bottom))
        if x2 > x1 and y2 > y1:
            yield label, image[y1:y2, x1:x2]


def _tight_crop_attempts(crop: ImageArray) -> Iterator[QrCandidate]:
    gray = _as_grayscale(crop)
    normalized = cast(
        ImageArray,
        cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray),
    )
    threshold = cast(
        ImageArray,
        cv2.threshold(
            cv2.GaussianBlur(gray, (3, 3), 0),
            0,
            255,
            cv2.THRESH_BINARY | cv2.THRESH_OTSU,
        )[1],
    )

    prepared = (
        ("raw", crop),
        ("grayscale normalized", normalized),
        ("otsu threshold", threshold),
    )
    for label, candidate in prepared:
        padded = _pad_quiet_zone(candidate)
        yield f"{label} padded", padded
        for scale in (2.0, 3.0, 4.0, 5.0):
            yield f"{label} padded {scale:g}x upscale", _resize(padded, scale)

    padded_normalized = _pad_quiet_zone(normalized)
    for angle in (-3, -2, -1, 1, 2, 3):
        rotated = _rotate(padded_normalized, angle)
        yield (
            "grayscale normalized padded "
            f"rotated {angle:+g} degrees 3x upscale",
            _resize(rotated, 3.0),
        )


def _as_grayscale(image: ImageArray) -> ImageArray:
    if image.ndim == 2:
        return image
    if image.ndim != 3:
        raise ValueError("Unsupported image dimensions.")
    channels = image.shape[2]
    if channels == 3:
        return cast(ImageArray, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    if channels == 4:
        return cast(ImageArray, cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY))
    raise ValueError("Unsupported image channel count.")


def _pad_quiet_zone(image: ImageArray) -> ImageArray:
    border = max(4, int(round(max(image.shape[:2]) * 0.15)))
    fill: int | tuple[int, int, int]
    fill = 255 if image.ndim == 2 else (255, 255, 255)
    return cast(
        ImageArray,
        cv2.copyMakeBorder(
            image,
            border,
            border,
            border,
            border,
            cv2.BORDER_CONSTANT,
            value=fill,
        ),
    )


def _resize(image: ImageArray, scale: float) -> ImageArray:
    return cast(
        ImageArray,
        cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        ),
    )


def _rotate(image: ImageArray, angle: float) -> ImageArray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D(
        (width / 2.0, height / 2.0),
        angle,
        1.0,
    )
    fill: int | tuple[int, int, int]
    fill = 255 if image.ndim == 2 else (255, 255, 255)
    return cast(
        ImageArray,
        cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=fill,
        ),
    )
