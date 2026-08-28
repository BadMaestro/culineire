"""NOOOO! is part of the collection and is sold on its own, for 100 tokens.

The Owner, 2026-08-28, in his own words: "стикер Nooo - входит в пак но
продаётся отдельно - за 100T - только с ним коллекция будет полной".

So the CulinEire Kitchen pack is TWELVE stickers for 100 tokens, and NOOOO! is
a thirteenth that belongs to the same collection, is shown beside it, and costs
100 on its own. Buying the pack does not grant it.

THIS ALSO SETTLES THE SHOP WINDOW. His contact sheet shows twelve, the pack
now sells twelve, and the two agree - which is why nothing is drawn onto his
artwork to make up a missing thirteenth (Carpet #3552: the layout is his).

Data only, and it reverses plainly: 10 tokens and not sold separately is
exactly what 0113 seeded.
"""
from django.db import migrations

TOKEN = "noooo"
SEPARATE_COST = 100
PACK_COST = 10


def apply(apps, schema_editor):
    StickerItem = apps.get_model("chef_battle", "StickerItem")
    StickerItem.objects.filter(token=TOKEN).update(
        token_cost=SEPARATE_COST, sold_separately=True,
    )


def revert(apps, schema_editor):
    StickerItem = apps.get_model("chef_battle", "StickerItem")
    StickerItem.objects.filter(token=TOKEN).update(
        token_cost=PACK_COST, sold_separately=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0114_sticker_sold_separately"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
    ]
