"""
Retroactively credit greenbear with moves for all approved content published
before the battle system existed, and fix their rank to Executive Chef.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Recalculate battle moves for the site owner (greenbear) based on all approved content."

    def handle(self, *args, **options):
        from accounts.models import RecipeAuthor
        from recipes.models import Recipe
        from articles.models import Article
        from pinch.models import Pinch
        from chef_battle.models import ChefBattleProfile, BattleMoveTransaction
        from chef_battle.services import (
            MOVES_RECIPE_APPROVED,
            MOVES_ARTICLE_APPROVED,
            get_or_create_battle_profile,
        )

        owner_slug = getattr(settings, "OWNER_SLUG", "greenbear")

        try:
            author = RecipeAuthor.objects.get(slug=owner_slug)
        except RecipeAuthor.DoesNotExist:
            self.stderr.write(f"Author with slug '{owner_slug}' not found.")
            return

        profile = get_or_create_battle_profile(author)

        recipe_count = Recipe.objects.filter(author=author, status="approved").count()
        article_count = Article.objects.filter(author=author, status="approved").count()
        ab_count = Pinch.objects.filter(author=author, status=Pinch.Status.APPROVED).count()

        recipe_moves = recipe_count * MOVES_RECIPE_APPROVED
        article_moves = article_count * MOVES_ARTICLE_APPROVED
        ab_moves = ab_count * MOVES_RECIPE_APPROVED  # same rate as recipes

        self.stdout.write(f"Recipes approved: {recipe_count} x {MOVES_RECIPE_APPROVED} = {recipe_moves} moves")
        self.stdout.write(f"Articles approved: {article_count} x {MOVES_ARTICLE_APPROVED} = {article_moves} moves")
        self.stdout.write(f"Pinch approved: {ab_count} x {MOVES_RECIPE_APPROVED} = {ab_moves} moves")

        # Remove old retroactive content transactions to avoid double-counting
        deleted, _ = BattleMoveTransaction.objects.filter(
            chef=author,
            reason__in={"Recipe approved", "Article approved", "Pinch approved"},
        ).delete()
        self.stdout.write(f"Removed {deleted} existing content transactions.")

        # Insert fresh transactions
        transactions = []
        if recipe_moves:
            transactions.append(BattleMoveTransaction(chef=author, amount=recipe_moves, reason="Recipe approved"))
        if article_moves:
            transactions.append(BattleMoveTransaction(chef=author, amount=article_moves, reason="Article approved"))
        if ab_moves:
            transactions.append(BattleMoveTransaction(chef=author, amount=ab_moves, reason="Pinch approved"))
        BattleMoveTransaction.objects.bulk_create(transactions)

        # Recalculate total from all transactions
        from django.db.models import Sum
        total = BattleMoveTransaction.objects.filter(chef=author).aggregate(t=Sum("amount"))["t"] or 0

        profile.battle_moves = max(0, total)
        profile.rank = ChefBattleProfile.Rank.EXECUTIVE_CHEF
        profile.rating = 9999
        profile.infinite_moves = True
        profile.save(update_fields=["battle_moves", "rank", "rating", "infinite_moves", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"Done. {owner_slug}: {total} total moves, rank=Executive Chef."
        ))
