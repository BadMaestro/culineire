from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from amuse_bouche.models import AmuseBouche
from recipes.models import RecipeAuthor

# Re-use the image pipeline that recipes already uses — no duplication.
from recipes.management.commands.generate_recipe import (
    fetch_image_bytes,
    _image_extension,
    _validate_image_bytes,
    _extract_json,
    _sanitise_generated_text,
)

logger = logging.getLogger("amuse_bouche")

AI_SOURCE_NOTE = (
    "An original CulinEire Amuse-Bouche, crafted with AI and reviewed by our editorial team."
)

CONTENT_TYPE_VALUES = [ct.value for ct in AmuseBouche.ContentType]


def _map_content_type(value: str) -> str:
    raw = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    labels = {ct.label.lower().replace(" ", "_"): ct.value for ct in AmuseBouche.ContentType}
    values = {ct.value: ct.value for ct in AmuseBouche.ContentType}
    return values.get(raw) or labels.get(raw) or AmuseBouche.ContentType.IRISH_BITE


def _prompt_for_amuse_bouche(topic: str, hint_type: str = "") -> str:
    types_list = ", ".join(CONTENT_TYPE_VALUES)
    type_hint = f' Use "{hint_type}" as the content_type.' if hint_type else ""
    return (
        f'Create an original CulinEire Amuse-Bouche post about "{topic}". '
        "Return strict JSON only with these keys: "
        "title, content_type, short_description, cover_image_alt. "
        f"content_type must be one of: {types_list}.{type_hint} "
        "short_description: 2-3 vivid, specific sentences about the dish or tip. "
        "No generic phrases, no tourist-brochure tone, no food-blog enthusiasm. "
        "cover_image_alt: comma-separated visual keywords for image generation, under 120 characters. "
        "Focus on what the finished dish looks like — colours, textures, plating, garnish. "
        "British/Irish English only. Metric measurements only. "
        "FORBIDDEN WORDS: rich, vibrant, unique, authentic, iconic, hearty, comforting, delightful, "
        "wonderful, amazing, incredible, perfect, ultimate, essential. "
        "FORBIDDEN PUNCTUATION: never use em dash, double dash, or excessive dashes. "
        "Output strict JSON only — no markdown, no explanation."
    )


