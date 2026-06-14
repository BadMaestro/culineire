from django.conf import settings
from django.db import migrations


def set_greenbear_infinite_balance(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    TokenWallet = apps.get_model("chef_battle", "TokenWallet")
    try:
        owner = RecipeAuthor.objects.get(slug=settings.OWNER_SLUG)
        wallet, _ = TokenWallet.objects.get_or_create(chef=owner)
        wallet.infinite_balance = True
        wallet.save(update_fields=["infinite_balance"])
    except RecipeAuthor.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0024_tokenwallet_infinite_balance"),
    ]

    operations = [
        migrations.RunPython(set_greenbear_infinite_balance, migrations.RunPython.noop),
    ]
