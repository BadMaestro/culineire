from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="collection.ContentReaction")
def award_like_moves(sender, instance, created, **kwargs):
    """Award +1 battle move to the content author when a LIKE is created."""
    if not created:
        return
    try:
        from collection.models import ContentReaction
        if instance.reaction != ContentReaction.Reaction.LIKE:
            return
        content_object = instance.content_object
        if content_object is None:
            return
        author = getattr(content_object, "author", None)
        if author is None:
            return
        from chef_battle.energy_service import award_moves, EARN_LIKE_RECEIVED
        from chef_battle.models import BattleMoveTransaction
        # Use the liker's RecipeAuthor as source for anti-farming (if they have one)
        liker_author = getattr(instance.user, "recipe_author_profile", None)
        award_moves(
            author,
            EARN_LIKE_RECEIVED,
            BattleMoveTransaction.TxType.LIKE_RECEIVED,
            source_author=liker_author,
        )
    except Exception:
        logger.exception(
            "Failed to award like moves for ContentReaction pk=%s",
            getattr(instance, "pk", "?"),
        )