def _call_anthropic(topic: str, hint_type: str = "") -> dict:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise CommandError("ANTHROPIC_API_KEY is not configured.")
    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 800,
        "messages": [{"role": "user", "content": _prompt_for_amuse_bouche(topic, hint_type)}],
    }
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        request = Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
            break
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 500, 529) and attempt < 3:
                logger.warning("generate_amuse_bouche: Anthropic HTTP %d attempt %d — retrying in 10s", exc.code, attempt)
                time.sleep(10)
                continue
            raise CommandError(f"Anthropic API returned HTTP {exc.code}: {body}") from exc
        except (URLError, OSError) as exc:
            last_exc = exc
            if attempt < 3:
                logger.warning("generate_amuse_bouche: Anthropic attempt %d failed (%s) — retrying in 5s", attempt, exc)
                time.sleep(5)
            else:
                raise CommandError(f"Anthropic API request failed after 3 attempts: {exc}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CommandError(f"Anthropic returned non-JSON: {exc}") from exc
    content = parsed.get("content") or []
    text = "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )
    return _extract_json(text)


def _normalise_payload(payload: dict, topic: str, status: str) -> dict:
    _s = _sanitise_generated_text
    title = _s(str(payload.get("title") or topic).strip()[:200])
    if not title:
        raise CommandError("Generated Amuse-Bouche has no title.")
    short_description = _s(str(payload.get("short_description") or "").strip())
    cover_image_alt = str(payload.get("cover_image_alt") or title).strip()[:255]
    content_type = _map_content_type(payload.get("content_type", ""))
    return {
        "title": title,
        "short_description": short_description,
        "cover_image_alt": cover_image_alt,
        "content_type": content_type,
        "status": status,
    }


def _build_image_prompt(title: str, cover_image_alt: str) -> str:
    subject = (cover_image_alt.strip() or title)[:300]
    return (
        f"Realistic editorial food photograph: {subject}. "
        "Irish cuisine, natural light, rustic wooden surface or dark slate, "
        "appetising close-up presentation. "
        "No text, no watermarks, no people, no brand names or logos."
    )


class Command(BaseCommand):
    help = "Generate AI-assisted Amuse-Bouche posts. Always saved as draft or pending — never auto-published."

    def add_arguments(self, parser):
        parser.add_argument("topic", nargs="*", help='Topic or dish name, e.g. "Irish Butter Coffee".')
        parser.add_argument("--batch", help="Path to a .txt file with one topic per line.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum batch items to process.")
        parser.add_argument("--author-slug", default="greenbear", help="RecipeAuthor slug to attach.")
        parser.add_argument(
            "--content-type", default="",
            help=f"Override content type. One of: {', '.join(CONTENT_TYPE_VALUES)}.",
        )
        parser.add_argument(
            "--status",
            choices=[AmuseBouche.Status.DRAFT, AmuseBouche.Status.PENDING],
            default=AmuseBouche.Status.PENDING,
        )
        parser.add_argument("--no-image", action="store_true", help="Skip image generation.")
        parser.add_argument("--dry-run", action="store_true", help="Print generated data without saving.")

    def handle(self, *args, **options):
        topics = self._topics(options)
        if not topics:
            raise CommandError("Provide a topic or --batch file.")

        try:
            author = RecipeAuthor.objects.get(slug=options["author_slug"])
        except RecipeAuthor.DoesNotExist as exc:
            raise CommandError(f'RecipeAuthor with slug "{options["author_slug"]}" not found.') from exc

        hint_type = options.get("content_type", "").strip()
        if hint_type and hint_type not in CONTENT_TYPE_VALUES:
            self.stderr.write(self.style.WARNING(f'Unknown content-type "{hint_type}" — ignoring hint.'))
            hint_type = ""

        for topic in topics:
            try:
                payload = _call_anthropic(topic, hint_type=hint_type)
                fields = _normalise_payload(payload, topic, options["status"])

                if options["dry_run"]:
                    self.stdout.write(json.dumps(fields, indent=2, ensure_ascii=False))
                    continue

                item = AmuseBouche.objects.create(author=author, **fields)
                logger.info("generate_amuse_bouche: created %r (%s) #%d", item.title, item.status, item.pk)

                # Image generation — reuses recipes pipeline
                openai_key = getattr(settings, "OPENAI_API_KEY", "")
                if not openai_key:
                    logger.warning("generate_amuse_bouche: OPENAI_API_KEY not set — skipping image for %r", item.title)
                elif options.get("no_image"):
                    logger.info("generate_amuse_bouche: --no-image set — skipping image for %r", item.title)
                else:
                    try:
                        prompt = _build_image_prompt(item.title, fields["cover_image_alt"])
                        image_bytes = fetch_image_bytes(prompt)
                        _validate_image_bytes(image_bytes, context="cover image")
                        ext = _image_extension(image_bytes)
                        item.cover_image.save(f"cover-{item.slug[:40]}{ext}", ContentFile(image_bytes), save=False)
                        item.save(update_fields=["cover_image"])
                        logger.info("generate_amuse_bouche: cover image saved for %r", item.title)
                    except Exception as exc:
                        logger.error("generate_amuse_bouche: image failed for %r: %s", item.title, exc)

                self.stdout.write(self.style.SUCCESS(
                    f'Created "{item.title}" ({item.get_content_type_display()}) — {item.get_absolute_url()}'
                ))

            except CommandError as exc:
                logger.error("generate_amuse_bouche: failed for %r: %s", topic, exc)
                if len(topics) > 1:
                    self.stderr.write(self.style.ERROR(f'Failed "{topic}": {exc}'))
                    continue
                raise
            except Exception as exc:
                logger.error("generate_amuse_bouche: unexpected failure for %r: %s", topic, exc, exc_info=True)
                if len(topics) > 1:
                    self.stderr.write(self.style.ERROR(f'Failed "{topic}": {exc}'))
                    continue
                raise

    @staticmethod
    def _topics(options) -> list[str]:
        if options.get("batch"):
            path = Path(options["batch"])
            if not path.exists():
                raise CommandError(f"Batch file not found: {path}")
            names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            limit = options.get("limit") or 0
            return names[:limit] if limit > 0 else names
        name = " ".join(options.get("topic") or []).strip()
        return [name] if name else []
