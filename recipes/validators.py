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


#: T05, 2026-08-13. The ceilings for an image a chef uploads as EVIDENCE of a
#: cooked dish, which a moderator then approves and the arena publishes.
NORMALISED_IMAGE_MAX_BYTES = 8 * 1024 * 1024
NORMALISED_IMAGE_MAX_PIXELS = 40_000_000        # decoded width * height
NORMALISED_IMAGE_MAX_EDGE = 4096                # longest side of the STORED file
NORMALISED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def normalise_uploaded_image(uploaded_file, *,
                             prefix: str = "image",
                             max_bytes: int = NORMALISED_IMAGE_MAX_BYTES,
                             max_pixels: int = NORMALISED_IMAGE_MAX_PIXELS,
                             max_edge: int = NORMALISED_IMAGE_MAX_EDGE):
    """Decode an upload, re-encode it, and return a brand-new file to store.

    T05, Owner brief 2026-08-12. The validator above checks an upload and then
    stores the CHEF'S OWN BYTES under the CHEF'S OWN NAME. That is enough for a
    format check and not enough for a file the arena serves back to the public:
    a polyglot (a file that is a valid image AND valid HTML) passes any decoder
    test ever written, and EXIF/ICC/XMP blocks ride along untouched.

    So nothing the uploader supplied survives this function. The bytes are
    decoded, the pixels - and only the pixels - are re-encoded, and the result
    is written under a name this server generated. What comes back is a
    ContentFile, so the caller stores something that never existed on the
    uploader's disk.

    Raises ValidationError with a plain message; the caller shows it as-is.
    """
    import uuid
    from io import BytesIO

    from django.core.files.base import ContentFile

    if not uploaded_file:
        raise ValidationError("Choose an image to upload.", code="no_file")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise ValidationError(
            f"Images must be {max_bytes // (1024 * 1024)} MB or smaller.",
            code="file_too_large",
        )

    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError, ValueError):
        pass

    # Pillow only WARNS about a decompression bomb up to twice the limit and
    # raises past it; we decide on the decoded dimensions ourselves either way,
    # so a 200-byte PNG claiming 60000x60000 is refused before any pixel is
    # allocated.
    try:
        probe = Image.open(uploaded_file)
        image_format = (probe.format or "").upper()
        width, height = probe.size
    except Image.DecompressionBombError as exc:
        raise ValidationError(
            "That image is too large to process.", code="image_too_large",
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError(
            "That file is not an image. Upload a JPG, PNG or WebP photo.",
            code="not_an_image",
        ) from exc

    # The DECODED image decides the format. The extension and the browser's
    # content type are the uploader's claims and are never consulted.
    if image_format not in NORMALISED_IMAGE_FORMATS:
        raise ValidationError(
            "Upload a JPG, PNG or WebP photo.", code="unsupported_format",
        )
    if width * height > max_pixels:
        raise ValidationError(
            "That image is too large to process.", code="image_too_large",
        )

    try:
        image = probe
        image.load()
        image = image.convert("RGBA" if image_format in {"PNG", "WEBP"} else "RGB")
        # convert() carries the source's info dict along, and Pillow writes the
        # EXIF block and the JPEG comment straight out of it on save - so
        # without this line the chef's camera GPS survives the re-encode.
        image.info = {}
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge))
        buffer = BytesIO()
        if image_format == "JPEG":
            image.save(buffer, format="JPEG", quality=88, optimize=True)
        elif image_format == "PNG":
            image.save(buffer, format="PNG", optimize=True)
        else:
            image.save(buffer, format="WEBP", quality=88, method=4)
    except Image.DecompressionBombError as exc:
        raise ValidationError(
            "That image is too large to process.", code="image_too_large",
        ) from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise ValidationError(
            "That image could not be read. Try saving it again and re-uploading.",
            code="corrupt_image",
        ) from exc
    finally:
        try:
            probe.close()
        except Exception:                       # closing must never mask the error
            pass

    extension = ImageUploadValidator.format_extensions[image_format]
    stored = ContentFile(buffer.getvalue(), name=f"{prefix}-{uuid.uuid4().hex}{extension}")
    stored.content_type = ImageUploadValidator.format_content_types[image_format]
    return stored
