from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class ImageUploadValidator:
    allowed_extensions = {
        ".jpg": {"JPEG"},
        ".jpeg": {"JPEG"},
        ".png": {"PNG"},
        ".webp": {"WEBP"},
    }

    supported_formats = {fmt for formats in allowed_extensions.values() for fmt in formats}

    def __init__(self, max_size: int = 5 * 1024 * 1024):
        self.max_size = max_size

    def __call__(self, uploaded_file) -> None:
        if not uploaded_file:
            return

        extension = Path(uploaded_file.name or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError(
                "Upload a JPG, JPEG, PNG, or WebP image.",
                code="invalid_extension",
            )

        if uploaded_file.size > self.max_size:
            raise ValidationError(
                f"Image files must be 5 MB or smaller.",
                code="file_too_large",
            )

        image_format = self._detect_image_format(uploaded_file)

        if image_format not in self.supported_formats:
            raise ValidationError(
                "Unsupported image format. Use JPG, JPEG, PNG, or WebP.",
                code="unsupported_format",
            )

        if image_format not in self.allowed_extensions[extension]:
            raise ValidationError(
                "The file extension does not match the actual image format.",
                code="format_mismatch",
            )

    def _detect_image_format(self, uploaded_file) -> str:
        original_position = 0
        if hasattr(uploaded_file, "tell"):
            try:
                original_position = uploaded_file.tell()
            except (OSError, ValueError):
                original_position = 0

        try:
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)

            with Image.open(uploaded_file) as image:
                image_format = (image.format or "").upper()
                image.verify()

            return image_format
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise ValidationError(
                "Upload a valid, non-corrupt image file.",
                code="invalid_image",
            ) from exc
        finally:
            if hasattr(uploaded_file, "seek"):
                try:
                    uploaded_file.seek(original_position)
                except (OSError, ValueError):
                    uploaded_file.seek(0)


validate_image_upload = ImageUploadValidator()
