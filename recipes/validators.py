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


#: T06, Owner 2026-08-25. What a chef may attach to a line of ARENA CHAT.
#:
#: Smaller than the cooked-dish ceilings above on purpose: a chat attachment is
#: glanced at inside a 400px rail, not judged as evidence, and it is polled back
#: to every reader in the hall rather than opened once by a moderator.
CHAT_MEDIA_MAX_BYTES = 5 * 1024 * 1024
CHAT_MEDIA_MAX_EDGE = 1280
#: Across ALL frames, not per frame - the work an animation costs is the sum of
#: its frames, and a 900x900 clip of 300 frames is a quarter of a billion pixels
#: however small each one looks.
CHAT_MEDIA_MAX_TOTAL_PIXELS = 60_000_000
CHAT_MEDIA_MAX_FRAMES = 240


def normalise_uploaded_chat_media(uploaded_file, *, prefix: str = "chat"):
    """Decode a chat attachment and return brand-new files to store.

    Returns ``(stored, poster, kind, width, height)``:

      stored  a ContentFile - the picture, or the animation as animated WebP
      poster  a ContentFile for an animation's first frame, else None
      kind    "image" or "animation"
      width, height  of the STORED file, so the client can reserve the box
                     before it loads and the log does not jump as it arrives

    THE SAME REFUSAL TO TRUST ANYTHING as normalise_uploaded_image above, and
    for the same reason: this file is served back to every reader in the hall.
    The format is read from the DECODED bytes, never from the extension or from
    the browser's content type; every frame is re-encoded, so a polyglot cannot
    survive; and info is emptied, so EXIF and its GPS do not ride along.

    WHY AN ANIMATION IS STORED AS WEBP RATHER THAN AS THE GIF IT ARRIVED AS.
    Two practical reasons. A GIF has to be re-encoded frame by frame through a
    palette, and palette-plus-disposal is exactly where a re-encode visibly
    damages an animation; WebP carries the frames as they were decoded. And the
    result is a fraction of the size, which matters for a file the hall's poll
    hands to everybody. What was uploaded is still what is seen - the container
    changed, the animation did not.
    """
    import uuid
    from io import BytesIO

    from PIL import ImageSequence
    from django.core.files.base import ContentFile

    if not uploaded_file:
        raise ValidationError("Choose an image to attach.", code="no_file")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > CHAT_MEDIA_MAX_BYTES:
        raise ValidationError(
            f"Attachments must be {CHAT_MEDIA_MAX_BYTES // (1024 * 1024)} MB or smaller.",
            code="file_too_large",
        )

    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError, ValueError):
        pass

    try:
        probe = Image.open(uploaded_file)
        image_format = (probe.format or "").upper()
        frames = int(getattr(probe, "n_frames", 1) or 1)
        width, height = probe.size
    except Image.DecompressionBombError as exc:
        raise ValidationError(
            "That image is too large to process.", code="image_too_large",
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError(
            "That file is not an image. Attach a JPG, PNG, WebP or GIF.",
            code="not_an_image",
        ) from exc

    animated = frames > 1 and image_format in {"GIF", "WEBP"}

    try:
        if image_format not in {"JPEG", "PNG", "WEBP", "GIF"}:
            raise ValidationError(
                "Attach a JPG, PNG, WebP or GIF.", code="unsupported_format",
            )
        if frames > CHAT_MEDIA_MAX_FRAMES:
            raise ValidationError(
                f"That animation has too many frames - {CHAT_MEDIA_MAX_FRAMES} is the limit.",
                code="too_many_frames",
            )
        if width * height * frames > CHAT_MEDIA_MAX_TOTAL_PIXELS:
            raise ValidationError(
                "That image is too large to process.", code="image_too_large",
            )

        if not animated:
            # A still picture is exactly the problem the function above already
            # solves, so it is solved there - one pipeline, not two. The one
            # thing that pipeline will not take is a GIF, so a single-frame GIF
            # is decoded here and handed on as pixels instead.
            if image_format == "GIF":
                probe.load()
                flat = probe.convert("RGBA")
                flat.info = {}
                if max(flat.size) > CHAT_MEDIA_MAX_EDGE:
                    flat.thumbnail((CHAT_MEDIA_MAX_EDGE, CHAT_MEDIA_MAX_EDGE))
                buffer = BytesIO()
                flat.save(buffer, format="WEBP", quality=88, method=4)
                stored = ContentFile(
                    buffer.getvalue(), name=f"{prefix}-{uuid.uuid4().hex}.webp",
                )
                stored.content_type = "image/webp"
                return stored, None, "image", flat.size[0], flat.size[1]

            stored = normalise_uploaded_image(
                uploaded_file,
                prefix=prefix,
                max_bytes=CHAT_MEDIA_MAX_BYTES,
                max_pixels=CHAT_MEDIA_MAX_TOTAL_PIXELS,
                max_edge=CHAT_MEDIA_MAX_EDGE,
            )
            with Image.open(BytesIO(stored.read())) as done:
                out_w, out_h = done.size
            stored.seek(0)
            return stored, None, "image", out_w, out_h

        # ANIMATED. Every frame is decoded and re-encoded, so nothing the
        # uploader supplied reaches the stored file.
        sequence = []
        durations = []
        for frame in ImageSequence.Iterator(probe):
            rgba = frame.convert("RGBA")
            rgba.info = {}
            if max(rgba.size) > CHAT_MEDIA_MAX_EDGE:
                rgba.thumbnail((CHAT_MEDIA_MAX_EDGE, CHAT_MEDIA_MAX_EDGE))
            sequence.append(rgba)
            # A frame with no stated duration is not a still frame: browsers
            # treat a 0ms GIF frame as roughly 100ms, so a floor here is what
            # keeps the animation running at something like its own pace.
            durations.append(max(int(frame.info.get("duration", 0) or 0), 20))
        if not sequence:
            raise ValidationError(
                "That animation could not be read.", code="corrupt_image",
            )

        buffer = BytesIO()
        sequence[0].save(
            buffer, format="WEBP", save_all=True, append_images=sequence[1:],
            duration=durations, loop=0, quality=80, method=4,
        )
        stored = ContentFile(
            buffer.getvalue(), name=f"{prefix}-{uuid.uuid4().hex}.webp",
        )
        stored.content_type = "image/webp"

        # THE POSTER IS NOT A CONVENIENCE. A reader who has turned animation
        # off has to be shown something real rather than a grey box, and it has
        # to cost them no animated bytes at all - so the first frame is stored
        # as its own still file, and that is what they are sent.
        poster_buffer = BytesIO()
        sequence[0].save(poster_buffer, format="WEBP", quality=82, method=4)
        poster = ContentFile(
            poster_buffer.getvalue(), name=f"{prefix}-{uuid.uuid4().hex}-poster.webp",
        )
        poster.content_type = "image/webp"
        return stored, poster, "animation", sequence[0].size[0], sequence[0].size[1]

    except Image.DecompressionBombError as exc:
        raise ValidationError(
            "That image is too large to process.", code="image_too_large",
        ) from exc
    except ValidationError:
        raise
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
