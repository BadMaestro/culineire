"""Seed the Owner's sticker pack: one pack, thirteen items.

CATALOGUE ROWS ONLY. This migration grants nothing, names no account and
touches no wallet - the thirteen items go on the shelf and that is all.

THE REVERSE IS AN ORDINARY ONE, and that is the Owner's ruling of 2026-08-27
(Carpet #3549) overriding the first draft of this card, which had it refuse
once anybody owned a sticker. His reasoning is better than the one it replaced:
nobody has bought anything and nobody can until the whole application launches,
because CHEF_BATTLE_ENABLED is False; by the time anyone can buy, the tests and
the migrations are long settled and nobody is coming back to them. And if it
ever does happen after launch, putting a pack back on an account is an OPERATOR
decision rather than a migration one - refund the tokens, or re-grant the pack
from the moderation panel. That is exactly what the panel's grant tool is for,
which is why it is built to work rather than to decorate.

The delete below is therefore deliberately narrow: it removes the thirteen
items and the pack, and PROTECT on ChefSticker.sticker means the database
itself refuses if a paid row still points at one. A refusal from the database
is a true statement about the data; a refusal invented here would only have
been a guess about the operator's intent.
"""
from django.db import migrations

PACK_SLUG = "culineire-kitchen"
PACK_NAME = "CulinEire Kitchen"

# The Owner's own order, matching STICKERS in static/js/arena_chat.js and both
# JSON maps in templates/chef_battle/_arena_chat_stickers.html. The token is
# the key in all three places and in the WebP filename; StickerCatalogueTests
# holds them to each other.
STICKERS = [
    ("let_him_cook", "Let him cook"),
    ("yes_chef", "Yes chef!"),
    ("order_up", "Order up!"),
    ("burnt_it", "Burnt it"),
    ("in_the_bin", "In the bin"),
    ("eighty_sixed", "86'd"),
    ("seared", "Seared"),
    ("salty", "Salty"),
    ("chefs_kiss", "Chef's kiss"),
    ("battle_time", "Battle time"),
    ("bear_approved", "Bear approved"),
    ("absolute_cinema", "Absolute cinema"),
    ("noooo", "Noooo!"),
]

SINGLE_COST = 10
PACK_COST = 100


def seed(apps, schema_editor):
    StickerPack = apps.get_model("chef_battle", "StickerPack")
    StickerItem = apps.get_model("chef_battle", "StickerItem")

    pack, _ = StickerPack.objects.get_or_create(
        slug=PACK_SLUG,
        defaults={"name": PACK_NAME, "token_cost": PACK_COST, "sort_order": 0},
    )
    for order, (token, label) in enumerate(STICKERS):
        StickerItem.objects.get_or_create(
            token=token,
            defaults={
                "label": label,
                "pack": pack,
                "token_cost": SINGLE_COST,
                "sort_order": order,
            },
        )


def unseed(apps, schema_editor):
    StickerPack = apps.get_model("chef_battle", "StickerPack")
    StickerItem = apps.get_model("chef_battle", "StickerItem")

    StickerItem.objects.filter(token__in=[token for token, _ in STICKERS]).delete()
    StickerPack.objects.filter(slug=PACK_SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0112_sticker_pack_item_ownership"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
