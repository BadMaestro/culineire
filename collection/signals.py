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
        # Anti-farm key. The liker's User is what always exists; the RecipeAuthor
        # is passed too, but only so rows written before the switch keep counting
        # towards the same daily allowance. Keying on the author profile alone
        # let every liker without one past the gate.
        liker_author = getattr(instance.user, "recipe_author_profile", None)
        award_moves(
            author,
            EARN_LIKE_RECEIVED,
            BattleMoveTransaction.TxType.LIKE_RECEIVED,
            source_author=liker_author,
            source_user=instance.user,
        )
    except Exception:
        logger.exception(
            "Failed to award like moves for ContentReaction pk=%s",
            getattr(instance, "pk", "?"),
        )
