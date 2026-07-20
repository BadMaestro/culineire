"""Remove every trace of an account so its address can be used again.

Deleting an account has been leaving half of it behind. The owner tried to
register julija.golovina.irl@gmail.com and was told the username and the email
were both taken — by a login row from 2026-05-12 whose author profile was long
gone. Nothing in the site can see such a row: it owns no recipes, no articles,
no profile page. It exists only to refuse the address.

This deletes both halves together, plus the content that hangs off the author,
in one transaction, so an address is either fully gone or fully there.

    manage.py purge_account --email someone@example.com
    manage.py purge_account --email someone@example.com --yes    (no prompt)
    manage.py purge_account --orphans                            (login rows with no profile)

Always prints what it is about to remove and refuses to touch a superuser
without --force: an operator clearing a stale signup should not be one typo
away from deleting the owner.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Delete an account and everything attached to it, so the address is free again."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Address to clear (matches username or email).")
        parser.add_argument("--orphans", action="store_true",
                            help="Clear every login row that has no author profile.")
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation.")
        parser.add_argument("--force", action="store_true",
                            help="Allow deleting a superuser. Required for one.")

    def handle(self, *args, **options):
        User = get_user_model()
        if not options["email"] and not options["orphans"]:
            raise CommandError("Give --email, or --orphans to sweep.")

        if options["orphans"]:
            from recipes.models import RecipeAuthor
            linked = set(RecipeAuthor.objects.filter(user__isnull=False)
                         .values_list("user_id", flat=True))
            targets = [u for u in User.objects.all() if u.pk not in linked]
        else:
            email = options["email"].strip()
            targets = list(User.objects.filter(username__iexact=email)
                           | User.objects.filter(email__iexact=email))
            if not targets:
                self.stdout.write("Nothing to remove — the address is already free.")
                return

        protected = [u for u in targets if u.is_superuser]
        if protected and not options["force"]:
            raise CommandError(
                "Refusing: %s is a superuser. Pass --force if that is really the intent."
                % ", ".join(u.username for u in protected))

        self.stdout.write("About to remove:")
        for user in targets:
            author = getattr(user, "recipe_author_profile", None)
            self.stdout.write(
                "  user id=%s username=%s email=%s joined=%s author=%s"
                % (user.pk, user.username, user.email or "-",
                   user.date_joined.strftime("%Y-%m-%d"),
                   getattr(author, "slug", "none")))

        if not options["yes"]:
            answer = input("Type the number of accounts to confirm (%d): " % len(targets))
            if answer.strip() != str(len(targets)):
                self.stdout.write("Cancelled, nothing was removed.")
                return

        removed = []
        with transaction.atomic():
            for user in targets:
                author = getattr(user, "recipe_author_profile", None)
                if author is not None:
                    # Content first: a recipe or article outliving its author is
                    # the same class of leftover as the login row itself.
                    from articles.models import Article
                    from recipes.models import Recipe
                    Article.objects.filter(author=author).delete()
                    Recipe.objects.filter(author=author).delete()
                    author.delete()
                label = user.username
                user.delete()
                removed.append(label)

        self.stdout.write(self.style.SUCCESS(
            "Removed %d: %s" % (len(removed), ", ".join(removed))))
        self.stdout.write("The address can be registered again.")
