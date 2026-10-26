"""
ArchPilot AI - Image Validation Module
Member 1: Architecture Understanding & Root-Cause Investigation

Validates uploaded architecture diagram images using Pillow.
Enforces file format, dimensions, size limits, and checks for file corruption.
Never executes embedded content and avoids logging raw image data.
"""

from __future__ import annotations

import io
from typing import Tuple
from PIL import Image, UnidentifiedImageError

from backend.config import settings
from backend.shared.schemas import ValidationIssue, ValidationSeverity


class ImageValidationError(Exception):
    def __init__(self, message: str, code: str = "ERR_IMAGE_INVALID"):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_image_bytes(image_bytes: bytes, filename: str = "upload.png") -> Tuple[int, int, str]:
    """
    Validates raw image bytes.

    Checks:
    1. Size limit (max_image_size_bytes)
    2. Non-empty content
    3. Valid image headers and format using Pillow (PNG, JPEG, WEBP)
    4. Dimension bounds (min 10x10, max max_image_dimension)
    5. Integrity check (verify no corruption)

    Returns:
        (width, height, format_name)

    Raises:
        ImageValidationError: If image is invalid, corrupt, or exceeds limits.
    """
    if not image_bytes:
        raise ImageValidationError("Image payload is empty", code="ERR_IMAGE_EMPTY")

    # Check byte size
    byte_size = len(image_bytes)
    if byte_size > settings.max_image_size_bytes:
        raise ImageValidationError(
            f"Image file size ({byte_size / (1024*1024):.2f} MB) exceeds maximum allowed "
            f"({settings.max_image_size_bytes / (1024*1024):.1f} MB)",
            code="ERR_IMAGE_SIZE_EXCEEDED"
        )

    try:
        # Wrap in BytesIO and inspect via Pillow
        stream = io.BytesIO(image_bytes)
        with Image.open(stream) as img:
            img_format = (img.format or "").upper()
            if img_format not in settings.allowed_image_formats:
                raise ImageValidationError(
                    f"Unsupported image format '{img_format}'. Allowed formats: {', '.join(settings.allowed_image_formats)}",
                    code="ERR_IMAGE_UNSUPPORTED_FORMAT"
                )

            width, height = img.size
            if width < 10 or height < 10:
                raise ImageValidationError(
                    f"Image dimensions ({width}x{height}) are too small to be a readable architecture diagram (minimum 10x10)",
                    code="ERR_IMAGE_TOO_SMALL"
                )

            if width > settings.max_image_dimension or height > settings.max_image_dimension:
                raise ImageValidationError(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {settings.max_image_dimension}px",
                    code="ERR_IMAGE_TOO_LARGE"
                )

            # Verify file integrity
            img.verify()

            return width, height, img_format

    except UnidentifiedImageError:
        raise ImageValidationError(
            "Uploaded file is not a recognized image or is corrupt",
            code="ERR_IMAGE_CORRUPT"
        )
    except ImageValidationError:
        raise
    except Exception as e:
        raise ImageValidationError(
            f"Failed to decode image: {type(e).__name__}",
            code="ERR_IMAGE_DECODE_FAILED"
        )
