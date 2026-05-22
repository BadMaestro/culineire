"""
articles/management/commands/suggest_article_editorial_format.py

Print or apply suggested editorial formatting for an article body.

Usage
-----
  python manage.py suggest_article_editorial_format --slug <slug>
  python manage.py suggest_article_editorial_format --slug <slug> --apply
  python manage.py suggest_article_editorial_format --slug <slug> --apply --force
"""

from django.core.management.base import BaseCommand, CommandError

from articles.models import Article
from articles.services.editorial_tools import suggest_article_body


class Command(BaseCommand):
    help = "Print (or apply) suggested editorial formatting for an article body."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            required=True,
            help="Slug of the article to process.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Write the suggested body back to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Apply even if body already has ## headings (no-op without --apply).",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        apply_changes = options["apply"]
        force = options["force"]

        try:
            article = Article.objects.get(slug=slug, is_deleted=False)
        except Article.DoesNotExist:
            raise CommandError(
                f"Article with slug '{slug}' not found or has been deleted."
            )

        current_body = article.body or ""
        suggested = suggest_article_body(
            title=article.title or "",
            excerpt=article.excerpt or "",
            body=current_body,
        )

        if suggested == current_body.strip():
            self.stdout.write(
                self.style.SUCCESS(
                    f"'{article.slug}' — body is already well-formatted. "
                    "No changes needed."
                )
            )
            return

        self.stdout.write(f"\nArticle: {article.title!r}  (slug: {article.slug})\n")
        self.stdout.write("─" * 60)
        self.stdout.write("\n--- SUGGESTED BODY ---\n")
        self.stdout.write(suggested)
        self.stdout.write("\n--- END ---\n")

        if apply_changes:
            article.body = suggested
            article.save(update_fields=["body"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nApplied to article '{article.slug}'."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry-run only. Run with --apply to write changes to the database."
                )
            )
