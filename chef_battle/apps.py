from django.apps import AppConfig


class ChefBattleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chef_battle"
    verbose_name = "Chef Battles"

    def ready(self):
        from . import faction_receivers
        faction_receivers.connect()
        from . import clan_receivers
        clan_receivers.connect()

