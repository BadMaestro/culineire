from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.deconstruct import deconstructible


@deconstructible
class ImageUploadValidator:
    allowed_extensions = {
        ".jpg": {"JPEG"},
        ".jpeg": {"JPEG"},
        ".png": {"PNG"},
        ".webp": {"WEBP"},
    }
    format_extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }
    format_content_types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }

    supported_formats = {fmt for formats in allowed_extensions.values() for fmt in formats}

    def __init__(self, max_size: int = 5 * 1024 * 1024):
        self.max_size = max_size

    def __call__(self, uploaded_file):
        if not uploaded_file:
            return
        # Only validate freshly uploaded files. FieldFile instances are already-stored
        # files that went through validation when first saved — re-validating them
        # during model clean_fields() would incorrectly reject AI-generated images
        # whose bytes do not match the file extension saved on disk.
        if not isinstance(uploaded_file, UploadedFile):
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
            self._normalize_uploaded_filename(uploaded_file, image_format)

    @staticmethod
    def _detect_image_format(uploaded_file) -> str:
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

    @classmethod
    def _normalize_uploaded_filename(cls, uploaded_file, image_format: str) -> None:
        normalized_extension = cls.format_extensions.get(image_format)
        if not normalized_extension:
            return

        original_name = Path(uploaded_file.name or f"upload{normalized_extension}").name
        stem = Path(original_name).stem or "upload"
        uploaded_file.name = f"{stem}{normalized_extension}"

        content_type = cls.format_content_types.get(image_format)
        if content_type and hasattr(uploaded_file, "content_type"):
            uploaded_file.content_type = content_type


validate_image_upload = ImageUploadValidator()
